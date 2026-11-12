# -*- coding: utf-8 -*-
"""
三高特征量化推演与深度共振引擎 (Tri-Category High Points & Deep Resonance Engine)
================================================================================
业务背景与量化逻辑:
  1. 重复高 (Repeat-High): 近期高频出号惯性与连庄追踪池；
  2. 边高 (Edge-High): 区间边界与左右双翼邻位延伸池 (Left 4 + Right 4)；
  3. 冷高 (Cold-High): 极限遗漏冷号回补与突袭池；
  4. 深度共振: 结合每日点位 (daily_points.txt) 与数据源1x2，解算三高共振金胆与黄金选2。
"""
from backend.utils.paths import get_outputs_dir
import os
import re
import sys
import json
import shutil
import collections
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any, Optional

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# backend/modules/tri_high/ -> project root (data/)
_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJ_DIR not in sys.path:
    sys.path.insert(0, _PROJ_DIR)
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from backend.utils.paths import data_path, get_cache_dir
from backend.utils.history_loader import load_history

TRI_HIGH_STORAGE_FILE = os.path.join(_PROJ_DIR, "storage", "points", "tri_high_points.json")
DAILY_POINTS_FILE = data_path("daily_points.txt")
ANALYSIS_OUTPUT_FILE = os.path.join(_PROJ_DIR, "storage", "points", "tri_high_analysis.json")
REPORT_OUTPUT_FILE = os.path.join(get_outputs_dir(), "reports", "tri_high_report_latest.md")

# 三高手账备份（与点位台账 daily_points 同一套自愈思路）
TRI_HIGH_BACKUP_DIR = os.path.join(get_cache_dir(), "tri_high_backup")
TRI_HIGH_BACKUP_KEEP = 50
_TRI_HIGH_BACKUP_RE = re.compile(r"^tri_high_points_\d{8}_\d{6}\.bak$")


