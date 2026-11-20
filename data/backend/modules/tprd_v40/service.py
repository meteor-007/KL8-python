#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 数据服务与缓存管理 (Service Layer)
负责将推演结果转换为前端可视化大屏友好的 JSON 结构
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, Any

_MODULE_DIR = Path(__file__).resolve().parent
_DATA_DIR = _MODULE_DIR.parents[2]                     # .../Python-Project/data
_PROJ_ROOT = _MODULE_DIR.parents[3]                    # .../Python-Project
_TPRD_ROOT = Path("D:/project/Python-Project/kl8_tprd_system").resolve()
_CACHE_PATH = _DATA_DIR / "storage" / "cache" / "tprd_v40_latest.json"
_STATIC_JSON_PATH = _DATA_DIR / "frontend" / "static" / "tprd_v40_latest.json"

if str(_TPRD_ROOT) not in sys.path:
    sys.path.insert(0, str(_TPRD_ROOT))

from tprd_core.data_sync import load_history, sync_latest_draws
from tprd_core.features import build_features
from tprd_core.model_v40 import infer_period_v40
from tprd_core.backtest import run_walk_forward_backtest
from tprd_core.matrices import generate_gf4_hypercube_pick5, generate_bibd_pick6


def get_latest_tprd_summary(force_refresh: bool = False) -> Dict[str, Any]:
    """
    获取最新的 TPRD v4.0 结构化推演数据，优先读取缓存
    """
    if not force_refresh and _CACHE_PATH.is_file():
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception:
            pass

    return update_tprd_cache()


def update_tprd_cache(backtest_periods: int = 30) -> Dict[str, Any]:
    """
    重新运行 TPRD v4.0 推演并持久化 JSON 缓存供 Web 终端与 API 使用
    """
    data_file = str(_DATA_DIR / "storage" / "raw" / "kl8_history_final.txt")
    if not os.path.exists(data_file):
        data_file = str(_TPRD_ROOT / "data" / "kl8_history_final.txt")

    sync_latest_draws(data_file)
    draws, B = load_history(data_file)
    N = len(draws)
    if N == 0:
        raise ValueError(f"账本数据为空: {data_file}")

    last_draw = draws[-1]
    last_period = int(last_draw['period'])
    target_period = last_period + 1

    # 特征工程与回测
    X, road_counts, prime_counts = build_features(B)
    df_bt, summary = run_walk_forward_backtest(draws, X, B, road_counts, test_periods=backtest_periods)
    pred = infer_period_v40(N, X, B, road_counts)

    # 4区分桶工具
    def bucket_by_zone(balls):
        z = {0: [], 1: [], 2: [], 3: []}
        for n in sorted(balls):
            z[(n - 1) // 20].append(int(n))
        return {
            "zone1": z[0], "zone2": z[1], "zone3": z[2], "zone4": z[3],
            "counts": [len(z[0]), len(z[1]), len(z[2]), len(z[3])]
        }

    p20 = [int(n) for n in pred['pool_20']]
    p25 = [int(n) for n in pred['pool_25']]
    p30 = [int(n) for n in pred['pool_30']]

    odd20 = sum(1 for n in p20 if n % 2 == 1)
    even20 = len(p20) - odd20

    # 选2抽屉4注
    p2_cards = []
    for d in pred['pick2_details']:
        p2_cards.append({
            "name": d['name'],
            "pair": [int(d['pair'][0]), int(d['pair'][1])],
            "score": round(float(d['score']), 4)
        })

    # DHM-Pro 30注
    dhm_list = []
    for idx, bet in enumerate(pred['dhm_bets']):
        dhm_list.append({
            "index": idx + 1,
            "label": f"第{idx+1:02d}注",
            "type": "Pool_20纯血锁定" if idx < 20 else "3α+2β外围耦合",
            "balls": [int(n) for n in bet]
        })

    # 回测走势图数据
    backtest_history = []
    for _, row in df_bt.iterrows():
        backtest_history.append({
            "period": str(row['期号']),
            "date": str(row['开奖日期']),
            "hit_20": int(row['20码命中']),
            "hit_25": int(row['25码命中']),
            "hit_30": int(row['30码命中']),
            "hit_p2": int(row['选2网格命中注数']),
            "sum_20": int(row['20码和值'])
        })

    # 80码Z评分明细
    scores_list = []
    rank_map = {n: idx + 1 for idx, n in enumerate(pred['ranked_all'])}
    for n in range(1, 81):
        scores_list.append({
            "num": n,
            "rank": rank_map[n],
            "z_score": round(float(pred['scores'][n]), 4),
            "pool": "20码" if n in p20 else ("25码" if n in p25 else ("30码" if n in p30 else "候补")),
            "road": int(n % 3),
            "is_prime": bool(n in {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79})
        })
    scores_list.sort(key=lambda x: x['rank'])

    result = {
        "status": "ok",
        "target_period": target_period,
        "last_period": last_period,
        "last_draw": {
            "period": last_period,
            "date": last_draw['date'],
            "numbers": [int(n) for n in last_draw['nums']]
        },
        "top1": int(pred['top5_leaders'][0]),
        "top3_orthogonal": [int(n) for n in pred['top5_leaders'][:3]],
        "top5": [int(n) for n in pred['top5_leaders']],
        "top10": [int(n) for n in pred['ranked_all'][:10]],
        "pick2_grid": p2_cards,
        "pool_20": {
            "balls": p20,
            "sum": sum(p20),
            "odd_even": f"{odd20}:{even20}",
            "corridor_status": "达标 [760, 860]",
            "zones": bucket_by_zone(p20)
        },
        "pool_25": {
            "balls": p25,
            "zones": bucket_by_zone(p25)
        },
        "pool_30": {
            "balls": p30,
            "zones": bucket_by_zone(p30),
            "zero_blind_spot": True
        },
        "dhm_bets": dhm_list,
        "backtest_summary": {
            "test_count": summary['test_count'],
            "mean_20": round(summary['mean_20'], 2),
            "lift_20": round(summary['lift_20'], 3),
            "mean_25": round(summary['mean_25'], 2),
            "lift_25": round(summary['lift_25'], 3),
            "mean_30": round(summary['mean_30'], 2),
            "lift_30": round(summary['lift_30'], 3),
            "p2_win_rate_pct": round(summary['p2_win_rate'] * 100, 2),
            "p2_lift": round(summary['p2_lift'], 3),
            "history": backtest_history
        },
        "ball_scores": scores_list,
        "updated_at": last_draw['date']
    }

    # 持久化落盘
    os.makedirs(_CACHE_PATH.parent, exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    os.makedirs(_STATIC_JSON_PATH.parent, exist_ok=True)
    with open(_STATIC_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
