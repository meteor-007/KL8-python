# -*- coding: utf-8 -*-
"""
feature_extractors.py — 五大物理特征提取器 (Unified Feature Engineering Layer)
=============================================================================
【各司其职，纯内存张量流，只出特征，绝不直接猜号，彻底杜绝文本正则反解】：
  1. TimeInertiaExtractor             : 80球时序惯性连续概率张量 (DoubleLSTM多头概率 + 时序指数衰减动量)
  2. SpatialEnergyExtractor           : 80球空间高斯能量场势能 (纯物理高斯核流能 + 反过热均值回归)
  3. DiscreteRuleExtractor            : 80球离散形态规则触发向量 (90条口诀激活态 + 7路形态反弹 + 平滑基线)
  4. TopologicalCooccurrenceExtractor : 80x80 对称共现粘性矩阵与一阶 Markov 跨期转移节点势能
  5. DefenseMaskExtractor             : 80球绝对防守禁区布尔硬掩码 (全 True 安全掩码，KillSeeker 已下架)
  6. UnifiedFeatureBundle             : 强类型统一特征数据包 (带自检与字典序列化)
  7. FeatureEngineeringPipeline       : 纯内存特征工程调度流水线
  8. FeatureEngineeringLayer          : 兼容门面层 (向后兼容已有系统与主脑)
"""
from __future__ import annotations
from backend.utils.paths import get_cache_dir, get_outputs_dir

import os
import sys
import re
import math
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Set, Any, Tuple, Optional, Union

import numpy as np

NUM_TOTAL = 80


# =====================================================================
# 辅助函数：历史开奖解析与统一读取
# =====================================================================

def _get_draw_period(d: Any) -> int:
    """提取期号整数 (大白话：安全提取期号，防止脏数据搞垮系统)"""
    if d is None:
        return 0
    if hasattr(d, "period"):
        raw = d.period
    elif isinstance(d, dict):
        raw = d.get("period", 0)
    else:
        return 0

    if raw is None:
        return 0
    if isinstance(raw, (int, np.integer)) and not isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, str):
        m = re.search(r"\d+", raw)
        return int(m.group()) if m else 0
    try:
        return int(raw)
    except Exception:
        return 0


def _get_draw_nums(d: Any) -> List[int]:
    """
    提取开奖号码列表并强力清洗为纯整数列表 (大白话：把各种奇奇怪怪格式的号码全部洗成干净的整数)
    """
    if d is None:
        return []

    raw = None
    if hasattr(d, "numbers"):
        raw = d.numbers
    elif isinstance(d, dict):
        raw = d.get("nums") if d.get("nums") is not None else d.get("numbers")
    elif isinstance(d, (list, tuple, set)):
        raw = d
    else:
        return []

    if raw is None:
        return []

    if isinstance(raw, str):
        try:
            return [int(x) for x in re.findall(r"\d+", raw)]
        except Exception:
            return []
    elif isinstance(raw, (list, tuple, set)):
        clean = []
        for x in raw:
            try:
                if isinstance(x, bool):
                    continue
                elif isinstance(x, (int, np.integer)):
                    clean.append(int(x))
                elif isinstance(x, (float, np.floating)) and not math.isnan(x) and not math.isinf(x):
                    clean.append(int(x))
                elif isinstance(x, str):
                    digits = re.findall(r"\d+", x)
                    for d_str in digits:
                        clean.append(int(d_str))
            except Exception:
                pass
        return clean
    return []


def _get_draw_date(d: Any) -> str:
    """提取开奖日期字符串"""
    if d is None:
        return ""
    if hasattr(d, "date"):
        val = d.date
    elif isinstance(d, dict):
        val = d.get("date", "")
    else:
        return ""
    return str(val) if val is not None else ""


def load_historical_draws(history_file: str) -> List[Dict[str, Any]]:
    """
    加载历史开奖文本并返回升序排列的字典列表
    :param history_file: kl8_history_final.txt 路径
    :return: 升序排列的开奖列表 [{"period": int, "date": str, "nums": List[int], "nums_set": set}, ...]
    """
    draws = []
    if not os.path.exists(history_file):
        return draws

    with open(history_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line_str)
            if not m:
                continue
            nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
            if len(nums) == 20:
                draws.append({
                    "period": int(m.group(2)),
                    "date": m.group(1),
                    "nums": sorted(nums),
                    "nums_set": set(nums)
                })

    draws.sort(key=lambda d: d["period"])
    return draws


# =====================================================================
# 抽象基类：BaseFeatureExtractor
# =====================================================================

