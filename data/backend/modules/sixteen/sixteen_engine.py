# -*- coding: utf-8 -*-
"""
16期中热号频次动态推演与组合决策核心引擎 (Sixteen-Period Medium-Hot Engine)
=============================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 核心原理：快乐8 16期滑动窗口大盘冷热光谱分析与出窗进窗动态动量推演。
2. 频次分桶 (1~8+次)：
   - 1次、2次 (冷号/温冷)
   - 3次、4次、5次、6次 (中热黄金号池，主力出号区间)
   - 7次、8+次 (超热极值号，过载透支防追高)
3. 出窗与进窗动态推演 (Image 1 & 3, Point 3 对齐)：
   - 16期前开出的号（出窗号）：若下期不开则频次减 1（例如 8->7, 3->2）；若开出则频次保持。
   - 16期前未开出的号：若下期开出则频次加 1（例如 2->3, 3->4）；若不开则频次保持。
4. 决策双轨 (2026-09-12 纠偏)：
   - 「回补胆」金/银/铜 = 高斯遗漏甜区排序，不得冒充中热主推。
   - 「中热主推」最优3码 = 仅从频次 3~6 池用动量分（频次钟形 + 近8期 + 遗漏2~5）。
   - 选2：冷热对冲互补；输出回补胆 + 最优3码 + 组合。
"""
from backend.utils.paths import get_cache_dir, get_outputs_dir, get_reports_dir
import os
import re
import sys
import math
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set

try:
    from backend.utils.paths import get_project_root, data_path
    PROJ_DIR = get_project_root()
except Exception:
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and os.path.dirname(curr) != curr:
        if os.path.exists(os.path.join(curr, 'kl8_history_final.txt')) or os.path.exists(os.path.join(curr, 'GEMINI.md')):
            break
        curr = os.path.dirname(curr)
    PROJ_DIR = curr

if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

NUM_TOTAL = 80
DRAW_SIZE = 20
WINDOW_SIZE = 16
BASE_SINGLE = 20 / 80  # 25.0%
BASE_PAIR = (20 / 80) * (19 / 79)  # 6.01%

# ══════════════════════════════════════════════════════════════════════════
# 中热动量打分器（midhot scorer）· 全仓唯一实现 + 调优常数集中登记
# ──────────────────────────────────────────────────────────────────────────
# 2026-09-18 网格搜索调优（100 期样本外 Top3 命中率 27.67%→31.00%，Lift 1.11x→1.24x）：
#   bell_center 4.5→5.25 ｜ bell_sigma 1.1→1.6 ｜ W_r8 0.35→0.45 ｜ W_om 0.20→0.10
# 缺陷修复（P1）：live 轨（analyze_at_index 内嵌套 _midhot_raw）与审计轨
# （excel_window_table 两处 inline 复刻）曾是两套参数不同的打分器，实测 200 期窗口
# top-3 一致率仅 12.5%。现两轨一律走本模块的 midhot_raw_score / midhot_score_for_ball，
# 禁止任何调用方再逐字复刻公式与常数。
MIDHOT_BELL_CENTER = 5.25      # 频次钟形中心：5~6 次最优
MIDHOT_BELL_SIGMA = 1.6        # 频次钟形方差：放宽，避免过度惩罚频 3 号
MIDHOT_OM_BELL_CENTER = 2.5    # 遗漏「活跃延续」钟形中心
MIDHOT_OM_BELL_SIGMA = 2.2
MIDHOT_OM_ACTIVE_MAX = 5       # omission <= 5：中热延续可接受区，走钟形
MIDHOT_OM_MID_MAX = 7          # omission <= 7：中性
MIDHOT_OM_NEUTRAL = 0.40
MIDHOT_OM_COLD = 0.08          # omission >= 8：过冷回补题材，重降权（那是回补胆的事）
MIDHOT_R8_DIVISOR = 8.0        # 近 8 期活跃度：线性 r8/8（不截顶、不除 4）
MIDHOT_W_FREQ = 0.45
MIDHOT_W_R8 = 0.45
MIDHOT_W_OM = 0.10
MIDHOT_OUT_PEN = 0.92          # 出窗且已强热(>=6) 的透支号轻微降权
MIDHOT_OUT_PEN_FREQ = 6
MIDHOT_SCORE_DECIMALS = 4      # 落盘/排序统一保留位数（两轨必须一致）
# 版本号沿用仓库既有 scoring_version 口径（不新造版本号）：
# 与 daily_ops_brief["scoring_version"] / service.py 的版本判据同源。
MIDHOT_SCORING_VERSION = "ops_pts_v4"


class MidhotScoringVersionMismatch(RuntimeError):
    """双轨打分版本不一致：产物里的 scoring_version 与当前 MIDHOT_SCORING_VERSION 不符。

    宁可乐死（显式抛错）也不静默输出旧算法的数——旧算法已不存在，数字会与
    sixteen_reviewer（走 live 引擎）的对账结果互相打架。
    处置：重跑 `python -u backend/modules/sixteen/run_daily.py 30`（或清掉对应缓存）重新生成。
    """


def assert_midhot_scoring_version(
    version: Any,
    *,
    where: str = "",
    expected: str = MIDHOT_SCORING_VERSION,
) -> str:
    """一致性自检：产物 stamped 的 scoring_version 必须等于当前常量，否则抛异常。"""
    if version is None:
        raise MidhotScoringVersionMismatch(
            f"中热打分版本缺失：{where or '产物'} 未写入 scoring_version，"
            f"当前口径应为 {expected!r}。请用 run_daily.py 重新生成该产物。"
        )
    if str(version) != str(expected):
        raise MidhotScoringVersionMismatch(
            f"中热打分版本不一致：{where or '产物'} 的 scoring_version={version!r}，"
            f"当前 MIDHOT_SCORING_VERSION={expected!r}（live 轨口径）。"
            f"该产物出自已废弃的旧算法，禁止继续展示；请用 run_daily.py 重新生成。"
        )
    return str(expected)


def midhot_raw_score(
    freq: float,
    recent_8: float,
    omission: float,
    is_outgoing: bool,
) -> float:
    """中热动量分·全仓唯一实现（模块级公共函数，live 轨与审计轨共用）。

    入参语义（两轨一致，勿传错）：
      freq        16 窗频次（原始值，不做 min(f,8) 截顶——截顶是旧审计轨的偏差写法）
      recent_8    近 8 期命中次数
      omission    当前遗漏（相对窗末，0 = 刚开）
      is_outgoing 是否出窗号（16 期前那期开出、即将掉出窗口）
    返回未取整分值；调用方统一用 round(., MIDHOT_SCORE_DECIMALS) 后再排序/落盘。
    """
    f = float(freq or 0)
    r8 = float(recent_8 or 0)
    om = float(omission or 0)
    # 频次钟形：5~6 次最优，3/4 次次之（网格搜索最优 center=5.25 sigma=1.6）
    freq_bell = math.exp(-((f - MIDHOT_BELL_CENTER) ** 2) / (2 * MIDHOT_BELL_SIGMA ** 2))
    r8_term = r8 / MIDHOT_R8_DIVISOR
    # 遗漏：0~5 均为中热延续可接受区（2026245 复盘：omit=0 的65连开、出窗中热4/4全中）
    # 过冷回补 omit>=8 仍降权 —— 那是回补胆题材，不是中热主推
    if om <= MIDHOT_OM_ACTIVE_MAX:
        om_term = math.exp(
            -((om - MIDHOT_OM_BELL_CENTER) ** 2) / (2 * MIDHOT_OM_BELL_SIGMA ** 2)
        )
    elif om <= MIDHOT_OM_MID_MAX:
        om_term = MIDHOT_OM_NEUTRAL
    else:
        om_term = MIDHOT_OM_COLD
    # 出窗中热：2026245 复盘禁止再惩罚（出窗四码 26/48/65/77 全中）
    # 仅对出窗且已强热(>=6) 的透支号轻微降权
    out_pen = MIDHOT_OUT_PEN if (is_outgoing and f >= MIDHOT_OUT_PEN_FREQ) else 1.0
    return (
        MIDHOT_W_FREQ * freq_bell + MIDHOT_W_R8 * r8_term + MIDHOT_W_OM * om_term
    ) * out_pen


def midhot_score_for_ball(ball: Dict[str, Any]) -> float:
    """按引擎 ball_details 的字段名取分（freq_16 / recent_8_hits / omission / is_outgoing）。

    审计轨（excel_window_table）的 ball 字典用的是同一组键名，可直接复用本函数；
    若某轨的键名不同，必须在该轨内先把值映射到本函数入参，不得复刻公式。
    """
    return midhot_raw_score(
        float(ball.get("freq_16", 0) or 0),
        float(ball.get("recent_8_hits", 0) or 0),
        float(ball.get("omission", 0) or 0),
        bool(ball.get("is_outgoing")),
    )

# 频次桶精选/剩余默认配额（对齐微信「N个X / 剩余」口径，可被 JSON 覆盖）
DEFAULT_BUCKET_PICK_CONFIG: Dict[str, Any] = {
    "version": 2,
    "mode": "quota",
    "sort_by": "midhot_score",
    "show_buckets": ["8+", "7", "6", "5", "4", "3", "2", "1", "0"],
    # 对齐民间表：0个8 / 2个7 / 1个6 / 3个5 / 7个4 / 5个3
    "quotas": {"8+": 0, "7": 2, "6": 1, "5": 3, "4": 7, "3": 5, "2": 0, "1": 0, "0": 0},
    "ratios": {"8+": 0.0, "7": 0.5, "6": 0.15, "5": 0.35, "4": 0.35, "3": 0.25, "2": 0, "1": 0, "0": 0},
}


