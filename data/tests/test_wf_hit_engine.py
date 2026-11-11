# -*- coding: utf-8 -*-
"""
wf_hit_engine 单元测试
----------------------
验证"诚实命中评估引擎"的度量口径:
- 单期命中/杀号度量;
- 池化指标 (命中率 / Lift / 95%CI下界 / p值 / 样本不足);
- 跨模块 BH-FDR 多重检验。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from core.wf_hit_engine import (
    period_hit_metrics,
    evaluate_series,
    evaluate_from_counts,
    fdr_summarize,
    render_report,
)


def test_period_hit_metrics_pick():
    rec = [1, 2, 3, 4, 5]
    actual = [3, 4, 10, 11, 12, 13, 14, 15]
    m = period_hit_metrics(rec, actual, is_kill=False)
    assert m["size"] == 5
    assert m["hit_count"] == 2  # 3,4 命中
    assert m["rate"] == 2 / 5


def test_period_hit_metrics_kill():
    rec = [1, 2, 3, 4, 5]           # 杀 5 码
    actual = [1, 2, 3, 8, 9]        # 开奖含 1,2,3
    m = period_hit_metrics(rec, actual, is_kill=True)
    assert m["hit_count"] == 2      # 杀对 4,5 (不在开奖中)


def test_evaluate_from_counts_random_not_significant():
    # 纯随机: 命中率≈25% -> lift≈1.0, 不应判显著
    counts = [{"period": f"R{i}", "size": 12, "hit_count": 3} for i in range(40)]
    ev = evaluate_from_counts(counts, baseline=0.25, min_n=30)
    assert ev["n_periods"] == 40
    assert ev["total_picks"] == 480
    assert round(ev["pooled_rate"], 3) == 0.25
    assert ev["lift"] == 1.0
    assert ev["p_value"] == 1.0
    assert ev["significant"] is False


def test_evaluate_from_counts_high_hit_significant():
    # 明显高于基线 (35%) 且样本足够 -> 应显著优于随机
    counts = [{"period": f"H{i}", "size": 12, "hit_count": 4} for i in range(40)]
    ev = evaluate_from_counts(counts, baseline=0.25, min_n=30)
    assert ev["total_picks"] == 480
    assert ev["pooled_rate"] > 0.3
    assert ev["lift"] > 1.0
    assert ev["lift_ci_lo"] > 1.0
    assert ev["insufficient"] is False
    assert ev["significant"] is True


def test_evaluate_from_counts_insufficient():
    # 样本过少 (n<30) -> 标记样本不足, 不判显著
    counts = [{"period": f"S{i}", "size": 12, "hit_count": 4} for i in range(2)]
    ev = evaluate_from_counts(counts, baseline=0.25, min_n=30)
    assert ev["insufficient"] is True


def test_fdr_summarize_picks_winner():
    random_ev = evaluate_from_counts(
        [{"period": f"R{i}", "size": 12, "hit_count": 3} for i in range(40)],
        baseline=0.25, min_n=30)
    biased_ev = evaluate_from_counts(
        [{"period": f"B{i}", "size": 12, "hit_count": 4} for i in range(40)],
        baseline=0.25, min_n=30)
    out = fdr_summarize({"random": random_ev, "biased": biased_ev})
    assert "biased" in out["winning"]
    assert "random" not in out["winning"]
    assert out["results"]["biased"]["bh_q"] <= 0.05
    assert isinstance(render_report(out["results"], out["winning"]), str)


if __name__ == "__main__":
    test_period_hit_metrics_pick()
    test_period_hit_metrics_kill()
    test_evaluate_from_counts_random_not_significant()
    test_evaluate_from_counts_high_hit_significant()
    test_evaluate_from_counts_insufficient()
    test_fdr_summarize_picks_winner()
    print("ALL WF_HIT_ENGINE UNIT TESTS PASSED!")
