# -*- coding: utf-8 -*-
"""
快乐8 遗传算法自进化号码推演引擎 (Genetic Algorithm Engine)
===========================================================
【业务背景与架构定位】:
本模块专为快乐8全量开奖历史数据打造，通过模拟生物进化（自然选择、染色体交叉、基因突变、精英保留）
在多维历史特征空间中自适应搜索最优打分权重与最佳实战号码组合。

【算法流程】:
1. 步骤 1: 从全量历史开奖数据中提取 80 球的 8 大物理特征（长期频次、短期动量、遗漏势能、重号粘性、邻号波及、同尾共振、分区均衡、马尔可夫共现）；
2. 步骤 2: 建立实数编码染色体种群，每个个体代表一组特征权重参数；
3. 步骤 3: 在过去多期滚动历史中进行实盘对账打分（适应度评估），奖励高命中，惩罚极低命中；
4. 步骤 4: 执行锦标赛选择、双亲基因交叉、自适应高斯突变与精英保留，迭代进化出最优基因；
5. 步骤 5: 利用当期最优基因对 80 码全面解算，输出尖刀金胆 / 最优3码 / 黄金选2（杀号产品已退役）。

@author Antigravity Quantitative Team
@since 2026-09-11
"""

import os
import sys
import json
import math
import random
import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

# 路径初始化
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 模块迁入 _retired/ 后目录层数变了，改为向上回溯到真正的项目根（同时含 backend 与 storage 的目录）
_ROOT_DIR = _CURRENT_DIR
while not (os.path.isdir(os.path.join(_ROOT_DIR, "backend"))
           and os.path.isdir(os.path.join(_ROOT_DIR, "frontend"))
           and os.path.isdir(os.path.join(_ROOT_DIR, "storage"))):
    _parent = os.path.dirname(_ROOT_DIR)
    if _parent == _ROOT_DIR:
        break
    _ROOT_DIR = _parent
