# -*- coding: utf-8 -*-
"""stable 号 walk-forward 评估：窗口相对目标期，杜绝 end-anchored 前视。"""


def top_freq_in_window(draws, t, window, top_n):
    """用 draws[t-window:t] 统计号码出现频次，返回 top_n 个高频号。"""
    from collections import Counter
    cnt = Counter()
    for s in draws[t - window:t]:
        cnt.update(s)
    return [n for n, _ in cnt.most_common(top_n)]


def walk_forward_stable(draws, window=20, top_n=5, min_history=30):
    """对每个可用目标期 t，用之前 window 期选高频 stable 号，评估当期命中。"""
    hits_list = []
    n_periods = 0
    for t in range(min_history, len(draws)):
        picks = top_freq_in_window(draws, t, window, top_n)
        h = len(set(picks) & draws[t])
        hits_list.append(h)
        n_periods += 1
    mean_hits = sum(hits_list) / n_periods if n_periods else 0.0
    return {
        "n_periods": n_periods,
        "mean_hits_per_period": mean_hits,
        "hits_list": hits_list,
    }


def is_lookahead_free(period_idx, window, n_periods):
    """评估期索引必须满足：窗口起点 ≥0 且 目标期 < 总数。"""
    return period_idx - window >= 0 and period_idx < n_periods