#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 data-sum 目录和历史开奖文件生成前端使用的专家看板 JSON。
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


TAB_KEYS = [
    ("daily", "每日矩阵总览"),
    ("insight", "重点结论与规律"),
    ("global", "全域分析结论"),
    ("energy", "重号与热点观察"),
    ("tracking", "历史命中复盘"),
]
MATRIX_TITLE_RE = re.compile(r"^\s*矩阵\s*(\d+)\s*[：:]?\s*$")


def _two_digit(value: str) -> str:
    value = value.strip()
    return value.zfill(2) if value.isdigit() and len(value) <= 2 else value


def _parse_number_line(line: str) -> list[str]:
    return [_two_digit(token) for token in re.findall(r"\d+", line)]


def _read_text_with_fallback(file_path: Path) -> tuple[str, str]:
    raw = file_path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def _parse_matrix_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        if "|" in line:
            left, right = line.split("|", 1)
        else:
            left, right = line, ""
        left_nums = _parse_number_line(left)[:4]
        right_nums = _parse_number_line(right)[:4]
        rows.append((left_nums + [""] * 4)[:4] + (right_nums + [""] * 4)[:4])
    while len(rows) < 4:
        rows.append([""] * 8)
    return rows[:4]


def _normalize_matrix_title(raw: str) -> str | None:
    match = MATRIX_TITLE_RE.match(raw.strip())
    if not match:
        return None
    return f"矩阵{match.group(1)}"


