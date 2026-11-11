# -*- coding: utf-8 -*-
"""
master_reviewer.py — 快乐8 全模块多维命中复盘对账引擎 (Master Multi-Module Review Engine)
========================================================================================
覆盖系统内 15 大核心预测模块与维度的全历史与滚动样本外 Walk-Forward 对账：
  1. Trinity Top 5 (三维一体核心爆发)
  2. Trinity Top 12 (三维一体大底)
  3. Hidden Energy 5 (首席特供能量场精选)
  4. Pure Pool 5 (纯净池遗漏定胆)
  5. LSTM Top 10 (双层时序深度学习金银铜胆)
  6. 顺口溜 90 条精英规则 (组合带出推荐)
  7. 空间重点点位分析 Top 5 (4维透明打分)
  8. 空间高压反弹与影子追踪 (弹簧压制 Top 1/Top 5)
  9. 历史条件跟随 Top 5 (重复号+多窗条件跟随)
 10. 黄金定胆选2搭档 (双重金胆法选2)
 11. Gemini 物理算子选2 (5大物理算子量化选2)
 12. 16期中热号动态出窗进窗推演 (大盘光谱精选)
 13. 数据源1×2 深层关联推演 (爆发最优3码、跨规则共识、连体搭档)
 14. 终审多路共识定胆池与 Stable Top 10 (终审大团长)
"""
from backend.utils.paths import get_cache_dir, get_outputs_dir
import os
import sys
import json
import re
import math
import glob
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# backend/modules/master_review/ -> project root (data/)
_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.paths import data_path, get_project_root
from utils.history_loader import load_history

STORAGE_DIR = os.path.join(_PROJ_DIR, "storage", "reviews")
os.makedirs(STORAGE_DIR, exist_ok=True)
MASTER_LEDGER_FILE = os.path.join(STORAGE_DIR, "master_review_ledger.json")


