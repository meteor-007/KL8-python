# -*- coding: utf-8 -*-
"""
快乐8 决策树驱动的 012路 × 质合特征推演与智能缩水系统核心引擎 (TPRD Engine v1.0)
================================================================================
【业务背景与架构定位】:
本模块基于机器学习可解释决策树（DecisionTree）与随机森林（RandomForest / AI海选团），
将快乐8全盘80码的「012路余数守恒」与「质数合数空间正交性」融合为高信噪比特征工坊，
实现全自动的大盘宏观偏态量化、微观动力学打分与高胜率正交剪枝缩水。

【主要计算流转】:
  // 步骤 1: 物理构建 80 码六维正交子池 (0路质/0路合/1路质/1路合/2路质/2路合)
  // 步骤 2: 滑动窗口提取 12 维时序、微观与宏观特征矩阵 (X, y)
  // 步骤 3: 训练可解释决策树与随机森林海选团，计算特征重要性与高胜率决策路径
  // 步骤 4: 预测下期 80 码出号胜率概率 (Probability Ranking)
  // 步骤 5: 执行六维正交配额剪枝，生成 28~30 码黄金实战大底
  // 步骤 6: 萃取尖刀三胆 (Top3)、主力五胆 (Top5) 与跨路对冲选2搭档

@author Antigravity Quant Team
@since 2026-10-23
"""

from __future__ import annotations

import os
import sys
import math
import logging
from typing import Dict, List, Set, Tuple, Any, Optional

import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.ensemble import RandomForestClassifier

logger = logging.getLogger("k8quant.road_prime_shrink")

# ─────────────────────────────────────────────────────────────────────────────
# 常量与六维正交子池定义
# ─────────────────────────────────────────────────────────────────────────────
TOTAL_BALLS = 80
TRAIN_WINDOW_DEFAULT = 120

# 1~80 标准 22 个质数清单
PRIMES_SET: Set[int] = {
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
    53, 59, 61, 67, 71, 73, 79
}

# 80 码六维正交子池 (互不相交且和为80)
POOL_0_PRIME: List[int] = [3]  # 0路质数仅此独苗
POOL_0_COMPOSITE: List[int] = [
    6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39,
    42, 45, 48, 51, 54, 57, 60, 63, 66, 69, 72, 75, 78
]
POOL_1_PRIME: List[int] = [7, 13, 19, 31, 37, 43, 61, 67, 73, 79]
POOL_1_COMPOSITE: List[int] = [
    1, 4, 10, 16, 22, 25, 28, 34, 40, 46, 49, 52, 55, 58, 64, 70, 76
]
POOL_2_PRIME: List[int] = [2, 5, 11, 17, 23, 29, 41, 47, 53, 59, 71]
POOL_2_COMPOSITE: List[int] = [
    8, 14, 20, 26, 32, 35, 38, 44, 50, 56, 62, 65, 68, 74, 77, 80
]

ALL_POOLS: Dict[str, List[int]] = {
    "0路质数": POOL_0_PRIME,
    "0路合数": POOL_0_COMPOSITE,
    "1路质数": POOL_1_PRIME,
    "1路合数": POOL_1_COMPOSITE,
    "2路质数": POOL_2_PRIME,
    "2路合数": POOL_2_COMPOSITE,
}

FEATURE_COLUMNS = [
    "f_road",            # 012路 (0, 1, 2)
    "f_prime",           # 质合标记 (1=质, 0=合)
    "f_omission",        # 当前遗漏期数
    "f_elasticity",      # 遗漏弹性比 (当前遗漏 / 历史平均遗漏)
    "f_freq_recent5",    # 近5期出号频次
    "f_freq_recent15",   # 近15期出号频次
    "f_momentum",        # 动能变化率 (近5期*3 / (近15期+1))
    "f_neighbor_pull",   # 邻号牵引力 (上期在其正负1邻近圈的号码数)
    "f_repeat_last",     # 上期重号标记 (1=开出, 0=未开出)
    "f_macro_road_diff", # 大盘对应路数偏离度 (上期该路出号数 - 6.67)
    "f_macro_prime_diff",# 大盘质数扎堆偏离度 (上期质数总数 - 5.50)
    "f_zone",            # 所在分区 (1~8分区)
    "f_tail",            # 个位尾数 (0~9)
]

