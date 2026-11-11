#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源1×数据源2 深层关联与极高命中率预测 - 每日量化独立执行器 v1.0
====================================================================
用法: python -m backend.modules.datasource.run_daily [30]
功能:
  1. 样本外滚动对账 (Walk-Forward 近 30 期)
  2. 精选爆发最优3码与跨规则共识金胆推演
  3. 黄金连体婴选2搭档挖掘
  4. 研报与纯文本预测落盘（杀号产品已退役）
"""
import os
import sys

# 路径自适应 (模块迁入 backend/modules 后：向上定位项目根)
def _find_project_root(start: str) -> str:
    curr = start
    for _ in range(8):
        if os.path.isdir(os.path.join(curr, "backend")) and os.path.isdir(os.path.join(curr, "frontend")):
            return curr
        if os.path.exists(os.path.join(curr, "GEMINI.md")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return start

_PROJ_DIR = _find_project_root(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.datasource_predictor import predict_datasource_deep, walk_forward_review_datasource
from utils.history_loader import load_history


def run_datasource_pipeline(n_review: int = 30, verbose: bool = True):
    if verbose:
        print("=" * 76)
        print("  🧬 数据源1×数据源2 深层关联与极高命中率量化推演引擎 (主系统整合版)")
        print("=" * 76)

    history = load_history()
    # 2026-10-21 P2 整改：原 `if history else 2026234` 会在历史库为空时**编造一个期号**
    # 继续跑完整轮推演并落盘，产物标着假期号，下游收割器/研报/看板都无从分辨。
    # 改走统一入口：数据不可用直接抛错，由上层按「当期不可推演」如实降级。
    from backend.utils.periods import next_target_period
    target_period = next_target_period(history)

    wf_res = walk_forward_review_datasource(n_review=n_review)
    pred_res = predict_datasource_deep(target_period=target_period)

    # 将样本外 Lift 写回预测 JSON，供 summary / UI 水印使用
    if pred_res and wf_res:
        try:
            import json
            from backend.utils.paths import get_outputs_dir
            pred_res["hot_lift"] = wf_res.get("hot_lift")
            pred_res["review_periods"] = wf_res.get("total_evaluated")
            pred_res["hot_single_rate"] = wf_res.get("hot_single_rate")
            pred_res["evidence_note"] = (
                f"结构推荐（非显著超额）；近{wf_res.get('total_evaluated')}期样本外热码 "
                f"Lift={wf_res.get('hot_lift')}（单码命中 "
                f"{(wf_res.get('hot_single_rate') or 0) * 100:.1f}% vs 基线25%），仅作形态参考。"
            )
            period = pred_res.get("target_period")
            if period:
                json_path = os.path.join(
                    get_outputs_dir(), "deep_association", f"深层关联预测_{period}.json"
                )
                if os.path.isfile(json_path):
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(pred_res, f, ensure_ascii=False, indent=2)
        except Exception as e:
            if verbose:
                print(f"  ⚠️ 回写 Lift 水印失败: {e}")

    if verbose and wf_res:
        print(f"  📁 历史库期数: {len(history)} 期 | 最新开奖: {history[0]['issue']} | 🎯 目标研判: {target_period}")
        print("\n" + "=" * 76)
        print("  ① 置信评级与样本外滚动对账 (Walk-Forward 近 30 期)")
        print("=" * 76)
        print(f"  🔥 最优3码均命中:     {wf_res.get('hot_top3_mean_hits', wf_res.get('hot_top5_mean_hits', 0)):.2f} / 3 码")
        print(f"  🔥 单码实际命中率:     {wf_res.get('hot_single_rate', 0)*100:.1f}%")
        print(f"  📈 最优3码 Lift:       {wf_res.get('hot_lift', 0):.2f}x (基线期望 0.75)")

        print("\n" + "=" * 76)
        print(f"  ② 目标期 {target_period} 核心决策阵列")
        print("=" * 76)
        print(f"  🎯 精选爆发最优3码:   " + "-".join(f"{n:02d}" for n in pred_res.get('top_hot_numbers', [])))
        cons = pred_res.get('consensus_numbers', [])
        print(f"  ⭐ 跨规则共识金胆:     " + ("-".join(f"{n:02d}" for n in cons) if cons else "无"))
        gp = pred_res.get('gold_pair')
        if gp:
            print(f"  👑 黄金连体婴选2搭档: [{gp[0]:02d}-{gp[1]:02d}] (近100期同出 {pred_res.get('gold_pair_cooccur_100', 0)} 次)")
        print("  （杀号产品已退役，不再输出防守杀号池）")

        print("\n" + "=" * 76)
        print("  数据源1×数据源2 深层关联推演完成 ✅")
        print("=" * 76)

    return pred_res, wf_res


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30
    run_datasource_pipeline(n_review=n, verbose=True)