def load_bucket_pick_config() -> Dict[str, Any]:
    """加载可配置的频次桶精选规则；缺省回落 DEFAULT。"""
    cfg = dict(DEFAULT_BUCKET_PICK_CONFIG)
    candidates = [
        os.path.join(get_cache_dir(), "sixteen_period", "bucket_pick_config.json"),
        os.path.join(PROJ_DIR, "storage", "cache", "sixteen_period", "bucket_pick_config.json"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                cfg.update({k: v for k, v in raw.items() if v is not None})
                cfg["_config_path"] = path
            break
        except Exception:
            continue
    return cfg


def save_bucket_pick_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """合并写入 bucket_pick_config.json，返回完整配置。"""
    cfg = load_bucket_pick_config()
    path = cfg.get("_config_path") or os.path.join(
        get_cache_dir(), "sixteen_period", "bucket_pick_config.json"
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    allowed = {"mode", "sort_by", "quotas", "ratios", "show_buckets", "sort_options", "description", "version", "notes"}
    for k, v in (updates or {}).items():
        if k in allowed and v is not None:
            cfg[k] = v
    out = {k: v for k, v in cfg.items() if not str(k).startswith("_")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["_config_path"] = path
    return out


def _bucket_key_for_freq(freq: int) -> str:
    return "8+" if freq >= 8 else str(int(freq))


def build_freq_bucket_picks(
    ball_details: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    actual_numbers: Optional[Set[int]] = None,
) -> Dict[str, Any]:
    """
    按 16 期频次分桶，再切成「精选 / 剩余」两列（民间用法）。
    配额与排序由 bucket_pick_config.json 控制。
    actual_numbers: 若传入目标期实开，则标注精选/剩余命中。
    """
    cfg = config or load_bucket_pick_config()
    mode = str(cfg.get("mode") or "quota").lower()
    sort_by = str(cfg.get("sort_by") or "midhot_score")
    quotas = cfg.get("quotas") or {}
    ratios = cfg.get("ratios") or {}
    show = cfg.get("show_buckets") or ["8+", "7", "6", "5", "4", "3", "2", "1"]
    actual = set(actual_numbers or [])

    by_bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for b in ball_details:
        by_bucket[_bucket_key_for_freq(int(b.get("freq_16", 0)))].append(b)

    def _sort_key(b: Dict[str, Any]):
        if sort_by == "omission_asc":
            return (int(b.get("omission", 99)), int(b.get("number", 0)))
        if sort_by == "omission_desc":
            return (-int(b.get("omission", 0)), int(b.get("number", 0)))
        if sort_by == "recent_8":
            return (-int(b.get("recent_8_hits", 0)), int(b.get("omission", 99)), int(b.get("number", 0)))
        if sort_by == "recent_3":
            return (-int(b.get("recent_3_hits", 0)), int(b.get("omission", 99)), int(b.get("number", 0)))
        if sort_by == "number_asc":
            return (int(b.get("number", 0)),)
        return (-float(b.get("midhot_score") or b.get("score") or 0), int(b.get("omission", 99)), int(b.get("number", 0)))

    buckets_out = []
    pick_all: List[int] = []
    pick_hit_all: List[int] = []
    for key in show:
        pool = list(by_bucket.get(key, []))
        pool.sort(key=_sort_key)
        n = len(pool)
        if mode == "ratio":
            ratio = float(ratios.get(key, 0) or 0)
            k = int(round(n * ratio)) if ratio > 0 else 0
        else:
            k = int(quotas.get(key, 0) or 0)
        k = max(0, min(k, n))
        picks = pool[:k]
        rests = pool[k:]
        pick_nums = [int(x["number"]) for x in picks]
        rest_nums = [int(x["number"]) for x in rests]
        pick_hits = [x for x in pick_nums if x in actual]
        rest_hits = [x for x in rest_nums if x in actual]
        pick_all.extend(pick_nums)
        pick_hit_all.extend(pick_hits)
        label = "8" if key == "8+" else key
        pick_str = "，".join(f"{x:02d}" for x in pick_nums)
        rest_str = "，".join(f"{x:02d}" for x in rest_nums)
        if k > 0 and pick_str:
            line = f"{k}个{label}：{pick_str}。剩余{len(rest_nums)}个：{rest_str or '—'}"
        else:
            line = f"0个{label}。剩余{len(rest_nums)}个：{rest_str or '—'}"
        buckets_out.append({
            "bucket": key,
            "freq_label": f"{label}次" if key != "8+" else "8+次",
            "pool_size": n,
            "pick_count": k,
            "rest_count": len(rest_nums),
            "picks": pick_nums,
            "rests": rest_nums,
            "pick_hits": pick_hits,
            "rest_hits": rest_hits,
            "pick_hit_count": len(pick_hits),
            "rest_hit_count": len(rest_hits),
            "line": line,
        })

    return {
        "config": {
            "mode": mode,
            "sort_by": sort_by,
            "quotas": quotas,
            "ratios": ratios,
            "show_buckets": show,
            "config_path": cfg.get("_config_path"),
            "sort_options": (cfg.get("sort_options") or [
                "midhot_score", "omission_asc", "omission_desc", "recent_8", "recent_3", "number_asc"
            ]),
        },
        "buckets": buckets_out,
        "all_picks": pick_all,
        "all_picks_count": len(pick_all),
        "all_pick_hits": pick_hit_all,
        "all_pick_hit_count": len(pick_hit_all),
        "has_actual": bool(actual),
        "format_note": "每桶：精选 N 个 + 剩余；配额/排序见 bucket_pick_config.json",
    }


def build_method2_bucket_mix(
    *,
    ball_details: List[Dict[str, Any]],
    freq_bucket_picks: Dict[str, Any],
) -> Dict[str, Any]:
    """
    方法2 · 微信桶中热混剪六码（方案B · 确定性算法，每期唯一输出）。

    席位规程（只在频 3/4/5 桶操作，不吃点位、不改 tip3）：
      ① 频5精选头 pick5[0]
      ② 频5剩余 ∩ 出窗边优先，否则 rest5[0]
      ③ 频4精选：omit≥1 中 max midhot；并列取 pick4 列表最靠后
      ④ 频4剩余 ∩ 出窗同源4：max(recent_8, -omission)；并列取小号
      ⑤ 频4剩余·刚开(omit=0)且非同源且未入选：max midhot；并列取小号
      ⑥ 频3剩余·omit∈[2,6]：max midhot；并列取小号

    与「微信手搓六码」可能不一致：手搓含主观挑号；本函数保证可复现、可对账。
    """
    by_n: Dict[int, Dict[str, Any]] = {}
    for b in ball_details or []:
        try:
            by_n[int(b["number"])] = b
        except (KeyError, TypeError, ValueError):
            continue

    buckets = {str(bk.get("bucket")): bk for bk in (freq_bucket_picks or {}).get("buckets") or []}
    pick5 = [int(x) for x in (buckets.get("5") or {}).get("picks") or []]
    rest5 = [int(x) for x in (buckets.get("5") or {}).get("rests") or []]
    pick4 = [int(x) for x in (buckets.get("4") or {}).get("picks") or []]
    rest4 = [int(x) for x in (buckets.get("4") or {}).get("rests") or []]
    rest3 = [int(x) for x in (buckets.get("3") or {}).get("rests") or []]

    outgoing = {n for n, b in by_n.items() if b.get("is_outgoing")}
    hom4 = {n for n in rest4 + pick4 if n in outgoing and int((by_n.get(n) or {}).get("freq_16") or 0) == 4}
    # 同源4 = 出窗且当前频次=4（含精选侧，席④只用剩余∩同源）
    hom4_all = {
        n for n, b in by_n.items()
        if b.get("is_outgoing") and int(b.get("freq_16") or 0) == 4
    }
    edge5 = {n for n in rest5 if n in outgoing}

    def _mid(n: int) -> float:
        b = by_n.get(n) or {}
        return float(b.get("midhot_score") or b.get("score") or 0.0)

    def _omit(n: int) -> int:
        return int((by_n.get(n) or {}).get("omission") or 0)

    def _r8(n: int) -> int:
        return int((by_n.get(n) or {}).get("recent_8_hits") or 0)

    seats: List[Dict[str, Any]] = []
    chosen: Set[int] = set()

    def _take(seat_id: str, rule: str, num: Optional[int], candidates: List[int]) -> None:
        n = int(num) if num is not None else None
        if n is not None and n in chosen:
            n = None
        if n is None:
            for c in candidates:
                if c not in chosen:
                    n = c
                    break
        row = {
            "seat": seat_id,
            "rule": rule,
            "number": n,
            "freq_16": int((by_n.get(n) or {}).get("freq_16") or 0) if n else None,
            "omission": _omit(n) if n else None,
            "recent_8": _r8(n) if n else None,
            "midhot_score": round(_mid(n), 4) if n else None,
            "is_outgoing": bool((by_n.get(n) or {}).get("is_outgoing")) if n else None,
        }
        seats.append(row)
        if n is not None:
            chosen.add(n)

    # ①
    _take("①", "频5精选头 pick5[0]", pick5[0] if pick5 else None, pick5 + rest5)
    # ②
    s2 = next((n for n in rest5 if n in edge5), None)
    _take("②", "频5剩余∩出窗边优先否则 rest5[0]", s2 if s2 is not None else (rest5[0] if rest5 else None), rest5)
    # ③
    c3 = [n for n in pick4 if _omit(n) >= 1] or list(pick4)
    if c3:
        best = max(_mid(n) for n in c3)
        top = [n for n in c3 if abs(_mid(n) - best) < 1e-12]
        # 并列取 pick4 列表最靠后
        s3 = None
        for n in reversed(pick4):
            if n in top:
                s3 = n
                break
        if s3 is None:
            s3 = top[-1]
    else:
        s3 = None
    _take("③", "频4精选 omit≥1 max midhot；并列取列表靠后", s3, pick4)
    # ④
    c4 = [n for n in rest4 if n in hom4_all]
    if c4:
        s4 = sorted(c4, key=lambda n: (-_r8(n), _omit(n), n))[0]
    else:
        s4 = None
    _take("④", "频4剩余∩出窗同源 max(r8,-omit)", s4, [n for n in rest4 if n in hom4_all] or rest4)
    # ⑤
    c5 = [n for n in rest4 if _omit(n) == 0 and n not in hom4_all and n not in chosen]
    if c5:
        best = max(_mid(n) for n in c5)
        top = [n for n in c5 if abs(_mid(n) - best) < 1e-12]
        s5 = sorted(top)[0]
    else:
        s5 = None
    _take("⑤", "频4剩余刚开非同源 max midhot；并列取小号", s5, c5 or rest4)
    # ⑥
    c6 = [n for n in rest3 if 2 <= _omit(n) <= 6 and n not in chosen]
    if not c6:
        c6 = [n for n in rest3 if n not in chosen]
    if c6:
        best = max(_mid(n) for n in c6)
        top = [n for n in c6 if abs(_mid(n) - best) < 1e-12]
        s6 = sorted(top)[0]
    else:
        s6 = None
    _take("⑥", "频3剩余 omit∈[2,6] max midhot；并列取小号", s6, c6 or rest3)

    six = [int(s["number"]) for s in seats if s.get("number") is not None]
    # 选2：④-② / ⑥-③ / ①-⑤
    def _pair(a: Optional[int], b: Optional[int], kind: str, desc: str) -> Optional[Dict[str, Any]]:
        if a is None or b is None or a == b:
            return None
        x, y = sorted([a, b])
        return {"pair": [x, y], "pair_str": f"{x:02d}-{y:02d}", "kind": kind, "desc": desc}

    n1 = seats[0]["number"] if len(seats) > 0 else None
    n2 = seats[1]["number"] if len(seats) > 1 else None
    n3 = seats[2]["number"] if len(seats) > 2 else None
    n4 = seats[3]["number"] if len(seats) > 3 else None
    n5 = seats[4]["number"] if len(seats) > 4 else None
    n6 = seats[5]["number"] if len(seats) > 5 else None
    pairs = [
        p for p in [
            _pair(n4, n2, "同源×出窗边", f"席④{n4:02d} × 席②{n2:02d}" if n4 and n2 else ""),
            _pair(n6, n3, "冲刺×精选4", f"席⑥{n6:02d} × 席③{n3:02d}" if n6 and n3 else ""),
            _pair(n1, n5, "精选5×刚开剩余4", f"席①{n1:02d} × 席⑤{n5:02d}" if n1 and n5 else ""),
        ]
        if p
    ]

    playbook = (
        f"方法2六码 {' '.join(f'{x:02d}' for x in six) or '—'}；"
        f"选2 {' / '.join(p['pair_str'] for p in pairs) or '—'}；"
        f"确定性混剪·不吃点位·不改 tip3。"
    )
    return {
        "version": "method2_bucket_mix_v1",
        "role": "辅轨·微信桶中热混剪（算法方案B）",
        "note": (
            "与方法1 tip3 并列输出；本轨不替换主推。"
            "手搓微信六码可能不同，对账时分开记账。"
        ),
        "six": six,
        "six_str": " ".join(f"{x:02d}" for x in six),
        "seats": seats,
        "pairs": pairs,
        "homology4": sorted(hom4_all),
        "edge5": sorted(edge5),
        "playbook": playbook,
    }


def _load_points_for_period(target_period: int) -> Dict[str, Any]:
    """加载目标期点位；缺失则回落最新一期并标注。"""
    try:
        from backend.data_acquisition.daily_points_manager import load_daily_points
        all_pts = load_daily_points()
    except Exception:
        all_pts = {}
    key = str(int(target_period))
    if key in all_pts:
        entry = all_pts[key]
        return {
            "period": int(entry["period"]),
            "date": entry.get("date") or "",
            "points": list(entry.get("points") or []),
            "matched": True,
            "source": "target_period",
        }
    if all_pts:
        latest_key = max(all_pts.keys(), key=lambda x: int(x))
        entry = all_pts[latest_key]
        return {
            "period": int(entry["period"]),
            "date": entry.get("date") or "",
            "points": list(entry.get("points") or []),
            "matched": False,
            "source": "latest_fallback",
            "note": f"目标期 {target_period} 无点位，暂用最新 {latest_key}",
        }
    return {"period": None, "date": "", "points": [], "matched": False, "source": "empty"}


def _load_killseeker_sets() -> Dict[str, Any]:
    """已下架 Kill 模块，返回空集以保证全链路安全平稳"""
    return {"available": False, "path": None, "high": [], "mid": [], "low": [], "all": []}


def _load_kill_avg_high_rate(window: int = 30) -> Dict[str, Any]:
    """已下架 Kill 模块，返回空指标"""
    return {"avg_high_rate": None, "n": 0}


def build_daily_ops_brief(
    *,
    target_period: int,
    latest_period: int,
    latest_nums: List[int],
    ball_details: List[Dict[str, Any]],
    midhot_ranked: List[Dict[str, Any]],
    rebound_ranked: List[Dict[str, Any]],
    freq_bucket_picks: Dict[str, Any],
    co_matrix: Optional[Dict[Tuple[int, int], int]] = None,
) -> Dict[str, Any]:
    """
    每日完整操盘简报：微信分桶原文 + 中热动量 + 点位交叉主排序 + 杀号条件缩水。

    ops_pts_v4（默认生效）:
    - ×1.15 仅 freq_16∈{3,4,5} 且在点位；刚开∩点位不加 ×1.15
    - tip3 优先 点位∩精选，不足再回退点位中热
    - Kill：近窗 avg_high_rate≥0.70 且 n≥10 时，仅对 Top12 边缘高杀降权/后移，永不踢 Top5
    - payload 保留 scoring_contrast（同日 v3 tip3/top5 对照）
    """
    points_info = _load_points_for_period(target_period)
    # 仅目标期已录入点位才参与主排序；串期回落只展示、不加权（防污染）
    points_matched = bool(points_info.get("matched"))
    points_set = set(points_info.get("points") or []) if points_matched else set()
    points_display = list(points_info.get("points") or [])
    kill = _load_killseeker_sets()
    kill_rate_info = _load_kill_avg_high_rate()
    # 仅当杀号缓存期号贴近目标期时启用软标注；过期杀号不参与排序
    kill_period = kill.get("period")
    try:
        kill_fresh = (
            kill.get("available")
            and kill_period is not None
            and abs(int(kill_period) - int(target_period)) <= 1
        )
    except (TypeError, ValueError):
        kill_fresh = False
    high_kill = set(kill.get("high") or []) if kill_fresh else set()
    mid_kill = set(kill.get("mid") or []) if kill_fresh else set()
    opened = set(int(x) for x in (latest_nums or []))

    pick_set: Set[int] = set(freq_bucket_picks.get("all_picks") or [])
    rest_set: Set[int] = set()
    for bk in freq_bucket_picks.get("buckets") or []:
        rest_set.update(int(x) for x in (bk.get("rests") or []))

    wechat_lines = []
    for bk in freq_bucket_picks.get("buckets") or []:
        if int(bk.get("pool_size") or 0) <= 0:
            continue
        wechat_lines.append(bk.get("line") or "")

    def _tags(num: int) -> List[str]:
        t = []
        if num in pick_set:
            t.append("精选")
        elif num in rest_set:
            t.append("剩余")
        if num in points_set:
            t.append("点位")
        if num in opened:
            t.append("刚开")
        if num in high_kill:
            t.append("高杀")
        elif num in mid_kill:
            t.append("中杀")
        return t

    POINTS_BOOST = 1.15
    TOP12_POINTS_ADD = 0.20
    BOOST_FREQS = {3, 4, 5}

    def _points_boost_v4(n: int, freq: int, just_opened: bool) -> float:
        """v4：仅频3~5∩点位加权；刚开∩点位不加。"""
        if n not in points_set:
            return 1.0
        if just_opened:
            return 1.0
        if freq in BOOST_FREQS:
            return POINTS_BOOST
        return 1.0

    def _adj_score_v3(b: Dict[str, Any]) -> float:
        base = float(b.get("midhot_score") or b.get("score") or 0)
        n = int(b["number"])
        return base * (POINTS_BOOST if n in points_set else 1.0)

    def _adj_score_v4(b: Dict[str, Any]) -> float:
        base = float(b.get("midhot_score") or b.get("score") or 0)
        n = int(b["number"])
        f = int(b.get("freq_16", 0))
        return base * _points_boost_v4(n, f, n in opened)

    # ── v3 对照（内存现算，不落双缓存）──
    ranked_v3 = []
    for b in midhot_ranked:
        n = int(b["number"])
        f = int(b.get("freq_16", 0))
        if not (3 <= f <= 6):
            continue
        ranked_v3.append({
            "number": n,
            "freq_16": f,
            "omission": int(b.get("omission", 0)),
            "midhot_score": float(b.get("midhot_score") or 0),
            "adj_score": round(_adj_score_v3(b), 4),
            "in_points": n in points_set,
            "in_picks": n in pick_set,
        })
    ranked_v3.sort(key=lambda x: (-x["adj_score"], x["omission"], x["number"]))
    tip_pool_v3 = [r for r in ranked_v3 if r["in_points"]] or ranked_v3
    tip3_v3 = [r["number"] for r in tip_pool_v3[:3]]
    if len(tip3_v3) < 3:
        for r in ranked_v3:
            if r["number"] not in tip3_v3:
                tip3_v3.append(r["number"])
            if len(tip3_v3) >= 3:
                break
    top5_v3 = [r["number"] for r in ranked_v3[:5]]

    # ── v4 主排序 ──
    ranked_rows = []
    for b in midhot_ranked:
        n = int(b["number"])
        f = int(b.get("freq_16", 0))
        if not (3 <= f <= 6):
            continue
        boost = _points_boost_v4(n, f, n in opened)
        adj = float(b.get("midhot_score") or b.get("score") or 0) * boost
        ranked_rows.append({
            "number": n,
            "freq_16": f,
            "omission": int(b.get("omission", 0)),
            "recent_8": int(b.get("recent_8_hits", 0)),
            "midhot_score": round(float(b.get("midhot_score") or 0), 4),
            "adj_score": round(adj, 4),
            "points_boost": boost,
            "tags": _tags(n),
            "in_points": n in points_set,
            "in_picks": n in pick_set,
            "just_opened": n in opened,
            "kill_level": "high" if n in high_kill else ("mid" if n in mid_kill else None),
        })
    ranked_rows.sort(key=lambda x: (-x["adj_score"], x["omission"], x["number"]))

    # tip3：优先 点位∩精选，不足再回退点位中热，再不足补动量
    tip3: List[int] = []
    for r in ranked_rows:
        if r["in_points"] and r["in_picks"] and r["number"] not in tip3:
            tip3.append(r["number"])
        if len(tip3) >= 3:
            break
    if len(tip3) < 3:
        for r in ranked_rows:
            if r["in_points"] and r["number"] not in tip3:
                tip3.append(r["number"])
            if len(tip3) >= 3:
                break
    if len(tip3) < 3:
        for r in ranked_rows:
            if r["number"] not in tip3:
                tip3.append(r["number"])
            if len(tip3) >= 3:
                break

    top5 = list(tip3)  # 兼容旧字段：主口径最优 3 码
    top12 = list(tip3)  # 兼容旧字段：不再维护独立 Top12 大底

    # KillSeeker 已下架：不再做杀号缩水，仅保留标签位兼容
    avg_hr = kill_rate_info.get("avg_high_rate")
    kill_n = int(kill_rate_info.get("n") or 0)
    kill_shrink_mode = "off"
    kill_shrink_reason = "KillSeeker 已下架，仅标签不缩水"

    demoted = [r for r in ranked_rows if r["kill_level"] in ("high", "mid") or r["just_opened"]]
    demoted_nums = [r["number"] for r in demoted]

    # 回补胆：甜区排序，避开高杀
    rebound_safe = []
    for b in rebound_ranked:
        n = int(b["number"])
        om = int(b.get("omission", 0))
        if n in high_kill:
            continue
        if om < 7 or om > 14:
            continue
        rebound_safe.append({
            "number": n,
            "omission": om,
            "freq_16": int(b.get("freq_16", 0)),
            "rebound_score": float(b.get("rebound_score") or b.get("score") or 0),
            "tags": _tags(n),
            "in_points": n in points_set,
            "kill_level": "mid" if n in mid_kill else None,
        })
        if len(rebound_safe) >= 5:
            break
    rebound_safe.sort(
        key=lambda x: (1 if x["in_points"] else 0, x["rebound_score"]),
        reverse=True,
    )
    gold = rebound_safe[0]["number"] if rebound_safe else None
    silver = rebound_safe[1]["number"] if len(rebound_safe) > 1 else None
    bronze = rebound_safe[2]["number"] if len(rebound_safe) > 2 else None

    # 选2：中热×回补 + 双中热共现
    pairs = []
    cm = co_matrix or {}
    if tip3 and gold:
        a, b = sorted([tip3[0], gold])
        pairs.append({
            "pair": [a, b],
            "pair_str": f"{a:02d}-{b:02d}",
            "kind": "中热×回补",
            "cooccur": int(cm.get((a, b), 0)),
            "desc": f"尖刀{tip3[0]:02d} × 回补{gold:02d}",
        })
    if len(tip3) >= 2:
        a, b = sorted([tip3[0], tip3[1]])
        pairs.append({
            "pair": [a, b],
            "pair_str": f"{a:02d}-{b:02d}",
            "kind": "双中热",
            "cooccur": int(cm.get((a, b), 0)),
            "desc": f"尖刀轴 {a:02d}-{b:02d}",
        })
    # 精选+点位结构轴
    struct = [r for r in ranked_rows if r["in_picks"] and r["in_points"]][:2]
    if len(struct) >= 2:
        a, b = sorted([struct[0]["number"], struct[1]["number"]])
        pairs.append({
            "pair": [a, b],
            "pair_str": f"{a:02d}-{b:02d}",
            "kind": "精选×点位",
            "cooccur": int(cm.get((a, b), 0)),
            "desc": "双精选且有点位",
        })
    elif tip3 and silver:
        a, b = sorted([tip3[1] if len(tip3) > 1 else tip3[0], silver])
        pairs.append({
            "pair": [a, b],
            "pair_str": f"{a:02d}-{b:02d}",
            "kind": "中热×回补银",
            "cooccur": int(cm.get((a, b), 0)),
            "desc": f"次核 × 银胆{silver:02d}",
        })

    cold_hedge = []
    for bk in freq_bucket_picks.get("buckets") or []:
        if bk.get("bucket") in ("8+", "7"):
            for n in (bk.get("rests") or []) + (bk.get("picks") or []):
                nn = int(n)
                if nn not in high_kill:
                    cold_hedge.append(nn)
    cold_hedge = cold_hedge[:6]

    method2 = build_method2_bucket_mix(
        ball_details=ball_details or [],
        freq_bucket_picks=freq_bucket_picks or {},
    )

    pts_phrase = (
        "点位×1.15仅频3~5且非刚开·已对齐目标期"
        if points_matched
        else "点位未录入·本期仅按动量排序（回落点位仅展示不加权）"
    )
    playbook = (
        f"【方法1】最优3码 {' '.join(f'{x:02d}' for x in tip3) or '—'}；"
        f"回补 {gold or '—'}/{silver or '—'}/{bronze or '—'}；{pts_phrase}。"
        f" 【方法2】{method2.get('playbook') or ''}"
    )

    # 展示用：始终带回落点位列表；排序是否生效看 points_applied
    points_payload = dict(points_info)
    points_payload["points"] = points_display
    points_payload["points_applied"] = points_matched
    if not points_matched and points_display:
        points_payload["note"] = points_info.get("note") or (
            f"目标期 {target_period} 无点位，回落仅展示不加权"
        )

    scoring_contrast = {
        "raw_v3_contrast": {
            "tip3": tip3_v3,
            "top5": tip3_v3,
            "note": "同日 ops_pts_v3 口径对照；主口径已统一为最优3码",
        },
        "v4": {"tip3": tip3, "top5": tip3},
        "diff_tip3": [n for n in tip3 if n not in tip3_v3] + [n for n in tip3_v3 if n not in tip3],
        "diff_top5": [],
        "method2_six": list(method2.get("six") or []),
        "method1_vs_method2_overlap": sorted(set(tip3) & set(method2.get("six") or [])),
    }

    return {
        "target_period": target_period,
        "latest_period": latest_period,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rule_note": (
            "双轨：方法1=中热频3~6×ops_pts_v4最优3码(主)；"
            "方法2=微信桶频3/4/5确定性混剪六码(辅，不吃点位、不改tip3)。"
        ),
        "scoring_version": MIDHOT_SCORING_VERSION,
        "scoring_contrast": scoring_contrast,
        "kill_shrink_mode": kill_shrink_mode,
        "kill_shrink_reason": kill_shrink_reason,
        "kill_avg_high_rate": avg_hr,
        "kill_high_n": kill_n,
        "wechat_bucket_lines": wechat_lines,
        "wechat_text": "\n".join(wechat_lines),
        "points": points_payload,
        "killseeker": {
            "available": False,
            "fresh": False,
            "period": None,
            "high": [],
            "mid": [],
            "path": None,
            "note": "KillSeeker 已下架",
            "avg_high_rate": None,
            "avg_high_n": 0,
        },
        "ranking": ranked_rows[:25],
        "tip3": tip3,
        "top3_gold": tip3,
        "top5": top5,
        "top12": top12,
        "rebound": {"gold": gold, "silver": silver, "bronze": bronze, "candidates": rebound_safe},
        "pairs": pairs[:5],
        "demoted": demoted[:15],
        "demoted_nums": demoted_nums[:20],
        "cold_hedge": cold_hedge,
        "method2": method2,
        "playbook": playbook,
    }


def enrich_brief_bridges_and_flags(brief: Dict[str, Any]) -> Dict[str, Any]:
    """在 bucket_dimension_board 挂好后，写入 A/B 桥接短名单与形态旗标。"""
    try:
        from backend.modules.unified_audit.bridges import build_bridge_shortlist, build_strategy_flags
    except Exception:
        return brief

    board = brief.get("bucket_dimension_board") or {}
    edge = board.get("freq4_edge_cohort") or {}
    homology4 = [int(x) for x in (edge.get("nums") or []) if str(x).isdigit() or isinstance(x, int)]
    midhot_picks4 = [int(x) for x in (edge.get("midhot_picks") or []) if str(x).isdigit() or isinstance(x, int)]

    vip: List[int] = []
    twin: List[int] = []
    road_counts = {"r0": 0, "r1": 0, "r2": 0}
    tail0_count = None
    cold_high: List[int] = []
    try:
        prime_path = os.path.join(PROJ_DIR, "storage", "stats", "prime_tail_entropy_analysis.json")
        if os.path.exists(prime_path):
            with open(prime_path, "r", encoding="utf-8") as f:
                prime = json.load(f)
            pa = prime.get("prime_attendance_analysis") or {}
            vip = [int(x) for x in (pa.get("top5_prime_recommend") or [])]
            twins = (prime.get("twin_prime_radar_analysis") or {}).get("recommended_twins") or []
            if twins:
                twin = [int(x) for x in ((twins[0] or {}).get("pair") or [])]
            road = prime.get("road_012_analysis") or {}
            ratio = road.get("current_ratio") or ""
            # 尝试 count 字段；否则从 ratio "4:9:7" 解析
            if road.get("count_r0") is not None:
                road_counts = {
                    "r0": int(road.get("count_r0") or 0),
                    "r1": int(road.get("count_r1") or 0),
                    "r2": int(road.get("count_r2") or 0),
                }
            elif isinstance(ratio, str) and ":" in ratio:
                parts = [int(x) for x in ratio.split(":") if x.strip().isdigit()]
                if len(parts) == 3:
                    road_counts = {"r0": parts[0], "r1": parts[1], "r2": parts[2]}
            for t in (prime.get("tail_entropy_analysis") or {}).get("tail_details") or []:
                if int(t.get("tail") or -1) == 0:
                    tail0_count = int(t.get("current_count") or 0)
                    break
    except Exception:
        pass

    try:
        tp = int(brief.get("target_period") or 0)
        tri_path = os.path.join(PROJ_DIR, "storage", "points", "tri_high_points.json")
        if os.path.exists(tri_path):
            with open(tri_path, "r", encoding="utf-8") as f:
                tri = json.load(f)
            for r in tri.get("records") or []:
                if str(r.get("period")) == str(tp):
                    cold_high = [int(x) for x in (r.get("cold_high") or [])]
                    break
        if not cold_high:
            tri_a = os.path.join(PROJ_DIR, "storage", "points", "tri_high_analysis.json")
            if os.path.exists(tri_a):
                with open(tri_a, "r", encoding="utf-8") as f:
                    ta = json.load(f)
                cold_high = [int(x) for x in ((ta.get("recommendations") or {}).get("cold_strikes") or [])]
    except Exception:
        pass

    ops_pool = list(dict.fromkeys(
        list(brief.get("top12") or []) + list(brief.get("tip3") or []) + list(brief.get("top5") or [])
    ))
    bridges = build_bridge_shortlist(
        ops_pool=ops_pool,
        vip_top5=vip,
        rebound=brief.get("rebound") or {},
        cold_high=cold_high,
        homology4=homology4,
        midhot_picks4=midhot_picks4,
    )
    freq3 = board.get("freq3") or {}
    flags = build_strategy_flags(
        tail0_count=tail0_count,
        freq3_count=freq3.get("count"),
        freq3_streak_high=freq3.get("streak_high"),
        homology_count=len(homology4),
        road_counts=road_counts,
    )
    flags["homology_count"] = len(homology4)
    # 同源旁证仅当 ≥5 激活（与计划一致；bridges 已含 homology_ge5）
    flags["homology_evidence_active"] = bool(len(homology4) >= 5)
    # 012 战术抬权：仅当某路 ≤4 或 ≥10
    flags["tactical_boost_allowed"] = bool(flags.get("road_extreme"))

    brief["bridge_shortlist"] = bridges["bridge_shortlist"]
    brief["bridge_details"] = bridges["bridge_details"]
    brief["strategy_flags"] = flags
    brief["b_vip_top5"] = vip
    brief["b_twin_pair"] = twin
    return brief


def build_bucket_dimension_board(
    *,
    target_period: int,
    latest_period: int,
    outgoing_period: int,
    outgoing_nums: Set[int],
    dist_counts: Dict[str, int],
    ball_details: List[Dict[str, Any]],
    dist_history: List[Dict[str, Any]],
    freq_bucket_picks: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    每日分桶维度看板（开奖后自动重算）：
    1) 各频次池规模 + 精选/剩余拆分校验
    2) 频3 高位水位与近窗走势（是否持续偏高）
    3) 出窗同源队列：同频次且同属出窗基准期同开的号码（如「7个4全出窗」）
    4) 下期跃迁区间：出窗号命中/未中对桶规模的上下界
    """
    out_set = set(int(x) for x in (outgoing_nums or []))
    by_freq: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for b in ball_details or []:
        f = int(b.get("freq_16") or 0)
        key = "8+" if f >= 8 else str(f)
        by_freq[key].append(b)

    # 精选卡校验
    pick_checks = []
    for bk in (freq_bucket_picks or {}).get("buckets") or []:
        bucket = str(bk.get("bucket"))
        picks = [int(x) for x in (bk.get("picks") or [])]
        rests = [int(x) for x in (bk.get("rests") or [])]
        pool = int(bk.get("pool_size") or (len(picks) + len(rests)))
        pick_checks.append({
            "bucket": bucket,
            "pool_size": pool,
            "pick_n": len(picks),
            "rest_n": len(rests),
            "split_ok": pool == len(picks) + len(rests),
            "line": bk.get("line") or "",
        })

    # 频3 高位
    hist_asc = list(reversed(dist_history or []))  # 旧→新
    count3_series = [
        {"period": int(r["period"]), "count_3": int(r.get("count_3") or 0),
         "count_4": int(r.get("count_4") or 0)}
        for r in hist_asc
    ]
    cur3 = int(dist_counts.get("3") or 0)
    high_th = 20
    elev_th = 17
    streak_high = 0
    for row in reversed(count3_series):
        if row["count_3"] >= high_th:
            streak_high += 1
        else:
            break
    streak_elev = 0
    for row in reversed(count3_series):
        if row["count_3"] >= elev_th:
            streak_elev += 1
        else:
            break
    look = count3_series[-21:] if len(count3_series) >= 21 else count3_series
    avg21 = round(sum(r["count_3"] for r in look) / max(1, len(look)), 2) if look else 0.0
    elev21 = sum(1 for r in look if r["count_3"] >= elev_th)

    # 出窗同源队列（按频次）
    edge_cohorts = []
    alerts = []
    for key in ["8+", "7", "6", "5", "4", "3", "2", "1"]:
        pool = by_freq.get(key) or []
        edge = sorted(int(b["number"]) for b in pool if int(b["number"]) in out_set)
        if not edge:
            continue
        row = {
            "bucket": key,
            "pool_size": len(pool),
            "edge_count": len(edge),
            "edge_nums": edge,
            "edge_ratio": round(len(edge) / max(1, len(pool)), 3),
            "outgoing_period": outgoing_period,
            "note": (
                f"频{key}池{len(pool)}个中有{len(edge)}个同属出窗期{outgoing_period}"
                + ("（整队出窗同源）" if len(edge) >= 5 and len(edge) == len(pool) else
                   "（出窗同源集中）" if len(edge) >= 5 else "")
            ),
        }
        edge_cohorts.append(row)
        if key == "4" and len(edge) >= 5:
            alerts.append({
                "level": "warn",
                "code": "freq4_outgoing_cohort",
                "msg": (
                    f"频4出窗同源 {len(edge)} 个：{' '.join(f'{x:02d}' for x in edge)}。"
                    f"下期若未开则整队 4→3；不可能全部留在4，也不等于全部掉到3。"
                ),
            })
        if key == "3" and cur3 >= high_th:
            alerts.append({
                "level": "info",
                "code": "freq3_high_water",
                "msg": f"频3池 {cur3} 个偏高（阈值≥{high_th}）；近21期均 {avg21}，≥{elev_th} 有 {elev21}/{len(look)} 期。",
            })

    # 去重同类 alert
    seen_codes = set()
    uniq_alerts = []
    for a in alerts:
        if a["code"] in seen_codes:
            continue
        seen_codes.add(a["code"])
        uniq_alerts.append(a)

    # 下期跃迁上下界（只看出窗号：未开减1 / 开出保持）
    def _next_bounds(bucket_key: str) -> Dict[str, Any]:
        pool_nums = [int(b["number"]) for b in (by_freq.get(bucket_key) or [])]
        edge = [n for n in pool_nums if n in out_set]
        stay = [n for n in pool_nums if n not in out_set]
        # 留窗号：未开保持原频，开出 +1 离开本桶
        # 出窗号：未开 -1 离开本桶，开出保持仍在本桶
        # 下界：出窗全中留在桶 + 留窗全开离开 → 只剩 edge（若全中）；更紧：全未开则 edge 全离、stay 全留
        # 规模下界 ≈ len(stay)（出窗全掉、留窗全未开升频失败仍在）当 stay 未开保持
        # 实际上：
        #   min_size: 出窗全未开离开 + 留窗全开离开 = 0（极端）
        #   实用区间：出窗全掉后剩 stay；出窗全留后 = stay+edge；另有他桶流入忽略（只做本桶保守）
        return {
            "bucket": bucket_key,
            "pool_size": len(pool_nums),
            "edge_n": len(edge),
            "stay_n": len(stay),
            "if_all_edge_miss": len(stay),          # 出窗全未开 → 本桶只剩留窗
            "if_all_edge_hit": len(stay) + len(edge),  # 出窗全开 → 规模暂不变（忽略他桶流入/留窗升走）
            "edge_nums": edge,
            "note": (
                f"出窗{len(edge)}个全未开→本桶约剩{len(stay)}；"
                f"出窗全开→本桶暂约{len(stay)+len(edge)}（未计他桶流入）"
            ),
        }

    transition_bounds = [_next_bounds(k) for k in ["7", "6", "5", "4", "3"] if by_freq.get(k)]

    # 出窗同源精选候选（频4）：供与 midhot 精选对照
    f4_edge = sorted(int(b["number"]) for b in (by_freq.get("4") or []) if int(b["number"]) in out_set)
    f4_midhot_picks = []
    for bk in (freq_bucket_picks or {}).get("buckets") or []:
        if str(bk.get("bucket")) == "4":
            f4_midhot_picks = [int(x) for x in (bk.get("picks") or [])]
            break

    verdict_bits = []
    if f4_edge and len(f4_edge) >= 5:
        verdict_bits.append(
            f"本期频4出窗同源{len(f4_edge)}个（期{outgoing_period}同开），"
            f"与动量精选重叠{len(set(f4_edge)&set(f4_midhot_picks))}个；"
            f"结构上「不会全部掉到3，也不会全部留在4」。"
        )
    if cur3 >= elev_th:
        verdict_bits.append(
            f"频3池{cur3}个（精选+剩余应={cur3}）；"
            f"近21期均值{avg21}，属偏高水位，但≥{high_th}连续仅{streak_high}期（不宜说「连续21期都≥20」）。"
        )
    split_bad = [c for c in pick_checks if not c["split_ok"] and c["bucket"] in ("7", "6", "5", "4", "3")]
    if split_bad:
        verdict_bits.append("精选/剩余拆分与池规模不一致，请检查配额配置。")
    else:
        verdict_bits.append("微信分桶「精选+剩余=池规模」校验通过。")

    return {
        "target_period": target_period,
        "latest_period": latest_period,
        "outgoing_period": outgoing_period,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pool_sizes": dict(dist_counts),
        "pick_checks": pick_checks,
        "freq3": {
            "count": cur3,
            "high_threshold": high_th,
            "elevated_threshold": elev_th,
            "streak_high": streak_high,
            "streak_elevated": streak_elev,
            "avg_last21": avg21,
            "elevated_last21": elev21,
            "lookback_n": len(look),
            "series_tail": count3_series[-21:],
            "is_high": cur3 >= high_th,
            "is_elevated": cur3 >= elev_th,
        },
        "edge_cohorts": edge_cohorts,
        "freq4_edge_cohort": {
            "nums": f4_edge,
            "count": len(f4_edge),
            "outgoing_period": outgoing_period,
            "midhot_picks": f4_midhot_picks,
            "overlap_with_midhot": sorted(set(f4_edge) & set(f4_midhot_picks)),
            "evidence_active": len(f4_edge) >= 5,
            "wechat_line": (
                f"出窗同源{len(f4_edge)}个4：{'，'.join(f'{x:02d}' for x in f4_edge)}"
                if f4_edge else ""
            ),
            "evidence_note": (
                "样本外近30期：动量精选7码均命中≈1.77（≈随机1.75）；"
                "出窗同源队均命中≈1.13；仅当同源≥5时均命中≈1.59、命中率略高于随机。"
                "故同源队作结构旁证（仅 count≥5 激活展示），主精选仍用动量分。"
            ),
        },
        "transition_bounds": transition_bounds,
        "alerts": uniq_alerts,
        "verdict": " ".join(verdict_bits),
        "settled_audit": None,
        "forward_audit": None,
    }


def _midhot_raw_static(freq: float, recent_8: float, omission: float, is_outgoing: bool) -> float:
    """[兼容别名] 与引擎中热动量分同构（供出窗同源对账轻量重算）。

    2026-09-18 网格搜索调优同步：center=5.25 sigma=1.6 W=[0.45/0.45/0.10]
    P1 修复后本函数只是 midhot_raw_score 的转发别名，不再是第二套实现；
    新代码请直接用 midhot_raw_score / midhot_score_for_ball。
    """
    return midhot_raw_score(freq, recent_8, omission, is_outgoing)


def snapshot_freq4_dual_tracks(
    window_draws: List[Dict[str, Any]],
    *,
    pick_quota: int = 7,
) -> Dict[str, Any]:
    """对给定 16 窗快照：频4全池 / 出窗同源 / 动量精选7。"""
    if not window_draws or len(window_draws) < WINDOW_SIZE:
        return {"pool4": [], "edge": [], "midhot_picks": [], "outgoing_period": None}
    edge_draw = window_draws[0]
    edge = set(int(x) for x in (edge_draw.get("nums") or []))
    outgoing_period = int(edge_draw.get("period") or 0)
    ctr: Counter = Counter()
    for d in window_draws:
        for n in d.get("nums") or []:
            ctr[int(n)] += 1
    # 近8 / 遗漏（相对窗末）
    last8 = window_draws[-8:]
    freq8: Counter = Counter()
    for d in last8:
        for n in d.get("nums") or []:
            freq8[int(n)] += 1
    omissions = {}
    for num in range(1, NUM_TOTAL + 1):
        om = 0
        found = False
        for d in reversed(window_draws):
            if num in d.get("nums") or []:
                found = True
                break
            om += 1
        omissions[num] = om if found else 99

    pool4 = sorted(n for n in range(1, NUM_TOTAL + 1) if ctr[n] == 4)
    edge4 = sorted(n for n in pool4 if n in edge)
    scored = []
    for n in pool4:
        mh = _midhot_raw_static(
            float(ctr[n]), float(freq8.get(n, 0)), float(omissions[n]), n in edge
        )
        scored.append((mh, omissions[n], n))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    midhot_picks = [n for _, _, n in scored[: max(0, int(pick_quota))]]
    return {
        "pool4": pool4,
        "edge": edge4,
        "midhot_picks": midhot_picks,
        "outgoing_period": outgoing_period,
        "pool_size": len(pool4),
    }


def audit_freq4_dual_tracks(
    *,
    settled_period: int,
    window_draws: List[Dict[str, Any]],
    actual_nums: List[int],
    pick_quota: int = 7,
) -> Dict[str, Any]:
    """昨夜/已开目标期：出窗同源 vs 动量精选 对账。"""
    snap = snapshot_freq4_dual_tracks(window_draws, pick_quota=pick_quota)
    actual = set(int(x) for x in (actual_nums or []))
    edge = snap.get("edge") or []
    mid = snap.get("midhot_picks") or []
    edge_hits = sorted(set(edge) & actual)
    mid_hits = sorted(set(mid) & actual)
    dropped_to3 = sorted(n for n in edge if n not in actual)  # 出窗未开 → 4→3
    stayed4 = sorted(n for n in edge if n in actual)  # 出窗开出 → 仍为4
    return {
        "settled_period": int(settled_period),
        "outgoing_period": snap.get("outgoing_period"),
        "edge_nums": edge,
        "edge_count": len(edge),
        "edge_hits": edge_hits,
        "edge_hit_n": len(edge_hits),
        "midhot_picks": mid,
        "midhot_hits": mid_hits,
        "midhot_hit_n": len(mid_hits),
        "overlap": sorted(set(edge) & set(mid)),
        "edge_miss_drop_to3": dropped_to3,
        "edge_hit_stay4": stayed4,
        "note": (
            f"第{settled_period}期实开对账：出窗同源{len(edge)}中{len(edge_hits)}，"
            f"动量精选{len(mid)}中{len(mid_hits)}；"
            f"同源未开掉3→{len(dropped_to3)}个，同源开出留4→{len(stayed4)}个。"
        ),
    }


def compare_bucket_sort_methods(n_periods: int = 20) -> Dict[str, Any]:
    """
    近 N 个已开目标期，对比各 sort_by 下「精选命中」均值，标出样本最优。
    只换桶内排序，配额/模式沿用当前配置。
    """
    draws = load_draws_from_file()
    cfg = load_bucket_pick_config()
    options = list(cfg.get("sort_options") or [
        "midhot_score", "omission_asc", "omission_desc", "recent_8", "recent_3", "number_asc"
    ])
    n_periods = max(5, min(int(n_periods or 20), 60))
    if len(draws) < n_periods + 2:
        return {"status": "error", "message": "历史不足，无法对比"}

    engine = SixteenPeriodEngine(draws)
    # 已开目标期 = draws[-n] … draws[-1]；对应 analyze 索引 = len-1-n … len-2
    start_off = 1
    end_off = n_periods
    stats: Dict[str, Dict[str, float]] = {
        opt: {"hit_sum": 0.0, "pick_sum": 0.0, "periods": 0} for opt in options
    }
    rows = []
    for offset in range(start_off, end_off + 1):
        idx = len(draws) - 1 - offset
        if idx < 0:
            break
        res = engine.analyze_at_index(idx)
        balls = res.get("matrix_80") or []
        actual = None
        if res.get("freq_bucket_picks", {}).get("has_actual"):
            # 从 hits 反推不如直接取目标期开奖
            tp = int(res["target_period"])
            for d in draws:
                if int(d["period"]) == tp:
                    actual = set(d["nums"])
                    break
        if not actual:
            continue
        period_row = {"target_period": res["target_period"], "by_sort": {}}
        for opt in options:
            trial_cfg = dict(cfg)
            trial_cfg["sort_by"] = opt
            fbp = build_freq_bucket_picks(balls, config=trial_cfg, actual_numbers=actual)
            hc = int(fbp.get("all_pick_hit_count") or 0)
            pc = int(fbp.get("all_picks_count") or 0)
            stats[opt]["hit_sum"] += hc
            stats[opt]["pick_sum"] += pc
            stats[opt]["periods"] += 1
            period_row["by_sort"][opt] = {"hits": hc, "picks": pc}
        rows.append(period_row)

    ranking = []
    for opt in options:
        s = stats[opt]
        p = int(s["periods"]) or 1
        avg_hits = round(s["hit_sum"] / p, 3)
        avg_picks = round(s["pick_sum"] / p, 3) if p else 0
        hit_rate = round(s["hit_sum"] / s["pick_sum"], 4) if s["pick_sum"] else 0.0
        ranking.append({
            "sort_by": opt,
            "periods": int(s["periods"]),
            "avg_pick_hits": avg_hits,
            "avg_picks": avg_picks,
            "hit_rate": hit_rate,
            "total_hits": int(s["hit_sum"]),
            "total_picks": int(s["pick_sum"]),
        })
    ranking.sort(key=lambda x: (x["avg_pick_hits"], x["hit_rate"]), reverse=True)
    best = ranking[0]["sort_by"] if ranking else (cfg.get("sort_by") or "midhot_score")
    current = str(cfg.get("sort_by") or "midhot_score")
    return {
        "status": "ok",
        "n_periods": len(rows),
        "current_sort_by": current,
        "best_sort_by": best,
        "best_is_current": best == current,
        "ranking": ranking,
        "note": "按近N期精选平均命中数排序；最优仅作样本参考，不等于下期保证。",
        "sample_from": rows[-1]["target_period"] if rows else None,
        "sample_to": rows[0]["target_period"] if rows else None,
    }


def load_draws_from_file(filepath: Optional[str] = None) -> List[Dict[str, Any]]:
    """从开奖历史文件加载开奖数据（按时间升序排列：最老在前，最新在后）"""
    if not filepath or not os.path.exists(filepath):
        candidates = [
            os.path.join(PROJ_DIR, "kl8_history_final.txt"),
            os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt"),
            os.path.join(PROJ_DIR, "data", "kl8_history_final.txt"),
        ]
        for c in candidates:
            if os.path.exists(c):
                filepath = c
                break

    draws = []
    if not filepath or not os.path.exists(filepath):
        return draws

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line.strip())
            if not m:
                continue
            nums = set(int(x) for x in m.group(3).split("-") if x.isdigit())
            if len(nums) == 20:
                draws.append({
                    "period": int(m.group(2)),
                    "date": m.group(1),
                    "nums": nums,
                    "sorted_nums": sorted(list(nums))
                })

    if len(draws) >= 2 and draws[0]["period"] > draws[-1]["period"]:
        draws.reverse()

    return draws


def get_freq_category(freq: int) -> Tuple[str, str, str]:
    if freq <= 2:
        return ("COLD", "冷温号", "#38bdf8")       # 冰蓝
    elif freq == 3:
        return ("WARM_MID", "中温号", "#facc15")     # 亮黄
    elif freq in (4, 5):
        return ("MEDIUM_HOT", "中热黄金号", "#34d399") # 翠绿
    elif freq == 6:
        return ("STRONG_HOT", "强热号", "#fb923c")   # 亮橙
    else:  # >= 7
        return ("ULTRA_HOT", "超热极值号", "#f43f5e") # 赤红


def _window_gap_stats(num: int, window_draws: List[Dict[str, Any]]) -> Tuple[int, float, int]:
    """
    计算某号码在滑动窗口内的最大遗漏 / 平均遗漏 / 最大连出 (仅用窗口内历史，无未来泄露)
    """
    appears = [i for i, d in enumerate(window_draws) if num in d["nums"]]
    wn = len(window_draws)
    if not appears:
        return wn, float(wn), 0

    gaps = []
    prev = -1
    for a in appears:
        gaps.append(a - prev - 1)
        prev = a
    gaps.append(wn - prev - 1)
    max_om = max(gaps)
    avg_om = sum(gaps) / len(gaps)

    run = 1
    max_stk = 1
    for k in range(1, len(appears)):
        if appears[k] == appears[k - 1] + 1:
            run += 1
            max_stk = max(max_stk, run)
        else:
            run = 1

    return max_om, round(avg_om, 2), max_stk


class SixteenPeriodEngine:
    def __init__(self, draws: Optional[List[Dict[str, Any]]] = None):
        self.draws = draws if draws is not None else load_draws_from_file()

    def analyze_at_index(self, target_idx: int) -> Dict[str, Any]:
        if target_idx < WINDOW_SIZE - 1:
            raise ValueError(f"至少需要 {WINDOW_SIZE} 期历史数据")

        window_draws = self.draws[target_idx - WINDOW_SIZE + 1 : target_idx + 1]
        latest_draw = window_draws[-1]
        outgoing_draw = window_draws[0]

        latest_period = latest_draw["period"]
        latest_date = latest_draw["date"]
        outgoing_period = outgoing_draw["period"]
        outgoing_nums = outgoing_draw["nums"]

        target_period = latest_period + 1

        freq_16 = Counter()
        for d in window_draws:
            for num in d["nums"]:
                freq_16[num] += 1

        freq_3 = Counter()
        for d in window_draws[-3:]:
            for num in d["nums"]:
                freq_3[num] += 1

        freq_8 = Counter()
        for d in window_draws[-8:]:
            for num in d["nums"]:
                freq_8[num] += 1

        omissions = {}
        for num in range(1, NUM_TOTAL + 1):
            omiss = 0
            found = False
            for d in reversed(self.draws[: target_idx + 1]):
                if num in d["nums"]:
                    found = True
                    break
                omiss += 1
            omissions[num] = omiss if found else 99

        ball_details = []
        freq_buckets = defaultdict(list)

        for num in range(1, NUM_TOTAL + 1):
            f16 = freq_16.get(num, 0)
            is_out = num in outgoing_nums

            max_om, avg_om, max_stk = _window_gap_stats(num, window_draws)

            next_f_if_nodraw = (f16 - 1) if is_out else f16
            next_f_if_draw = f16 if is_out else (f16 + 1)

            cat_key, cat_name, cat_color = get_freq_category(f16)

            bucket_key = "8+" if f16 >= 8 else str(f16)
            freq_buckets[bucket_key].append(num)

            zone = (num - 1) // 10 + 1
            tail = num % 10

            ball_info = {
                "number": num,
                "display": f"{num:02d}",
                "freq_16": f16,
                "is_outgoing": is_out,
                "outgoing_period": outgoing_period,
                "next_freq_if_nodraw": next_f_if_nodraw,
                "next_freq_if_draw": next_f_if_draw,
                "shift_text": f"不出变{next_f_if_nodraw}次/开出变{next_f_if_draw}次",
                "category_key": cat_key,
                "category_name": cat_name,
                "category_color": cat_color,
                "recent_3_hits": freq_3.get(num, 0),
                "recent_8_hits": freq_8.get(num, 0),
                "omission": omissions[num],
                "max_omission": max_om,
                "avg_omission": avg_om,
                "max_streak": max_stk,
                "zone": zone,
                "tail": tail
            }
            ball_details.append(ball_info)

        dist_counts = {
            "0": len(freq_buckets.get("0", [])),
            "1": len(freq_buckets.get("1", [])),
            "2": len(freq_buckets.get("2", [])),
            "3": len(freq_buckets.get("3", [])),
            "4": len(freq_buckets.get("4", [])),
            "5": len(freq_buckets.get("5", [])),
            "6": len(freq_buckets.get("6", [])),
            "7": len(freq_buckets.get("7", [])),
            "8+": len(freq_buckets.get("8+", []))
        }

        medium_hot_total_count = dist_counts["3"] + dist_counts["4"] + dist_counts["5"] + dist_counts["6"]
        latest_draw_nums = latest_draw["nums"]
        curr_med_hits = sum(1 for n in latest_draw_nums if 3 <= freq_16.get(n, 0) <= 6)

        # ── 选号: 遗漏甜区高斯非线性加权与动量全盘精排 ──
        # 优化说明 (2026-09-11 样本外升级):
        # 1. 废止纯线性遗漏打分（线性大遗漏导致金胆陷入 >=15 期极冷死号陷阱，命中率仅 22~26%）。
        # 2. 引入高斯钟形遗漏回补甜区（中心 10.0 期，方差 4.2 期），大盘 9~12 期遗漏命中率实测达 28.99% (Lift: 1.16x)。
        # 3. 施加死冷硬惩罚：遗漏 >= 16 期的失控死号打分衰减 40% (x0.6)，防守避坑。
        # 4. 提升 16 期频次与近 8 期动量权重至 30%（频次 0.18 + 近8期 0.12），恢复中热号活跃度。
        def _znorm(vals):
            if not vals:
                return []
            mu = sum(vals) / len(vals)
            sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
            return [(v - mu) / sd for v in vals]

        sweet_l = []
        for b in ball_details:
            om = b["omission"]
            # 钟形高斯曲线：中心 10.0，两翼扩散
            sweet_val = math.exp(-((om - 10.0) ** 2) / (2 * 4.2 ** 2))
            if om >= 16:
                sweet_val *= 0.6  # 极冷僵尸号惩罚
            sweet_l.append(sweet_val)

        cur_l = [b["omission"] for b in ball_details]
        mx_l = [b["max_omission"] for b in ball_details]
        av_l = [b["avg_omission"] for b in ball_details]
        freq_l = [b["freq_16"] for b in ball_details]
        r8_l = [b["recent_8_hits"] for b in ball_details]

        sw_z = _znorm(sweet_l)
        cz = _znorm(cur_l); mz = _znorm(mx_l); az = _znorm(av_l); fz = _znorm(freq_l); rz = _znorm(r8_l)

        # 调优后权重: 甜区回补分 → 只服务「回补胆」(金/银/铜)。
        # 「中热主推」另走动量分，禁止用遗漏甜区冒充中热（2026-09-12 纠偏）。
        W_SWEET, W_CUR, W_MX, W_AV, W_FREQ, W_R8 = 0.38, 0.05, 0.15, 0.10, 0.20, 0.12
        scored = []
        for i, b in enumerate(ball_details):
            s = (W_SWEET * sw_z[i] +
                 W_CUR * cz[i] +
                 W_MX * mz[i] +
                 W_AV * az[i] +
                 W_FREQ * fz[i] +
                 W_R8 * rz[i])
            b["rebound_score"] = round(s, 4)
            b["score"] = round(s, 4)
            scored.append(b)
        scored.sort(key=lambda x: x["score"], reverse=True)

        # 回补胆：遗漏甜区排序（金胆样本外约 42%/Lift~1.7）— 与中热主推职责分离
        gold_dan = scored[0]["number"] if scored else 1
        silver_dan = scored[1]["number"] if len(scored) > 1 else 2
        bronze_dan = scored[2]["number"] if len(scored) > 2 else 3

        # 中热动量分：在频次 3~6 池内，重频次/近8期，轻遗漏甜区；
        # 刚开(omit=0)与过冷回补(omit>=8)降权 —— 中热主推要的是「池内活跃延续」，不是「冷号回补」。
        # 2026-09-18 网格搜索调优：100期样本外回测 Top3 命中率 27.67%→31.00% (Lift 1.11x→1.24x)
        #   - bell_center: 4.5→5.25（偏向频5~6的活跃号）
        #   - bell_sigma:  1.1→1.6（放宽钟形，减少对频3号的过度惩罚）
        #   - W_r8: 0.35→0.45（近8期活跃度权重提升，"最近火不火"比"歇了多久"更靠谱）
        #   - W_om: 0.20→0.10（遗漏甜区权重减半，回补信号独立性弱）
        # P1 修复：原此处嵌套复刻的 _midhot_raw 已提为模块级唯一实现，
        # 常数见文件头 MIDHOT_* 常量；审计轨（excel_window_table）复用同一函数。
        _midhot_raw = midhot_score_for_ball

        midhot_pool = [b for b in ball_details if 3 <= int(b.get("freq_16", 0)) <= 6]
        for b in midhot_pool:
            b["midhot_score"] = round(_midhot_raw(b), MIDHOT_SCORE_DECIMALS)
        midhot_ranked = sorted(midhot_pool, key=lambda x: x.get("midhot_score", 0), reverse=True)
        if len(midhot_ranked) < 5:
            widen = [b for b in ball_details if 2 <= int(b.get("freq_16", 0)) <= 7]
            for b in widen:
                if "midhot_score" not in b:
                    b["midhot_score"] = round(_midhot_raw(b), MIDHOT_SCORE_DECIMALS)
            midhot_ranked = sorted(widen, key=lambda x: x.get("midhot_score", 0), reverse=True)

        med_top5 = [x["number"] for x in midhot_ranked[:5]]
        med_top10 = [x["number"] for x in midhot_ranked[:10]]

        # 非中热号也挂上 midhot_score 占位（桶内排序回落 rebound/score）
        mid_map = {b["number"]: b.get("midhot_score") for b in midhot_ranked}
        for b in ball_details:
            if b["number"] in mid_map and mid_map[b["number"]] is not None:
                b["midhot_score"] = mid_map[b["number"]]
            else:
                b.setdefault("midhot_score", round(float(b.get("rebound_score") or b.get("score") or 0), 4))

        # 频次桶「精选 / 剩余」两列（民间分桶精选口径，规则可配置）
        actual_for_target = None
        if target_idx + 1 < len(self.draws) and int(self.draws[target_idx + 1]["period"]) == int(target_period):
            actual_for_target = self.draws[target_idx + 1]["nums"]
        freq_bucket_picks = build_freq_bucket_picks(ball_details, actual_numbers=actual_for_target)

        # 展示候选：中热动量榜优先，再拼接回补分榜，去重截 30
        seen = set()
        scored_candidates = []
        for x in midhot_ranked + scored:
            n = x["number"]
            if n in seen:
                continue
            seen.add(n)
            # 统一对外 score：中热池用 midhot_score，其余保留 rebound score
            if "midhot_score" in x and 3 <= int(x.get("freq_16", 0)) <= 6:
                x = {**x, "score": x["midhot_score"]}
            scored_candidates.append(x)
            if len(scored_candidates) >= 30:
                break

        # ── 频次演变趋势与跃迁动量深度分析 (Transition Momentum State Machine) ──
        # 1. 留窗号 vs 出窗号列表与状态
        outgoing_nums_sorted = sorted(list(outgoing_nums))
        in_window_nums_sorted = sorted([n for n in range(1, NUM_TOTAL + 1) if n not in outgoing_nums])

        # 2. 分桶跃迁明细
        buckets_transition = {}
        for f in range(9):
            k = "8+" if f == 8 else str(f)
            b_nums = freq_buckets.get(k, [])
            in_b = [n for n in b_nums if n not in outgoing_nums]
            out_b = [n for n in b_nums if n in outgoing_nums]

            # 内部按综合评分排序
            in_b_sorted = sorted(in_b, key=lambda n: next((x["score"] for x in scored if x["number"] == n), 0), reverse=True)
            out_b_sorted = sorted(out_b, key=lambda n: next((x["score"] for x in scored if x["number"] == n), 0), reverse=True)

            next_draw_val = (f + 1) if f < 8 else 8
            next_nodraw_val = max(0, f - 1)

            buckets_transition[k] = {
                "current_freq": f if f < 8 else "8+",
                "total_count": len(b_nums),
                "all_numbers": b_nums,
                "in_candidates": {
                    "count": len(in_b),
                    "numbers": in_b_sorted,
                    "next_freq_if_draw": next_draw_val,
                    "next_freq_if_nodraw": f if f < 8 else "8+",
                    "shift_text": f"开出升为{next_draw_val}次 / 不开保持{k}次",
                    "top_picks": in_b_sorted[:3]
                },
                "out_candidates": {
                    "count": len(out_b),
                    "numbers": out_b_sorted,
                    "next_freq_if_draw": f if f < 8 else "8+",
                    "next_freq_if_nodraw": next_nodraw_val,
                    "shift_text": f"不开降为{next_nodraw_val}次 / 开出保持{k}次",
                    "top_picks": out_b_sorted[:3]
                }
            }

        # 3. 五大跃迁核心梯队 (Five Transition Ladders)
        # 梯队 1: 破冰反弹 (0➔1 & 1➔2)
        ice_break_cands = [x for x in scored if x["freq_16"] in (0, 1) and not x["is_outgoing"]]
        # 梯队 2: 温号苏醒 (2➔3)
        warm_wake_cands = [x for x in scored if x["freq_16"] == 2 and not x["is_outgoing"]]
        # 梯队 3: 黄金中热冲刺 (3➔4 · 主攻核心区)
        gold_rush_cands = [x for x in scored if x["freq_16"] == 3 and not x["is_outgoing"]]
        # 梯队 4: 黄金动量延续 (4➔5 & 5➔6)
        hot_momentum_cands = [x for x in scored if x["freq_16"] in (4, 5) and not x["is_outgoing"]]
        # 梯队 5: 出窗自然降频避坑 (8➔7 & 7➔6 高位透支)
        outgoing_cool_cands = [x for x in scored if x["freq_16"] >= 6 and x["is_outgoing"]]

        transition_ladders = {
            "ladder_ice_break": {
                "key": "ICE_BREAK",
                "name": "破冰反弹梯队 (0➔1 & 1➔2)",
                "badge": "🧊 破冰跃迁",
                "desc": "极冷死号/低频冷号触底反弹，均值回归动能最强，防冷号突袭",
                "target_shift": "0次➔1次 / 1次➔2次",
                "count": len(ice_break_cands),
                "top_picks": [x["number"] for x in ice_break_cands[:3]],
                "candidates": ice_break_cands[:6]
            },
            "ladder_warm_wake": {
                "key": "WARM_WAKE",
                "name": "温号苏醒梯队 (2➔3)",
                "badge": "🌿 温号苏醒",
                "desc": "温冷号蓄势结束，启动向中热黄金区间突破，出号赔率极佳",
                "target_shift": "2次➔3次",
                "count": len(warm_wake_cands),
                "top_picks": [x["number"] for x in warm_wake_cands[:4]],
                "candidates": warm_wake_cands[:6]
            },
            "ladder_gold_rush": {
                "key": "GOLD_RUSH",
                "name": "黄金中热冲刺梯队 (3➔4 · 核心主力攻坚区)",
                "badge": "👑 黄金冲刺",
                "desc": "大盘最厚实的粮仓，3次中温号跨入4次黄金中热甜区，单期产出主力",
                "target_shift": "3次➔4次",
                "count": len(gold_rush_cands),
                "top_picks": [x["number"] for x in gold_rush_cands[:6]],
                "candidates": gold_rush_cands[:10]
            },
            "ladder_hot_momentum": {
                "key": "HOT_MOMENTUM",
                "name": "黄金动量延续梯队 (4➔5 & 5➔6)",
                "badge": "🚀 动量延续",
                "desc": "强势中热号持续高频输出，动能连击突破强热，防踏空",
                "target_shift": "4次➔5次 / 5次➔6次",
                "count": len(hot_momentum_cands),
                "top_picks": [x["number"] for x in hot_momentum_cands[:5]],
                "candidates": hot_momentum_cands[:8]
            },
            "ladder_outgoing_cool": {
                "key": "OUTGOING_COOL",
                "name": "出窗自然降频避坑梯队 (8➔7 & 7➔6 高位透支)",
                "badge": "🛡️ 出窗降温",
                "desc": "16期前开出且近期高位透支号，大概率轮空自然降温卸压，建议防守/杀号避坑",
                "target_shift": "8次➔7次 / 7次➔6次 (若不开)",
                "count": len(outgoing_cool_cands),
                "avoid_picks": [x["number"] for x in outgoing_cool_cands[:4]],
                "candidates": outgoing_cool_cands[:6]
            }
        }

        # 4. 跨梯队跃迁黄金搭档 (选2 / 选3 配对)
        transition_pairs = []
        # 搭档 1: 破冰 + 黄金中热冲刺
        if ice_break_cands and gold_rush_cands:
            p1, p2 = ice_break_cands[0]["number"], gold_rush_cands[0]["number"]
            transition_pairs.append({
                "pair": sorted([p1, p2]),
                "pair_str": f"{min(p1, p2):02d}-{max(p1, p2):02d}",
                "tag": "破冰极值 + 黄金冲刺",
                "desc": f"极冷破冰{p1:02d} + 中热冲刺{p2:02d}",
                "score": round((ice_break_cands[0]["score"] + gold_rush_cands[0]["score"]) * 10 + 20, 1)
            })
        # 搭档 2: 双黄金中热冲刺 (双核进攻)
        if len(gold_rush_cands) >= 2:
            p1, p2 = gold_rush_cands[0]["number"], gold_rush_cands[1]["number"]
            transition_pairs.append({
                "pair": sorted([p1, p2]),
                "pair_str": f"{min(p1, p2):02d}-{max(p1, p2):02d}",
                "tag": "双核黄金冲刺 (核心主推)",
                "desc": f"均值回归双星 {min(p1, p2):02d} + {max(p1, p2):02d} (3次➔4次)",
                "score": round((gold_rush_cands[0]["score"] + gold_rush_cands[1]["score"]) * 10 + 25, 1)
            })
        # 搭档 3: 黄金中热冲刺 + 动量延续
        if gold_rush_cands and hot_momentum_cands:
            p1, p2 = gold_rush_cands[0]["number"], hot_momentum_cands[0]["number"]
            transition_pairs.append({
                "pair": sorted([p1, p2]),
                "pair_str": f"{min(p1, p2):02d}-{max(p1, p2):02d}",
                "tag": "攻守兼备组合",
                "desc": f"中热冲刺{p1:02d} + 动量延续{p2:02d}",
                "score": round((gold_rush_cands[0]["score"] + hot_momentum_cands[0]["score"]) * 10 + 18, 1)
            })
        # 搭档 4: 温号苏醒 + 黄金中热冲刺
        if warm_wake_cands and gold_rush_cands:
            p1, p2 = warm_wake_cands[0]["number"], (gold_rush_cands[1]["number"] if len(gold_rush_cands) > 1 else gold_rush_cands[0]["number"])
            transition_pairs.append({
                "pair": sorted([p1, p2]),
                "pair_str": f"{min(p1, p2):02d}-{max(p1, p2):02d}",
                "tag": "温冷蓄势 + 中热共振",
                "desc": f"温号苏醒{p1:02d} + 黄金冲刺{p2:02d}",
                "score": round((warm_wake_cands[0]["score"] + gold_rush_cands[0]["score"]) * 10 + 15, 1)
            })
        # 搭档 5: 破冰 + 动量延续
        if ice_break_cands and hot_momentum_cands:
            p1, p2 = ice_break_cands[0]["number"], hot_momentum_cands[0]["number"]
            transition_pairs.append({
                "pair": sorted([p1, p2]),
                "pair_str": f"{min(p1, p2):02d}-{max(p1, p2):02d}",
                "tag": "冷热对冲组合",
                "desc": f"冷号破冰{p1:02d} + 热号动量{p2:02d}",
                "score": round((ice_break_cands[0]["score"] + hot_momentum_cands[0]["score"]) * 10 + 12, 1)
            })

        # 5. 更新 matrix_80 赋能字段
        enhanced_matrix = []
        for b in ball_details:
            num = b["number"]
            f = b["freq_16"]
            is_out = b["is_outgoing"]
            
            # 梯队归属与标签
            ladder_key = "NORMAL"
            ladder_name = "常规态势"
            promo_tag = "▲ 升频" if not is_out else "■ 保频"
            demo_tag = "▼ 降频" if is_out else "■ 保频"
            
            if not is_out:
                if f in (0, 1):
                    ladder_key = "ICE_BREAK"
                    ladder_name = f"破冰反弹 ({f}➔{f+1})"
                elif f == 2:
                    ladder_key = "WARM_WAKE"
                    ladder_name = "温号苏醒 (2➔3)"
                elif f == 3:
                    ladder_key = "GOLD_RUSH"
                    ladder_name = "黄金冲刺 (3➔4)"
                elif f in (4, 5):
                    ladder_key = "HOT_MOMENTUM"
                    ladder_name = f"动量延续 ({f}➔{f+1})"
                elif f >= 6:
                    ladder_key = "HOT_MOMENTUM"
                    ladder_name = f"极热冲刺 ({f}➔{f+1})"
            else:
                if f >= 6:
                    ladder_key = "OUTGOING_COOL"
                    ladder_name = f"出窗降温 ({f}➔{f-1})"
                else:
                    ladder_key = "OUTGOING_NORMAL"
                    ladder_name = f"出窗回踩 ({f}➔{f-1})"

            # 胆码与主推标签
            rec_tag = "⚪"
            if num == gold_dan:
                rec_tag = "👑 回补金胆"
            elif num == silver_dan:
                rec_tag = "🥈 回补银胆"
            elif num == bronze_dan:
                rec_tag = "🥉 回补铜胆"
            elif num in med_top5:
                rec_tag = "⚡ 中热主推"
            elif num in transition_ladders["ladder_outgoing_cool"]["avoid_picks"]:
                rec_tag = "🛡️ 降温防守"

            enhanced_matrix.append({
                **b,
                "ladder_key": ladder_key,
                "ladder_name": ladder_name,
                "promo_tag": promo_tag,
                "demo_tag": demo_tag,
                "recommend_tag": rec_tag
            })

        # 16 期共现(仅在候选池内) 供配对/三连组合使用
        cand_nums = [x["number"] for x in scored_candidates]
        co_matrix = defaultdict(int)
        for d in window_draws:
            in_pool = [n for n in d["nums"] if n in cand_nums]
            for i in range(len(in_pool)):
                for j in range(i + 1, len(in_pool)):
                    a, b = min(in_pool[i], in_pool[j]), max(in_pool[i], in_pool[j])
                    co_matrix[(a, b)] += 1

        # 优化说明 (2026-09-11 样本外升级):
        # 废除原有的「金胆硬加+15分/银胆硬加+8分」单核绑架机制，引入「冷热对冲互补协同」(+8.0)：
        # 实测表明：一冷(遗漏>=7, 频次<=3) + 一热(频次>=4, 遗漏<=5)的双全中率达 11.0% (Lift: 1.83x)，
        # 避免两个同温号相互抢占名额。
        pair_candidates = []
        for i in range(len(scored_candidates[:15])):
            for j in range(i + 1, len(scored_candidates[:15])):
                c1 = scored_candidates[i]
                c2 = scored_candidates[j]
                n1, n2 = c1["number"], c2["number"]
                pair_tuple = (min(n1, n2), max(n1, n2))
                co_cnt = co_matrix.get(pair_tuple, 0)

                has_gold = (gold_dan in pair_tuple)
                has_silver = (silver_dan in pair_tuple)

                # 冷热对冲互补判定: 一枚为黄金回补冷号(om>=7, freq<=3), 一枚为动量中热号(freq>=4, om<=5)
                is_comp = ((c1["omission"] >= 7 and c1["freq_16"] <= 3 and c2["freq_16"] >= 4 and c2["omission"] <= 5) or
                           (c2["omission"] >= 7 and c2["freq_16"] <= 3 and c1["freq_16"] >= 4 and c1["omission"] <= 5))

                pair_score = (c1["score"] + c2["score"]) / 2.0  # 独立宪法: 共现加成归零 (Lift≈1.008)
                if is_comp:
                    pair_score += 8.0  # 互补对冲黄金协同加成 (实测显著)
                if has_gold:
                    pair_score += 4.0  # 温和金胆加成, 避免单核垄断
                elif has_silver:
                    pair_score += 2.0

                desc_tag = "冷热对冲互补搭档" if is_comp else "双中热共振组合"
                pair_candidates.append({
                    "pair": list(pair_tuple),
                    "pair_str": f"{pair_tuple[0]:02d}-{pair_tuple[1]:02d}",
                    "score": round(pair_score, 2),
                    "co_count": co_cnt,
                    "has_gold": has_gold,
                    "has_silver": has_silver,
                    "is_complementary": is_comp,
                    "desc": f"{desc_tag}: {pair_tuple[0]:02d}({c1['freq_16']}次/遗{c1['omission']}) + {pair_tuple[1]:02d}({c2['freq_16']}次/遗{c2['omission']})"
                })

        pair_candidates.sort(key=lambda x: x["score"], reverse=True)
        top5_pairs = pair_candidates[:5]

        triple_candidates = []
        for i in range(len(scored_candidates[:8])):
            for j in range(i + 1, len(scored_candidates[:8])):
                for k in range(j + 1, len(scored_candidates[:8])):
                    c1, c2, c3 = scored_candidates[i], scored_candidates[j], scored_candidates[k]
                    n1, n2, n3 = sorted([c1["number"], c2["number"], c3["number"]])
                    t_tuple = (n1, n2, n3)
                    co_sum = (co_matrix.get((n1, n2), 0) +
                              co_matrix.get((n1, n3), 0) +
                              co_matrix.get((n2, n3), 0))
                    t_score = (c1["score"] + c2["score"] + c3["score"]) / 3.0 + co_sum * 2.0
                    if gold_dan in t_tuple:
                        t_score += 12.0
                    triple_candidates.append({
                        "triple": list(t_tuple),
                        "triple_str": f"{n1:02d}-{n2:02d}-{n3:02d}",
                        "score": round(t_score, 2),
                        "co_sum": co_sum,
                        "has_gold": gold_dan in t_tuple
                    })

        triple_candidates.sort(key=lambda x: x["score"], reverse=True)
        top5_triples = triple_candidates[:5]

        dist_history_table = []
        hist_start_idx = max(WINDOW_SIZE - 1, target_idx - 30 + 1)
        for h_idx in range(hist_start_idx, target_idx + 1):
            h_win = self.draws[h_idx - WINDOW_SIZE + 1 : h_idx + 1]
            h_draw = self.draws[h_idx]
            h_freq = Counter()
            for d in h_win:
                for n in d["nums"]:
                    h_freq[n] += 1
            
            b_cnt = {str(k): 0 for k in range(9)}
            b_cnt["8+"] = 0
            for n in range(1, NUM_TOTAL + 1):
                f = h_freq.get(n, 0)
                if f >= 8:
                    b_cnt["8+"] += 1
                else:
                    b_cnt[str(f)] += 1

            h_med_hits = sum(1 for n in h_draw["nums"] if 3 <= h_freq.get(n, 0) <= 6)

            dist_history_table.append({
                "period": h_draw["period"],
                "date": h_draw["date"],
                "count_1": b_cnt["1"],
                "count_2": b_cnt["2"],
                "count_3": b_cnt["3"],
                "count_4": b_cnt["4"],
                "count_5": b_cnt["5"],
                "count_6": b_cnt["6"],
                "count_7": b_cnt["7"],
                "count_8plus": b_cnt["8+"],
                "medium_hot_pool_size": b_cnt["3"] + b_cnt["4"] + b_cnt["5"] + b_cnt["6"],
                "medium_hot_draw_hits": h_med_hits,
                "drawn_nums": h_draw["sorted_nums"]
            })

        dist_history_table_desc = list(reversed(dist_history_table))
        daily_ops_brief = build_daily_ops_brief(
            target_period=int(target_period),
            latest_period=int(latest_period),
            latest_nums=list(latest_draw.get("nums") or []),
            ball_details=ball_details,
            midhot_ranked=midhot_ranked,
            rebound_ranked=scored,
            freq_bucket_picks=freq_bucket_picks,
            co_matrix=dict(co_matrix),
        )
        bucket_dimension_board = build_bucket_dimension_board(
            target_period=int(target_period),
            latest_period=int(latest_period),
            outgoing_period=int(outgoing_period),
            outgoing_nums=set(int(x) for x in (outgoing_nums or [])),
            dist_counts=dist_counts,
            ball_details=ball_details,
            dist_history=dist_history_table_desc,
            freq_bucket_picks=freq_bucket_picks,
        )
        # 维度交叉研究：出现次数×剩余次数矩阵 + 尾数/012路/质合画像 + 约束优化选号
        try:
            from backend.modules.sixteen.dimension_cross import analyze_dimension_cross
            dimension_cross = analyze_dimension_cross(self.draws, target_idx=target_idx)
        except Exception:
            logger.exception("维度交叉研究计算失败")
            dimension_cross = {}
        # 刚开期对账：上一窗（预测 latest_period）的出窗同源 vs 动量精选
        if target_idx >= WINDOW_SIZE:
            prev_window = self.draws[target_idx - WINDOW_SIZE : target_idx]
            bucket_dimension_board["settled_audit"] = audit_freq4_dual_tracks(
                settled_period=int(latest_period),
                window_draws=prev_window,
                actual_nums=list(latest_draw.get("nums") or []),
            )
        # 若目标期已开（回看），对本窗双轨做前瞻对账
        if actual_for_target is not None:
            bucket_dimension_board["forward_audit"] = audit_freq4_dual_tracks(
                settled_period=int(target_period),
                window_draws=window_draws,
                actual_nums=list(actual_for_target),
            )
        daily_ops_brief["bucket_dimension_board"] = bucket_dimension_board
        daily_ops_brief = enrich_brief_bridges_and_flags(daily_ops_brief)
        # 双轨原文附在微信分桶后（结构旁证，不替换动量精选）
        edge_line = ((bucket_dimension_board.get("freq4_edge_cohort") or {}).get("wechat_line") or "").strip()
        # 同源旁证仅当 count≥5 才写入微信行（否则保留数据但不强调）
        edge_nums = (bucket_dimension_board.get("freq4_edge_cohort") or {}).get("nums") or []
        evidence_active = len(edge_nums) >= 5
        if edge_line and evidence_active:
            wt = (daily_ops_brief.get("wechat_text") or "").rstrip()
            daily_ops_brief["wechat_text"] = (wt + "\n" + edge_line) if wt else edge_line
            lines = list(daily_ops_brief.get("wechat_bucket_lines") or [])
            lines.append(edge_line)
            daily_ops_brief["wechat_bucket_lines"] = lines
        # 若简报已算出更稳妥的回补/主推，同步到 cross 与展示字段（主口径 tip3）
        brief_tip3 = list(daily_ops_brief.get("tip3") or daily_ops_brief.get("top3_gold") or [])[:3]
        if len(brief_tip3) < 3:
            brief_tip3 = ([gold_dan, silver_dan, bronze_dan] + list(med_top5 or []))[:3]
        brief_top5 = brief_tip3  # 兼容旧字段
        brief_gold = (daily_ops_brief.get("rebound") or {}).get("gold") or gold_dan
        cross_validation = self._build_cross_validation(
            brief_gold,
            brief_tip3,
            points=set(daily_ops_brief.get("points", {}).get("points") or []),
        )

        transition_analysis = {
            "summary": {
                "outgoing_period": outgoing_period,
                "outgoing_count": len(outgoing_nums_sorted),
                "in_window_count": len(in_window_nums_sorted),
                "outgoing_nums": outgoing_nums_sorted,
                "in_window_nums": in_window_nums_sorted
            },
            "buckets": buckets_transition,
            "ladders": transition_ladders,
            "transition_pairs": transition_pairs,
            "transition_top5_picks": [x["number"] for x in scored_candidates[:3]]
        }

        tip3_out = [gold_dan, silver_dan, bronze_dan]
        # Excel 同款 16 窗开奖矩阵（1头=10-19，≠一区）
        excel_window_slim: Dict[str, Any] = {}
        try:
            from backend.modules.sixteen.excel_window_table import build_excel_window_table
            _ew = build_excel_window_table(
                self.draws[: target_idx + 1],
                window_size=WINDOW_SIZE,
                history_tail=WINDOW_SIZE,
            )
            if _ew.get("status") == "ok":
                excel_window_slim = {
                    "window_label": _ew.get("window_label"),
                    "window_start_period": _ew.get("window_start_period"),
                    "window_end_period": _ew.get("window_end_period"),
                    "note": _ew.get("note"),
                    "one_head": _ew.get("one_head"),
                    "head_stats": _ew.get("head_stats"),
                    "zone_stats": _ew.get("zone_stats"),
                    "window_rows": [
                        {
                            "period": r["period"],
                            "date": r["date"],
                            "nums_str": r["nums_str"],
                            "1头": r["1头"],
                            "一区": r["一区"],
                            **{k: r[k] for k in ("0头", "2头", "3头", "4头", "5头", "6头", "7头", "8头") if k in r},
                        }
                        for r in (_ew.get("window_rows") or [])
                    ],
                }
        except Exception:
            excel_window_slim = {}

        return {
            "target_period": target_period,
            "latest_period": latest_period,
            "latest_date": latest_date,
            "outgoing_period": outgoing_period,
            "excel_window": excel_window_slim,
            "gold_dan": gold_dan,
            "silver_dan": silver_dan,
            "bronze_dan": bronze_dan,
            "medium_top5": med_top5,  # 兼容：中热5码大名单
            "medium_top10": med_top10,
            "ops_tip3": brief_tip3,
            "ops_top5": brief_top5,
            "ops_top12": list(brief_tip3),  # 兼容：同最优3码
            "ops_method2_six": list((daily_ops_brief.get("method2") or {}).get("six") or []),
            "ops_method2": daily_ops_brief.get("method2"),
            "top5_pairs": top5_pairs,
            "top5_triples": top5_triples,
            "distribution_counts": dist_counts,
            "medium_hot_total_count": medium_hot_total_count,
            "latest_medium_hot_hits": curr_med_hits,
            "matrix_80": enhanced_matrix,
            "scored_candidates": scored_candidates,
            "distribution_history": dist_history_table_desc,
            "cross_validation": cross_validation,
            "transition_analysis": transition_analysis,
            "freq_bucket_picks": freq_bucket_picks,
            "daily_ops_brief": daily_ops_brief,
            "bucket_dimension_board": bucket_dimension_board,
            "dimension_cross": dimension_cross,
            "meta": {
                "window_size": WINDOW_SIZE,
                "medium_hot_range": "3-6次",
                "scoring_split": "rebound_dan_vs_midhot_top_vs_bucket_picks",
                "ops_brief": "daily_ops_brief=方法1 tip3主轨 + 方法2混剪六码辅轨",
                "dimension_board": "bucket_dimension_board=频池水位/出窗同源/跃迁上下界",
                "dual_track": "method1=ops_pts_v4 tip3；method2=bucket_mix_v1 六码",
                "timestamp": datetime.now().isoformat()
            }
        }

    def _build_cross_validation(
        self,
        gold_dan: int,
        tip3: List[int],
        points: Optional[Set[int]] = None,
    ) -> Dict[str, Any]:
        pts = set(points or [])
        tip3 = list(tip3 or [])[:3]
        while len(tip3) < 3:
            tip3.append(gold_dan if tip3 else 1)
        res = {
            "gold_dan": gold_dan,
            "top3_gold": tip3[:3],
            "in_he5": False,
            "in_trinity12": False,
            "in_spatial_points": gold_dan in pts,
            "in_suppression": False,
            "safety_audit": "✓ 安全绿灯",
        }
        return res

    def generate_report(self, analysis_res: Dict[str, Any]) -> str:
        target_p = analysis_res["target_period"]
        latest_p = analysis_res["latest_period"]
        out_p = analysis_res["outgoing_period"]
        gold = analysis_res["gold_dan"]
        silver = analysis_res["silver_dan"]
        bronze = analysis_res["bronze_dan"]
        top5 = analysis_res["medium_top5"]
        top10 = analysis_res["medium_top10"]
        top5_pairs = analysis_res["top5_pairs"]
        dist = analysis_res["distribution_counts"]
        med_cnt = analysis_res["medium_hot_total_count"]
        ta = analysis_res.get("transition_analysis", {})
        ladders = ta.get("ladders", {})
        trans_pairs = ta.get("transition_pairs", [])

        top5_str = " ".join(f"{x:02d}" for x in top5)
        top10_str = " ".join(f"{x:02d}" for x in top10)

        lines = [
            f"# 🔥 16期频次动态推演与跃迁动量决策研报 (第 {target_p} 期)",
            "",
            f"> **研判基准**：第 {latest_p} 期开奖 | **出窗基准**：第 {out_p} 期 (16期前) | **推演目标**：第 {target_p} 期",
            f"> **生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | **核心逻辑**：16期滑动窗口频次状态机 + 动态出窗/留窗跃迁动量推演 + 均值回归遗漏精排",
            "",
            "---",
            "",
            "## 🧬 一、16期频次演变状态机核心公理 (老派操盘手大白话)",
            "",
            "1. **【留窗号（60个）】**：16期前那期**未开出**的号码。",
            "   - 若下期**开出** ➔ **频次自动 +1（升频跃迁）**：例如 $0\\to 1$, $1\\to 2$, $2\\to 3$, $3\\to 4$, $4\\to 5$...",
            "   - 若下期**不开** ➔ **频次维持不变**。",
            "2. **【出窗号（20个）】**：16期前那期**开出过**的号码（窗口边缘号）。",
            "   - 若下期**不开** ➔ **频次自动 -1（物理卸压降频）**：例如 $8\\to 7$, $7\\to 6$, $6\\to 5$, $4\\to 3$...",
            "   - 若下期**开出** ➔ 新老对冲，**频次维持原状（保频）**。",
            "",
            "---",
            "",
            "## 🎯 二、下一期五大频次跃迁核心梯队 (攻防一体)",
            "",
            "| 梯队名称 | 跃迁方向 | 核心研判逻辑 | 推荐重点号码 | 操盘建议 |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]

        if ladders:
            ib = ladders.get("ladder_ice_break", {})
            ww = ladders.get("ladder_warm_wake", {})
            gr = ladders.get("ladder_gold_rush", {})
            hm = ladders.get("ladder_hot_momentum", {})
            oc = ladders.get("ladder_outgoing_cool", {})

            ib_str = " ".join(f"{x:02d}" for x in ib.get("top_picks", [])) or "无"
            ww_str = " ".join(f"{x:02d}" for x in ww.get("top_picks", [])) or "无"
            gr_str = " ".join(f"{x:02d}" for x in gr.get("top_picks", [])) or "无"
            hm_str = " ".join(f"{x:02d}" for x in hm.get("top_picks", [])) or "无"
            oc_str = " ".join(f"{x:02d}" for x in oc.get("avoid_picks", [])) or "无"

            lines.append(f"| **{ib.get('badge','破冰')} {ib.get('name','破冰反弹')}** | `{ib.get('target_shift','')}` | {ib.get('desc','')} | `{ib_str}` | 冷号极值突袭 |")
            lines.append(f"| **{ww.get('badge','苏醒')} {ww.get('name','温号苏醒')}** | `{ww.get('target_shift','')}` | {ww.get('desc','')} | `{ww_str}` | 温冷突破甜区 |")
            lines.append(f"| **{gr.get('badge','冲刺')} {gr.get('name','黄金冲刺')}** | `{gr.get('target_shift','')}` | {gr.get('desc','')} | `{gr_str}` | **核心进攻底仓** |")
            lines.append(f"| **{hm.get('badge','延续')} {hm.get('name','动量延续')}** | `{hm.get('target_shift','')}` | {hm.get('desc','')} | `{hm_str}` | 顺势连击防踏空 |")
            lines.append(f"| **{oc.get('badge','降温')} {oc.get('name','出窗降温')}** | `{oc.get('target_shift','')}` | {oc.get('desc','')} | `{oc_str}` | **高位透支防追高** |")

        lines.extend([
            "",
            "---",
            "",
            "## 👑 三、双轨定胆与中热主推（名实分离）",
            "",
            f"- 👑 **回补金胆（遗漏甜区，非中热主推）**：`{gold:02d}`",
            f"- 🥈 **回补银胆**：`{silver:02d}`",
            f"- 🥉 **回补铜胆**：`{bronze:02d}`",
            f"- 🛡️ **中热主推 5 码（频次 3~6 动量）**：`{top5_str}`",
            f"- 📋 **中热精选 10 码大名单**：`{top10_str}`",
            "",
        ])

        fbp = analysis_res.get("freq_bucket_picks") or {}
        if fbp.get("buckets"):
            cfg = fbp.get("config") or {}
            lines.extend([
                "---",
                "",
                "## 📊 三附、频次桶精选 / 剩余（民间同款分桶）",
                "",
                f"> mode=`{cfg.get('mode','quota')}` · sort=`{cfg.get('sort_by','midhot_score')}` · 精选合计 `{fbp.get('all_picks_count', 0)}` 码",
                "",
            ])
            if fbp.get("has_actual"):
                lines.append(
                    f"> 目标期已开：精选命中 **{fbp.get('all_pick_hit_count', 0)}/{fbp.get('all_picks_count', 0)}**"
                )
                lines.append("")
            for bk in fbp.get("buckets") or []:
                if not bk.get("pool_size"):
                    continue
                picks_str = " ".join(f"{x:02d}" for x in (bk.get("picks") or [])) or "—"
                rests_str = " ".join(f"{x:02d}" for x in (bk.get("rests") or [])) or "—"
                hit_note = ""
                if fbp.get("has_actual"):
                    hit_note = f" · 精选中{bk.get('pick_hit_count', 0)} / 剩余中{bk.get('rest_hit_count', 0)}"
                lines.append(f"### {bk.get('freq_label')}（池 {bk.get('pool_size')}{hit_note}）")
                lines.append(f"- **精选 {bk.get('pick_count', 0)}**：`{picks_str}`")
                lines.append(f"- **剩余 {bk.get('rest_count', 0)}**：`{rests_str}`")
                lines.append("")

        brief = analysis_res.get("daily_ops_brief") or {}
        if brief:
            pts = brief.get("points") or {}
            rb = brief.get("rebound") or {}
            lines.extend([
                "---",
                "",
                "## 📌 每日完整操盘简报（开奖16窗 + 点位 + 杀号）",
                "",
                f"> {brief.get('rule_note', '')}",
                "",
                "### 微信分桶原文",
                "```",
                brief.get("wechat_text") or "（无）",
                "```",
                "",
                f"- 点位期 `{pts.get('period')}` · 匹配目标={'是' if pts.get('matched') else '否'} · "
                f"`{' '.join(f'{x:02d}' for x in (pts.get('points') or []))}`",
                f"- 尖刀3：`{' '.join(f'{x:02d}' for x in (brief.get('tip3') or []))}`",
                f"- 操盘Top5：`{' '.join(f'{x:02d}' for x in (brief.get('top5') or []))}`",
                f"- 最优3码：`{' '.join(f'{x:02d}' for x in (brief.get('tip3') or brief.get('top3_gold') or []))}`",
                f"- 回补（避高杀）：金`{rb.get('gold') or '--'}` / 银`{rb.get('silver') or '--'}` / 铜`{rb.get('bronze') or '--'}`",
                f"- 口诀：{brief.get('playbook', '')}",
                "",
            ])
            m2 = brief.get("method2") or {}
            if m2.get("six"):
                lines.extend([
                    "### 方法2 · 微信桶混剪六码（算法）",
                    f"- 六码：`{m2.get('six_str') or ' '.join(f'{x:02d}' for x in m2.get('six') or [])}`",
                    f"- 口径：{m2.get('note') or m2.get('role') or ''}",
                    "",
                ])
                for s in m2.get("seats") or []:
                    n = s.get("number")
                    lines.append(
                        f"- 席{s.get('seat')} `{n:02d}` · {s.get('rule')} · "
                        f"频{s.get('freq_16')} 遗{s.get('omission')} 近8={s.get('recent_8')} mid={s.get('midhot_score')}"
                        if n is not None else f"- 席{s.get('seat')} — · {s.get('rule')}"
                    )
                lines.append("")
                for p in (m2.get("pairs") or [])[:3]:
                    lines.append(f"- 方法2选2 `{p.get('pair_str')}` · {p.get('kind')} · {p.get('desc')}")
                lines.append("")
            for p in (brief.get("pairs") or [])[:3]:
                lines.append(f"- 选2 `{p.get('pair_str')}` · {p.get('kind')} · {p.get('desc')}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 💎 四、跨梯队选2跃迁黄金搭档",
            "",
            "| 组合排名 | 选2搭档 | 组合策略分类 | 综合评分 | 核心特征说明 |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ])

        for idx, p in enumerate(trans_pairs[:5], 1):
            lines.append(f"| Top {idx} | **[{p['pair_str']}]** | `{p['tag']}` | `{p['score']}` | {p['desc']} |")

        lines.extend([
            "",
            "---",
            "",
            "## 📊 五、16期大盘频次分桶态势 (1~8+ 光谱)",
            "",
            f"- **当前中热号总数 (3-6次)**：`{med_cnt}` 码 (大盘黄金出号底仓，单期平均开出 13~16 码)",
            f"- **0次极冷绝响**：`{dist.get('0', 0)}` 码 | **1次低频号**：`{dist.get('1', 0)}` 码",
            f"- **2次温冷号**：`{dist.get('2', 0)}` 码 | **3次中温号**：`{dist.get('3', 0)}` 码",
            f"- **4次黄金号**：`{dist.get('4', 0)}` 码 | **5次活跃号**：`{dist.get('5', 0)}` 码",
            f"- **6次强热号**：`{dist.get('6', 0)}` 码 | **7次高热号**：`{dist.get('7', 0)}` 码",
            f"- **8+极热过载号**：`{dist.get('8+', 0)}` 码 (防过载透支)",
            "",
        ])

        ew = analysis_res.get("excel_window") or {}
        if ew.get("window_rows"):
            oh = ew.get("one_head") or {}
            lines.extend([
                "---",
                "",
                f"## 📑 六、Excel同款16窗开奖矩阵（{ew.get('window_label') or ''}）",
                "",
                f"> {ew.get('note') or '1头=10-19；一区=01-10'}",
                "",
                "| 期号 | 开奖20码 | 0头 | **1头** | 2头 | 3头 | 4头 | 5头 | 6头 | 7头 | 一区 |",
                "|------|----------|-----|---------|-----|-----|-----|-----|-----|-----|------|",
            ])
            for r in ew["window_rows"]:
                flag = " ❄️" if int(r.get("1头") or 0) == 0 else ""
                lines.append(
                    f"| {r['period']} | `{r['nums_str']}` | {r.get('0头', '')} | **{r.get('1头', '')}**{flag} | "
                    f"{r.get('2头', '')} | {r.get('3头', '')} | {r.get('4头', '')} | {r.get('5头', '')} | "
                    f"{r.get('6头', '')} | {r.get('7头', '')} | {r.get('一区', '')} |"
                )
            if oh:
                lines.extend([
                    "",
                    f"- **1头(10-19)** 窗内合计 `{oh.get('countifs_total')}`（期望约 {oh.get('expected_total')}）；"
                    f"空冷期数 `{oh.get('cold_periods_in_window')}`；"
                    f"当前连冷 `{oh.get('cold_streak_from_latest')}`；"
                    f"偏冷≤1 连续 `{oh.get('soft_cold_streak_le1')}`",
                    "",
                ])

        lines.extend([
            "---",
            "*K8-Quant 智能量化操盘决策终端 · 16期频次推演引擎自动生成*"
        ])

        return "\n".join(lines)


def run_single_period_analysis(target_idx: Optional[int] = None) -> Dict[str, Any]:
    draws = load_draws_from_file()
    if len(draws) < WINDOW_SIZE:
        raise RuntimeError(f"历史开奖数据不足 {WINDOW_SIZE} 期")

    engine = SixteenPeriodEngine(draws)
    idx = (len(draws) - 1) if target_idx is None else target_idx
    res = engine.analyze_at_index(idx)

    report_md = engine.generate_report(res)
    target_period = res["target_period"]

    report_dirs = [get_reports_dir(), os.path.join(get_outputs_dir(), "reports")]
    for dpath in report_dirs:
        os.makedirs(dpath, exist_ok=True)
        fname = f"sixteen_analysis_report_{target_period}.md"
        with open(os.path.join(dpath, fname), "w", encoding="utf-8") as f:
            f.write(report_md)

    cache_dir = os.path.join(get_cache_dir(), "sixteen_period")
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "latest_summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    try:
        from backend.modules.sixteen.excel_window_table import run_excel_window_from_draws
        ew = run_excel_window_from_draws(draws[: idx + 1], target_period=target_period, persist=True)
        if ew.get("status") == "ok":
            res["excel_window_export"] = ew.get("export_paths") or {}
    except Exception:
        pass

    return res
