# -*- coding: utf-8 -*-
"""
选二 K 线形态与反向排雷引擎 (K-Line Pick-2 Engine)

借鉴 K 线形态图解思路并去伪存真：
1. 将 C(80,2)=3160 对选二组合的「近10期命中总和(0~20)」翻译为收盘价，每5期合成一根蜡烛（含双中成交量）。
2. 正向信号：箱体蓄势、江恩同开时间之窗、道氏量价配合、黄金分割0.382回撤。
3. 反向排雷（核心护城河）：识别 OOS 实证中显著跑输基线的坑人信号（V型反转、次级回调、上升趋势线支撑），进行主动降权避坑。
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.utils.paths import data_path

HISTORY_REL_PATH = os.path.join("storage", "raw", "kl8_history_final.txt")
BASELINE_DUAL = 0.0601


def load_chronological_draws(history_path: Optional[str] = None) -> List[Tuple[int, str, List[int]]]:
    """按期号升序加载开奖历史 [(issue, date, nums20), ...]。"""
    path = history_path or data_path(HISTORY_REL_PATH)
    if not os.path.exists(path):
        return []
    records: List[Tuple[int, str, List[int]]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"date:([^,]+),period:(\d+),numbers:([\d-]+)", line)
            if m:
                dt = m.group(1).strip()
                issue = int(m.group(2))
                nums = [int(x) for x in m.group(3).split("-") if x.isdigit() and 1 <= int(x) <= 80]
                if len(nums) == 20:
                    records.append((issue, dt, sorted(nums)))
    records.sort(key=lambda x: x[0])
    return records


def _build_pair_matrices(draws: List[Tuple[int, str, List[int]]]):
    """构建 (N, 80) 命中矩阵及 3160 对选二索引与滚动收盘价。"""
    n_draws = len(draws)
    M = np.zeros((n_draws, 80), dtype=np.int8)
    for t, (_, _, nums) in enumerate(draws):
        for v in nums:
            M[t, v - 1] = 1
    pairs_i, pairs_j = np.triu_indices(80, k=1)
    S = M[:, pairs_i] + M[:, pairs_j]  # (N, 3160), 0/1/2
    D = (S == 2).astype(np.int8)       # (N, 3160), dual-hit

    cs = np.cumsum(S, axis=0, dtype=np.int16)
    C = np.zeros_like(cs)
    if n_draws > 10:
        C[10:] = cs[10:] - cs[:-10]
        C[:10] = cs[:10]
    else:
        C[:] = cs[:]
    return M, pairs_i, pairs_j, S, D, C


def _evaluate_pair_signals_at_t(
    M: np.ndarray,
    S: np.ndarray,
    D: np.ndarray,
    C: np.ndarray,
    pairs_i: np.ndarray,
    pairs_j: np.ndarray,
    t: int,
) -> Dict[str, Any]:
    """在历史下标 t (含) 处无未来函数地评估全部 3160 对的正向与反向 K 线信号。"""
    n_pairs = len(pairs_i)
    if t < 60:
        return {
            "net_score": np.zeros(n_pairs, dtype=np.float32),
            "pos_signals": [[] for _ in range(n_pairs)],
            "neg_signals": [[] for _ in range(n_pairs)],
            "has_toxic": np.zeros(n_pairs, dtype=bool),
            "has_positive": np.zeros(n_pairs, dtype=bool),
        }

    # 1. 箱体蓄势：近 20 期收盘极差 <= 3，最新收盘 >= 5，均值 >= 4.5，近 15 期双中 >= 1
    win_c = C[t - 19 : t + 1]
    c_range = win_c.max(axis=0) - win_c.min(axis=0)
    c_mean = win_c.mean(axis=0)
    recent_d15 = D[t - 14 : t + 1].sum(axis=0)
    sig_box = (c_range <= 3) & (C[t] >= 5) & (c_mean >= 4.5) & (recent_d15 >= 1)

    # 2. 江恩同开时间之窗：近12次同开间隔中位数 <= 20，当前距上次同开间隔在 [median-2, median+2]
    sig_gann = np.zeros(n_pairs, dtype=bool)
    # 仅对近 60 期有过至少 2 次同开的组合做精确间隔计算以保证速度
    recent_d_cnt = D[max(0, t - 200) : t + 1].sum(axis=0)
    cand_gann = np.where(recent_d_cnt >= 6)[0]
    d_slice = D[: t + 1]
    for p in cand_gann:
        hit_ts = np.where(d_slice[:, p] == 1)[0]
        if len(hit_ts) >= 7:
            ivs = np.diff(hit_ts[-13:])
            med = float(np.median(ivs))
            gap = t - int(hit_ts[-1])
            if med <= 20.0 and abs(gap - med) <= 2.0:
                sig_gann[p] = True

    # 3. 合成蜡烛收盘序列用于均线与形态判断 (5期一根蜡烛，取最近12根 = 60期)
    # 蜡烛索引 k=0..11 对应 t-55, t-50, ..., t
    candle_idx = np.arange(t - 55, t + 1, 5)  # 12 个收盘点
    cc = C[candle_idx].astype(np.float32)     # (12, 3160)
    ma5 = cc[-5:].mean(axis=0)
    ma10 = cc[-10:].mean(axis=0)
    prev_ma5 = cc[-6:-1].mean(axis=0)

    # 道氏量价配合：收盘 > MA5 > MA10 且近 15 期(3根蜡烛)双中 >= 2 次
    sig_vol_price = (cc[-1] > ma5) & (ma5 > ma10) & (recent_d15 >= 2)

    # 黄金分割 0.382 回撤企稳：12 根蜡烛高低点区间 >= 4，当前收盘处于 high - 0.382*(high-low) ± 1.0
    hi12 = cc.max(axis=0)
    lo12 = cc.min(axis=0)
    fib_target = hi12 - 0.382 * (hi12 - lo12)
    sig_fib382 = ((hi12 - lo12) >= 4) & (np.abs(cc[-1] - fib_target) <= 1.0) & (cc[-1] >= cc[-2])

    # ── 反向毒药信号 (OOS z <= -2.0 坑人信号，必须避坑) ──
    # A. 形态·V型反转 (z=-2.7): 前期急跌(cc[-3] <= lo12 + 1) 后近2根快速拉升 >= 3 点且无筑底双中量能
    sig_neg_v = (cc[-3] <= lo12 + 1) & ((cc[-1] - cc[-3]) >= 3.0) & (recent_d15 == 0)

    # B. 道氏·次级回调企稳 (z=-2.0): MA5 向下拐头但收盘反抽，近15期双中 == 0
    sig_neg_pullback = (ma5 < prev_ma5) & (cc[-1] > cc[-2]) & (recent_d15 == 0)

    # C. 切线·上升趋势线支撑 (z=-2.7, lift=0.386): 连续3根缓慢抬升后缩量踩线但近15期无双中
    sig_neg_trendline = (cc[-4] < cc[-3]) & (cc[-3] < cc[-2]) & (cc[-1] <= cc[-2]) & (ma5 > ma10) & (recent_d15 == 0)

    net_score = (
        sig_box.astype(np.float32) * 2.5
        + sig_gann.astype(np.float32) * 2.0
        + sig_vol_price.astype(np.float32) * 1.5
        + sig_fib382.astype(np.float32) * 1.5
        - sig_neg_v.astype(np.float32) * 3.0
        - sig_neg_pullback.astype(np.float32) * 2.0
        - sig_neg_trendline.astype(np.float32) * 3.5
    )

    has_toxic = sig_neg_v | sig_neg_pullback | sig_neg_trendline
    has_positive = sig_box | sig_gann | sig_vol_price | sig_fib382

    return {
        "net_score": net_score,
        "sig_box": sig_box,
        "sig_gann": sig_gann,
        "sig_vol_price": sig_vol_price,
        "sig_fib382": sig_fib382,
        "sig_neg_v": sig_neg_v,
        "sig_neg_pullback": sig_neg_pullback,
        "sig_neg_trendline": sig_neg_trendline,
        "has_toxic": has_toxic,
        "has_positive": has_positive,
        "close_now": C[t],
        "recent_d15": recent_d15,
    }


def _collect_signal_labels(eval_res: Dict[str, Any], idx: int) -> Tuple[List[str], List[str]]:
    pos: List[str] = []
    neg: List[str] = []
    if eval_res["sig_box"][idx]:
        pos.append("箱体蓄势")
    if eval_res["sig_gann"][idx]:
        pos.append("江恩同开时间之窗")
    if eval_res["sig_vol_price"][idx]:
        pos.append("道氏量价配合")
    if eval_res["sig_fib382"][idx]:
        pos.append("黄金分割0.382回撤")
    if eval_res["sig_neg_v"][idx]:
        neg.append("反向坑·V型反转")
    if eval_res["sig_neg_pullback"][idx]:
        neg.append("反向坑·次级回调")
    if eval_res["sig_neg_trendline"][idx]:
        neg.append("反向坑·上升趋势线")
    return pos, neg


def get_pair_kline_chart(
    a: int,
    b: int,
    num_candles: int = 60,
    history_path: Optional[str] = None,
) -> Dict[str, Any]:
    """返回任意选二组合 (a, b) 的 5 期蜡烛 K 线、MA5/MA10、双中成交量与信号明细。"""
    if not (1 <= a <= 80 and 1 <= b <= 80 and a != b):
        return {"status": "error", "message": "号码必须在 1-80 之间且不能相同"}
    x, y = (a, b) if a < b else (b, a)
    draws = load_chronological_draws(history_path)
    if len(draws) < 15:
        return {"status": "error", "message": "历史期数不足"}

    M, pairs_i, pairs_j, S, D, C = _build_pair_matrices(draws)
    match = np.where((pairs_i == x - 1) & (pairs_j == y - 1))[0]
    p_idx = int(match[0])

    n_draws = len(draws)
    t = n_draws - 1
    eval_res = _evaluate_pair_signals_at_t(M, S, D, C, pairs_i, pairs_j, t)
    pos, neg = _collect_signal_labels(eval_res, p_idx)

    # 每 5 期合成一根蜡烛（对齐最新一期）
    end_idx = n_draws
    start_idx = max(0, end_idx - num_candles * 5)
    rem = (end_idx - start_idx) % 5
    start_idx += rem

    candles = []
    closes = []
    for s_i in range(start_idx, end_idx, 5):
        e_i = s_i + 5
        seg_c = C[s_i:e_i, p_idx]
        seg_d = D[s_i:e_i, p_idx]
        o_v = int(seg_c[0])
        c_v = int(seg_c[-1])
        h_v = int(seg_c.max())
        l_v = int(seg_c.min())
        vol = int(seg_d.sum())
        closes.append(c_v)
        ma5 = round(float(np.mean(closes[-5:])), 2) if len(closes) >= 5 else None
        ma10 = round(float(np.mean(closes[-10:])), 2) if len(closes) >= 10 else None
        candles.append({
            "period_range": f"{draws[s_i][0]}~{draws[e_i - 1][0]}",
            "end_period": draws[e_i - 1][0],
            "open": o_v,
            "close": c_v,
            "low": l_v,
            "high": h_v,
            "volume": vol,
            "ma5": ma5,
            "ma10": ma10,
        })

    total_dual = int(D[:, p_idx].sum())
    total_any1 = int((S[:, p_idx] >= 1).sum())
    return {
        "status": "success",
        "pair": [x, y],
        "latest_issue": draws[-1][0],
        "target_issue": draws[-1][0] + 1,
        "close_now": int(C[-1, p_idx]),
        "dual_hits_total": total_dual,
        "any1_rate": round(total_any1 / n_draws, 4),
        "net_score": round(float(eval_res["net_score"][p_idx]), 2),
        "positive_signals": pos,
        "toxic_signals": neg,
        "candles": candles,
    }


def get_kline_risk_map(
    candidate_pairs: Optional[List[Tuple[int, int]]] = None,
    history_path: Optional[str] = None,
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """供 PairSelector 快速调用的轻量接口：返回候选组合的 K 线正/负信号标签。"""
    draws = load_chronological_draws(history_path)
    if len(draws) < 65:
        return {}
    M, pairs_i, pairs_j, S, D, C = _build_pair_matrices(draws)
    eval_res = _evaluate_pair_signals_at_t(M, S, D, C, pairs_i, pairs_j, len(draws) - 1)

    result: Dict[Tuple[int, int], Dict[str, Any]] = {}
    if candidate_pairs:
        for a, b in candidate_pairs:
            x, y = (a, b) if a < b else (b, a)
            match = np.where((pairs_i == x - 1) & (pairs_j == y - 1))[0]
            if len(match) == 0:
                continue
            idx = int(match[0])
            pos, neg = _collect_signal_labels(eval_res, idx)
            result[(x, y)] = {
                "net_score": float(eval_res["net_score"][idx]),
                "has_toxic": bool(eval_res["has_toxic"][idx]),
                "has_positive": bool(eval_res["has_positive"][idx]),
                "positive_signals": pos,
                "toxic_signals": neg,
            }
    return result


def get_kline_summary(
    oos_window: int = 200,
    history_path: Optional[str] = None,
) -> Dict[str, Any]:
    """生成 K 线选二形态总览：Top10 健康精选、Top10 反向避坑警示、近200期 OOS 避坑对比。"""
    draws = load_chronological_draws(history_path)
    if len(draws) < 65:
        return {"status": "error", "message": "历史开奖数据不足"}

    M, pairs_i, pairs_j, S, D, C = _build_pair_matrices(draws)
    n_draws = len(draws)
    t_now = n_draws - 1
    eval_now = _evaluate_pair_signals_at_t(M, S, D, C, pairs_i, pairs_j, t_now)
    net_scores = eval_now["net_score"]

    # Top 10 正向健康组合
    top_pos_idx = np.argsort(net_scores)[::-1][:10]
    top_positive: List[Dict[str, Any]] = []
    for idx in top_pos_idx:
        i_idx = int(idx)
        a, b = int(pairs_i[i_idx] + 1), int(pairs_j[i_idx] + 1)
        pos, neg = _collect_signal_labels(eval_now, i_idx)
        any1_rate = float((S[:, i_idx] >= 1).mean())
        top_positive.append({
            "pair": [a, b],
            "net_score": round(float(net_scores[i_idx]), 2),
            "close_now": int(C[t_now, i_idx]),
            "recent_d15": int(eval_now["recent_d15"][i_idx]),
            "any1_rate": round(any1_rate, 4),
            "positive_signals": pos,
            "toxic_signals": neg,
        })

    # Top 10 反向踩坑警示组合
    top_neg_idx = np.argsort(net_scores)[:10]
    top_toxic: List[Dict[str, Any]] = []
    for idx in top_neg_idx:
        i_idx = int(idx)
        if net_scores[i_idx] >= 0:
            break
        a, b = int(pairs_i[i_idx] + 1), int(pairs_j[i_idx] + 1)
        pos, neg = _collect_signal_labels(eval_now, i_idx)
        top_toxic.append({
            "pair": [a, b],
            "net_score": round(float(net_scores[i_idx]), 2),
            "close_now": int(C[t_now, i_idx]),
            "positive_signals": pos,
            "toxic_signals": neg,
        })

    # 近 200 期 Walk-Forward 样本外对比：正向净分 Top5 vs 反向踩坑组
    start_t = max(60, n_draws - 1 - oos_window)
    pos_dual = pos_any1 = pos_cnt = 0
    tox_dual = tox_any1 = tox_cnt = 0
    for t in range(start_t, n_draws - 1):
        ev = _evaluate_pair_signals_at_t(M, S, D, C, pairs_i, pairs_j, t)
        ns = ev["net_score"]
        next_d = D[t + 1]
        next_s = (S[t + 1] >= 1)

        p5 = np.argsort(ns)[::-1][:5]
        pos_cnt += 5
        pos_dual += int(next_d[p5].sum())
        pos_any1 += int(next_s[p5].sum())

        tox_mask = ev["has_toxic"]
        if tox_mask.any():
            tox_cnt += int(tox_mask.sum())
            tox_dual += int(next_d[tox_mask].sum())
            tox_any1 += int(next_s[tox_mask].sum())

    pos_dual_rate = pos_dual / max(1, pos_cnt)
    tox_dual_rate = tox_dual / max(1, tox_cnt)
    return {
        "status": "success",
        "total_draws": n_draws,
        "latest_issue": draws[-1][0],
        "target_issue": draws[-1][0] + 1,
        "total_pairs_scanned": len(pairs_i),
        "positive_count": int(eval_now["has_positive"].sum()),
        "toxic_count": int(eval_now["has_toxic"].sum()),
        "top_positive": top_positive,
        "top_toxic": top_toxic,
        "oos_audit": {
            "window": n_draws - 1 - start_t,
            "baseline_dual": BASELINE_DUAL,
            "pos_top5_samples": pos_cnt,
            "pos_top5_dual_hits": pos_dual,
            "pos_top5_dual_rate": round(pos_dual_rate, 4),
            "pos_top5_lift": round(pos_dual_rate / BASELINE_DUAL, 2),
            "pos_top5_any1_rate": round(pos_any1 / max(1, pos_cnt), 4),
            "toxic_samples": tox_cnt,
            "toxic_dual_hits": tox_dual,
            "toxic_dual_rate": round(tox_dual_rate, 4),
            "toxic_lift": round(tox_dual_rate / BASELINE_DUAL, 2),
        },
    }