FEATURE_NAMES_CN = [
    "012路余数",
    "质合属性",
    "当前遗漏",
    "遗漏弹性比(憋冷程度)",
    "近5期频次",
    "近15期频次",
    "冷热动能斜率",
    "邻居牵引力(沾光度)",
    "连击重号惯性",
    "大盘路数偏离度",
    "大盘质数偏离度",
    "十分区编号",
    "号码个位尾数",
]


class TreeRoadPrimeShrinkEngine:
    """
    快乐8 决策树驱动的 012路 × 质合特征推演与智能缩水引擎
    """

    def __init__(self, history_data: List[Dict[str, Any]], train_window: int = TRAIN_WINDOW_DEFAULT):
        """
        初始化引擎实例并准备历史开奖矩阵

        :param history_data: 开奖历史列表，元素包含 'period'/'issue' 与 'numbers'
        :param train_window: 决策树训练滚动样本窗口大小，默认 120 期
        """
        self.history_data = history_data or []
        self.train_window = max(30, train_window)
        self.draws: List[List[int]] = []
        self.periods: List[str] = []
        self._prepare_data()

    def _prepare_data(self) -> None:
        """步骤 1: 清洗并按期号升序构建开奖时序矩阵"""
        cleaned = []
        for item in self.history_data:
            p = str(item.get("period", item.get("issue", "")))
            raw_nums = item.get("numbers", [])
            if isinstance(raw_nums, str):
                nums = [int(x) for x in raw_nums.replace("-", " ").replace(",", " ").split() if x.isdigit()]
            else:
                nums = [int(x) for x in raw_nums if isinstance(x, (int, str)) and str(x).isdigit()]
            if len(nums) >= 10:
                cleaned.append((p, sorted(nums)))

        # 确保按期号从小到大严格排序 (最老 -> 最新)
        cleaned.sort(key=lambda x: x[0])
        self.periods = [c[0] for c in cleaned]
        self.draws = [c[1] for c in cleaned]

    def _extract_feature_vector(
        self,
        ball: int,
        idx: int,
        macro_road_diff: Dict[int, float],
        macro_prime_diff: float,
        omission_map: Dict[int, int],
        avg_omission_map: Dict[int, float],
        freq5_map: Dict[int, int],
        freq15_map: Dict[int, int],
        last_draw_set: Set[int],
    ) -> List[float]:
        """为指定期的指定号码抽取 13 维特征向量"""
        road = ball % 3
        is_p = 1.0 if ball in PRIMES_SET else 0.0
        cur_om = omission_map.get(ball, 0)
        avg_om = avg_omission_map.get(ball, 4.0)
        elasticity = round(cur_om / max(avg_om, 1.0), 4)
        f5 = freq5_map.get(ball, 0)
        f15 = freq15_map.get(ball, 0)
        momentum = round((f5 * 3.0) / max(f15 + 1.0, 1.0), 4)

        # 邻号引力 (检查上一期其正负1位置是否出号)
        n_pull = 0
        if (ball - 1) in last_draw_set and ball > 1:
            n_pull += 1
        if (ball + 1) in last_draw_set and ball < TOTAL_BALLS:
            n_pull += 1

        repeat_last = 1.0 if ball in last_draw_set else 0.0
        m_road = macro_road_diff.get(road, 0.0)
        m_prime = macro_prime_diff
        zone = float((ball - 1) // 10 + 1)
        tail = float(ball % 10)

        return [
            float(road),
            is_p,
            float(cur_om),
            elasticity,
            float(f5),
            float(f15),
            momentum,
            float(n_pull),
            repeat_last,
            m_road,
            m_prime,
            zone,
            tail,
        ]

    def _build_training_dataset(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
        """
        步骤 2: 构建过去 train_window 期的特征矩阵与当前待预测特征向量
        """
        n_draws = len(self.draws)
        if n_draws < 20:
            raise ValueError(f"开奖历史数据量不足 (仅 {n_draws} 期)，无法进行决策树建模")

        start_t = max(20, n_draws - self.train_window)
        X_train_list = []
        y_train_list = []

        # 遍历历史各期构造训练样本 (以期 t 预测期 t 开奖情况)
        for t in range(start_t, n_draws):
            last_draw = self.draws[t - 1]
            last_draw_set = set(last_draw)
            cur_target_set = set(self.draws[t])

            # 宏观大盘偏态
            cnt_road = {0: 0, 1: 0, 2: 0}
            cnt_prime = 0
            for num in last_draw:
                cnt_road[num % 3] += 1
                if num in PRIMES_SET:
                    cnt_prime += 1
            macro_r_diff = {r: cnt_road[r] - 6.67 for r in (0, 1, 2)}
            macro_p_diff = cnt_prime - 5.50

            # 计算在期 t-1 时刻各号码的遗漏与历史平均遗漏
            om_map: Dict[int, int] = {}
            avg_om_map: Dict[int, float] = {}
            f5_map: Dict[int, int] = {b: 0 for b in range(1, TOTAL_BALLS + 1)}
            f15_map: Dict[int, int] = {b: 0 for b in range(1, TOTAL_BALLS + 1)}

            # 统计近5期与近15期
            for back_i in range(1, 16):
                if t - back_i >= 0:
                    for b in self.draws[t - back_i]:
                        f15_map[b] += 1
                        if back_i <= 5:
                            f5_map[b] += 1

            for b in range(1, TOTAL_BALLS + 1):
                # 寻找距离 t-1 最近一次开出位置
                om = 0
                while t - 1 - om >= 0 and b not in self.draws[t - 1 - om]:
                    om += 1
                om_map[b] = om

                # 估算历史平均遗漏
                total_hits = sum(1 for d in self.draws[:t] if b in d)
                avg_om_map[b] = (t / max(total_hits, 1.0)) if total_hits > 0 else 4.0

                feat = self._extract_feature_vector(
                    ball=b,
                    idx=t,
                    macro_road_diff=macro_r_diff,
                    macro_prime_diff=macro_p_diff,
                    omission_map=om_map,
                    avg_omission_map=avg_om_map,
                    freq5_map=f5_map,
                    freq15_map=f15_map,
                    last_draw_set=last_draw_set,
                )
                label = 1 if b in cur_target_set else 0
                X_train_list.append(feat)
                y_train_list.append(label)

        # 提取最新一期（即等待预测目标期）的 80 码特征向量
        latest_draw = self.draws[-1]
        latest_draw_set = set(latest_draw)
        cnt_road_latest = {0: 0, 1: 0, 2: 0}
        cnt_prime_latest = 0
        for num in latest_draw:
            cnt_road_latest[num % 3] += 1
            if num in PRIMES_SET:
                cnt_prime_latest += 1
        macro_r_diff_latest = {r: cnt_road_latest[r] - 6.67 for r in (0, 1, 2)}
        macro_p_diff_latest = cnt_prime_latest - 5.50

        f5_map_latest: Dict[int, int] = {b: 0 for b in range(1, TOTAL_BALLS + 1)}
        f15_map_latest: Dict[int, int] = {b: 0 for b in range(1, TOTAL_BALLS + 1)}
        for back_i in range(1, 16):
            if n_draws - back_i >= 0:
                for b in self.draws[n_draws - back_i]:
                    f15_map_latest[b] += 1
                    if back_i <= 5:
                        f5_map_latest[b] += 1

        om_map_latest: Dict[int, int] = {}
        avg_om_map_latest: Dict[int, float] = {}
        X_predict_list = []

        for b in range(1, TOTAL_BALLS + 1):
            om = 0
            while n_draws - 1 - om >= 0 and b not in self.draws[n_draws - 1 - om]:
                om += 1
            om_map_latest[b] = om
            total_hits = sum(1 for d in self.draws if b in d)
            avg_om_map_latest[b] = (n_draws / max(total_hits, 1.0)) if total_hits > 0 else 4.0

            feat = self._extract_feature_vector(
                ball=b,
                idx=n_draws,
                macro_road_diff=macro_r_diff_latest,
                macro_prime_diff=macro_p_diff_latest,
                omission_map=om_map_latest,
                avg_omission_map=avg_om_map_latest,
                freq5_map=f5_map_latest,
                freq15_map=f15_map_latest,
                last_draw_set=latest_draw_set,
            )
            X_predict_list.append(feat)

        macro_info = {
            "latest_period": self.periods[-1],
            "last_draw": latest_draw,
            "cnt_road": cnt_road_latest,
            "cnt_prime": cnt_prime_latest,
            "macro_road_diff": macro_r_diff_latest,
            "macro_prime_diff": macro_p_diff_latest,
        }

        return np.array(X_train_list, dtype=np.float32), np.array(y_train_list, dtype=np.int32), np.array(X_predict_list, dtype=np.float32), macro_info

    def execute_inference(self) -> Dict[str, Any]:
        """
        步骤 3 ~ 6: 全链路执行决策树训练、特征重要性解析、正交缩水与实操推荐
        """
        X_train, y_train, X_pred, macro_info = self._build_training_dataset()

        # // 步骤 3.1: 训练可解释单决策树 (最大深度 4，提取通俗规则)
        tree = DecisionTreeClassifier(
            max_depth=4,
            min_samples_leaf=15,
            criterion="entropy",
            random_state=42,
        )
        tree.fit(X_train, y_train)

        # 提取高胜率规则文本
        tree_rules_raw = export_text(tree, feature_names=FEATURE_NAMES_CN, max_depth=3)

        # // 步骤 3.2: 训练随机森林海选团 (50 棵树联合平滑预测)
        rf = RandomForestClassifier(
            n_estimators=50,
            max_depth=5,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1,
        )
        rf.fit(X_train, y_train)

        # 计算特征重要性排行榜 (看谁最管用)
        importances = rf.feature_importances_
        sorted_feat_idx = np.argsort(importances)[::-1]
        feature_ranking = [
            {
                "rank": i + 1,
                "feature": FEATURE_NAMES_CN[idx],
                "code": FEATURE_COLUMNS[idx],
                "importance": round(float(importances[idx]), 4),
                "weight_percent": f"{importances[idx] * 100:.2f}%",
            }
            for i, idx in enumerate(sorted_feat_idx)
        ]

        # // 步骤 4: 计算 80 码出号概率 (双模型加权: 树模型 0.35 + 森林 0.65)
        tree_probs = tree.predict_proba(X_pred)[:, 1]
        rf_probs = rf.predict_proba(X_pred)[:, 1]
        fused_probs = tree_probs * 0.35 + rf_probs * 0.65

        # // 步骤 4.1 (v2.0 升级): 双元共现引力场增强 (Pairwise Co-occurrence Affinity)
        co_mat = self._compute_cooccurrence_matrix(window=100)
        # 取树模型初选 Top5 作为引力核心种子
        init_top_idx = np.argsort(fused_probs)[::-1]
        core_seeds = [int(idx + 1) for idx in init_top_idx[:5]]

        affinity_scores = np.zeros(TOTAL_BALLS, dtype=np.float32)
        for b in range(1, TOTAL_BALLS + 1):
            aff_val = sum(co_mat[b, s] for s in core_seeds if b != s)
            affinity_scores[b - 1] = aff_val

        max_aff = float(np.max(affinity_scores))
        min_aff = float(np.min(affinity_scores))
        norm_aff = (affinity_scores - min_aff) / max(max_aff - min_aff, 1e-6)

        # 终极融合得分: 树模型 72% + 共现引力 28%
        v2_final_probs = fused_probs * 0.72 + norm_aff * 0.28

        # 组装 80 码评分清单
        ball_scores = []
        for b in range(1, TOTAL_BALLS + 1):
            p_val = float(v2_final_probs[b - 1])
            road = b % 3
            is_p = b in PRIMES_SET
            ball_scores.append({
                "ball": b,
                "ball_str": f"{b:02d}",
                "prob": round(p_val, 4),
                "road": road,
                "is_prime": is_p,
                "pool": "0路质数" if (road == 0 and is_p) else
                        "0路合数" if (road == 0 and not is_p) else
                        "1路质数" if (road == 1 and is_p) else
                        "1路合数" if (road == 1 and not is_p) else
                        "2路质数" if (road == 2 and is_p) else "2路合数",
            })

        # 按综合概率降序排列 (排行榜选秀)
        ball_scores.sort(key=lambda x: x["prob"], reverse=True)

        # // 步骤 5: 执行多梯度六维正交配额剪枝缩水 (生成 30码/25码/20码)
        basket30, pools30 = self._orthogonal_prune(ball_scores, target_size=30, max_primes=8, max_road=11, max_zone=5)
        basket25, pools25 = self._orthogonal_prune(ball_scores, target_size=25, max_primes=7, max_road=9, max_zone=4)
        basket20, pools20 = self._orthogonal_prune(ball_scores, target_size=20, max_primes=6, max_road=8, max_zone=4)

        # // 步骤 6: 萃取尖刀 Top3、主力 Top5 与跨路对冲选2搭档 (基于高纯度 basket20 萃取)
        top3_gold = [item["ball"] for item in basket20[:3]]
        top5_gold = [item["ball"] for item in basket20[:5]]
        top20_core_base = sorted([item["ball"] for item in basket20])
        top25_mid_base = sorted([item["ball"] for item in basket25])
        top30_large_base = sorted([item["ball"] for item in basket30])

        pick2_pairs = self._generate_pick2_pairs_v2(basket20, co_mat)

        # 整理老派操盘手实战解析卡
        analysis_card = self._generate_analysis_summary(macro_info, feature_ranking, pools30)

        target_p_str = str(int(macro_info["latest_period"]) + 1) if macro_info["latest_period"].isdigit() else "NEXT"

        return {
            "target_period": target_p_str,
            "target_issue": target_p_str,
            "meta": {
                "engine": "TreeRoadPrimeShrinkEngine v2.0 (Co-occurrence Affinity & Sum Guard)",
                "latest_period": macro_info["latest_period"],
                "target_period": target_p_str,
                "train_samples": int(len(X_train)),
                "trees_count": 50,
            },
            "macro_diagnosis": macro_info,
            "feature_ranking": feature_ranking,
            "tree_rules_text": tree_rules_raw,
            "pool_distribution": pools30,
            "pool_distribution_25": pools25,
            "pool_distribution_20": pools20,
            "top3_gold": top3_gold,
            "top5_gold": top5_gold,
            "top20_core_base": top20_core_base,
            "top25_mid_base": top25_mid_base,
            "top30_large_base": top30_large_base,
            "pick2_pairs": pick2_pairs,
            "analysis_card": analysis_card,
            "all_80_scores": ball_scores,
        }

    def _compute_cooccurrence_matrix(self, window: int = 100) -> np.ndarray:
        """统计最近 window 期内 80 码之间的双元共现频次矩阵 (81x81)"""
        n_draws = len(self.draws)
        start_idx = max(0, n_draws - window)
        co_mat = np.zeros((TOTAL_BALLS + 1, TOTAL_BALLS + 1), dtype=np.float32)
        for d in self.draws[start_idx:]:
            for i in range(len(d)):
                for j in range(i + 1, len(d)):
                    b1, b2 = d[i], d[j]
                    co_mat[b1, b2] += 1.0
                    co_mat[b2, b1] += 1.0
        return co_mat

    def _orthogonal_prune(
        self,
        sorted_scores: List[Dict[str, Any]],
        target_size: int = 30,
        max_primes: int = 8,
        max_road: int = 11,
        max_zone: int = 5,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        六维正交配额剪枝算法 (v2.0 和值黄金中枢滤波保护):
        确保缩水篮子满足大数定律守恒红线：
        - 质数总数严格控制在指定上限之内；
        - 0路、1路、2路总数均衡分布；
        - 单一分区避免过度堆积；
        - 和值均值紧紧锚定在 40.5 (对应 20 码和值 810 点黄金中枢)。
        """
        basket: List[Dict[str, Any]] = []
        selected_set: Set[int] = set()
        zone_counts = {z: 0 for z in range(1, 9)}
        road_counts = {0: 0, 1: 0, 2: 0}
        prime_count = 0

        # 第一轮：由高到低贪心配额填充 (融入中枢引力防护)
        for item in sorted_scores:
            if len(basket) >= target_size:
                break
            b = item["ball"]
            r = item["road"]
            is_p = item["is_prime"]
            z = (b - 1) // 10 + 1

            # 质数配额上限防守
            if is_p and prime_count >= max_primes:
                continue
            # 单路配额上限防守
            if road_counts[r] >= max_road:
                continue
            # 单分区上限防守
            if zone_counts[z] >= max_zone:
                continue

            # 和值中枢偏态防护 (若当前已选超过10个球，且平均值严重偏高/偏低时做软拦截)
            if len(basket) >= 10:
                cur_mean = sum(x["ball"] for x in basket) / len(basket)
                if cur_mean > 47.0 and b > 55:  # 严重偏大号，暂缓超大号
                    continue
                if cur_mean < 34.0 and b < 25:  # 严重偏小号，暂缓超小号
                    continue

            basket.append(item)
            selected_set.add(b)
            road_counts[r] += 1
            zone_counts[z] += 1
            if is_p:
                prime_count += 1

        # 若不足 target_size，放宽约束平滑补齐
        if len(basket) < target_size:
            for item in sorted_scores:
                if len(basket) >= target_size:
                    break
                b = item["ball"]
                if b not in selected_set:
                    basket.append(item)
                    selected_set.add(b)
                    road_counts[item["road"]] += 1
                    if item["is_prime"]:
                        prime_count += 1

        # 统计六大子池在篮子中的分布
        pool_stats: Dict[str, int] = {k: 0 for k in ALL_POOLS}
        for item in basket:
            pool_stats[item["pool"]] += 1

        return basket, pool_stats

    def _generate_pick2_pairs_v2(
        self,
        basket: List[Dict[str, Any]],
        co_mat: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """v2.0 升级：结合双元共现亲和力最高的跨路对冲黄金选 2 搭档"""
        top_candidates = basket[:12]
        pairs = []

        # 搭档 1: 0路金胆 + 2路中与其历史共现频次最高的搭档
        cand_0 = [x["ball"] for x in top_candidates if x["road"] == 0]
        cand_2 = [x["ball"] for x in top_candidates if x["road"] == 2]
        if not cand_0:
            cand_0 = [basket[0]["ball"]]
        if not cand_2:
            cand_2 = [basket[1]["ball"]]

        best_p1 = (cand_0[0], cand_2[0])
        max_co1 = -1.0
        for b0 in cand_0:
            for b2 in cand_2:
                if b0 != b2 and co_mat[b0, b2] > max_co1:
                    max_co1 = co_mat[b0, b2]
                    best_p1 = (b0, b2)

        pair1 = sorted([best_p1[0], best_p1[1]])
        pairs.append({
            "pair": pair1,
            "label": "0路×2路 高共现跨路对冲搭档",
            "desc": f"0路金胆 {pair1[0]:02d} 与 2路搭档 {pair1[1]:02d} (历史共现 {int(max_co1)} 次)，攻守平衡且粘性极强",
        })

        # 搭档 2: 1路金胆 + 2路中与其历史共现最高的搭档 (避开搭档1)
        cand_1 = [x["ball"] for x in top_candidates if x["road"] == 1]
        if not cand_1:
            cand_1 = [basket[2]["ball"]]

        best_p2 = (cand_1[0], cand_2[0])
        max_co2 = -1.0
        for b1 in cand_1:
            for b2 in cand_2:
                if b1 != b2 and (b1, b2) != (pair1[0], pair1[1]) and co_mat[b1, b2] > max_co2:
                    max_co2 = co_mat[b1, b2]
                    best_p2 = (b1, b2)

        pair2 = sorted([best_p2[0], best_p2[1]])
        pairs.append({
            "pair": pair2,
            "label": "1路×2路 强动能连体搭档",
            "desc": f"1路金胆 {pair2[0]:02d} 与 2路搭档 {pair2[1]:02d} (历史共现 {int(max_co2)} 次)，主打高频爆发",
        })

        # 搭档 3: 质数金胆 + 合数中与其共现最高的搭档
        cand_prime = [x["ball"] for x in top_candidates if x["is_prime"]]
        cand_comp = [x["ball"] for x in top_candidates if not x["is_prime"]]
        if not cand_prime:
            cand_prime = [5]
        if not cand_comp:
            cand_comp = [8]

        best_p3 = (cand_prime[0], cand_comp[0])
        max_co3 = -1.0
        for bp in cand_prime:
            for bc in cand_comp:
                if bp != bc and co_mat[bp, bc] > max_co3:
                    max_co3 = co_mat[bp, bc]
                    best_p3 = (bp, bc)

        pair3 = sorted([best_p3[0], best_p3[1]])
        pairs.append({
            "pair": pair3,
            "label": "质合协同 孪生共振搭档",
            "desc": f"质数尖刀 {pair3[0]:02d} 搭配 稳健合数 {pair3[1]:02d} (历史共现 {int(max_co3)} 次)，风险平价稳防守",
        })

        return pairs

    def _generate_pick2_pairs(self, basket: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从高概率篮子中挑出 3 组跨路对冲黄金选 2 搭档"""
        # 提取概率最高且分属不同路的号码
        top_candidates = basket[:10]
        pairs = []

        # 搭档 1: 0路金胆 + 2路搭档
        b_0 = next((x["ball"] for x in top_candidates if x["road"] == 0), basket[0]["ball"])
        b_2 = next((x["ball"] for x in top_candidates if x["road"] == 2 and x["ball"] != b_0), basket[1]["ball"])
        pair1 = sorted([b_0, b_2])
        pairs.append({
            "pair": pair1,
            "label": "0路×2路 跨路对冲搭档",
            "desc": f"0路码 {pair1[0]:02d} 搭配 2路码 {pair1[1]:02d}，攻守平衡互补防撞",
        })

        # 搭档 2: 1路金胆 + 2路搭档
        b_1 = next((x["ball"] for x in top_candidates if x["road"] == 1 and x["ball"] not in pair1), None)
        if b_1 is None:
            b_1 = next((x["ball"] for x in basket if x["road"] == 1), 7)
        b_2_alt = next((x["ball"] for x in top_candidates if x["road"] == 2 and x["ball"] != b_1), None)
        if b_2_alt is None:
            b_2_alt = next((x["ball"] for x in basket if x["road"] == 2 and x["ball"] != b_1), 2)
        pair2 = sorted([b_1, b_2_alt])
        pairs.append({
            "pair": pair2,
            "label": "1路×2路 双强出击搭档",
            "desc": f"1路码 {pair2[0]:02d} 搭配 2路码 {pair2[1]:02d}，主抓两路高频动能",
        })

        # 搭档 3: 质数金胆 + 合数防守搭档
        p_prime = next((x["ball"] for x in top_candidates if x["is_prime"]), 5)
        p_comp = next((x["ball"] for x in top_candidates if not x["is_prime"] and x["ball"] != p_prime), 8)
        pair3 = sorted([p_prime, p_comp])
        pairs.append({
            "pair": pair3,
            "label": "质合协同 攻矛守盾搭档",
            "desc": f"质数尖刀 {pair3[0]:02d} 搭配 稳重合数 {pair3[1]:02d}，分摊风险防极端偏态",
        })

        return pairs

    def _generate_analysis_summary(
        self,
        macro_info: Dict[str, Any],
        ranking: List[Dict[str, Any]],
        pool_stats: Dict[str, int],
    ) -> Dict[str, Any]:
        """生成操盘手通俗易懂的体检卡片"""
        top1_feat = ranking[0]["feature"]
        top2_feat = ranking[1]["feature"]
        top3_feat = ranking[2]["feature"]

        c0 = macro_info["cnt_road"][0]
        c1 = macro_info["cnt_road"][1]
        c2 = macro_info["cnt_road"][2]
        cp = macro_info["cnt_prime"]

        # 偏态诊断
        advice = []
        if c0 <= 5:
            advice.append("上期0路出号仅5个显著偏冷，本期强烈看好0路绝地反弹回补；")
        elif c0 >= 8:
            advice.append("上期0路开出超标过热，本期防范0路降温熔断；")

        if c1 >= 8:
            advice.append("上期1路出号8个达到高位，本期建议适度压制1路合数；")
        if c2 >= 7:
            advice.append("上期2路动能充沛，本期重点关注2路优质重号与邻号；")

        if cp >= 7:
            advice.append("上期质数开出扎堆，本期必须严格卡死质数配额在6~7码以内。")

        return {
            "macro_status": f"上期012路比 [{c0}:{c1}:{c2}]，质数开出 {cp} 个",
            "key_drivers": f"机器虚拟裁判判定最管用的前三大指标为：① {top1_feat}、② {top2_feat}、③ {top3_feat}",
            "tactical_advice": "".join(advice),
            "pool_breakdown": pool_stats,
        }
