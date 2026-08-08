# kl8_stats/permutation.py
# -*- coding: utf-8 -*-
"""walk-forward 置换检验：评估预测函数是否超越随机基线。"""
import random
import re


def _parse_numbers(line):
    m = re.search(r"numbers:([\d\-]+)", line)
    if not m:
        raise ValueError(f"无法解析开奖行: {line[:80]}")
    return set(int(x) for x in m.group(1).split("-"))


def _parse_draws(draws):
    """解析开奖历史，返回 [(numbers_set), ...] 按时间升序。"""
    sets = []
    for ln in draws:
        ln = ln.strip()
        if not ln:
            continue
        sets.append(_parse_numbers(ln))
    return sets


def evaluate_lifts(pred_fn, draws, history_len=30, n_perm=200, seed=0, k=10):
    """walk-forward 评估 pred_fn 真实 lift，并与期号置换分布比较。

    pred_fn(history_lines) -> list[int] 预测 k 个号码（1..80）。
    返回 {"hits": 总命中, "n": 期数, "mean_hits": 期望命中,
          "lift": 真实命中/期望, "p_value": 置换 p 值,
          "permuted_lifts": [置换 lift 列表]}
    """
    rng = random.Random(seed)
    all_sets = _parse_draws(draws)
    if len(all_sets) < history_len + 10:
        raise ValueError(f"历史太少: {len(all_sets)} < {history_len + 10}")

    # walk-forward：用 history_len 期预测下一期
    preds = []
    actuals = []
    for t in range(history_len, len(all_sets)):
        hist = draws[t - history_len:t]
        pred = pred_fn(hist)
        if not pred:
            continue
        preds.append(set(pred))
        actuals.append(all_sets[t])

    if not preds:
        raise ValueError("pred_fn 未产生任何预测")

    n = len(preds)
    hits = sum(len(p & a) for p, a in zip(preds, actuals))
    mean_expect = sum(len(p) * 20 / 80 for p in preds)
    lift = hits / mean_expect if mean_expect > 0 else float("nan")

    # 置换：打乱 actuals 与 preds 的配对，重算 lift
    permuted_lifts = []
    for _ in range(n_perm):
        rng.shuffle(actuals)
        ph = sum(len(p & a) for p, a in zip(preds, actuals))
        if mean_expect > 0:
            permuted_lifts.append(ph / mean_expect)
    # 经验 p 值：置换 lift ≥ 真实 lift 的比例
    p_value = sum(1 for pl in permuted_lifts if pl >= lift) / len(permuted_lifts)
    return {
        "hits": hits, "n": n, "mean_hits": mean_expect, "lift": lift,
        "p_value": p_value, "permuted_lifts": permuted_lifts,
    }