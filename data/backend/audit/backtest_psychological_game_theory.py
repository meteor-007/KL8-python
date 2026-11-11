# -*- coding: utf-8 -*-
"""
心理博弈论与逆向均值回归量化引擎 · 严格样本外滚动回测复盘引擎
(Psychological Game Theory & Contrarian Reversion Engine - Walk-Forward Audit)
================================================================================
【业务背景与架构定位】:
本模块专为快乐8【心理博弈论与逆向均值回归】提供工业级样本外滚动回测 (Walk-Forward Rolling Window)。
严格遵循《反幻觉实战物理锚定红线》与《全局大白话落地架构 V7.0》：
1. 绝对屏蔽未来数据：推演第 T 期时，仅使用第 T-1 及之前的历史开奖，绝无未来信息泄露；
2. 完整记录逐期明细：包含 Top 5 突击金牌、Top 12 稳健大底、弹性冷号突击、单点健康重号、极热膨胀杀号的预测与真实开奖对账；
3. 输出多维度统计决算指标与持久化 JSON / Markdown 实战复盘研报。

@author Antigravity Quantitative Audit Team
@since 2026-09-07
"""
import os
import sys
import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(_DIR)          # backend/
_ROOT_DIR = os.path.dirname(_PROJ_DIR)     # data/
for p in [_ROOT_DIR, _PROJ_DIR, _DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.utils.paths import get_outputs_dir
from backend.utils.history_loader import load_history
from backend.core.psychological_game_engine import PsychologicalGameEngine

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class PsychologicalGameTheoryAuditor:
    """心理博弈与逆向均值回归严格样本外滚动回测引擎"""

    def __init__(self, history: Optional[List[Dict[str, Any]]] = None):
        """
        初始化审计引擎
        @param history 历史开奖列表 (最新期排在 index 0)
        """
        if history is None:
            self.history = load_history()
        else:
            self.history = history
        self.total_draws = len(self.history)
        self.engine = PsychologicalGameEngine(self.history)

    def run_walk_forward_backtest(self, n_tests: int = 100) -> Dict[str, Any]:
        """
        执行严格样本外滚动回测 (Rolling Window Walk-Forward Backtest)
        @param n_tests 测试期数规模 (如 30, 50, 100, 200)
        @return 包含逐期复盘明细与宏观决算指标的字典
        """
        max_available = self.total_draws - 35
        if n_tests > max_available:
            n_tests = max_available

        records = []
        hits_top5_total = 0
        hits_top12_total = 0
        hits_cold4_total = 0
        hits_repeat4_total = 0
        # 2026-10-21 P1 缺陷修复 (Bug#12)：分母必须用**实际推荐码数**的池化口径。
        # 引擎早已把主口径收敛为"最优 3 码"，top5_assault / top12_balanced 只是 top3 的
        # 兼容别名（长度恒为 3，见 psychological_game_engine.py:358-361 与
        # tests/test_psychological_game_engine.py:53-56 的断言），
        # 但回测却把分母**写死成 5 和 12**，把 3 码方案评成 Lift 0.24x 的"灾难"。
        # 前端标签写的是"最优3码均中 / 命中率 …/ 3码"，读的却是这个 /5 的数 —— 号与标签互相打架。
        picks_top5_total = 0
        picks_top12_total = 0

        top5_dist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        top12_dist = {i: 0 for i in range(13)}

        top5_win2_count = 0
        top5_win3_count = 0
        top12_win4_count = 0
        top12_win5_count = 0

        current_streak_win = 0
        max_streak_win = 0
        current_streak_lose = 0
        max_streak_lose = 0

        for offset in range(n_tests - 1, -1, -1):
            target_draw = self.history[offset]
            target_nums = set(target_draw.get("numbers", []))
            issue = str(target_draw.get("issue") or target_draw.get("period") or "")
            draw_date = str(target_draw.get("date", ""))

            # 严格屏蔽未来：推演 target_draw (index: offset) 时，输入历史从 offset + 1 开始
            pred = self.engine.compute_full_prediction(offset=offset + 1)
            t5 = pred.get("top5_assault", [])
            t12 = pred.get("top12_balanced", [])
            # 2026-10-21 P1 缺陷修复 (Bug#12)：kill5_defense 这个键引擎**从不产出**
            # (全模块 grep 0 命中，KillSeeker 已于 2026-09 拆除)，
            # 于是 k5 恒为 []、avoid_count 恒为 0、kill_avoid_rate_pct 四窗口全是 0.0，
            # 却仍被当"杀号防守成功率 0%"写进账本与研报 —— 统计一个不存在的产品。
            # 现停止记账该指标，不再产出恒 0 的假结论。
            c4 = pred.get("top_cold_spring", [])
            r4 = pred.get("top_healthy_repeats", [])
            macro = pred.get("macro_pendulum", {})

            # 1. 对账 Top 5 突击金牌
            h5_list = [x for x in t5 if x in target_nums]
            h5_count = len(h5_list)
            hits_top5_total += h5_count
            top5_dist[h5_count] = top5_dist.get(h5_count, 0) + 1
            if h5_count >= 2:
                top5_win2_count += 1
            if h5_count >= 3:
                top5_win3_count += 1

            if h5_count >= 1:
                current_streak_win += 1
                current_streak_lose = 0
                max_streak_win = max(max_streak_win, current_streak_win)
            else:
                current_streak_lose += 1
                current_streak_win = 0
                max_streak_lose = max(max_streak_lose, current_streak_lose)

            # 2. 对账 Top 12 稳健大底
            h12_list = [x for x in t12 if x in target_nums]
            h12_count = len(h12_list)
            hits_top12_total += h12_count
            top12_dist[h12_count] = top12_dist.get(h12_count, 0) + 1
            if h12_count >= 4:
                top12_win4_count += 1
            if h12_count >= 5:
                top12_win5_count += 1

            # 3. 对账 弹性冷号突击 (4码)
            hcold_list = [x for x in c4 if x in target_nums]
            hcold_count = len(hcold_list)
            hits_cold4_total += hcold_count

            # 4. 对账 单点健康重号 (4码)
            hrep_list = [x for x in r4 if x in target_nums]
            hrep_count = len(hrep_list)
            hits_repeat4_total += hrep_count

            # 5. (已删除) 极热膨胀杀号对账 —— 引擎不产出 kill5_defense，见上方 Bug#12 说明

            # 6. 大小比实际与预测对比
            actual_big = sum(1 for x in target_nums if x > 40)
            actual_small = 20 - actual_big

            picks_top5_total += len(t5)
            picks_top12_total += len(t12)

            records.append({
                "issue": issue,
                "date": draw_date,
                "target_numbers": sorted(list(target_nums)),
                "top5": t5,
                "top5_size": len(t5),
                "top5_hits": h5_list,
                "top5_hit_count": h5_count,
                "top12": t12,
                "top12_size": len(t12),
                "top12_hits": h12_list,
                "top12_hit_count": h12_count,
                "cold4": c4,
                "cold4_hits": hcold_list,
                "cold4_hit_count": hcold_count,
                "repeats4": r4,
                "repeats4_hits": hrep_list,
                "repeats4_hit_count": hrep_count,
                "predicted_size_bias": macro.get("target_size_bias", "均衡"),
                "actual_size_ratio": f"{actual_small}:{actual_big} (小:大)"
            })

        avg_h5 = hits_top5_total / float(n_tests)
        avg_h12 = hits_top12_total / float(n_tests)
        # 池化命中率 = Σ命中 / Σ推荐码数 (与 core.wf_hit_engine / module_gate 同口径)
        denom5 = float(picks_top5_total) if picks_top5_total else float(n_tests * 5)
        denom12 = float(picks_top12_total) if picks_top12_total else float(n_tests * 12)
        rate5 = (hits_top5_total / denom5) * 100.0
        rate12 = (hits_top12_total / denom12) * 100.0
        lift5 = (hits_top5_total / denom5) / 0.25
        lift12 = (hits_top12_total / denom12) / 0.25

        avg_cold4 = hits_cold4_total / float(n_tests)
        rate_cold4 = (avg_cold4 / 4.0) * 100.0 if n_tests > 0 else 0.0
        lift_cold4 = (avg_cold4 / 4.0) / 0.25 if n_tests > 0 else 0.0

        avg_rep4 = hits_repeat4_total / float(n_tests)
        rate_rep4 = (avg_rep4 / 4.0) * 100.0 if n_tests > 0 else 0.0

        # (已删除) kill_avoid_rate / kill_lift —— 引擎不产出 kill5_defense，
        # 原先既统计不存在的产品，又把已是比例的 kill_avoid_rate 再除 75 当"防守提升度"，
        # 口径双重错误 (见 Bug#12)。KillSeeker 已于 2026-09 拆除，不再输出占位假指标。

        top5_win2_rate = (top5_win2_count / float(n_tests)) * 100.0
        top5_win3_rate = (top5_win3_count / float(n_tests)) * 100.0
        top12_win4_rate = (top12_win4_count / float(n_tests)) * 100.0
        top12_win5_rate = (top12_win5_count / float(n_tests)) * 100.0

        summary = {
            "n_tests": n_tests,
            "start_issue": records[0]["issue"] if records else "",
            "end_issue": records[-1]["issue"] if records else "",
            # 分母透明化：把实际参与对账的推荐码总数写进账本，杜绝"号是对的、标签是错的"
            "picks_top5_total": int(picks_top5_total),
            "picks_top12_total": int(picks_top12_total),
            "avg_pool_size_top5": round(picks_top5_total / float(n_tests), 3) if n_tests else 0,
            "avg_pool_size_top12": round(picks_top12_total / float(n_tests), 3) if n_tests else 0,
            "denominator_note": (
                "口径已改为池化命中率 = Σ命中 / Σ实际推荐码数。"
                "引擎主口径为「最优3码」，top5_assault/top12_balanced 仅为其兼容别名"
                "(长度恒 3)，故 top5/top12 两栏实测为同一组号码、同一口径，非两个独立产品。"
            ),
            "avg_h5": round(avg_h5, 2),
            "rate5_pct": round(rate5, 2),
            "lift5": round(lift5, 3),
            "max_h5": max([r["top5_hit_count"] for r in records]) if records else 0,
            "top5_dist": top5_dist,
            "top5_win2_rate_pct": round(top5_win2_rate, 2),
            "top5_win3_rate_pct": round(top5_win3_rate, 2),
            "max_streak_win": max_streak_win,
            "max_streak_lose": max_streak_lose,
            "avg_h12": round(avg_h12, 2),
            "rate12_pct": round(rate12, 2),
            "lift12": round(lift12, 3),
            "max_h12": max([r["top12_hit_count"] for r in records]) if records else 0,
            "top12_dist": top12_dist,
            "top12_win4_rate_pct": round(top12_win4_rate, 2),
            "top12_win5_rate_pct": round(top12_win5_rate, 2),
            "avg_cold4": round(avg_cold4, 2),
            "rate_cold4_pct": round(rate_cold4, 2),
            "lift_cold4": round(lift_cold4, 3),
            "avg_rep4": round(avg_rep4, 2),
            "rate_rep4_pct": round(rate_rep4, 2),
            "records": records
        }

        return summary

    def generate_full_audit_ledger_and_report(self) -> Dict[str, Any]:
        """
        执行全景多周期实测对账，并输出结构化账本与详尽 Markdown 复盘研报
        """
        print("=" * 70)
        print("  🧠 正在启动【心理博弈论与逆向均值回归】全景样本外滚动回测...")
        print(f"  ■ 数据库总历史开奖期数: {self.total_draws} 期")
        print("  ■ 回测机制: 严格屏蔽未来数据 (Walk-Forward Rolling Window)")
        print("=" * 70)

        results_by_window = {}
        for w in [30, 50, 100, 200]:
            print(f"  -> 正在计算 近 {w} 期 滚动实测...")
            results_by_window[f"last_{w}"] = self.run_walk_forward_backtest(n_tests=w)

        main_res_100 = results_by_window["last_100"]

        base_dir = _ROOT_DIR
        storage_dir = os.path.join(base_dir, "storage", "reviews")
        os.makedirs(storage_dir, exist_ok=True)
        ledger_path = os.path.join(storage_dir, "psychological_game_backtest_ledger.json")

        ledger_payload = {
            "meta": {
                "engine_name": "Psychological Game Theory & Contrarian Reversion Engine",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_history_draws": self.total_draws,
                "protocol": "Walk-Forward Out-of-Sample Rolling Test (Zero Future Leakage)",
            },
            "multi_window_summary": {
                w_key: {
                    "n_tests": val["n_tests"],
                    "start_issue": val["start_issue"],
                    "end_issue": val["end_issue"],
                    # 池规模与口径说明随账本一起落盘，避免前端把 3 码池标成 "5码/12码"
                    "avg_pool_size_top5": val["avg_pool_size_top5"],
                    "avg_pool_size_top12": val["avg_pool_size_top12"],
                    "denominator_note": val["denominator_note"],
                    "avg_h5": val["avg_h5"],
                    "rate5_pct": val["rate5_pct"],
                    "lift5": val["lift5"],
                    "avg_h12": val["avg_h12"],
                    "rate12_pct": val["rate12_pct"],
                    "lift12": val["lift12"],
                    # (已删除) kill_avoid_rate_pct：引擎不产出 kill5_defense，旧账本恒为 0.0 的假指标
                    "top5_win2_rate_pct": val["top5_win2_rate_pct"],
                    "avg_cold4": val["avg_cold4"],
                    "avg_rep4": val["avg_rep4"],
                }
                for w_key, val in results_by_window.items()
            },
            "detailed_100_records": main_res_100["records"]
        }

        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger_payload, f, ensure_ascii=False, indent=2)
        print(f"  [+] 结构化回测总账本已落盘: {ledger_path}")

        # 同步落盘至前端静态高可用离线目录
        static_ledger_path = os.path.join(base_dir, "frontend", "static", "psychological_game_backtest_ledger.json")
        try:
            with open(static_ledger_path, "w", encoding="utf-8") as sf:
                json.dump(ledger_payload, sf, ensure_ascii=False, indent=2)
            print(f"  [+] 前端静态回测账本已同步: {static_ledger_path}")
        except Exception as se:
            print(f"  [!] 前端静态回测账本同步异常: {se}")

        report_dir = os.path.join(get_outputs_dir(), "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "psychological_game_backtest_detailed_report.md")

        md_content = self._render_detailed_backtest_markdown(results_by_window)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"  [+] 操盘手回测研报已落盘: {report_path}")

        print("=" * 70)
        print("  🎉 心理博弈论与逆向均值回归 滚动回测对账全部圆满完成！")
        print("=" * 70)

        return results_by_window

    def _render_detailed_backtest_markdown(self, multi_res: Dict[str, Any]) -> str:
        """生成具备老派操盘手大白话风格的详尽回测复盘 Markdown 研报"""
        res30 = multi_res.get("last_30", {})
        res50 = multi_res.get("last_50", {})
        res100 = multi_res.get("last_100", {})
        res200 = multi_res.get("last_200", {})

        records100 = res100.get("records", [])

        md = f"""# 🧠 快乐8【心理博弈论与逆向均值回归】实战滚动回测决算大研报
> **审计机制**: 严格样本外滚动窗口 (Walk-Forward Rolling Window · 绝对屏蔽未来数据)  
> **底层样本**: 全量 {self.total_draws} 期真实历史开奖  
> **生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
> **执行协议**: 《全局大白话落地架构 V7.0》×《反幻觉实战物理锚定红线》

---

## 一、 核心黑话实战大白话速查对照表 (操盘手白话大典)

| 学术/系统黑话 | 老派操盘手大白话 | 实战中的真实含义 |
| :--- | :--- | :--- |
| **逆向均值回归 (Mean Reversion)** | **风水轮流转 / 物极必反** | 连着开大号肯定要回调小号；冷号憋到极限大众死心割肉时，大数定律必定拉回补仓。 |
| **散户羊群效应惩罚 (Herd Bias)** | **散户跟风买热，咱趁机撤退** | 散户看到某个号天天开就疯抢追涨，此时极易冲顶滞涨，系统反向给它降温扣分。 |
| **弹性冷号突击 (Spring Cold Rebound)** | **绝望点抓反弹 (遗漏6-18期)** | 遗漏6~18期的中冷号是大众心态崩溃点，最容易发生强力报复性回补。 |
| **单点健康重号 (Uncut Repeats)** | **顺风车连庄 (两旁无连号截断)** | 昨天开出且身边没被连号撞伤的热码，阻力最小，极易连庄。 |
| **提升度 (Lift)** | **跑赢大盘倍数 (超额收益)** | 实际单码命中率除以随机瞎蒙基准(25.0%)。>= 1.00x 为跑赢大盘，>= 1.10x 为强信标。 |
| **防守回避率 (Defense Avoidance)** | **成功避雷率** | 推荐杀掉的5个号实际没开出来的比率（基准为 75.0%）。 |

---

## 二、 多周期样本外滚动实测全景决算总表

> ⚠️ **口径说明 (2026-10-21 整改)**：引擎主口径已收敛为「最优 3 码」，
> `top5_assault` / `top12_balanced` 只是它的兼容别名（实际长度见下表"池"列），
> 因此下表两栏评的是**同一组号码**，不是两个独立产品。
> 命中率与 Lift 一律按池化口径 Σ命中 / Σ实际推荐码数 计算，不再用写死的 5 或 12 当分母。

| 实测周期 | 样本期数 | 覆盖期号范围 | 突击池 (均码数/期) | 均中码数 | 命中率 | 提升度 Lift (基准25%) | 单期≥2码率 | 大底池 (均码数/期) | 均中码数 | 命中率 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **近 30 期** | 30 期 | {res30.get('start_issue')} ~ {res30.get('end_issue')} | {res30.get('avg_pool_size_top5')} | **{res30.get('avg_h5')} 码** | **{res30.get('rate5_pct')}%** | **{res30.get('lift5')}x** | **{res30.get('top5_win2_rate_pct')}%** | {res30.get('avg_pool_size_top12')} | **{res30.get('avg_h12')} 码** | **{res30.get('rate12_pct')}%** |
| **近 50 期** | 50 期 | {res50.get('start_issue')} ~ {res50.get('end_issue')} | {res50.get('avg_pool_size_top5')} | **{res50.get('avg_h5')} 码** | **{res50.get('rate5_pct')}%** | **{res50.get('lift5')}x** | **{res50.get('top5_win2_rate_pct')}%** | {res50.get('avg_pool_size_top12')} | **{res50.get('avg_h12')} 码** | **{res50.get('rate12_pct')}%** |
| **近 100 期** | 100 期 | {res100.get('start_issue')} ~ {res100.get('end_issue')} | {res100.get('avg_pool_size_top5')} | **{res100.get('avg_h5')} 码** | **{res100.get('rate5_pct')}%** | **{res100.get('lift5')}x** | **{res100.get('top5_win2_rate_pct')}%** | {res100.get('avg_pool_size_top12')} | **{res100.get('avg_h12')} 码** | **{res100.get('rate12_pct')}%** |
| **近 200 期** | 200 期 | {res200.get('start_issue')} ~ {res200.get('end_issue')} | {res200.get('avg_pool_size_top5')} | **{res200.get('avg_h5')} 码** | **{res200.get('rate5_pct')}%** | **{res200.get('lift5')}x** | **{res200.get('top5_win2_rate_pct')}%** | {res200.get('avg_pool_size_top12')} | **{res200.get('avg_h12')} 码** | **{res200.get('rate12_pct')}%** |

---

## 三、 近 100 期核心维度深度对账解析

### 1. 突击池 (原 Top 5 金牌) 分档命中分布
- **实际池规模**: 平均 **{res100.get('avg_pool_size_top5')} 码 / 期**（引擎主口径为最优 3 码）
- **均中码数**: **`{res100.get('avg_h5')} 码`** (池化单码命中率 `{res100.get('rate5_pct')}%`，随机基线 25.0%)
- **提升度 Lift**: **`{res100.get('lift5')}x`**
- **单期 ≥2 码率**: **`{res100.get('top5_win2_rate_pct')}%`** (近 100 期中约 {int(res100.get('top5_win2_rate_pct', 0))} 期双中及以上)
- **单期 ≥3 码率**: **`{res100.get('top5_win3_rate_pct')}%`**
- **最长连续命中 (≥1 码)**: 连续 **{res100.get('max_streak_win')} 期**
- **各档位命中频次分布**:
"""
        t5_dist = res100.get("top5_dist", {})
        _t5_n = sum(t5_dist.values()) or 1
        for k in sorted(t5_dist.keys()):
            c = t5_dist.get(k, 0)
            pct = (c / _t5_n) * 100.0
            md += f"  * **命中 {k} 码**: **{c} 期** ({pct:.1f}%)\n"

        md += f"""
### 2. 大底池 (原 Top 12 稳健大网 · 与上栏同源同码)
- **实际池规模**: 平均 **{res100.get('avg_pool_size_top12')} 码 / 期**
- **均中码数**: **`{res100.get('avg_h12')} 码`** (池化单码命中率 `{res100.get('rate12_pct')}%`)
- **提升度 Lift**: **`{res100.get('lift12')}x`**
- **单期命中 >= 4 码概率**: **`{res100.get('top12_win4_rate_pct')}%`**
- **单期命中 >= 5 码概率**: **`{res100.get('top12_win5_rate_pct')}%`**
- **单期历史最高斩获**: **{res100.get('max_h12')} 码**

### 3. 子战术专项对账
- **弹性冷号突击 (遗漏6-18期·4码)**: 100期平均每期命中 **`{res100.get('avg_cold4')} 码`** (命中率 `{res100.get('rate_cold4_pct')}%`，提升度 `{res100.get('lift_cold4')}x`)
- **单点健康重号 (连庄精选·4码)**: 100期平均每期命中 **`{res100.get('avg_rep4')} 码`** (命中率 `{res100.get('rate_rep4_pct')}%`)

> 原「极热膨胀杀号 (Top 5 杀号) 防守回避率」一项已删除：引擎从不产出 `kill5_defense`，
> KillSeeker 已于 2026-09 拆除，继续统计只会得到恒 0 的假结论 (见 Bug#12)。

---

## 四、 近 100 期逐期滚动复盘对账大明细 (屏蔽未来数据)

> 表格说明：
> - **突击池命中**: 该期推荐码中实际开出的号码及个数（池规模见第三节，主口径为最优 3 码）；
> - **大底池命中数**: 与上栏同源同码，故个数一致，仅作分档观察；
> - **弹性冷号命中**: 4 个中冷弹性码中实际开出的号码；
> - **健康重号命中**: 4 个健康顺风重号中实际开出的号码。

| 期号 | 开奖日期 | 实际开奖 (20码) | 突击池预测 | 突击池命中 | 大底池命中数 | 弹性冷号命中 | 健康重号命中 | 大小比趋势 |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- | :--- | :--- |
"""
        for r in reversed(records100):
            t_nums_str = " ".join(f"{x:02d}" for x in r["target_numbers"])
            t5_str = " ".join(f"{x:02d}" for x in r["top5"])
            h5_str = " ".join(f"{x:02d}" for x in r["top5_hits"]) if r["top5_hits"] else "—"
            c4_hits_str = " ".join(f"{x:02d}" for x in r["cold4_hits"]) if r["cold4_hits"] else "—"
            r4_hits_str = " ".join(f"{x:02d}" for x in r["repeats4_hits"]) if r["repeats4_hits"] else "—"

            md += f"| **{r['issue']}** | {r['date']} | `{t_nums_str}` | `{t5_str}` | **{r['top5_hit_count']}个** (`{h5_str}`) | **{r['top12_hit_count']} / {r.get('top12_size', len(r['top12']))}** | `{c4_hits_str}` ({r['cold4_hit_count']}) | `{r4_hits_str}` ({r['repeats4_hit_count']}) | {r['actual_size_ratio']} |\n"

        # 2026-10-21 数据诚信修复 (Bug#12 连带)：本节总结原先是**写死的话术**
        # ("斩获 1.38 码均中与 1.10x 超强提升度，选2双全中率 37.0%")，
        # 与账本实际数字无关 —— 回测结论变了它也不会变。现全部改为从 res100 实算取数。
        _r100 = res100
        _lift5_v = float(_r100.get("lift5") or 0)
        _verdict_top = (
            f"{_lift5_v:.2f}x（跑赢随机基线）" if _lift5_v >= 1.10 else
            (f"{_lift5_v:.2f}x（贴随机基线，单期波动不构成优势）" if _lift5_v >= 0.95 else
             f"{_lift5_v:.2f}x（低于随机基线，属负贡献）")
        )
        md += f"""
---

## 五、 老派操盘手复盘总结与实战使用建议 (数字均由本表实算，非模板话术)

1. **突击池实测战果**：
   - 近 {_r100.get('n_tests')} 期样本外测试中，均中 **{_r100.get('avg_h5')} 码 / 池均 {_r100.get('avg_pool_size_top5')} 码**，
     池化单码命中率 **{_r100.get('rate5_pct')}%**，提升度 **{_verdict_top}**；
   - 单期 ≥2 码率 **{_r100.get('top5_win2_rate_pct')}%**，单期 ≥3 码率 **{_r100.get('top5_win3_rate_pct')}%**；
   - 最长连续命中 **{_r100.get('max_streak_win')} 期**，最长连续空手 **{_r100.get('max_streak_lose')} 期**。
2. **冷热对冲子战术**：
   - 弹性冷号突击（遗漏 6-18 期）平均每期命中 **{_r100.get('avg_cold4')} 码**（提升度 {_r100.get('lift_cold4')}x）；
   - 单点健康重号平均每期命中 **{_r100.get('avg_rep4')} 码**。
3. **使用边界（务必读）**：
   - 上表命中率是**池化点估计**。快乐8 单码随机基线就是 25.0%，样本量不足时 1.0x~1.2x 的差值
     基本落在随机波动范围内；**未经 BH-FDR 多重检验校正通过的模块，不得当作下注依据**。
   - 各模块同期推荐高度重叠，把它们逐条算成"独立战绩"会虚增显著性 ——
     本账本只描述历史，不构成任何"稳赚"承诺。

---
*本研报由自动化回测审计流水线原生生成，严格遵循全自动、零未来数据泄漏、物理对账准则；*
*文内所有数字均由账本实算取数，无任何写死话术。*
"""
        return md


if __name__ == "__main__":
    auditor = PsychologicalGameTheoryAuditor()
    auditor.generate_full_audit_ledger_and_report()