def _parse_matrix_file(file_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    matrices: list[dict[str, Any]] = []
    diagnostics = {
        "file": str(file_path),
        "matrixCount": 0,
        "recognizedTitles": [],
    }
    if not file_path.exists():
        diagnostics["missing"] = True
        return matrices, diagnostics

    text, used_encoding = _read_text_with_fallback(file_path)
    lines = text.splitlines()
    diagnostics["encoding"] = used_encoding
    current_title = ""
    current_rows: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_rows
        if current_title:
            matrices.append(
                {
                    "title": current_title,
                    "rows": _parse_matrix_rows(current_rows),
                }
            )
        current_title = ""
        current_rows = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        normalized_title = _normalize_matrix_title(line)
        if normalized_title:
            flush()
            current_title = normalized_title
            diagnostics["recognizedTitles"].append(normalized_title)
            continue
        current_rows.append(raw_line.rstrip())
    flush()
    diagnostics["matrixCount"] = len(matrices)
    return matrices, diagnostics


def _load_actual_history(history_file: Path) -> dict[str, dict[str, Any]]:
    actual_draws: dict[str, dict[str, Any]] = {}
    if not history_file.exists():
        return actual_draws

    for line in history_file.read_text(encoding="utf-8").splitlines():
        match = re.match(r"date:(\d{4}-\d{2}-\d{2}),period:([^,]+),numbers:([\d\-]+)", line.strip())
        if not match:
            continue
        date_key = match.group(1).replace("-", "")
        numbers = [_two_digit(num) for num in match.group(3).split("-")]
        actual_draws[date_key] = {
            "date": match.group(1),
            "period": match.group(2),
            "numbers": numbers,
        }
    return actual_draws


def _build_daily_views(data_sum_dir: Path, actual_draws: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for date_dir in sorted([d for d in data_sum_dir.iterdir() if d.is_dir() and d.name.isdigit()], key=lambda p: p.name, reverse=True):
        date_key = date_dir.name
        data1_path = date_dir / f"{date_key}-data1.txt"
        data2_path = date_dir / f"{date_key}-data2.txt"
        data1_matrices, data1_diag = _parse_matrix_file(data1_path)
        data2_matrices, data2_diag = _parse_matrix_file(data2_path)

        if data1_path.exists() and data1_diag["matrixCount"] == 0:
            print(f"[WARN] {date_key} data1 已存在但未识别出矩阵标题: {data1_path}")
        if data2_path.exists() and data2_diag["matrixCount"] == 0:
            print(f"[WARN] {date_key} data2 已存在但未识别出矩阵标题: {data2_path}")
        if data1_path.exists() and data1_diag.get("encoding") not in {"utf-8", "utf-8-sig"}:
            print(f"[INFO] {date_key} data1 使用非 UTF-8 编码读取: {data1_diag.get('encoding')}")
        if data2_path.exists() and data2_diag.get("encoding") not in {"utf-8", "utf-8-sig"}:
            print(f"[INFO] {date_key} data2 使用非 UTF-8 编码读取: {data2_diag.get('encoding')}")

        if not data1_matrices and not data2_matrices:
            continue

        actual_info = actual_draws.get(date_key)
        actual_numbers = actual_info["numbers"] if actual_info else []
        actual_set = set(actual_numbers)

        def enrich(matrices: list[dict[str, Any]]) -> list[dict[str, Any]]:
            enriched = []
            for matrix in matrices:
                hit_numbers = sorted({value for row in matrix["rows"] for value in row if value and value in actual_set})
                enriched.append({**matrix, "hitNumbers": hit_numbers})
            return enriched

        view = {
            "date": date_key,
            "displayDate": f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}",
            "actualNumbers": actual_numbers,
            "actualPeriod": actual_info["period"] if actual_info else "",
            "actualStatus": "matched" if actual_info else "missing",
            "missingActualData": actual_info is None,
            "matrixDiagnostics": {
                "data1MatrixCount": data1_diag["matrixCount"],
                "data2MatrixCount": data2_diag["matrixCount"],
            },
            "sourceGroups": [
                {"key": "data1", "title": "第一套矩阵数据", "matrices": enrich(data1_matrices)},
                {"key": "data2", "title": "第二套矩阵数据", "matrices": enrich(data2_matrices)},
            ],
        }
        view["dailyBrief"] = _build_daily_brief(view)
        views.append(view)
    return views


def _build_daily_brief(view: dict[str, Any]) -> dict[str, Any]:
    all_matrices = []
    all_values: list[str] = []
    hit_total = 0
    for group in view["sourceGroups"]:
        for matrix in group["matrices"]:
            values = [value for row in matrix["rows"] for value in row if value]
            all_values.extend(values)
            all_matrices.append(
                {
                    "name": f"{group['title']}·{matrix['title']}",
                    "hitCount": len(matrix["hitNumbers"]),
                    "fillCount": len(values),
                }
            )
            hit_total += len(matrix["hitNumbers"])

    total_count = len(all_values)
    hit_rate = round((hit_total / total_count) * 100, 1) if total_count else 0.0
    number_counter = Counter(all_values)
    top_numbers = [number for number, _ in number_counter.most_common(5)]
    top_matrices = [
        item["name"]
        for item in sorted(
            all_matrices,
            key=lambda item: (item["hitCount"], item["fillCount"]),
            reverse=True,
        )[:3]
    ]

    if view.get("missingActualData"):
        verdict = "待验证"
        uncertainty = "高"
        summary = "当前日期缺少开奖数据，先看结构分布，命中表现待补开奖后复核。"
    elif hit_rate >= 30:
        verdict = "信号集中"
        uncertainty = "低"
        summary = "命中率明显高于常规阈值，优先关注当前重点矩阵与重复号码。"
    elif hit_rate >= 18:
        verdict = "均衡推进"
        uncertainty = "中"
        summary = "命中表现处于可用区间，可结合全域结论与风险提示继续筛选。"
    else:
        verdict = "分散观察"
        uncertainty = "中"
        summary = "命中表现偏分散，建议降低集中下注思路，优先看防守和回测证据。"

    return {
        "verdict": verdict,
        "summary": summary,
        "uncertainty": uncertainty,
        "score": round(hit_rate, 1),
        "focusNumbers": top_numbers,
        "focusMatrices": top_matrices,
        "triggerThreshold": {
            "primaryHitRate": 18,
            "strongHitRate": 30,
            "minimumSamples": 24,
        },
        "evidenceRefs": [
            f"命中率 {hit_rate}%（阈值 18%）",
            f"命中总数 {hit_total} / 样本数 {total_count}",
            f"双源重复前五号码：{'、'.join(top_numbers) if top_numbers else '暂无'}",
        ],
    }


def _build_insight_summary(daily_views: list[dict[str, Any]]) -> dict[str, Any]:
    if not daily_views:
        return {
            "title": "重点结论与规律",
            "overview": "暂无可分析的矩阵数据。",
            "focusNumbers": [],
            "focusMatrices": [],
            "riskReminder": "请先生成每日矩阵数据。",
            "keyFindings": [],
        }

    latest = daily_views[0]
    counter = Counter()
    matrix_scores = []
    for group in latest["sourceGroups"]:
        for matrix in group["matrices"]:
            values = [value for row in matrix["rows"] for value in row if value]
            counter.update(values)
            matrix_scores.append(
                {
                    "sourceTitle": group["title"],
                    "matrixTitle": matrix["title"],
                    "count": len(values),
                    "repeatCount": sum(1 for value in values if counter[value] > 1),
                    "hitCount": len(matrix["hitNumbers"]),
                }
            )

    focus_numbers = [
        {"number": number, "weight": weight}
        for number, weight in counter.most_common(8)
    ]
    focus_matrices = sorted(
        matrix_scores,
        key=lambda item: (item["hitCount"], item["repeatCount"], item["count"]),
        reverse=True,
    )[:3]

    actual_text = "、".join(latest["actualNumbers"]) if latest["actualNumbers"] else "暂未同步开奖"
    focus_number_text = "、".join([item["number"] for item in focus_numbers[:5]]) or "暂无重点号码"
    focus_matrix_text = "；".join([f"{item['sourceTitle']}·{item['matrixTitle']}" for item in focus_matrices]) or "暂无重点矩阵"
    key_findings = [
        f"今天优先关注 {focus_number_text}。",
        f"最值得先看的矩阵是 {focus_matrix_text}。",
        f"当前已同步的开奖号码为 {actual_text}。",
    ]

    return {
        "title": "重点结论与规律",
        "overview": "先看重点号码、重点矩阵和风险提醒，再决定是否继续看证据表。",
        "focusNumbers": focus_numbers,
        "focusMatrices": focus_matrices,
        "riskReminder": "如果昨日仍显示未开奖，优先检查历史开奖同步链路是否更新到最新日期。",
        "keyFindings": key_findings,
    }


def _build_global_highlights(daily_views: list[dict[str, Any]]) -> dict[str, Any]:
    matrix_stats: dict[str, dict[str, Any]] = {}
    for view in daily_views:
        actual_set = set(view["actualNumbers"])
        for group in view["sourceGroups"]:
            for matrix in group["matrices"]:
                key = f"{group['title']}·{matrix['title']}"
                values = [value for row in matrix["rows"] for value in row if value]
                hits = [value for value in values if value in actual_set]
                stats = matrix_stats.setdefault(key, {"name": key, "days": 0, "totalHits": 0, "lastHits": [], "fillCount": len(values)})
                stats["days"] += 1
                stats["totalHits"] += len(hits)
                if not stats["lastHits"]:
                    stats["lastHits"] = hits

    evidence_rows = sorted(matrix_stats.values(), key=lambda item: (item["totalHits"], item["fillCount"]), reverse=True)
    highlight_cards = [
        {
            "title": item["name"],
            "summary": f"累计命中 {item['totalHits']} 次，覆盖天数 {item['days']} 天。",
            "lastHits": item["lastHits"],
        }
        for item in evidence_rows[:3]
    ]
    persistence_rows = []
    for item in evidence_rows[:8]:
        persistence_rows.append(
            {
                "name": item["name"],
                "days": item["days"],
                "totalHits": item["totalHits"],
                "persistenceScore": round(item["totalHits"] / max(1, item["days"]), 2),
            }
        )
    return {
        "title": "全域分析结论",
        "intro": "先看最值得关注的矩阵，再看它们为什么值得关注。",
        "highlightCards": highlight_cards,
        "reasons": [
            "优先展示最近阶段命中累计更高的矩阵块。",
            "矩阵内号码更密集、重复出现更明显的区域，会被放到更靠前位置。",
            "证据表只作为辅助，不抢首屏重点。",
        ],
        "evidenceRows": evidence_rows,
        "persistenceRows": persistence_rows,
    }


def _build_energy_highlights(daily_views: list[dict[str, Any]]) -> dict[str, Any]:
    if not daily_views:
        return {
            "title": "重号与热点观察",
            "focusRepeats": [],
            "hotMatrices": [],
            "observations": [],
            "evidenceRows": [],
        }

    latest = daily_views[0]
    counter = Counter()
    evidence_rows = []
    for group in latest["sourceGroups"]:
        for matrix in group["matrices"]:
            values = [value for row in matrix["rows"] for value in row if value]
            counter.update(values)
            evidence_rows.append(
                {
                    "name": f"{group['title']}·{matrix['title']}",
                    "repeatedCount": sum(1 for value in values if counter[value] > 1),
                    "hitCount": len(matrix["hitNumbers"]),
                    "numbers": values,
                }
            )

    focus_repeats = [{"number": number, "count": count} for number, count in counter.items() if count >= 2]
    focus_repeats.sort(key=lambda item: (item["count"], item["number"]), reverse=True)
    hot_matrices = sorted(evidence_rows, key=lambda item: (item["hitCount"], item["repeatedCount"]), reverse=True)[:3]

    cross_source_consensus = [
        {
            "number": item["number"],
            "count": item["count"],
        }
        for item in focus_repeats[:8]
    ]

    cell_heat_map = defaultdict(lambda: {"hits": 0, "total": 0})
    for view in daily_views:
        actual_set = set(view["actualNumbers"])
        for group in view["sourceGroups"]:
            for matrix in group["matrices"]:
                for row_index, row in enumerate(matrix["rows"]):
                    for col_index, value in enumerate(row):
                        if not value:
                            continue
                        key = f"{group['title']}·{matrix['title']}·{row_index + 1}-{col_index + 1}"
                        cell_heat_map[key]["total"] += 1
                        if value in actual_set:
                            cell_heat_map[key]["hits"] += 1

    heat_cells = [
        {"cell": key, "hitRate": round(stats["hits"] / max(1, stats["total"]), 2), "samples": stats["total"]}
        for key, stats in cell_heat_map.items()
    ]
    heat_cells.sort(key=lambda item: (item["hitRate"], item["samples"]), reverse=True)

    return {
        "title": "重号与热点观察",
        "focusRepeats": focus_repeats[:8],
        "hotMatrices": hot_matrices,
        "observations": [
            "同一天在两套矩阵里重复出现的号码，更适合优先观察。",
            "已经命中的矩阵块应放在前面，让普通用户先看到重点。",
            "如果开奖号码缺失，页面会明确提示为开奖数据缺失，而不是继续误报待开奖。",
        ],
        "evidenceRows": evidence_rows,
        "crossSourceConsensus": cross_source_consensus,
        "cellHeatMap": heat_cells[:12],
    }


def _load_tracking_rows(csv_file: Path, actual_draws: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not csv_file.exists():
        return rows

    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            date_key = (raw.get("Date") or "").strip()
            if not date_key:
                continue
            actual_info = actual_draws.get(date_key)
            actual_numbers = actual_info["numbers"] if actual_info else []
            actual_set = set(actual_numbers)
            is_pending = actual_info is None

            gold2 = [_two_digit(item) for item in (raw.get("Gold_2") or "").split(",") if item.strip()]
            gold7 = [_two_digit(item) for item in (raw.get("Gold_7") or "").split(",") if item.strip()]
            top12 = [_two_digit(item) for item in (raw.get("Top_12") or "").split(",") if item.strip()]

            gold2_hits = [item for item in gold2 if item in actual_set]
            gold7_hits = [item for item in gold7 if item in actual_set]
            top12_hits = [item for item in top12 if item in actual_set]
            weighted_score = round(len(gold2_hits) * 2.0 + len(gold7_hits) * 1.2 + len(top12_hits) * 0.8, 2)

            if is_pending:
                verdict = "开奖数据缺失"
                miss_reason = "该日期尚未同步到历史开奖文件，当前无法给出完整命中复盘。"
                status = "pending"
                uncertainty = "高"
            elif len(top12_hits) >= 6 or len(gold7_hits) >= 4:
                verdict = "表现强"
                miss_reason = f"核心组合形成集中命中，Top12 命中 {len(top12_hits)} 个，精选7 命中 {len(gold7_hits)} 个。"
                status = "great"
                uncertainty = "低"
            elif len(top12_hits) >= 3 or len(gold7_hits) >= 2 or len(gold2_hits) >= 1:
                verdict = "表现中"
                miss_reason = f"命中表现可用但集中度一般，Top12 命中 {len(top12_hits)} 个。"
                status = "stable"
                uncertainty = "中"
            else:
                verdict = "需观察"
                miss_reason = "本期核心组合未形成有效命中，建议结合趋势证据降低激进决策。"
                status = "watch"
                uncertainty = "中"

            rows.append(
                {
                    "date": date_key,
                    "displayDate": f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}",
                    "gold2": gold2,
                    "gold7": gold7,
                    "top12": top12,
                    "actualNumbers": actual_numbers,
                    "actualPeriod": actual_info["period"] if actual_info else "",
                    "gold2Hits": gold2_hits,
                    "gold7Hits": gold7_hits,
                    "top12Hits": top12_hits,
                    "gold2HitCount": len(gold2_hits),
                    "gold7HitCount": len(gold7_hits),
                    "top12HitCount": len(top12_hits),
                    "isPending": is_pending,
                    "missingActualData": is_pending,
                    "pendingReason": "历史开奖文件尚未同步到该日期。" if is_pending else "",
                    "verdict": verdict,
                    "missReason": miss_reason,
                    "status": status,
                    "uncertainty": uncertainty,
                    "confidence": "低" if is_pending else ("高" if status == "great" else "中"),
                    "riskScore": max(0, round(10 - weighted_score, 1)),
                    "triggerThreshold": {
                        "gold2Hit": 1,
                        "gold7Hit": 2,
                        "top12Hit": 3,
                        "strongTop12Hit": 6,
                    },
                    "evidenceRefs": [
                        f"黄金选2 命中 {len(gold2_hits)}/2",
                        f"精选选7 命中 {len(gold7_hits)}/7",
                        f"全域Top12 命中 {len(top12_hits)}/12",
                    ],
                }
            )
    return rows


def export_dashboard_json() -> Path:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    data_sum_dir = project_root / "src" / "data-sum"
    history_file = project_root / "src" / "data" / "kl8_history_final.txt"
    tracking_file = project_root / "src" / "data" / "recommendation_history.csv"
    output_path = project_root / "src" / "data" / "expert_dashboard.json"

    actual_draws = _load_actual_history(history_file)
    daily_views = _build_daily_views(data_sum_dir, actual_draws)
    tracking_rows = _load_tracking_rows(tracking_file, actual_draws)

    latest_matrix_date = daily_views[0]["date"] if daily_views else ""
    history_latest_date = max(actual_draws.keys()) if actual_draws else ""
    data_health = {
        "pointsLatestDate": latest_matrix_date,
        "historyLatestDate": history_latest_date,
        "expertLatestDate": latest_matrix_date,
        "isMisaligned": bool(latest_matrix_date and history_latest_date and history_latest_date < latest_matrix_date),
        "message": "历史开奖晚于或等于矩阵日期，数据健康。"
        if latest_matrix_date and history_latest_date and history_latest_date >= latest_matrix_date
        else "历史开奖尚未追平矩阵日期，请谨慎看待最新一期命中复盘。",
    }

    dashboard = {
        "meta": {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "latestDate": latest_matrix_date,
            "historyLatestDate": history_latest_date,
            "dataHealth": data_health,
        },
        "overviewTabs": [{"key": key, "label": label} for key, label in TAB_KEYS],
        "dailyMatrixViews": daily_views,
        "insightSummary": _build_insight_summary(daily_views),
        "globalHighlights": _build_global_highlights(daily_views),
        "energyHighlights": _build_energy_highlights(daily_views),
        "trackingDetails": tracking_rows,
    }

    output_path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    target = export_dashboard_json()
    print(f"专家看板 JSON 导出成功: {target}")
