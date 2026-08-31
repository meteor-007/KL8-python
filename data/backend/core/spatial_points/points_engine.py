# -*- coding: utf-8 -*-
"""
重点点位分析 (空间点位打分与精排) - 特征计算与打分引擎
================================================================
4维全可解释特征栈：
  1. 遗漏强度 gap: 距上次开出间隔（越大越接近弹簧回补）
  2. 冷热Z freq: 近 20 期出现次数 vs 全局期望（衡量活跃度）
  3. 邻区热度 reg: 点位左右±1三号区环绕近20期热度（区域能量）
  4. 邻居引力 neb: 点位周围±2邻域环绕近20期热度（引力流能）
点位得分 = 加权组合 → Sigmoid 映射到 0.50~0.65 尺度
p值 = 组合Z的标准正态近似 (stdlib math.erfc，无外部重量级依赖)
"""
import os
import re
import math
from typing import Dict, List, Any, Tuple, Optional

NUM_BALLS = 80
DEFAULT_WIN = 20  # 热度统计窗口期数
FEATURE_WEIGHTS = {"gap": 0.35, "freq": 0.20, "reg": 0.25, "neb": 0.20}


def comb(n: int, k: int) -> int:
    """组合数 C(n, k) 计算"""
    k = min(k, n - k)
    r = 1
    for i in range(k):
        r = r * (n - i) // (i + 1)
    return r


def get_region_baseline() -> float:
    """计算 3 连号区域随机至少命中 1 码的理论概率基线 (~58.35%)"""
    return 1.0 - comb(77, 20) / comb(80, 20)


def norm_z(vals: List[float]) -> List[float]:
    """Z-Score 标准化，具备防除以 0 保护"""
    if not vals:
        return []
    mu = sum(vals) / len(vals)
    sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
    return [(v - mu) / sd for v in vals]


def sigmoid(x: float) -> float:
    """标准 Sigmoid 激活函数，带防溢出截断"""
    if x > 20.0:
        return 1.0
    if x < -20.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def load_draws_from_file(history_path: str) -> List[Dict[str, Any]]:
    """
    从 kl8_history_final.txt 加载开奖历史记录并按期号升序排序
    """
    draws = []
    if not os.path.exists(history_path):
        return draws

    with open(history_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line)
            if not m:
                continue
            nums = set(int(x) for x in m.group(3).split("-") if x.isdigit())
            if len(nums) == 20:
                draws.append({
                    "period": int(m.group(2)),
                    "date": m.group(1),
                    "nums": nums,
                    "sorted_nums": sorted(list(nums))
                })

    draws.sort(key=lambda d: d["period"])
    return draws


def calculate_spatial_point_features(
    draws: List[Dict[str, Any]],
    cutoff_idx: Optional[int] = None,
    win: int = DEFAULT_WIN,
    weights: Optional[Dict[str, float]] = None
) -> Dict[int, Dict[str, Any]]:
    """
    计算截至 cutoff_idx（不含 cutoff_idx 当期，严格无未来泄露）的 80 点位空间特征
    """
    if cutoff_idx is None:
        cutoff_idx = len(draws)
    
    w = weights or FEATURE_WEIGHTS
    hist_nums = [d["nums"] for d in draws[:cutoff_idx]]
    n_hist = len(hist_nums)
    recent = range(max(0, n_hist - win), n_hist)

    def feats_of(n: int) -> Tuple[int, int, int, int]:
        appears = [i for i, s in enumerate(hist_nums) if n in s]
        gap = (n_hist - appears[-1]) if appears else n_hist
        freq = sum(1 for i in recent if n in hist_nums[i])
        
        # n-1, n, n+1 环绕
        reg = [(n - 2) % NUM_BALLS + 1, n, n % NUM_BALLS + 1]
        reg_h = sum(1 for i in recent for m in reg if m in hist_nums[i])
        
        # n-2, n-1, n+1, n+2 邻居
        neb = (
            [(n + d - 1) % NUM_BALLS + 1 for d in (1, 2)] +
            [(n - d - 1) % NUM_BALLS + 1 for d in (1, 2)]
        )
        neb_h = sum(1 for i in recent for m in neb if m in hist_nums[i])
        return gap, freq, reg_h, neb_h

    f_dict = {n: feats_of(n) for n in range(1, NUM_BALLS + 1)}
    
    gz = norm_z([f_dict[n][0] for n in f_dict])
    fz = norm_z([f_dict[n][1] for n in f_dict])
    rz = norm_z([f_dict[n][2] for n in f_dict])
    nz = norm_z([f_dict[n][3] for n in f_dict])

    points_data = {}
    for n in range(1, NUM_BALLS + 1):
        idx0 = n - 1
        raw_z = (
            w["gap"] * gz[idx0] +
            w["freq"] * fz[idx0] +
            w["reg"] * rz[idx0] +
            w["neb"] * nz[idx0]
        )
        score = 0.5 + 0.15 * sigmoid(raw_z)
        p_val = 0.5 * math.erfc(abs(raw_z) / math.sqrt(2))
        region = [(n - 2) % NUM_BALLS + 1, n, n % NUM_BALLS + 1]

        points_data[n] = {
            "num": n,
            "score": round(score, 4),
            "p_value": round(p_val, 4),
            "is_significant": p_val < 0.05,
            "region": region,
            "raw_z": round(raw_z, 4),
            "features": {
                "gap": f_dict[n][0],
                "freq": f_dict[n][1],
                "reg_heat": f_dict[n][2],
                "neb_heat": f_dict[n][3],
                "gap_z": round(gz[idx0], 2),
                "freq_z": round(fz[idx0], 2),
                "reg_z": round(rz[idx0], 2),
                "neb_z": round(nz[idx0], 2),
            }
        }

    return points_data