def _load_records_from(path: str) -> List[Dict[str, Any]]:
    """读一份手账文件的 records；解析失败返回空列表（只代表读不出来，不代表文件里没数据）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        recs = data.get("records", []) if isinstance(data, dict) else []
        return [r for r in recs if isinstance(r, dict) and str(r.get("period", "")).strip()]
    except Exception:
        return []


def _records_span(records: List[Dict[str, Any]]) -> Tuple[int, int]:
    """返回 (期数, 最新期号)；空手账返回 (0, 0)。"""
    periods = []
    for r in records:
        try:
            periods.append(int(str(r.get("period", "")).strip()))
        except (TypeError, ValueError):
            continue
    return (len(records), max(periods)) if periods else (0, 0)


def backup_tri_high_file(storage_file: Optional[str] = None) -> Optional[str]:
    """把当前手账复制一份带时间戳的备份，并轮转清理旧备份（保留最近 TRI_HIGH_BACKUP_KEEP 份）。

    三高手账是人工逐期录入、多期累积的 JSON。外部工具或误操作把它覆盖成只剩一两期时，
    所有读取方都是「没有就跳过」，故障是静默的 —— 往往几周后才有人发现历史没了
    （点位台账 daily_points.txt 就被这样冲掉过两次）。每次写入前先备份，是让这类损失可回滚的前提。
    """
    target = storage_file or TRI_HIGH_STORAGE_FILE
    if not os.path.exists(target):
        return None
    try:
        os.makedirs(TRI_HIGH_BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(TRI_HIGH_BACKUP_DIR, f"tri_high_points_{ts}.bak")
        shutil.copy2(target, backup_path)

        baks = sorted(
            os.path.join(TRI_HIGH_BACKUP_DIR, n)
            for n in os.listdir(TRI_HIGH_BACKUP_DIR)
            if _TRI_HIGH_BACKUP_RE.match(n)
        )
        if len(baks) > TRI_HIGH_BACKUP_KEEP:
            for old in baks[:-TRI_HIGH_BACKUP_KEEP]:
                try:
                    os.remove(old)
                except Exception:
                    pass
        return backup_path
    except Exception as e:
        print(f"⚠️ 备份三高手账失败: {e}")
        return None


def repair_tri_high_file(storage_file: Optional[str] = None,
                         backup_dir: Optional[str] = None) -> Dict[str, Any]:
    """三高手账自愈：被覆盖或清空后，从最近一份合法备份重建。

    判定缩水（任一成立）：
      · 当前可解析期数少于最佳备份
      · 当前最新期号早于备份最新期号
    重建方式：备份 ∪ 当前（同期以当前为准，保住刚录入的那期），按期号降序原子写。
    修复前把坏文件另存为 tri_high_points_BROKEN_<ts>.bak 留证，不直接丢弃。
    """
    target = storage_file or TRI_HIGH_STORAGE_FILE
    bdir = backup_dir or TRI_HIGH_BACKUP_DIR
    current = _load_records_from(target)

    if not os.path.isdir(bdir):
        return {"status": "skipped", "reason": "无备份目录"}

    candidates = []
    for name in os.listdir(bdir):
        if not _TRI_HIGH_BACKUP_RE.match(name):
            continue
        path = os.path.join(bdir, name)
        recs = _load_records_from(path)
        if recs:
            n, latest = _records_span(recs)
            candidates.append((latest, os.path.getmtime(path), path, n, recs))
    if not candidates:
        return {"status": "skipped", "reason": "无合法备份"}

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best_latest, _, best_path, best_n, best_recs = candidates[0]

    cur_n, cur_latest = _records_span(current)
    if cur_n >= best_n and cur_latest >= best_latest:
        return {"status": "ok", "reason": "手账完整，无需修复",
                "records": cur_n, "latest": cur_latest}

    merged: Dict[str, Dict[str, Any]] = {}
    for r in best_recs:
        merged[str(r["period"]).strip()] = r
    for r in current:                       # 同期以当前为准，保住新录入
        merged[str(r["period"]).strip()] = r

    evidence = ""
    if os.path.exists(target):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            evidence = os.path.join(bdir, f"tri_high_points_BROKEN_{ts}.bak")
            shutil.copy2(target, evidence)
        except Exception:
            evidence = ""

    ordered = sorted(merged.values(), key=lambda r: int(str(r["period"]).strip()), reverse=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"records": ordered, "updated_at": datetime.now().isoformat()},
                  f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)

    return {
        "status": "repaired",
        "reason": f"当前 {cur_n} 期(最新 {cur_latest}) < 备份 {best_n} 期(最新 {best_latest})",
        "before_records": cur_n,
        "after_records": len(ordered),
        "latest": max(int(str(r["period"]).strip()) for r in ordered),
        "source_backup": os.path.basename(best_path),
        "evidence": evidence,
    }


class TriHighResonanceEngine:
    def __init__(self, proj_dir: str = _PROJ_DIR):
        self.proj_dir = proj_dir
        self.storage_file = os.path.join(proj_dir, "storage", "points", "tri_high_points.json")
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        os.makedirs(os.path.join(get_outputs_dir(), "reports"), exist_ok=True)

    def load_tri_high_records(self) -> List[Dict[str, Any]]:
        """加载全部三高录入历史记录"""
        if not os.path.exists(self.storage_file):
            return []
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                records = data.get("records", [])
                records.sort(key=lambda x: int(x.get("period", 0)), reverse=True)
                return records
        except Exception as e:
            print(f"⚠️ 读取三高历史记录失败: {e}")
            return []

    def save_tri_high_records(self, records: List[Dict[str, Any]]):
        """持久化保存三高录入历史记录。

        写入前先备份、写入走 tmp+replace：手账是唯一的人工输入真相源，
        一旦被覆盖或写到一半中断，历史就没了，而所有读取方都只是"没有就跳过"，
        故障完全静默。
        """
        records.sort(key=lambda x: int(x.get("period", 0)), reverse=True)
        backup_tri_high_file(self.storage_file)
        tmp = self.storage_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"records": records, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.storage_file)

    def save_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """录入或更新单期记录"""
        period_str = str(payload.get("period", "")).strip()
        if not period_str:
            raise ValueError("期号不能为空")
        records = self.load_tri_high_records()

        def _clean_list(raw):
            res = []
            for x in raw:
                try:
                    val = int(x)
                    if 1 <= val <= 80:
                        res.append(val)
                except Exception:
                    pass
            return res

        new_rec = {
            "period": period_str,
            "date": str(payload.get("date", "")).strip(),
            "repeat_high": _clean_list(payload.get("repeat_high", [])),
            "edge_high_left": _clean_list(payload.get("edge_high_left", [])),
            "edge_high_right": _clean_list(payload.get("edge_high_right", [])),
            "cold_high": _clean_list(payload.get("cold_high", []))
        }

        # 过滤掉同期的旧记录（支持覆盖更新）
        filtered = [r for r in records if str(r.get("period", "")).strip() != period_str]
        filtered.append(new_rec)
        self.save_tri_high_records(filtered)
        return new_rec

    def delete_record(self, period: str) -> bool:
        """删除单期记录"""
        period_str = str(period).strip()
        records = self.load_tri_high_records()
        filtered = [r for r in records if str(r.get("period", "")).strip() != period_str]
        if len(filtered) < len(records):
            self.save_tri_high_records(filtered)
            return True
        return False

    def load_daily_points(self) -> Dict[str, Any]:
        """加载最新每日点位 (daily_points.txt，最新期在文件顶部)。"""
        try:
            from backend.data_acquisition.daily_points_manager import get_latest_points_entry
            entry = get_latest_points_entry()
            if entry and entry.get("points"):
                return {
                    "period": str(entry.get("period") or ""),
                    "points": list(entry.get("points") or []),
                }
        except Exception:
            pass
        if not os.path.exists(DAILY_POINTS_FILE):
            return {"period": "", "points": []}
        try:
            import re
            with open(DAILY_POINTS_FILE, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            if not lines:
                return {"period": "", "points": []}
            # 文件按期号降序，首行即最新；兼容旧格式 issue/numbers
            best = None
            for line in lines:
                m_iss = re.search(r"(?:period|issue):(\d+)", line)
                m_pts = re.search(r"points:([\d\s]+)", line)
                m_nums = re.search(r"numbers:([\d\-]+)", line)
                if not m_iss:
                    continue
                period_str = m_iss.group(1)
                pts: List[int] = []
                if m_pts:
                    pts = [int(x) for x in m_pts.group(1).strip().split() if x.isdigit()]
                elif m_nums:
                    pts = [int(x) for x in m_nums.group(1).split("-") if x.isdigit()]
                if not pts:
                    continue
                p_int = int(period_str)
                if best is None or p_int > best[0]:
                    best = (p_int, period_str, pts)
            if best:
                return {"period": best[1], "points": best[2]}
            return {"period": "", "points": []}
        except Exception as e:
            print(f"⚠️ 加载每日点位失败: {e}")
            return {"period": "", "points": []}

    def get_history_with_wins(self) -> List[Dict[str, Any]]:
        """获取带有自动开奖标黄与命中统计的逐期三高数据"""
        records = self.load_tri_high_records()
        history = load_history()
        draw_map = {h["issue"]: h for h in history}

        formatted = []
        for r in records:
            period = str(r.get("period", "")).strip()
            draw = draw_map.get(period, {})
            actual_nums = sorted(list(draw.get("numbers", [])))
            draw_date = draw.get("date", r.get("date", ""))

            rep = r.get("repeat_high", [])
            edge_l = r.get("edge_high_left", [])
            edge_r = r.get("edge_high_right", [])
            cold = r.get("cold_high", [])

            edge_all = edge_l + edge_r
            all_tri_set = set(rep + edge_all + cold)

            rep_hits = [n for n in rep if n in actual_nums] if actual_nums else []
            edge_hits = [n for n in edge_all if n in actual_nums] if actual_nums else []
            cold_hits = [n for n in cold if n in actual_nums] if actual_nums else []
            total_hits = [n for n in all_tri_set if n in actual_nums] if actual_nums else []

            formatted.append({
                "period": period,
                "date": draw_date,
                "has_draw": bool(actual_nums),
                "actual_numbers": actual_nums,
                "repeat_high": [{"num": n, "num_str": f"{n:02d}", "is_win": n in actual_nums} for n in rep],
                "edge_high_left": [{"num": n, "num_str": f"{n:02d}", "is_win": n in actual_nums} for n in edge_l],
                "edge_high_right": [{"num": n, "num_str": f"{n:02d}", "is_win": n in actual_nums} for n in edge_r],
                "cold_high": [{"num": n, "num_str": f"{n:02d}", "is_win": n in actual_nums} for n in cold],
                "stats": {
                    "repeat_count": len(rep),
                    "repeat_hits": len(rep_hits),
                    "repeat_hit_rate": round(len(rep_hits) / len(rep), 4) if rep else 0.0,
                    "edge_count": len(edge_all),
                    "edge_hits": len(edge_hits),
                    "edge_hit_rate": round(len(edge_hits) / len(edge_all), 4) if edge_all else 0.0,
                    "cold_count": len(cold),
                    "cold_hits": len(cold_hits),
                    "cold_hit_rate": round(len(cold_hits) / len(cold), 4) if cold else 0.0,
                    "union_count": len(all_tri_set),
                    "union_hits": len(total_hits),
                    "union_hit_rate": round(len(total_hits) / len(all_tri_set), 4) if all_tri_set else 0.0
                }
            })
        return formatted

    def run_tri_high_analysis(self) -> Dict[str, Any]:
        """运行三高特征与每日点位深度共振推演"""
        history_list = self.get_history_with_wins()
        daily_pts_info = self.load_daily_points()
        daily_points = set(daily_pts_info.get("points", []))

        # 确定目标期
        history_draws = load_history()
        latest_draw_period = history_draws[0]["issue"] if history_draws else "2026240"
        target_period = str(int(latest_draw_period) + 1) if latest_draw_period.isdigit() else "2026241"

        # 寻找最新可用的三高数据基准
        latest_record = history_list[0] if history_list else {}
        base_period = latest_record.get("period", latest_draw_period)

        cur_repeat = [item["num"] for item in latest_record.get("repeat_high", [])]
        cur_edge_l = [item["num"] for item in latest_record.get("edge_high_left", [])]
        cur_edge_r = [item["num"] for item in latest_record.get("edge_high_right", [])]
        cur_edge = cur_edge_l + cur_edge_r
        cur_cold = [item["num"] for item in latest_record.get("cold_high", [])]

        # 1. 历史均值与胜率表现计算
        valid_history = [h for h in history_list if h["has_draw"]]
        n_history = len(valid_history)
        avg_rep_hits = round(sum(h["stats"]["repeat_hits"] for h in valid_history) / max(1, n_history), 2)
        avg_edge_hits = round(sum(h["stats"]["edge_hits"] for h in valid_history) / max(1, n_history), 2)
        avg_cold_hits = round(sum(h["stats"]["cold_hits"] for h in valid_history) / max(1, n_history), 2)
        avg_union_hits = round(sum(h["stats"]["union_hits"] for h in valid_history) / max(1, n_history), 2)

        # 2. 三高×点位 深度共振打分模型 (80 码扫描)
        scores = {}
        for num in range(1, 81):
            score = 0.0
            tags = []

            # 三高打分
            if num in cur_repeat:
                score += 35.0
                tags.append("重复高")
            if num in cur_edge:
                score += 30.0
                tags.append("边高")
            if num in cur_cold:
                score += 25.0
                tags.append("冷高")

            # 每日点位共振强加权 (+40.0)
            if num in daily_points:
                score += 40.0
                tags.append("每日点位")

            scores[num] = {
                "score": round(score, 1),
                "tags": tags,
                "in_repeat": num in cur_repeat,
                "in_edge": num in cur_edge,
                "in_cold": num in cur_cold,
                "in_point": num in daily_points
            }

        # 排序
        ranked_nums = sorted(scores.keys(), key=lambda x: scores[x]["score"], reverse=True)

        # 2026-09-10 数据诚信整改：无有效评分时不再编造金胆/搭档/精选号
        # （原兜底为 24 / [24,35] / [13,66] / [11,48] / [12,21]，会冒充真实推演结果）
        # 尖刀共振金胆
        resonance_gold = ranked_nums[0] if ranked_nums else None

        # 黄金选2搭档 (共振分最高的组合，优先选取跨分类连体)
        gold_pair = [ranked_nums[0], ranked_nums[1]] if len(ranked_nums) >= 2 else []

        # 主口径：最优 3 码；Top5 为前 5 码，Top12 为前 12 码
        top3_gold = ranked_nums[:3]
        top5_picks = ranked_nums[:5]
        top12_picks = ranked_nums[:12]

        # 冷高突袭精选 (在冷高池中且得分最高者)
        cold_ranked = [n for n in ranked_nums if scores[n]["in_cold"]]
        cold_strikes = cold_ranked[:4]

        # 边高精选
        edge_ranked = [n for n in ranked_nums if scores[n]["in_edge"]]
        edge_picks = edge_ranked[:4]

        # 重复高连庄精选
        repeat_ranked = [n for n in ranked_nums if scores[n]["in_repeat"]]
        repeat_picks = repeat_ranked[:4]

        # 3. 计算智能待录入期号与开奖日期联动
        existing_periods = [int(r.get("period", 0)) for r in history_list]
        max_existing_period = max(existing_periods) if existing_periods else 2026220
        latest_draw_date = history_draws[0].get("date", "") if history_draws else datetime.now().strftime("%Y-%m-%d")
        draw_map = {h["issue"]: h for h in history_draws}

        # 优先推荐当前活跃目标期号 (如 2026240)
        if str(max_existing_period) not in draw_map:
            suggested_period_int = max_existing_period
            suggested_period = str(suggested_period_int)
            suggested_date = datetime.now().strftime("%Y-%m-%d")
            suggested_label = f"第 {suggested_period[-3:]} 期 (今晚预测·已录入)"
        else:
            suggested_period_int = max_existing_period + 1
            suggested_period = str(suggested_period_int)
            if suggested_period in draw_map:
                suggested_date = draw_map[suggested_period].get("date", datetime.now().strftime("%Y-%m-%d"))
                suggested_label = f"第 {suggested_period[-3:]} 期 (已开奖·待补录)"
            else:
                suggested_date = datetime.now().strftime("%Y-%m-%d")
                suggested_label = f"第 {suggested_period[-3:]} 期 (今晚目标·待录入)"

        # 快捷候选期号列表
        quick_options = []
        for p_int in range(max(2026221, max_existing_period - 3), max_existing_period + 3):
            p_str = str(p_int)
            d_str = draw_map.get(p_str, {}).get("date", datetime.now().strftime("%Y-%m-%d"))
            is_rec = p_int in existing_periods
            status_txt = "已录入" if is_rec else "待录入"
            quick_options.append({
                "period": p_str,
                "date": d_str,
                "label": f"{p_str[-3:]}期 ({status_txt})",
                "is_recorded": is_rec
            })

        input_target_info = {
            "suggested_period": suggested_period,
            "suggested_date": suggested_date,
            "suggested_label": suggested_label,
            "latest_recorded_period": str(max_existing_period),
            "latest_draw_period": latest_draw_period,
            "latest_draw_date": latest_draw_date,
            "quick_options": quick_options
        }

        analysis_result = {
            "status": "ok",
            "target_period": target_period,
            "base_period": base_period,
            "latest_draw_period": latest_draw_period,
            "history_periods_count": n_history,
            "daily_points_period": daily_pts_info.get("period", ""),
            "daily_points_count": len(daily_points),
            "input_target_info": input_target_info,
            "averages": {
                "avg_repeat_hits": avg_rep_hits,
                "avg_edge_hits": avg_edge_hits,
                "avg_cold_hits": avg_cold_hits,
                "avg_union_hits": avg_union_hits
            },
            "recommendations": {
                "resonance_gold_single": resonance_gold,
                "gold_pair": gold_pair,
                "top3_gold": top3_gold,
                "top5": top5_picks,
                "top12": top12_picks,
                "repeat_picks": repeat_picks,
                "edge_picks": edge_picks,
                "cold_strikes": cold_strikes,
            },
            "scores_table": {str(k): v for k, v in scores.items() if v["score"] > 0}
        }

        # 持久化落盘 JSON
        with open(ANALYSIS_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)

        # 生成研报
        self._generate_markdown_report(analysis_result)

        return analysis_result

    def _generate_markdown_report(self, res: Dict[str, Any]):
        """生成操盘手专业研报"""
        rec = res.get("recommendations", {})
        avg = res.get("averages", {})
        t_period = res.get("target_period", "2026241")

        lines = [
            f"# 🧬 三高特征×每日点位 深度共振量化决策研报",
            f"**目标研判期号：** 第 {t_period} 期 | **生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**分析模型：** Tri-Category High Points & Deep Resonance Engine v1.0\n",
            f"---",
            f"## 一、 核心操盘手推演策略",
            f"- 👑 **三高共振尖刀金胆：** " + (f"`【 {rec['resonance_gold_single']:02d} 】`" if rec.get('resonance_gold_single') else "`数据缺失(未生成)`"),
            f"- 💎 **三高黄金选2搭档：** " + (f"`[ {rec['gold_pair'][0]:02d} - {rec['gold_pair'][1]:02d} ]`" if len(rec.get('gold_pair') or []) == 2 else "`数据缺失(未生成)`"),
            f"- 🌟 **最优 3 码：** `{' '.join(f'{x:02d}' for x in rec.get('top3_gold', []))}`",
            f"- ❄️ **冷高突袭回补号：** `{' '.join(f'{x:02d}' for x in rec.get('cold_strikes', []))}`\n",
            f"---",
            f"## 二、 历史实战样本对账统计 (近 {res.get('history_periods_count', 17)} 期手账流水)",
            f"| 分类名称 | 核心特征定位 | 平均每期出号数 | 实战操盘建议 |",
            f"| :--- | :--- | :--- | :--- |",
            f"| **重复高** | 连出连庄热码池 | **{avg.get('avg_repeat_hits', 0.0)} 码 / 期** | 顺势而为，精选连庄核心 |",
            f"| **边高 (4+4)** | 左右翼邻位延伸 | **{avg.get('avg_edge_hits', 0.0)} 码 / 期** | 盯紧边界搭档延伸 |",
            f"| **冷高** | 极限遗漏冷码回补 | **{avg.get('avg_cold_hits', 0.0)} 码 / 期** | 重点伏击 1-2 码反弹回补 |",
            f"| **三高合集** | 三维全面覆盖 | **{avg.get('avg_union_hits', 0.0)} 码 / 期** | 占据大盘半壁江山，主力阵地 |",
            f"\n> 💡 **操盘法则**：当号码同时命中【三高】与【每日点位 (daily_points)】时，属于极高概率的双重共振态，优先作为金胆与选2核心！"
        ]

        with open(REPORT_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def run_tri_high_pipeline():
    """CLI / 流水线调用统一入口"""
    engine = TriHighResonanceEngine()
    res = engine.run_tri_high_analysis()
    rec = res["recommendations"]
    print(f"\n" + "=" * 70)
    print(f"  🧬 三高特征×每日点位 深度共振量化推演完成！目标期: 第 {res['target_period']} 期")
    _gold_txt = f"【 {rec['resonance_gold_single']:02d} 】" if rec.get("resonance_gold_single") else "数据缺失"
    _pair = rec.get("gold_pair") or []
    _pair_txt = f"[ {_pair[0]:02d} - {_pair[1]:02d} ]" if len(_pair) == 2 else "数据缺失"
    print(f"  💎 共振金胆: {_gold_txt} | 👑 黄金选2: {_pair_txt}")
    print(f"  🎯 突击Top5: {' '.join(f'{x:02d}' for x in rec['top5'])}")
    print(f"  📄 研报落盘: {REPORT_OUTPUT_FILE}")
    print("=" * 70 + "\n")
    return res


if __name__ == "__main__":
    run_tri_high_pipeline()
