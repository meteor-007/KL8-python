# -*- coding: utf-8 -*-
"""方法2微信桶混剪六码：确定性席位规程。"""
from __future__ import annotations

from backend.modules.sixteen.sixteen_engine import build_method2_bucket_mix


def _ball(n, freq, score, omission=1, r8=2, outgoing=False):
    return {
        "number": n,
        "freq_16": freq,
        "midhot_score": score,
        "score": score,
        "omission": omission,
        "recent_8_hits": r8,
        "is_outgoing": outgoing,
    }


def test_method2_bucket_mix_deterministic_seats():
    # 频5: pick 31,56 / rest 73(出窗),20
    # 频4: pick 16,18,78(并列高分靠后) / rest 39(刚开),71(同源刚开),28
    # 频3 rest: 67,76 omit4 并列 → 取小号67
    balls = [
        _ball(31, 5, 0.70, 1, 3),
        _ball(56, 5, 0.69, 1, 3),
        _ball(73, 5, 0.64, 0, 3, outgoing=True),
        _ball(20, 5, 0.65, 2, 2),
        _ball(16, 4, 0.6956, 1, 3),
        _ball(18, 4, 0.6956, 1, 3),
        _ball(78, 4, 0.6956, 1, 3),
        _ball(39, 4, 0.68, 0, 4),
        _ball(71, 4, 0.64, 0, 3, outgoing=True),
        _ball(28, 4, 0.64, 0, 3),
        _ball(67, 3, 0.4236, 4, 2),
        _ball(76, 3, 0.4236, 4, 2),
        _ball(26, 3, 0.40, 2, 1),
    ]
    fbp = {
        "buckets": [
            {"bucket": "5", "picks": [31, 56], "rests": [73, 20]},
            {"bucket": "4", "picks": [16, 18, 78], "rests": [39, 71, 28]},
            {"bucket": "3", "picks": [10], "rests": [67, 76, 26]},
        ]
    }
    m2 = build_method2_bucket_mix(ball_details=balls, freq_bucket_picks=fbp)
    assert m2["version"] == "method2_bucket_mix_v1"
    assert m2["six"] == [31, 73, 78, 71, 39, 67]
    seats = {s["seat"]: s["number"] for s in m2["seats"]}
    assert seats["①"] == 31
    assert seats["②"] == 73
    assert seats["③"] == 78  # 并列靠后
    assert seats["④"] == 71
    assert seats["⑤"] == 39  # 刚开非同源动量最高
    assert seats["⑥"] == 67  # 并列取小号
    assert len(m2["pairs"]) >= 2