class MasterReviewEngine:
    def __init__(self, proj_dir: str = None):
        self.proj_dir = proj_dir or _PROJ_DIR
        self.history = load_history()
        self.hist_map = {}
        for h in self.history:
            issue = int(h['issue'])
            nums = sorted(list(h['numbers']))
            self.hist_map[issue] = set(nums)

    def _get_draw_numbers(self, period: int) -> Optional[set]:
        return self.hist_map.get(period)

    def run_master_review(self, n_review: int = 100) -> Dict[str, Any]:
        """执行近 n_review 期全模块详细命中复盘对账

        2026-09-10 C2 整改: 默认窗口 30→100 期。
        30 期窗口分辨不出 1.2x 以下的差异 (C2: 30期 Top5 的 95%CI 约 ±0.9x),
        100 期容量化到 ±0.3x 量级。样本不足的模块在打榜时收缩 Lift 并挂水印。
        """
        if not self.history or len(self.history) < n_review + 2:
            return {"status": "error", "message": "历史开奖数据不足，无法复盘"}

        from backend.api.data_service import QuantDataService
        ds = QuantDataService(self.proj_dir)

        # 1. 汇聚各个子系统的对账数据
        jingle_rev = ds.get_jingle_review(n=n_review)
        points_rev = ds.get_spatial_points_review(n=n_review)
        supp_rev = ds.get_suppression_review(n=n_review)
        follow_rev = ds.get_follow_review(n=n_review)
        pick2_rev = ds.get_gold_pick2_review(n=n_review)
        gemini_rev = ds.get_gemini_review(n=n_review)
        ds_rev = ds.get_datasource_review(n=n_review)
        sixteen_rev = ds.get_sixteen_review(n=n_review)

        # 2. 从 self_learning_state / learner_state 读取 Trinity / HE5 / PurePool 历史
        learner_records = []
        try:
            mem_file = os.path.join(get_cache_dir(), 'self_learning_state.json')
            if os.path.exists(mem_file):
                with open(mem_file, 'r', encoding='utf-8') as f:
                    learner_records = json.load(f).get('history', [])
        except Exception:
            pass

        target_periods = [int(h['issue']) for h in self.history[:n_review]]
        target_periods.sort()

        # 统计收集器
        stats_collector = {
            "trinity_top5": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "Trinity 三维融合 Top 5"},
            "trinity_top12": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "Trinity 三维融合 Top 12"},
            "hidden_energy5": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "Hidden Energy 5 首席特供"},
            "pure_pool": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "纯净池定胆 (冷号回补)"},
            "formula_jingle": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "顺口溜 90 条精英口诀"},
            "spatial_points": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "空间重点点位分析 Top 5"},
            "point_suppression": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "空间高压反弹与影子追踪"},
            "follow_track": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "历史条件跟随 Top 5"},
            "gold_pick2": {"p2_both": 0, "p2_one": 0, "p2_zero": 0, "total": 0, "name": "黄金定胆选2搭档"},
            "gemini_pick2": {"p2_both": 0, "p2_one": 0, "p2_zero": 0, "total": 0, "name": "Gemini 物理算子选2"},
            "sixteen_hot": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "16期中热号出窗进窗推演"},
            "datasource_1x2_hot": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "数据源1×2 爆发最优3码"},
            "aggregation_stable10": {"hits": [], "total_picks": 0, "total_hits": 0, "name": "终审共识 Stable Top 10"},
        }

        # 2026-09-10 数据诚信整改：
        # - no_data_modules: 复盘文件缺关键指标的模块，如实列出，不再用硬编码默认值冒充实测
        # - per_period_estimated: 只有汇总均值、无逐期明细的模块（hits 数组为均值的平铺，仅供汇总口径参考）
        no_data_modules: List[str] = []
        per_period_estimated = set()

        # 填充 Trinity 历史
        rec_map = {str(r.get('target_issue')): r for r in learner_records}
        detailed_ledger = []

        for period in target_periods:
            actual = self._get_draw_numbers(period)
            if not actual:
                continue

            row = {
                "period": period,
                "actual_count": len(actual),
                "modules": {}
            }

            rec = rec_map.get(str(period))
            if rec:
                t5 = sorted(rec.get('top5', []))
                t12 = sorted(rec.get('top12', []))
                he5 = sorted(rec.get('b3_final5', []))
                pure = sorted(rec.get('pure_pool_top', []))

                if t5:
                    hit_t5 = sorted(list(set(t5) & actual))
                    row["modules"]["trinity_top5"] = {"picks": t5, "hit_balls": hit_t5, "hits": len(hit_t5), "total": len(t5)}
                    stats_collector["trinity_top5"]["hits"].append(len(hit_t5))
                    stats_collector["trinity_top5"]["total_picks"] += len(t5)
                    stats_collector["trinity_top5"]["total_hits"] += len(hit_t5)

                if t12:
                    hit_t12 = sorted(list(set(t12) & actual))
                    row["modules"]["trinity_top12"] = {"picks": t12, "hit_balls": hit_t12, "hits": len(hit_t12), "total": len(t12)}
                    stats_collector["trinity_top12"]["hits"].append(len(hit_t12))
                    stats_collector["trinity_top12"]["total_picks"] += len(t12)
                    stats_collector["trinity_top12"]["total_hits"] += len(hit_t12)

                if he5:
                    hit_he5 = sorted(list(set(he5) & actual))
                    row["modules"]["hidden_energy5"] = {"picks": he5, "hit_balls": hit_he5, "hits": len(hit_he5), "total": len(he5)}
                    stats_collector["hidden_energy5"]["hits"].append(len(hit_he5))
                    stats_collector["hidden_energy5"]["total_picks"] += len(he5)
                    stats_collector["hidden_energy5"]["total_hits"] += len(hit_he5)

                if pure:
                    hit_pure = sorted(list(set(pure) & actual))
                    row["modules"]["pure_pool"] = {"picks": pure, "hit_balls": hit_pure, "hits": len(hit_pure), "total": len(pure)}
                    stats_collector["pure_pool"]["hits"].append(len(hit_pure))
                    stats_collector["pure_pool"]["total_picks"] += len(pure)
                    stats_collector["pure_pool"]["total_hits"] += len(hit_pure)

            detailed_ledger.append(row)

        # 填充子系统的统计数据 (以各子模块真实数据结构为准)
        # 顺口溜
        if jingle_rev and "metrics" in jingle_rev:
            jm = jingle_rev["metrics"]
            if jm.get("mean_pair_hits") is not None:
                tot_p = jm.get("total_eval_periods", len(target_periods))
                np_mean = float(jm["mean_pair_hits"])
                stats_collector["formula_jingle"]["hits"] = [int(np_mean)] * tot_p
                stats_collector["formula_jingle"]["total_picks"] = tot_p * 5
                stats_collector["formula_jingle"]["total_hits"] = int(np_mean * tot_p)
                per_period_estimated.add("formula_jingle")
            else:
                no_data_modules.append("顺口溜(复盘文件缺 mean_pair_hits 指标)")

        # 空间高压反弹与影子追踪 (五星精锐)
        if supp_rev and ("top1_single_rate" in supp_rev or "summary" in supp_rev):
            sm = supp_rev.get("summary", supp_rev)
            if sm.get("top1_single_rate") is not None:
                t1_acc = float(sm["top1_single_rate"])
                tot_p = int(sm.get("n_periods", len(target_periods)))
                stats_collector["point_suppression"]["hits"] = [1 if i < int(tot_p * t1_acc) else 0 for i in range(tot_p)]
                stats_collector["point_suppression"]["total_picks"] = tot_p
                stats_collector["point_suppression"]["total_hits"] = int(tot_p * t1_acc)
                per_period_estimated.add("point_suppression")
            else:
                no_data_modules.append("空间高压反弹(复盘文件缺 top1_single_rate 指标)")

        # 黄金定胆选2搭档 (五星精锐 - 选2之王)
        if pick2_rev and ("stats" in pick2_rev or "metrics" in pick2_rev):
            p2m = pick2_rev.get("stats", pick2_rev.get("metrics", {}))
            both_raw = p2m.get("both_hit_count", p2m.get("top1_both_count"))
            one_raw = p2m.get("single_hit_count", p2m.get("top1_one_count"))
            if both_raw is None or one_raw is None:
                no_data_modules.append("黄金定胆选2(复盘文件缺双中/单中计数)")
            else:
                tot = int(p2m.get("total_periods", p2m.get("n_periods", len(target_periods))))
                both = int(both_raw)
                one = int(one_raw)
                stats_collector["gold_pick2"]["total"] = tot
                stats_collector["gold_pick2"]["p2_both"] = both
                stats_collector["gold_pick2"]["p2_one"] = one
                stats_collector["gold_pick2"]["p2_zero"] = max(0, tot - both - one)

        # KillSeeker 已拆除，不再记账

        # 16期中热号出窗进窗推演 (五星精锐)
        # ─────────────────────────────────────────────────────────────────
        # 2026-10-21 P0 缺陷修复：原实现有两重错误
        #   (1) 键名错配：`sxm.get("top3_avg_hits", sxm.get("top5_avg_hits", ...))`
        #       —— 复盘产物 stats 里**根本没有 top3_avg_hits**（真名 ops_tip3_avg_hits），
        #       于是永远落到「每 5 码均中」top5_avg_hits；
        #   (2) 分子分母口径错配：拿每期 5 码的均中数 ÷ 每期 3 码的分母 (tot_p*3)。
        #   叠加 hits=[int(m)]*tot_p 的平铺伪造，使 sixteen_hot 的 Lift 从真实 ~0.90~1.24
        #   被虚报成 1.56x，并成为全系统「唯一样本外显著正信号」与票权 0.28 的唯一依据。
        # 现改为与 aggregation_stable10 同一套做法：逐期读真实 ops_tip3 池与真实开奖对账。
        if sixteen_rev and ("rows" in sixteen_rev or "stats" in sixteen_rev):
            sx_rows = sixteen_rev.get("rows") or []
            sx_counted = 0
            for r in sx_rows:
                tip3 = [int(x) for x in (r.get("ops_tip3") or []) if 1 <= int(x) <= 80]
                if not tip3:
                    continue
                p_raw = r.get("target_period") or r.get("period")
                try:
                    p = int(p_raw)
                except (TypeError, ValueError):
                    continue
                actual = self._get_draw_numbers(p)
                if not actual:
                    continue
                hit = len(set(tip3) & actual)
                stats_collector["sixteen_hot"]["hits"].append(hit)
                stats_collector["sixteen_hot"]["total_picks"] += len(tip3)
                stats_collector["sixteen_hot"]["total_hits"] += hit
                sx_counted += 1
            if sx_counted == 0:
                # 无逐期明细时按 stats 的真实口径兜底：取与该指标同码数的均值，绝不再跨口径猜键名
                sxm = sixteen_rev.get("stats", sixteen_rev.get("summary", {}))
                _SIXTEEN_SIZE = [("ops_tip3_avg_hits", 3), ("top3_avg_hits", 3),
                                 ("ops_top5_avg_hits", 5), ("top5_avg_hits", 5),
                                 ("mean_top5_hits", 5), ("top10_avg_hits", 10)]
                _m_key = next((k for k, _sz in _SIXTEEN_SIZE if sxm.get(k) is not None), None)
                if _m_key is not None:
                    _size = dict(_SIXTEEN_SIZE)[_m_key]
                    _m_hits = float(sxm[_m_key])
                    _tot_p = int(sxm.get("n_periods", len(target_periods)))
                    stats_collector["sixteen_hot"]["hits"] = [int(_m_hits)] * _tot_p
                    stats_collector["sixteen_hot"]["total_picks"] = _tot_p * _size
                    stats_collector["sixteen_hot"]["total_hits"] = int(_m_hits * _tot_p)
                    per_period_estimated.add("sixteen_hot")
                    print(f"  ⚠️ sixteen_hot 走 stats 兜底口径: {_m_key} (每期 {_size} 码), 无逐期明细可对账")
                else:
                    no_data_modules.append("16期中热(复盘缺 ops_tip3/top3/top5 均中指标与逐期明细)")
            elif sx_counted < len(sx_rows):
                per_period_estimated.add("sixteen_hot")  # 部分期缺开奖档，样本期数以 hits 长度为准

        # 数据源1×2 爆发最优3码
        if ds_rev and "data" in ds_rev:
            ds_d = ds_rev["data"]
            hot_m_raw = ds_d.get("hot_top3_mean_hits", ds_d.get("hot_top5_mean_hits"))
            if hot_m_raw is not None:
                hot_m = float(hot_m_raw)
                tot_p = ds_d.get("evaluated_periods", ds_d.get("total_evaluated", len(target_periods)))
                stats_collector["datasource_1x2_hot"]["hits"] = [int(hot_m)] * tot_p
                stats_collector["datasource_1x2_hot"]["total_picks"] = tot_p * 3
                stats_collector["datasource_1x2_hot"]["total_hits"] = int(hot_m * tot_p)
                per_period_estimated.add("datasource_1x2_hot")
            else:
                no_data_modules.append("数据源1×2爆发最优3码(复盘文件缺 hot_top3_mean_hits 指标)")

        # 终审共识 Stable Top 10
        # 2026-09-10 数据诚信整改：废除 hits=[3]*n 编造口径，
        # 改为逐期读取 outputs/aggregation/aggregation_{期号}.json 的 stable_top10 与真实开奖对账。
        # 注意：该 JSON 是开奖前生成的前瞻预测，期号与 target_period 一致。
        agg_dir = os.path.join(get_outputs_dir(), "aggregation")
        agg_files_found = 0
        for period in target_periods:
            actual = self._get_draw_numbers(period)
            if not actual:
                continue
            agg_file = os.path.join(agg_dir, f"aggregation_{period}.json")
            if not os.path.exists(agg_file):
                continue
            try:
                with open(agg_file, 'r', encoding='utf-8') as f:
                    agg = json.load(f)
                st10 = agg.get("stable_top10") or []
                if not st10:
                    continue
                hit10 = len(set(st10) & actual)
                stats_collector["aggregation_stable10"]["hits"].append(hit10)
                stats_collector["aggregation_stable10"]["total_picks"] += len(st10)
                stats_collector["aggregation_stable10"]["total_hits"] += hit10
                agg_files_found += 1
            except Exception:
                continue
        if agg_files_found == 0:
            no_data_modules.append("终审共识Stable Top10(无 aggregation_{期号}.json 逐期产出可对账)")
        elif agg_files_found < len(target_periods):
            per_period_estimated.add("aggregation_stable10")  # 部分期缺档，样本期数以 hits 长度为准

        # D3 整改 (2026-09-10): 退役黑名单不再硬编码，由 module_gate 注册表 live 读取
        try:
            from core.module_gate import ModuleGate
            DISCARDED_SUBSYSTEMS = set(ModuleGate(self.proj_dir).retired_ids())
        except Exception:
            DISCARDED_SUBSYSTEMS = {"pure_pool", "follow_track", "spatial_points",
                                    "gemini_pick2", "lstm_deep", "lstm", "lstm_top10",
                                    "datasource_1x2_hot"}

        # 3. 汇总排行榜
        leaderboard = []
        baseline_rate = 0.25
        def _shrink(lift_v: float, n_p: int, n0: float = 30.0) -> float:
            """C2 赢家诅咒收缩: 样本越小，Lift 被拉回 1.0 越多"""
            if n_p <= 0:
                return 1.0
            return (n_p * lift_v + n0) / (n_p + n0)

        def _stats(phat: float, n_trials: int, p0: float):
            """Wilson CI 下界 + 单侧 p 值（口径与 core.wf_hit_engine 一致）"""
            if n_trials <= 0:
                return 0.0, 1.0
            z = 1.96
            z2 = z * z
            denom = 1.0 + z2 / n_trials
            center = phat + z2 / (2 * n_trials)
            margin = z * math.sqrt(phat * (1 - phat) / n_trials + z2 / (4 * n_trials * n_trials))
            lo = max(0.0, (center - margin) / denom)
            if phat <= p0:
                return lo, 1.0
            sd = math.sqrt(p0 * (1 - p0) / n_trials)
            pv = 0.5 * math.erfc((phat - p0) / sd / math.sqrt(2.0)) if sd > 0 else 1.0
            return lo, pv

        for key, sc in stats_collector.items():
            if key in DISCARDED_SUBSYSTEMS:
                continue
            if "total_picks" in sc and sc["total_picks"] > 0:
                mean_hits = sc["total_hits"] / len(sc["hits"]) if sc["hits"] else 0.0
                rate = sc["total_hits"] / sc["total_picks"]
                lift = rate / baseline_rate
                n_periods = len(sc["hits"])
                picks_per_period = sc["total_picks"] / n_periods if sc["hits"] else 0.0

                # C2: 统计量（CI 下界 / p 值 / 收缩 Lift / 样本不足水印）
                ci_lo, p_val = _stats(rate, sc["total_picks"], baseline_rate)
                lift_shrunk = _shrink(lift, n_periods)
                insufficient = n_periods < 100

                recent_5_hits = sum(sc["hits"][-5:]) if len(sc["hits"]) >= 5 else sum(sc["hits"])
                recent_5_picks = picks_per_period * min(5, len(sc["hits"]))
                recent_rate = (recent_5_hits / recent_5_picks) if recent_5_picks > 0 else rate
                if key in per_period_estimated:
                    # 逐期明细为均值平铺或部分缺档，"动量趋势"无意义，如实标注
                    momentum = "➖ 汇总口径(无逐期明细)"
                else:
                    momentum = "🔥 处于爆发上升期" if recent_rate >= rate * 1.05 else ("❄️ 处于回撤防守期" if recent_rate < rate * 0.95 else "⚡ 处于稳健平稳期")

                # C2: 评级用收缩后 Lift；样本不足或统计不显著者封顶 🟡，不许戴 🟢 超强信标
                if lift_shrunk < 1.0:
                    status_tag = "🔴 熔断防御(收缩后落后于基线)"
                elif insufficient:
                    status_tag = "🟡 样本不足100期·仅供观察"
                elif p_val > 0.05:
                    status_tag = "🟡 稳健达标(未证显著)"
                elif lift_shrunk >= 1.25:
                    status_tag = "🟢 超强信标(已证显著)"
                else:
                    status_tag = "🟡 稳健达标"

                leaderboard.append({
                    "id": key,
                    "name": sc["name"],
                    "type": "pick_set",
                    "n_periods": n_periods,
                    "picks_per_period": round(picks_per_period, 1),
                    "mean_hits": round(mean_hits, 2),
                    "actual_rate": round(rate * 100, 1),
                    "baseline_rate": 25.0,
                    "lift": round(lift, 2),
                    "lift_shrunk": round(lift_shrunk, 4),
                    "lift_ci_lo": round(ci_lo / baseline_rate, 4) if baseline_rate else 0.0,
                    "p_value": round(p_val, 6),
                    "insufficient": insufficient,
                    "recent_5_rate": round(recent_rate * 100, 1),
                    "momentum": momentum,
                    "per_period_estimated": key in per_period_estimated,
                    "status_tag": status_tag
                })
            elif "total" in sc and sc["total"] > 0:
                both_rate = sc["p2_both"] / sc["total"]
                one_rate = sc["p2_one"] / sc["total"]
                win_rate = (sc["p2_both"] + sc["p2_one"]) / sc["total"]
                n_periods = int(sc["total"])
                # C2: 选2双中率的 CI/p 以 6.07% 为随机基线；盈亏平衡需双中率 ≥ 10.53%（约 1.75x）
                ci_lo_p2, p_val_p2 = _stats(both_rate, n_periods, 0.0607)
                lift_p2 = both_rate / 0.0607
                lift_p2_shrunk = _shrink(lift_p2, n_periods)
                insufficient_p2 = n_periods < 100
                if insufficient_p2:
                    p2_tag = "🟡 样本不足100期·仅供观察"
                elif p_val_p2 > 0.05:
                    p2_tag = "🟡 正常波动(未证显著)"
                elif lift_p2_shrunk >= 1.05:
                    p2_tag = "👑 黄金搭档(已证显著)"
                else:
                    p2_tag = "🟡 正常波动"
                leaderboard.append({
                    "id": key,
                    "name": sc["name"],
                    "type": "pick2_pair",
                    "n_periods": n_periods,
                    "both_hits": sc["p2_both"],
                    "one_hits": sc["p2_one"],
                    "zero_hits": sc["p2_zero"],
                    "both_rate": round(both_rate * 100, 1),
                    "one_rate": round(one_rate * 100, 1),
                    "total_win_rate": round(win_rate * 100, 1),
                    "lift": round(lift_p2, 2),
                    "lift_shrunk": round(lift_p2_shrunk, 4),
                    "lift_ci_lo": round(ci_lo_p2 / 0.0607, 4),
                    "p_value": round(p_val_p2, 6),
                    "insufficient": insufficient_p2,
                    "breakeven_note": "选2盈亏平衡双中率需≥10.53%(≈1.75x)",
                    "status_tag": p2_tag
                })
            # kill_set 产品已退役，不再入榜

        # C2: 排序用收缩后 Lift（赢家诅咒折扣），原始 Lift 仍保留展示
        leaderboard.sort(key=lambda x: x.get("lift_shrunk", x.get("lift", 0.0)), reverse=True)

        summary_result = {
            "status": "ok",
            "audit_time": datetime.now().isoformat(),
            "target_period": target_periods[-1] if target_periods else 0,
            "n_review": len(target_periods),
            "eval_standard": "C2整改口径: 收缩Lift=(n·lift+30)/(n+30) | 评级封顶规则: n<100期或未证显著(p>0.05)不得标🟢",
            "leaderboard": leaderboard,
            # 2026-10-21 P1 缺陷修复 (Bug#10)：账本原先只落 `detailed_ledger[-10:]`，
            # 而 module_gate._lift_30_from_detailed 的生效条件是 `n >= 20` ——
            # 于是「近30窗 Lift」那条 `lift_30<0.95 自动转观察仓` 的降级熔断**永远不可能触发**，
            # 100% 退回 leaderboard_proxy(全窗均值) 且 n_30 被伪造成 30。
            # 账本留足 40 条供熔断取数；展示层的截断应放到渲染层做，不要在数据层砍。
            "detailed_ledger": detailed_ledger[-40:],
            "detailed_ledger_total_periods": len(detailed_ledger),
            "total_evaluated_modules": len(leaderboard),
            "no_data_modules": no_data_modules,
            "data_integrity_note": "缺关键实测指标的模块不再用默认值冒充实测（2026-09-10 数据诚信整改）"
        }

        try:
            with open(MASTER_LEDGER_FILE, 'w', encoding='utf-8') as f:
                json.dump(summary_result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存复盘账本失败: {e}")

        self._generate_master_report_md(summary_result)
        return summary_result

    def _generate_master_report_md(self, res: Dict[str, Any]):
        out_dir = os.path.join(get_outputs_dir(), "reports")
        os.makedirs(out_dir, exist_ok=True)
        report_file = os.path.join(out_dir, "master_review_report_latest.md")

        lines = [
            "# 🏆 快乐8 全模块多维实战命中复盘总决算战报",
            f"> 审计周期: 近 {res.get('n_review')} 期 Walk-Forward 滚动样本外对账 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📊 1. 跨模块胜率排行榜 (全系统天梯榜)",
            "| 模块排名 | 预测子系统名称 | 推荐规模 | 均命中球数 | 实际命中率 | 随机基线 | 提升度 (Lift) | 势头动向 | 状态评级 |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        ]

        rank = 1
        for m in res.get("leaderboard", []):
            wm = " ⚠️样本不足" if m.get("insufficient") else ""
            if m.get("type") == "pick_set":
                lines.append(f"| {rank} | **{m['name']}** | {m.get('picks_per_period', '-')} 码 | `{m.get('mean_hits', '-')}` | **{m.get('actual_rate', '-')}%** | {m.get('baseline_rate', '-')}% | **{m.get('lift', '-')}x** (收缩 {m.get('lift_shrunk', '-')}x) | {m.get('momentum', '-')}{wm} | {m.get('status_tag', '-')} |")
                rank += 1
            elif m.get("type") == "pick2_pair":
                lines.append(f"| {rank} | **{m['name']}** | 选2搭档 | 双中:{m.get('both_hits', 0)}次 | 双全中率:**{m.get('both_rate', 0)}%** | 6.0% | **{m.get('lift', '-')}x** (收缩 {m.get('lift_shrunk', '-')}x) | 单中:{m.get('one_rate', 0)}%{wm} | {m.get('status_tag', '-')} |")
                rank += 1

        # C2/C4: 总结改为注册表驱动的实话, 不再念"优先采纳HE5"的旧剧本
        retired_names = []
        observation_names = []
        try:
            from core.module_gate import ModuleGate
            _gate = ModuleGate(self.proj_dir)
            retired_names = [m2["name"] for m2 in _gate.registry().get("modules", {}).values()
                             if m2.get("status") == "retired"]
            observation_names = [m2["name"] for m2 in _gate.registry().get("modules", {}).values()
                                 if m2.get("status") == "observation"]
        except Exception:
            pass
        green_beacons = [m["name"] for m in res.get("leaderboard", [])
                         if m.get("status_tag", "").startswith("🟢")]
        insufficient_cnt = sum(1 for m in res.get("leaderboard", []) if m.get("insufficient"))
        lines.extend([
            "",
            "## 🎯 2. 操盘手复盘总结与诊断建议（整改后实话版）",
            f"- **已证显著(🟢超强信标)**: {('、'.join(green_beacons)) if green_beacons else '本轮没有 —— 没有任何模块在收缩后 Lift 与显著性双重门槛下达标，榜单第一也不等于真优势'}；",
            f"- **样本不足水印**: 本榜 {insufficient_cnt} 个模块样本 < 100 期, 其 Lift 数字仅供观察，不构成上票依据；",
            f"- **已退役(不投票)**: {('、'.join(retired_names)) if retired_names else '无'}；",
            f"- **观察仓(记账不投票)**: {('、'.join(observation_names)) if observation_names else '无'}；",
            "- **数学提醒**: 快乐8返奖率约58%，任何玩法需真实可复现 Lift ≥ 1.75x 才有正期望；",
            "- **联动说明**: 本榜数据由 `module_gate` 注册表消费，每晚据此重算各模块投票权重（权重=max(0, 收缩Lift−1)）。",
            ""
        ])

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
        except Exception:
            pass


def print_master_review_table(res: Dict[str, Any]):
    print("\n" + "=" * 80)
    print("  🏆 快乐8 全模块多维实战命中复盘总决算 (Master Multi-Module Review)")
    print("=" * 80)
    print(f"  📅 审计对账期数: 近 {res.get('n_review')} 期 | 目标期号: {res.get('target_period')}")
    print("-" * 80)
    print(f"  {'排名':^4} │ {'模块名称':<26} │ {'均命中':^8} │ {'实际命中':^9} │ {'提升度Lift':^10} │ {'势头与状态':<14}")
    print("  " + "─"*4 + "┼" + "─"*28 + "┼" + "─"*10 + "┼" + "─"*11 + "┼" + "─"*12 + "┼" + "─"*16)

    rank = 1
    for m in res.get("leaderboard", []):
        name = m["name"]
        lift_s = f"{m.get('lift', 0.0):.2f}x→{m.get('lift_shrunk', m.get('lift', 0.0)):.2f}x"
        if m.get("insufficient"):
            lift_s += "⚠️"
        if m.get("type") == "pick_set":
            mean_s = f"{m.get('mean_hits', 0.0):.2f}/{m.get('picks_per_period', 5):.0f}"
            rate_s = f"{m.get('actual_rate', 0.0):.1f}%"
            status_s = f"{m.get('status_tag', '')}"
            print(f"  {rank:^4} │ {name:<26} │ {mean_s:^8} │ {rate_s:^9} │ {lift_s:^10} │ {status_s}")
            rank += 1
        elif m.get("type") == "pick2_pair":
            both_s = f"双中{m.get('both_rate', 0.0):.1f}%"
            print(f"  {rank:^4} │ {name:<26} │ {'选2搭档':^8} │ {both_s:^9} │ {lift_s:^10} │ {m.get('status_tag', '')}")
            rank += 1

    print("=" * 80 + "\n")