class BaseFeatureExtractor(ABC):
    """快乐8物理特征提取器抽象基类 (Base Physical Feature Extractor)"""

    @abstractmethod
    def extract(self, draws: List[Any], target_period: int, **hyperparams) -> Any:
        """
        纯内存无状态特征提取方法 (严禁未来数据)
        :param draws: 升序排列的完整历史开奖数据列表
        :param target_period: 待解算的目标期号 (int)
        :param hyperparams: 支持反向自进化微调的超参数字典
        :return: 规范化的特征张量/矩阵/掩码
        """
        pass


# =====================================================================
# 1. 时序惯性张量提取器 (TimeInertiaExtractor)
# =====================================================================

class TimeInertiaExtractor(BaseFeatureExtractor):
    """
    时序惯性张量特征提取器 (TimeInertiaExtractor)
    大白话：看号码的时间连贯性与冷热势头。
    结合 DoubleLSTM 多头连续转移概率与指数衰减时序动量，纯内存输出 80 维连续概率张量。
    """

    def __init__(self, data_root: Optional[str] = None, model_dir: Optional[str] = None):
        self.data_root = data_root or os.getcwd()
        self.model_dir = model_dir or os.path.join(get_cache_dir(), "models")
        self._model: Optional[Any] = None
        self._model_loaded: bool = False

    def _get_model(self) -> Optional[Any]:
        """Lazy 懒加载 DoubleLSTM 模型权重，常驻内存避免重复 I/O"""
        if self._model_loaded:
            return self._model

        self._model_loaded = True
        candidate_paths = [
            os.path.join(self.model_dir, "best_model.pt"),
            os.path.join(get_outputs_dir(), "models", "best_model.pt"),
            os.path.join(get_cache_dir(), "models", "best_model.pt"),
            os.path.join(self.data_root, "models", "lstm", "cache", "best_model.pt"),
        ]

        model_path = None
        for p in candidate_paths:
            if os.path.exists(p):
                model_path = p
                break

        if not model_path:
            return None

        try:
            from models.lstm.lstm_model import DoubleLSTM
            ck = torch.load(model_path, map_location="cpu")
            mdl = DoubleLSTM(n_in=80, hidden=64, layers=2, dropout=0.3)
            state_dict = ck["state"] if isinstance(ck, dict) and "state" in ck else ck
            mdl.load_state_dict(state_dict)
            mdl.eval()
            self._model = mdl
            return self._model
        except Exception:
            return None

    def extract(
        self,
        draws: List[Any],
        target_period: int,
        lambda_decay: float = 0.95,
        alpha_momentum: float = 0.15,
        seq_len: int = 30,
        **kwargs
    ) -> np.ndarray:
        """
        提取 80 维连续时序概率张量
        :param draws: 历史开奖列表
        :param target_period: 待预测目标期号
        :param lambda_decay: 时序半衰衰减率 (默认 0.95, 范围 [0.85, 0.98])
        :param alpha_momentum: 动量融合权重 (默认 0.15)
        :param seq_len: LSTM 时序回溯窗口 (默认 30 期)
        :return: np.ndarray, shape: (80,), float64, 值域: [0.0, 1.0]
        """
        # 1. 严格过滤未来信息 (Period < target_period)
        valid_draws = [d for d in draws if _get_draw_period(d) < int(target_period)]
        if not valid_draws:
            return np.zeros(NUM_TOTAL, dtype=np.float64)

        # 2. 计算指数衰减时序动量 (保底与短程微调基底)
        hist_recent = valid_draws[-15:]
        n_hist = len(hist_recent)
        f_momentum = np.zeros(NUM_TOTAL, dtype=np.float64)
        for i, d in enumerate(hist_recent):
            weight = math.pow(lambda_decay, n_hist - 1 - i)
            for num in _get_draw_nums(d):
                if 1 <= num <= NUM_TOTAL:
                    f_momentum[num - 1] += weight

        max_mom = np.max(f_momentum)
        f_momentum_norm = (f_momentum / max_mom) if max_mom > 0 else np.full(NUM_TOTAL, 0.5, dtype=np.float64)

        # 3. DoubleLSTM 纯内存前向推断 (未截断 80 维多头概率)
        f_lstm_norm = None
        if len(valid_draws) >= seq_len:
            model = self._get_model()
            if model is not None:
                try:
                    seq_draws = valid_draws[-seq_len:]
                    x = np.zeros((1, seq_len, NUM_TOTAL), dtype=np.float32)
                    for t_idx, d in enumerate(seq_draws):
                        for num in _get_draw_nums(d):
                            if 1 <= num <= NUM_TOTAL:
                                x[0, t_idx, num - 1] = 1.0

                    with torch.no_grad():
                        inp = torch.from_numpy(x)
                        ball, zone, tail = model(inp)

                    p = ball[0].cpu().numpy().astype(np.float64)
                    z_raw = zone[0].cpu().numpy().astype(np.float64)
                    t_raw = tail[0].cpu().numpy().astype(np.float64)

                    # 分区与尾数平滑增益
                    z_adj = np.clip(z_raw * 4.0, 0.96, 1.04)
                    t_adj = np.clip(t_raw * 2.0, 0.96, 1.04)
                    zone_mult = np.array([z_adj[(n - 1) // 10] for n in range(1, NUM_TOTAL + 1)])
                    tail_mult = np.array([t_adj[n % 10] for n in range(1, NUM_TOTAL + 1)])

                    fused = p * zone_mult * tail_mult
                    min_f, max_f = np.min(fused), np.max(fused)
                    if max_f > min_f:
                        f_lstm_norm = (fused - min_f) / (max_f - min_f)
                    else:
                        f_lstm_norm = fused
                except Exception:
                    f_lstm_norm = None

        # 4. 融合输出或平滑 Fallback 降级
        if f_lstm_norm is not None:
            f_time = (1.0 - alpha_momentum) * f_lstm_norm + alpha_momentum * f_momentum_norm
        else:
            f_time = f_momentum_norm

        # 5. 数值合法性与归一化加固
        f_time = np.nan_to_num(f_time, nan=0.5, posinf=1.0, neginf=0.0)
        min_v, max_v = np.min(f_time), np.max(f_time)
        if max_v > min_v:
            f_time = (f_time - min_v) / (max_v - min_v)
        elif max_v > 0:
            f_time = f_time / max_v

        # 保证最大值为 1.0 (若存在正数)
        if np.any(f_time > 0) and np.max(f_time) > 0:
            f_time = f_time / np.max(f_time)

        return np.clip(f_time, 0.0, 1.0).astype(np.float64)


# =====================================================================
# 2. 空间能量密度势能提取器 (SpatialEnergyExtractor)
# =====================================================================

class SpatialEnergyExtractor(BaseFeatureExtractor):
    """
    空间能量密度势能提取器 (SpatialEnergyExtractor)
    大白话：看号码在 1-80 空间上的抱团扎堆热度与高斯弥散势能。
    纯物理高斯核矩阵卷积 + 反过热均值回归惩罚。
    """

    def __init__(self, num_total: int = NUM_TOTAL):
        self.num_total = num_total

    def extract(
        self,
        draws: List[Any],
        target_period: int,
        sigma: float = 2.50,
        window: int = 5,
        apply_overheating: bool = True,
        overheat_threshold: int = 3,
        **kwargs
    ) -> np.ndarray:
        """
        提取 80 维空间高斯能量势能向量
        :param draws: 历史开奖列表
        :param target_period: 待解算目标期号
        :param sigma: 高斯核宽参数 (默认 2.50, 支持自进化在 [1.5, 4.0] 微调)
        :param window: 局部热度考察窗口 (默认近 5 期)
        :param apply_overheating: 是否启用过热号码均值回归惩罚
        :param overheat_threshold: 过热触发阈值 (默认 >= 3 次)
        :return: np.ndarray, shape: (80,), float64, 值域: [0.0, 1.0]
        """
        # 1. 严格过滤未来数据
        valid_draws = [d for d in draws if _get_draw_period(d) < int(target_period)]
        if not valid_draws:
            return np.zeros(self.num_total, dtype=np.float64)

        # 2. 截取最近 window 期历史
        hist = valid_draws[-window:] if len(valid_draws) >= window else valid_draws
        w_len = len(hist)

        # 3. 计算过热均值回归惩罚乘数 (火久必冷)
        hit_counts = np.zeros(self.num_total, dtype=np.int32)
        for d in hist:
            for n in _get_draw_nums(d):
                if 1 <= n <= self.num_total:
                    hit_counts[n - 1] += 1

        penalty = np.ones(self.num_total, dtype=np.float64)
        if apply_overheating:
            for idx in range(self.num_total):
                c = hit_counts[idx]
                if c >= overheat_threshold:
                    penalty[idx] = math.exp(- (c - overheat_threshold + 1) * 0.40)

        # 4. 构造加权点源激活向量 a (80,)
        a = np.zeros(self.num_total, dtype=np.float64)
        for d_idx, d in enumerate(hist):
            # 时间衰减权重: 越新权重越大
            w_time = math.pow(0.80, w_len - 1 - d_idx)
            for n in _get_draw_nums(d):
                if 1 <= n <= self.num_total:
                    idx = n - 1
                    a[idx] += w_time * penalty[idx]

        # 5. 高性能向量化高斯核卷积 (80x80 核矩阵点乘 a)
        coords = np.arange(self.num_total, dtype=np.float64)
        dist_sq = (coords[:, None] - coords[None, :]) ** 2  # shape (80, 80)
        safe_sigma = max(0.1, float(sigma))
        K = np.exp(- dist_sq / (2.0 * (safe_sigma ** 2)))   # 高斯核矩阵

        V = K @ a  # 矩阵-向量乘法 shape (80,)

        # 6. 平滑归一化到 [0.0, 1.0]
        min_v = np.min(V)
        max_v = np.max(V)
        if max_v > min_v:
            f_space = (V - min_v) / (max_v - min_v)
        elif max_v > 0:
            f_space = V / max_v
        else:
            f_space = np.full(self.num_total, 0.5, dtype=np.float64)

        f_space = np.nan_to_num(f_space, nan=0.5, posinf=1.0, neginf=0.0)

        # 确保最大值为 1.0 (若存在正数)
        if np.any(f_space > 0) and np.max(f_space) > 0:
            f_space = f_space / np.max(f_space)

        return np.clip(f_space, 0.0, 1.0).astype(np.float64)


# =====================================================================
# 3. 离散形态规则向量提取器 (DiscreteRuleExtractor)
# =====================================================================

class DiscreteRuleExtractor(BaseFeatureExtractor):
    """
    离散形态规则向量提取器 (DiscreteRuleExtractor)
    大白话：经典老经验与形态出击。
    纯内存计算 90 条口诀触发态 + 7路形态反弹，输出 80 维标准化激活特征。
    """

    def __init__(self, rules_path: Optional[str] = None):
        self.rules_path = rules_path or self._get_default_rules_path()
        self.rules = self._load_rules(self.rules_path)

    def _get_default_rules_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        candidates = [
            os.path.join(base_dir, "backend", "modules", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(base_dir, "modules", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(os.getcwd(), "backend", "modules", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(base_dir, "backend", "core", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(base_dir, "core", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(os.getcwd(), "backend", "core", "formula_jingle", "rules", "口诀表_stats.json"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return candidates[0]

    def _load_rules(self, path: str) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("rules", {})
        except Exception:
            return {}

    def extract(
        self,
        draws: List[Any],
        target_period: int,
        rule_weights: Optional[Dict[str, float]] = None,
        smooth_eps: float = 0.05,
        **kwargs
    ) -> np.ndarray:
        """
        纯内存提取 80 维规则激发特征向量
        :param draws: 历史开奖列表
        :param target_period: 待解算目标期号
        :param rule_weights: M3 自进化动态规则权重字典 {"1": 1.2, "2": 0.8, ...}
        :param smooth_eps: 无规则触发时的平滑底噪基线
        :return: np.ndarray, shape: (80,), float64, 范围: [0.0, 1.0]
        """
        f_rule = np.zeros(NUM_TOTAL, dtype=np.float64)
        valid_draws = [d for d in draws if _get_draw_period(d) < int(target_period)]
        if not valid_draws:
            return np.zeros(NUM_TOTAL, dtype=np.float64)

        last_draw_set = set(_get_draw_nums(valid_draws[-1]))

        # 1. 纯内存扫描 90 条口诀触发态
        for rid, r in self.rules.items():
            trigger = set(r.get("trigger", []))
            if trigger and trigger.issubset(last_draw_set):
                # 动态权重：优先读取 M3 自进化更新的权重，否则采用 lift_oof 初始赋权
                w_dynamic = rule_weights.get(rid, 1.0) if rule_weights else 1.0
                lift_oof = float(r.get("lift_oof", 1.0))
                rule_power = w_dynamic * math.log(1.0 + max(0.1, lift_oof))

                for p_num in r.get("predict", []):
                    if 1 <= p_num <= NUM_TOTAL:
                        f_rule[p_num - 1] += rule_power

        # 2. 融合 7 路轻量形态反弹信号 (重码、隔期、遗漏回补、连号扩散)
        if len(valid_draws) >= 4:
            prev_set = set(_get_draw_nums(valid_draws[-2]))
            p2_set = set(_get_draw_nums(valid_draws[-3]))
            p3_set = set(_get_draw_nums(valid_draws[-4]))

            # 计算各号码最近出现位置 (近 15 期遗漏)
            last_pos = {}
            recent_15 = valid_draws[-15:]
            for idx, d in enumerate(recent_15):
                for n in _get_draw_nums(d):
                    last_pos[n] = len(recent_15) - 1 - idx

            for n in range(1, NUM_TOTAL + 1):
                idx = n - 1
                gap = last_pos.get(n, 99)
                # 遗漏回补 (3-6期温号)
                if 3 <= gap <= 6:
                    f_rule[idx] += 0.15
                # 重码连庄
                if n in last_draw_set and n not in prev_set:
                    f_rule[idx] += 0.25
                # 隔 1 期回补
                if n in prev_set and n not in last_draw_set:
                    f_rule[idx] += 0.20
                # 隔 2 期回补
                if n in p2_set and n not in prev_set and n not in last_draw_set:
                    f_rule[idx] += 0.10
                # 连号邻居能量外溢 (±1 号码上期开出)
                left_n = (n - 2) % NUM_TOTAL + 1
                right_n = n % NUM_TOTAL + 1
                if left_n in last_draw_set or right_n in last_draw_set:
                    f_rule[idx] += 0.15

        # 3. 平滑基线注入与归一化
        f_rule = f_rule + smooth_eps
        max_val = np.max(f_rule)
        if max_val > 0:
            f_rule = f_rule / max_val
        else:
            f_rule = np.full(NUM_TOTAL, 0.5, dtype=np.float64)

        return np.clip(f_rule, 0.0, 1.0).astype(np.float64)


# =====================================================================
# 4. 拓扑共现与跟随粘性矩阵提取器 (TopologicalCooccurrenceExtractor)
# =====================================================================

class TopologicalCooccurrenceExtractor(BaseFeatureExtractor):
    """
    拓扑共现与跟随粘性提取器 (TopologicalCooccurrenceExtractor)
    大白话：找跟班与找连体搭档。
    纯内存计算 Markov 一阶跨期转移节点势能 F_topo 与 80x80 对称双元共现粘性矩阵 M_cooccur。
    """

    def __init__(self, num_total: int = NUM_TOTAL):
        self.num_total = num_total

    def extract(
        self,
        draws: List[Any],
        target_period: int,
        window: int = 50,
        markov_alpha: float = 2.0,
        **kwargs
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        纯内存提取拓扑特征
        :param draws: 升序排列的历史开奖列表
        :param target_period: 待解算的目标期号
        :param window: 滑动窗口期数 (默认近 50 期)
        :param markov_alpha: 贝叶斯拉普拉斯平滑系数
        :return: (F_topo, M_cooccur)
                 - F_topo: shape: (80,), float64, 范围 [0.0, 1.0]
                 - M_cooccur: shape: (80, 80), float64, 严格对称, 范围 [0.0, 1.0]
        """
        f_topo = np.zeros(self.num_total, dtype=np.float64)
        m_cooccur = np.zeros((self.num_total, self.num_total), dtype=np.float64)

        valid_draws = [d for d in draws if _get_draw_period(d) < int(target_period)]
        if not valid_draws:
            return np.zeros(self.num_total, dtype=np.float64), np.zeros((self.num_total, self.num_total), dtype=np.float64)

        # 截取滑动窗口历史
        hist = valid_draws[-window:] if len(valid_draws) >= window else valid_draws
        last_nums = _get_draw_nums(hist[-1])

        # 1. 计算 80x80 对称双元共现矩阵 (找连体搭档)
        for d in hist:
            nums = sorted(_get_draw_nums(d))
            l_len = len(nums)
            for i in range(l_len):
                u = nums[i] - 1
                if 0 <= u < self.num_total:
                    m_cooccur[u, u] += 1.0  # 对角线：单号自出现频次
                    for j in range(i + 1, l_len):
                        v = nums[j] - 1
                        if 0 <= v < self.num_total:
                            m_cooccur[u, v] += 1.0
                            m_cooccur[v, u] += 1.0

        # 归一化共现矩阵到 [0, 1]
        max_cooccur = np.max(m_cooccur)
        if max_cooccur > 0:
            m_cooccur_norm = m_cooccur / max_cooccur
        else:
            m_cooccur_norm = np.eye(self.num_total, dtype=np.float64)

        # 2. 计算一阶 Markov 跨期转移概率 (找跟班)
        markov_counts = np.zeros((self.num_total, self.num_total), dtype=np.float64)
        starts = np.zeros(self.num_total, dtype=np.float64)

        # 统计 hist 中相邻两期转移
        for t in range(len(hist) - 1):
            cur_set = _get_draw_nums(hist[t])
            nxt_set = set(_get_draw_nums(hist[t + 1]))
            for u_num in cur_set:
                u_idx = u_num - 1
                if 0 <= u_idx < self.num_total:
                    starts[u_idx] += 1.0
                    for v_num in nxt_set:
                        v_idx = v_num - 1
                        if 0 <= v_idx < self.num_total:
                            markov_counts[u_idx, v_idx] += 1.0

        # 贝叶斯平滑转移概率矩阵 P(v | u)
        prior_p = 20.0 / float(self.num_total)  # 0.25
        denom = starts[:, None] + markov_alpha
        p_trans = (markov_counts + markov_alpha * prior_p) / denom

        # 3. 基于最新一期已开 20 码释放拓扑激发电位
        for last_num in last_nums:
            if 1 <= last_num <= self.num_total:
                idx = last_num - 1
                f_topo += p_trans[idx]

        # 归一化 F_topo 到 [0, 1]
        min_topo = np.min(f_topo)
        max_topo = np.max(f_topo)
        if max_topo > min_topo:
            f_topo_norm = (f_topo - min_topo) / (max_topo - min_topo)
        elif max_topo > 0:
            f_topo_norm = f_topo / max_topo
        else:
            f_topo_norm = np.full(self.num_total, 0.5, dtype=np.float64)

        return np.clip(f_topo_norm, 0.0, 1.0).astype(np.float64), m_cooccur_norm.astype(np.float64)


# =====================================================================
# 5. 绝对防守禁区掩码提取器 (DefenseMaskExtractor)
# =====================================================================

class DefenseMaskExtractor(BaseFeatureExtractor):
    """
    绝对防守禁区掩码提取器 (DefenseMaskExtractor)
    KillSeeker 已下架：不再产生杀号，恒返回全 True 安全掩码（空 killed set）。
    """

    def extract_with_meta(
        self,
        draws: List[Any],
        target_period: int,
        kill_size: int = 15,
        engine_weights: Optional[Dict[str, float]] = None,
        max_per_decade: int = 4,
        **kwargs
    ) -> Tuple[np.ndarray, List[int], Dict[str, Any]]:
        """
        纯内存提取防守掩码与元数据
        KillSeeker 已下架：不再产生杀号，恒返回全 True 安全掩码（空 killed set）。
        :return: (defense_mask, killed_numbers, meta_stats)
                 defense_mask: shape (80,), dtype=bool (全 True)
                 killed_numbers: List[int] (空列表)
                 meta_stats: 元数据
        """
        defense_mask = np.ones(NUM_TOTAL, dtype=bool)
        meta_stats = {
            "target_period": int(target_period),
            "status": "retired",
            "retired": True,
            "kill_size": 0,
            "engine_contributions": {},
        }
        return defense_mask, [], meta_stats

    def extract(
        self,
        draws: List[Any],
        target_period: int,
        kill_size: int = 15,
        engine_weights: Optional[Dict[str, float]] = None,
        max_per_decade: int = 4,
        **kwargs
    ) -> np.ndarray:
        """实现 BaseFeatureExtractor 契约：直接返回 80 维布尔硬掩码"""
        defense_mask, _, _ = self.extract_with_meta(
            draws=draws,
            target_period=target_period,
            kill_size=kill_size,
            engine_weights=engine_weights,
            max_per_decade=max_per_decade,
            **kwargs
        )
        return defense_mask


# =====================================================================
# 6. 强类型统一特征数据包 (UnifiedFeatureBundle)
# =====================================================================

@dataclass
class UnifiedFeatureBundle:
    """
    五大物理特征统一数据包 (Unified Feature Bundle)
    所有特征均为纯内存张量，严格符合数学和物理定义。
    """
    target_period: int                   # 目标解算期号 (例如 2026201)
    draw_date: str                       # 目标日期或基准日期

    # 1. 时序惯性张量 (LSTM连续概率 + 指数衰减动量)
    time_inertia: np.ndarray             # shape: (80,), float64, 范围: [0.0, 1.0]

    # 2. 空间能量密度势能 (连续高斯核流能场)
    spatial_energy: np.ndarray           # shape: (80,), float64, 范围: [0.0, 1.0]

    # 3. 离散形态规则向量 (90条口诀激活态 + 7路高压反弹形态)
    rule_activation: np.ndarray          # shape: (80,), float64, 范围: [0.0, 1.0]

    # 4. 拓扑网络激发电位 (上期20码在共现图上的牵引力)
    topological_energy: np.ndarray       # shape: (80,), float64, 范围: [0.0, 1.0]

    # 5. 二维对称共现粘性矩阵 (双元共现拓扑)
    cooccurrence_matrix: np.ndarray      # shape: (80, 80), float64, 对称矩阵

    # 6. 绝对防守禁区硬掩码 (KillSeeker 已下架，恒为全 True)
    defense_mask: np.ndarray             # shape: (80,), bool, True=安全区, False=硬雷区

    # 7. 辅助元数据与解释性字段
    killed_numbers: List[int] = field(default_factory=list)  # 杀号列表 (1-80, 长度 15-25)
    meta_info: Dict[str, Any] = field(default_factory=dict)  # 超参数、置信度等元数据

    def validate(self) -> bool:
        """
        张量形状、类型与数值边界强校验 (数据纯净性防线)
        """
        if self.time_inertia.shape != (NUM_TOTAL,):
            raise ValueError(f"time_inertia shape error: {self.time_inertia.shape}")
        if self.spatial_energy.shape != (NUM_TOTAL,):
            raise ValueError(f"spatial_energy shape error: {self.spatial_energy.shape}")
        if self.rule_activation.shape != (NUM_TOTAL,):
            raise ValueError(f"rule_activation shape error: {self.rule_activation.shape}")
        if self.topological_energy.shape != (NUM_TOTAL,):
            raise ValueError(f"topological_energy shape error: {self.topological_energy.shape}")
        if self.cooccurrence_matrix.shape != (NUM_TOTAL, NUM_TOTAL):
            raise ValueError(f"cooccurrence_matrix shape error: {self.cooccurrence_matrix.shape}")
        if self.defense_mask.shape != (NUM_TOTAL,):
            raise ValueError(f"defense_mask shape error: {self.defense_mask.shape}")
        if self.defense_mask.dtype != bool:
            raise ValueError(f"defense_mask dtype must be bool, got {self.defense_mask.dtype}")

        # 校验数值无 NaN 或 Inf
        for name, arr in [
            ("time_inertia", self.time_inertia),
            ("spatial_energy", self.spatial_energy),
            ("rule_activation", self.rule_activation),
            ("topological_energy", self.topological_energy),
            ("cooccurrence_matrix", self.cooccurrence_matrix),
        ]:
            if np.isnan(arr).any() or np.isinf(arr).any():
                raise ValueError(f"Feature tensor {name} contains NaN or Inf!")

        # 校验共现矩阵对称性
        if not np.allclose(self.cooccurrence_matrix, self.cooccurrence_matrix.T, atol=1e-8):
            raise ValueError("cooccurrence_matrix must be symmetric!")

        # 校验掩码安全点数量 (至少保留 50 个合法号码供主脑推演)
        safe_count = int(np.sum(self.defense_mask))
        if safe_count < 50 or safe_count > NUM_TOTAL:
            raise ValueError(f"Invalid safe numbers count: {safe_count} (expected >= 50)")

        return True

    def to_dict(self) -> Dict[str, Any]:
        """将特征包序列化为 JSON 兼容字典，供 Web API 和审计日志使用"""
        return {
            "target_period": int(self.target_period),
            "draw_date": str(self.draw_date),
            "time_inertia": self.time_inertia.tolist(),
            "spatial_energy": self.spatial_energy.tolist(),
            "rule_activation": self.rule_activation.tolist(),
            "topological_energy": self.topological_energy.tolist(),
            "cooccurrence_matrix": self.cooccurrence_matrix.tolist(),
            "defense_mask": self.defense_mask.tolist(),
            "killed_numbers": [int(x) for x in self.killed_numbers],
            "safe_count": int(np.sum(self.defense_mask)),
            "meta_info": self.meta_info,
        }


# =====================================================================
# 7. 纯内存特征工程调度流水线 (FeatureEngineeringPipeline)
# =====================================================================

class FeatureEngineeringPipeline:
    """
    统一特征提取流水线 (FeatureEngineeringPipeline)
    负责调度 5 大纯内存提取器，执行数据自检并打包输出 UnifiedFeatureBundle。
    """

    def __init__(
        self,
        data_root: Optional[str] = None,
        rules_path: Optional[str] = None,
        model_dir: Optional[str] = None,
    ):
        self.data_root = data_root or os.getcwd()

        # 初始化 5 大纯内存物理提取器
        self.time_extractor = TimeInertiaExtractor(data_root=self.data_root, model_dir=model_dir)
        self.spatial_extractor = SpatialEnergyExtractor(num_total=NUM_TOTAL)
        self.rule_extractor = DiscreteRuleExtractor(rules_path=rules_path)
        self.topo_extractor = TopologicalCooccurrenceExtractor(num_total=NUM_TOTAL)
        self.defense_extractor = DefenseMaskExtractor()

    def extract_bundle(
        self,
        draws: List[Any],
        target_period: int,
        hyperparams: Optional[Dict[str, Any]] = None,
    ) -> UnifiedFeatureBundle:
        """
        对目标期号提取全量五大物理特征并打包
        :param draws: 升序排列的历史开奖数据
        :param target_period: 待解算的目标期号
        :param hyperparams: 自进化内核传入的可调超参数
        :return: UnifiedFeatureBundle
        """
        hp = hyperparams or {}

        # 1. 提取超参数 (若未提供则使用默认值)
        lambda_decay = float(hp.get("lambda_decay", 0.95))
        sigma = float(hp.get("sigma", 2.50))
        rule_weights = hp.get("rule_weights", None)
        topo_window = int(hp.get("topo_window", 50))
        kill_size = int(hp.get("kill_size", 15))
        engine_weights = hp.get("kill_engine_weights", None)

        # 2. 纯内存提取 5 大物理特征
        f_time = self.time_extractor.extract(draws, target_period, lambda_decay=lambda_decay)
        f_space = self.spatial_extractor.extract(draws, target_period, sigma=sigma)
        f_rule = self.rule_extractor.extract(draws, target_period, rule_weights=rule_weights)
        f_topo, co_matrix = self.topo_extractor.extract(draws, target_period, window=topo_window)
        defense_mask, killed_nums, defense_meta = self.defense_extractor.extract_with_meta(
            draws, target_period, kill_size=kill_size, engine_weights=engine_weights
        )

        # 3. 确定开奖日期与上一期开奖号码元数据 (供冷热对冲审计)
        valid_draws = [d for d in draws if _get_draw_period(d) < int(target_period)]
        draw_date = _get_draw_date(valid_draws[-1]) if valid_draws else "UNKNOWN"
        last_draw_numbers = _get_draw_nums(valid_draws[-1]) if valid_draws else []

        # 4. 组装并校验数据包
        bundle = UnifiedFeatureBundle(
            target_period=int(target_period),
            draw_date=draw_date,
            time_inertia=f_time,
            spatial_energy=f_space,
            rule_activation=f_rule,
            topological_energy=f_topo,
            cooccurrence_matrix=co_matrix,
            defense_mask=defense_mask,
            killed_numbers=killed_nums,
            meta_info={
                "hyperparams": hp,
                "defense_stats": defense_meta,
                "last_draw_numbers": last_draw_numbers,
                "extracted_at": datetime.now().isoformat(),
            }
        )

        # 5. 执行数据纯净性强校验
        bundle.validate()

        return bundle


# =====================================================================
# 8. 兼容门面层 (FeatureEngineeringLayer)
# =====================================================================

class FeatureEngineeringLayer:
    """
    五大物理特征统一提取层 (兼容门面层)
    直接委托给纯内存 FeatureEngineeringPipeline，确保统一决策主脑和已有测试无缝衔接。
    """

    def __init__(self, data_root: str):
        self.data_root = data_root
        self.proj_root = os.path.dirname(data_root)
        direct_file = os.path.join(data_root, "kl8_history_final.txt")
        storage_file = os.path.join(data_root, "storage", "raw", "kl8_history_final.txt")
        if os.path.exists(direct_file):
            self.history_file = direct_file
        elif os.path.exists(storage_file):
            self.history_file = storage_file
        else:
            from backend.utils.paths import data_path
            self.history_file = data_path("kl8_history_final.txt")
        self.draws = load_historical_draws(self.history_file)
        self.pipeline = FeatureEngineeringPipeline(data_root=data_root)

    def get_draw_by_period(self, period: int) -> Optional[Dict[str, Any]]:
        for d in self.draws:
            if d["period"] == period:
                return d
        return None

    def get_history_before(self, target_period: int, window: int = 30) -> List[Dict[str, Any]]:
        valid = [d for d in self.draws if d["period"] < target_period]
        return valid[-window:] if len(valid) >= window else valid

    def extract_time_features(self, target_period: int, lambda_decay: float = 0.95) -> np.ndarray:
        """1. 时序惯性特征 F_time (80维)"""
        return self.pipeline.time_extractor.extract(self.draws, target_period, lambda_decay=lambda_decay)

    def extract_spatial_energy_features(self, target_period: int, sigma: float = 2.50) -> np.ndarray:
        """2. 空间能量特征 F_space (80维)"""
        return self.pipeline.spatial_extractor.extract(self.draws, target_period, sigma=sigma)

    def extract_discrete_rule_features(self, target_period: int, rule_weights: Optional[Dict[str, float]] = None) -> np.ndarray:
        """3. 离散形态规则特征 F_rule (80维)"""
        return self.pipeline.rule_extractor.extract(self.draws, target_period, rule_weights=rule_weights)

    def extract_topological_cooccurrence(self, target_period: int, window: int = 50) -> Tuple[np.ndarray, np.ndarray]:
        """4. 拓扑共现特征与搭档粘性矩阵 F_topo (80维) & M_cooccur (80x80)"""
        return self.pipeline.topo_extractor.extract(self.draws, target_period, window=window)

    def extract_defense_mask(self, target_period: int, kill_size: int = 15) -> np.ndarray:
        """5. 硬防守禁区掩码 F_mask (80维 boolean, True=安全区, False=硬雷区一票否决)"""
        return self.pipeline.defense_extractor.extract(self.draws, target_period, kill_size=kill_size)

    def extract_bundle(self, target_period: int, hyperparams: Optional[Dict[str, Any]] = None) -> UnifiedFeatureBundle:
        """提取全量统一特征数据包"""
        return self.pipeline.extract_bundle(self.draws, target_period, hyperparams=hyperparams)