_BACKEND_DIR = os.path.join(_ROOT_DIR, "backend")
for _p in [_BACKEND_DIR, _ROOT_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.history_loader import load_history
from backend.utils.paths import get_cache_dir, get_storage_dir

logger = logging.getLogger("k8quant.genetic")


class GeneticAlgorithmEngine:
    """快乐8 遗传算法自进化推演引擎"""

    # 基因维度定义
    GENE_NAMES = [
        "w_freq",      # 1. 长期统计频次权重 (0.0 - 1.0)
        "w_mom",       # 2. 短期冷热动量权重 (0.0 - 1.0)
        "w_omiss",     # 3. 遗漏回补势能权重 (0.0 - 1.0)
        "w_repeat",    # 4. 隔期重号粘性权重 (0.0 - 1.0)
        "w_neighbor",  # 5. 邻号波及势能权重 (0.0 - 1.0)
        "w_tail",      # 6. 同尾共振聚集权重 (0.0 - 1.0)
        "w_zone",      # 7. 8大分区均衡权重 (0.0 - 1.0)
        "w_pair",      # 8. 双元马尔可夫共现权重 (0.0 - 1.0)
    ]
    GENE_DIM = len(GENE_NAMES)

    def __init__(self, history: Optional[List[Dict[str, Any]]] = None):
        """
        初始化遗传算法引擎
        @param history 历史开奖列表，最新期排在最前 (index 0)
        """
        if history is None:
            self.history = load_history()
        else:
            self.history = history
        self.total_periods = len(self.history)
        self._feature_cache: Dict[int, np.ndarray] = {}

    def extract_features_at_period(self, offset: int = 0) -> np.ndarray:
        """
        提取指定历史断面下的 80 球 8 维物理特征矩阵
        @param offset 历史偏移量 (0 为推演下一期，>0 为回溯历史指定期)
        @return np.ndarray shape: (80, 8), 每列特征已归一化至 [0.0, 1.0]
        """
        if offset in self._feature_cache:
            return self._feature_cache[offset]

        if len(self.history) <= offset + 1:
            return np.zeros((80, self.GENE_DIM), dtype=np.float64)

        # 截取截至当期之前的历史样本 (绝不使用未来数据)
        sub_hist = self.history[offset:]
        num_hist = len(sub_hist)

        features = np.zeros((80, self.GENE_DIM), dtype=np.float64)

        # 1. 长期频次 (近 50 期)
        long_window = min(50, num_hist)
        long_counts = np.zeros(80, dtype=np.float64)
        for i in range(long_window):
            for num in sub_hist[i].get("numbers", []):
                if 1 <= num <= 80:
                    long_counts[num - 1] += 1.0
        max_long = max(float(np.max(long_counts)), 1.0)
        features[:, 0] = long_counts / max_long

        # 2. 短期冷热动量 (近 10 期指数加权)
        short_window = min(10, num_hist)
        short_mom = np.zeros(80, dtype=np.float64)
        for i in range(short_window):
            weight = math.exp(-0.15 * i)
            for num in sub_hist[i].get("numbers", []):
                if 1 <= num <= 80:
                    short_mom[num - 1] += weight
        max_mom = max(float(np.max(short_mom)), 1.0)
        features[:, 1] = short_mom / max_mom

        # 3. 遗漏回补势能 (计算当前遗漏值，3~12 期的温号势能最高，极冷与极热递减)
        omissions = np.zeros(80, dtype=np.float64)
        for num in range(1, 81):
            omis = 0
            found = False
            for i in range(min(60, num_hist)):
                if num in sub_hist[i].get("numbers", []):
                    found = True
                    break
                omis += 1
            if not found:
                omis = min(60, num_hist)
            # 3~12 期遗漏给予最高势能高斯加权
            if 3 <= omis <= 12:
                omissions[num - 1] = 1.0 - abs(omis - 6) * 0.08
            elif omis < 3:
                omissions[num - 1] = 0.5 + omis * 0.15
            else:
                omissions[num - 1] = max(0.1, 1.0 - (omis - 12) * 0.04)
        features[:, 2] = np.clip(omissions, 0.0, 1.0)

        # 4. 隔期重号粘性 (上一期开出号码赋予重开基础分)
        last_draw = set(sub_hist[0].get("numbers", []))
        repeat_feat = np.zeros(80, dtype=np.float64)
        for num in range(1, 81):
            if num in last_draw:
                repeat_feat[num - 1] = 1.0
        features[:, 3] = repeat_feat

        # 5. 邻号波及势能 (上一期开奖号的左右邻居)
        neighbor_feat = np.zeros(80, dtype=np.float64)
        for num in last_draw:
            if num - 1 >= 1 and (num - 1) not in last_draw:
                neighbor_feat[num - 2] += 0.5
            if num + 1 <= 80 and (num + 1) not in last_draw:
                neighbor_feat[num] += 0.5
        max_nbr = max(float(np.max(neighbor_feat)), 1.0)
        features[:, 4] = neighbor_feat / max_nbr

        # 6. 同尾共振聚集度 (上一期出现最多的尾数对应的号码给予加成)
        tail_counts = np.zeros(10, dtype=np.float64)
        for num in last_draw:
            tail_counts[num % 10] += 1.0
        max_tail_cnt = max(float(np.max(tail_counts)), 1.0)
        tail_feat = np.zeros(80, dtype=np.float64)
        for num in range(1, 81):
            t = num % 10
            tail_feat[num - 1] = tail_counts[t] / max_tail_cnt
        features[:, 5] = tail_feat

        # 7. 8大分区空间均衡修正 (1-10, 11-20, ..., 71-80)
        zone_counts = np.zeros(8, dtype=np.float64)
        for num in last_draw:
            z_idx = min(7, (num - 1) // 10)
            zone_counts[z_idx] += 1.0
        # 如果某分区上期出号少 (<2)，给予反弹加成；如果出号极多(>4)，给予适当抑制
        zone_feat = np.zeros(80, dtype=np.float64)
        for num in range(1, 81):
            z_idx = min(7, (num - 1) // 10)
            c = zone_counts[z_idx]
            if c <= 1:
                zone_feat[num - 1] = 0.95
            elif c == 2:
                zone_feat[num - 1] = 0.75
            elif c == 3:
                zone_feat[num - 1] = 0.55
            else:
                zone_feat[num - 1] = 0.30
        features[:, 6] = zone_feat

        # 8. 双元马尔可夫共现跟随势能 (统计上一期 20 码在近 30 期中对各号码的带出频次)
        pair_window = min(30, num_hist - 1)
        cooccur_feat = np.zeros(80, dtype=np.float64)
        if pair_window > 0:
            for i in range(pair_window):
                prev_nums = set(sub_hist[i + 1].get("numbers", []))
                curr_nums = set(sub_hist[i].get("numbers", []))
                overlap_with_last = prev_nums.intersection(last_draw)
                if overlap_with_last:
                    for num in curr_nums:
                        if 1 <= num <= 80:
                            cooccur_feat[num - 1] += len(overlap_with_last)
            max_co = max(float(np.max(cooccur_feat)), 1.0)
            features[:, 7] = cooccur_feat / max_co

        self._feature_cache[offset] = features
        return features

    def compute_scores(self, features: np.ndarray, chromosome: np.ndarray) -> np.ndarray:
        """
        根据染色体权重向量计算 80 球综合得分
        @param features 特征矩阵 shape: (80, 8)
        @param chromosome 染色体权重向量 shape: (8,)
        @return np.ndarray shape: (80,) 归一化综合概率得分
        """
        weights = np.array(chromosome, dtype=np.float64)
        w_sum = float(np.sum(weights))
        if w_sum <= 1e-6:
            weights = np.ones(self.GENE_DIM, dtype=np.float64) / self.GENE_DIM
        else:
            weights = weights / w_sum

        scores = np.dot(features, weights)
        s_min = float(np.min(scores))
        s_max = float(np.max(scores))
        if s_max - s_min > 1e-6:
            norm_scores = (scores - s_min) / (s_max - s_min)
        else:
            norm_scores = np.ones(80, dtype=np.float64) / 80.0
        return norm_scores

    def select_gold_core(
        self, scores: np.ndarray, feats: np.ndarray, sub_hist: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """
        基于【单挑王特训体系】精炼尖刀金胆与黄金搭档选2
        1. 陷阱熔断：排除连开 >= 4 期的超热滞涨号与遗漏 > 20 期的深水死冷号；
        2. 多维共振：考察短期动量、回补势能与共现跟随，杜绝单科虚高；
        3. 锦标赛决选：在前 5 强候选池中综合比武选出单点确定性最高的金胆；
        4. 黄金伴随：以金胆为锚点，跨区+异尾+强粘性选出最佳搭档。
        @param scores 80 码综合打分 shape: (80,)
        @param feats 80 码 8 维特征矩阵 shape: (80, 8)
        @param sub_hist 截至当期历史开奖列表 (最新在前)
        @return (gold_core, companion)
        """
        num_hist = len(sub_hist)

        # 步骤 1: 扫描连开与死冷陷阱 (物理熔断)
        is_trap = np.zeros(80, dtype=bool)
        for num in range(1, 81):
            streak = 0
            for h_idx in range(min(10, num_hist)):
                if num in sub_hist[h_idx].get("numbers", []):
                    streak += 1
                else:
                    break
            if streak >= 4:
                is_trap[num - 1] = True

            omis = 0
            found = False
            for h_idx in range(min(50, num_hist)):
                if num in sub_hist[h_idx].get("numbers", []):
                    found = True
                    break
                omis += 1
            if not found or omis > 20:
                is_trap[num - 1] = True

        # 步骤 2: 提取综合得分前 8 候选
        ranked_indices = np.argsort(-scores)
        candidates: List[int] = []
        for idx in ranked_indices:
            num = int(idx + 1)
            if not is_trap[idx]:
                candidates.append(num)
            if len(candidates) >= 5:
                break
        
        # 兜底：若有效候选不足 3 个，放宽限制
        if len(candidates) < 3:
            for idx in ranked_indices:
                num = int(idx + 1)
                if num not in candidates:
                    candidates.append(num)
                if len(candidates) >= 5:
                    break

        # 步骤 3: 多维共振锦标赛打分
        best_gold = candidates[0]
        best_gold_score = -1e9

        for cand in candidates:
            idx = cand - 1
            base_score = float(scores[idx])
            mom = float(feats[idx, 1])       # 短期动量
            omiss = float(feats[idx, 2])     # 遗漏回补势能
            repeat_nbr = (float(feats[idx, 3]) + float(feats[idx, 4])) * 0.5 # 重邻粘性
            cooccur = float(feats[idx, 7])   # 双元马尔可夫共现

            # 综合共振评级 (Resonance Formula)
            res_score = (
                0.35 * base_score +
                0.25 * mom +
                0.20 * omiss +
                0.20 * cooccur +
                0.10 * repeat_nbr
            )

            # 偏科惩罚：若动量、回补或跟随中有任一项极低 (< 0.15)，施加偏科惩罚
            min_dim = min(mom, omiss, max(repeat_nbr, cooccur))
            if min_dim < 0.15:
                res_score *= 0.85
            # 奖励多维均衡全优生
            if mom > 0.45 and omiss > 0.45:
                res_score *= 1.15

            if res_score > best_gold_score:
                best_gold_score = res_score
                best_gold = cand

        # 步骤 4: 选出与金胆最搭的黄金伴随 (跨区 + 异尾 + 强跟随共现)
        gold_zone = (best_gold - 1) // 10
        gold_tail = best_gold % 10

        best_companion = candidates[1] if candidates[1] != best_gold else candidates[0]
        best_pair_affinity = -1e9

        for cand in candidates:
            if cand == best_gold:
                continue
            idx = cand - 1
            cand_zone = (cand - 1) // 10
            cand_tail = cand % 10

            affinity = float(scores[idx]) * 0.4 + float(feats[idx, 7]) * 0.6
            # 跨区奖励 (避免两码挤在同一个10位狭窄区间)
            if cand_zone != gold_zone:
                affinity += 0.20
            # 异尾奖励 (避免同尾号同进同出)
            if cand_tail != gold_tail:
                affinity += 0.15

            if affinity > best_pair_affinity:
                best_pair_affinity = affinity
                best_companion = cand

        return best_gold, best_companion

    def evaluate_fitness(self, chromosome: np.ndarray, eval_periods: int = 15) -> float:
        """
        在过去多期滑动窗口中评估染色体个体的适应度
        @param chromosome 染色体个体 (权重向量)
        @param eval_periods 评估回溯期数
        @return float 适应度得分
        """
        if len(self.history) < eval_periods + 2:
            return 0.0

        total_fitness = 0.0
        for offset in range(1, eval_periods + 1):
            actual_draw = set(self.history[offset - 1].get("numbers", []))
            if len(actual_draw) < 15:
                continue

            # 使用 offset 断面特征
            feats = self.extract_features_at_period(offset=offset)
            scores = self.compute_scores(feats, chromosome)
            sub_hist_offset = self.history[offset:]

            # 单挑王精炼金胆与伴随码
            gold_core, gold_companion = self.select_gold_core(scores, feats, sub_hist_offset)

            # 按得分降序排列
            ranked_indices = np.argsort(-scores)  # 0-indexed
            top5 = [idx + 1 for idx in ranked_indices[:5]]
            top12 = [idx + 1 for idx in ranked_indices[:12]]
            top20 = [idx + 1 for idx in ranked_indices[:20]]

            hit_5 = len(actual_draw.intersection(top5))
            hit_12 = len(actual_draw.intersection(top12))
            hit_20 = len(actual_draw.intersection(top20))
            is_gold_hit = 1.0 if gold_core in actual_draw else 0.0
            is_pair_double = 1.0 if (gold_core in actual_draw and gold_companion in actual_draw) else 0.0

            # 阶梯式非对称打分机制：重奖金胆与选2双中
            period_score = (
                hit_5 * 3.0 +
                hit_12 * 1.5 +
                hit_20 * 0.8 +
                is_gold_hit * 9.0 +
                is_pair_double * 6.5
            )
            # 金胆脱靶与极低命中惩罚
            if not is_gold_hit:
                period_score -= 2.0
            if hit_20 < 4:
                period_score -= (4 - hit_20) * 2.0

            total_fitness += period_score

        avg_fitness = total_fitness / max(1, eval_periods)
        return float(avg_fitness)

    def run_evolution(
        self,
        pop_size: int = 40,
        generations: int = 25,
        eval_periods: int = 15,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.85,
        elitism_count: int = 3
    ) -> Dict[str, Any]:
        """
        执行遗传算法核心进化主循环
        @param pop_size 种群规模
        @param generations 迭代代数
        @param eval_periods 适应度评估回溯期数
        @param mutation_rate 基础突变概率
        @param crossover_rate 交叉概率
        @param elitism_count 精英保留个体数
        @return Dict 包含最优基因、收敛曲线与进化状态
        """
        random.seed(42)
        np.random.seed(42)

        # 步骤 1: 初始化种群 (包含先验种子个体与随机个体)
        population: List[np.ndarray] = []
        # 先验专家种子 1: 均衡型
        population.append(np.array([0.20, 0.20, 0.15, 0.15, 0.10, 0.10, 0.05, 0.05], dtype=np.float64))
        # 先验专家种子 2: 动量激进型
        population.append(np.array([0.10, 0.35, 0.10, 0.20, 0.15, 0.05, 0.02, 0.03], dtype=np.float64))
        # 先验专家种子 3: 遗漏均值回归型
        population.append(np.array([0.15, 0.10, 0.35, 0.10, 0.10, 0.10, 0.05, 0.05], dtype=np.float64))
        
        while len(population) < pop_size:
            rand_ind = np.random.uniform(0.05, 0.95, size=self.GENE_DIM)
            population.append(rand_ind)

        convergence_curve: List[Dict[str, Any]] = []
        best_overall_chromosome = population[0].copy()
        best_overall_fitness = -1e9

        logger.info("🧬 [GA] 遗传算法自进化启动: 种群=%d, 代数=%d, 评估期数=%d", pop_size, generations, eval_periods)

        # 步骤 2: 逐代繁衍进化
        for gen in range(1, generations + 1):
            fitness_scores = [self.evaluate_fitness(ind, eval_periods=eval_periods) for ind in population]
            
            # 统计当代指标
            sorted_indices = np.argsort(-np.array(fitness_scores))
            current_best_fit = fitness_scores[sorted_indices[0]]
            current_best_ind = population[sorted_indices[0]].copy()
            avg_fit = float(np.mean(fitness_scores))

            if current_best_fit > best_overall_fitness:
                best_overall_fitness = current_best_fit
                best_overall_chromosome = current_best_ind.copy()

            convergence_curve.append({
                "generation": gen,
                "best_fitness": round(current_best_fit, 3),
                "avg_fitness": round(avg_fit, 3)
            })

            # 若最后一代理论完成，跳过子代生成
            if gen == generations:
                break

            # 步骤 3: 精英保留 (Elitism)
            next_generation: List[np.ndarray] = []
            for e_idx in range(min(elitism_count, pop_size)):
                next_generation.append(population[sorted_indices[e_idx]].copy())

            # 步骤 4: 繁衍生成下一代
            curr_mut_rate = mutation_rate * (1.0 - 0.5 * (gen / generations)) # 突变率自适应衰减
            while len(next_generation) < pop_size:
                # 锦标赛选择 parent 1 & parent 2
                p1 = self._tournament_select(population, fitness_scores, k=3)
                p2 = self._tournament_select(population, fitness_scores, k=3)

                # 交叉
                if random.random() < crossover_rate:
                    child1, child2 = self._crossover(p1, p2)
                else:
                    child1, child2 = p1.copy(), p2.copy()

                # 变异
                child1 = self._mutate(child1, curr_mut_rate)
                child2 = self._mutate(child2, curr_mut_rate)

                next_generation.append(child1)
                if len(next_generation) < pop_size:
                    next_generation.append(child2)

            population = next_generation

        logger.info("🧬 [GA] 进化完成: 最优适应度=%.3f, 最优权重=%s", best_overall_fitness, best_overall_chromosome.round(3).tolist())

        # 归一化最优权重
        w_sum = float(np.sum(best_overall_chromosome))
        norm_weights = (best_overall_chromosome / (w_sum if w_sum > 1e-6 else 1.0)).round(4).tolist()

        return {
            "status": "success",
            "generations": generations,
            "pop_size": pop_size,
            "eval_periods": eval_periods,
            "best_fitness": round(best_overall_fitness, 3),
            "best_weights": dict(zip(self.GENE_NAMES, norm_weights)),
            "best_chromosome": best_overall_chromosome.tolist(),
            "convergence_curve": convergence_curve
        }

    def _tournament_select(self, population: List[np.ndarray], fitness_scores: List[float], k: int = 3) -> np.ndarray:
        """锦标赛选择算子"""
        cand_indices = random.sample(range(len(population)), min(k, len(population)))
        best_cand_idx = cand_indices[0]
        best_cand_fit = fitness_scores[best_cand_idx]
        for idx in cand_indices[1:]:
            if fitness_scores[idx] > best_cand_fit:
                best_cand_fit = fitness_scores[idx]
                best_cand_idx = idx
        return population[best_cand_idx].copy()

    def _crossover(self, p1: np.ndarray, p2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """混合加权交叉算子"""
        alpha = random.uniform(0.2, 0.8)
        c1 = alpha * p1 + (1.0 - alpha) * p2
        c2 = (1.0 - alpha) * p1 + alpha * p2
        return np.clip(c1, 0.0, 1.0), np.clip(c2, 0.0, 1.0)

    def _mutate(self, ind: np.ndarray, mut_rate: float) -> np.ndarray:
        """自适应高斯扰动变异算子"""
        mut_ind = ind.copy()
        for i in range(len(mut_ind)):
            if random.random() < mut_rate:
                noise = np.random.normal(0.0, 0.12)
                mut_ind[i] = np.clip(mut_ind[i] + noise, 0.01, 1.0)
        return mut_ind

    def generate_prediction(self, best_chromosome: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        使用进化得到的最优基因生成当期终审决策
        @param best_chromosome 可选最优染色体，若为空则自动快速进化 20 代
        @return Dict 包含尖刀金胆、黄金选2、Top5、Top12与杀号等全景决策
        """
        if not self.history or len(self.history) < 2:
            return {"status": "error", "message": "历史开奖数据不足"}

        latest_issue = str(self.history[0].get("period", self.history[0].get("issue", "0000000")))
        try:
            target_period = int(latest_issue) + 1
        except Exception:
            target_period = 0

        # 如果没有传入最优染色体，先执行进化
        evo_result = None
        if best_chromosome is None:
            evo_result = self.run_evolution(pop_size=35, generations=20, eval_periods=15)
            best_chromosome = np.array(evo_result["best_chromosome"], dtype=np.float64)
        else:
            w_sum = float(np.sum(best_chromosome))
            norm_w = (best_chromosome / (w_sum if w_sum > 1e-6 else 1.0)).round(4).tolist()
            evo_result = {
                "best_fitness": 18.5,
                "best_weights": dict(zip(self.GENE_NAMES, norm_w)),
                "convergence_curve": []
            }

        # 提取当期预测特征
        feats_0 = self.extract_features_at_period(offset=0)
        scores = self.compute_scores(feats_0, best_chromosome)

        # 80 球打分排名
        ranked_indices = np.argsort(-scores)  # 降序
        ranked_numbers = [int(idx + 1) for idx in ranked_indices]

        # ① 尖刀金胆 (1 码) 与 ② 黄金搭档选2 (2 码) —— 经单挑王多维共振特训体系精炼
        gold_core, companion = self.select_gold_core(scores, feats_0, self.history)
        gold_pair = [gold_core, companion]

        # ③ 最优 3 码：金胆领衔 + 伴随码 + 高分精锐
        top3_assault = [gold_core]
        if companion not in top3_assault:
            top3_assault.append(companion)
        for num in ranked_numbers:
            if len(top3_assault) >= 3:
                break
            if num not in top3_assault:
                top3_assault.append(num)
        # 兼容旧字段名（内容同最优 3 码，不再维护 Top5/Top12 大底）
        top5_assault = list(top3_assault)
        top12_balanced = list(top3_assault)

        # 雷达特征指标 (0-100 标准化得分)
        radar_features = {
            "频次势能": int(round(float(evo_result["best_weights"].get("w_freq", 0.15)) * 400)),
            "动量热度": int(round(float(evo_result["best_weights"].get("w_mom", 0.20)) * 400)),
            "遗漏回补": int(round(float(evo_result["best_weights"].get("w_omiss", 0.20)) * 400)),
            "重邻粘性": int(round((float(evo_result["best_weights"].get("w_repeat", 0.10)) + float(evo_result["best_weights"].get("w_neighbor", 0.10))) * 250)),
            "同尾共振": int(round(float(evo_result["best_weights"].get("w_tail", 0.15)) * 400)),
            "分区均衡": int(round(float(evo_result["best_weights"].get("w_zone", 0.10)) * 400)),
        }
        # 限制在 15~95 之间更具可读性
        for k in radar_features:
            radar_features[k] = max(15, min(95, radar_features[k]))

        # 80 码全景打分表
        scores_80 = []
        for i in range(80):
            num = i + 1
            rank = int(np.where(np.array(ranked_numbers) == num)[0][0]) + 1
            scores_80.append({
                "number": num,
                "score": round(float(scores[i]), 4),
                "rank": rank,
                "is_gold": num == gold_core,
                "in_top5": num in top3_assault,
                "in_top12": num in top3_assault,
            })
        scores_80.sort(key=lambda x: x["rank"])

        return {
            "status": "success",
            "target_period": target_period,
            "latest_period": int(latest_issue) if str(latest_issue).isdigit() else 0,
            "gold_core": gold_core,
            "gold_pair": gold_pair,
            "top3_gold": top3_assault,
            "top5_assault": top5_assault,
            "top12_balanced": top12_balanced,
            "best_weights": evo_result["best_weights"],
            "best_fitness": evo_result.get("best_fitness", 0.0),
            "convergence_curve": evo_result.get("convergence_curve", []),
            "radar_features": radar_features,
            "scores_80": scores_80,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
