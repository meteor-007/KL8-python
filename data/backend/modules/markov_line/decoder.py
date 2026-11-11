# -*- coding: utf-8 -*-
"""
反向解码与高分辨力动能选择器 (Decoder & Micro-Gradient Selector - 终极实战进阶版)
================================================================================
彻底破除“大锅饭打分”与“平庸噪声”弊端，注入三大核心超额胜率因子：
  1. 16 期中热黄金带分桶 (16-Period Mid-Hot Regime):
     出号主力军是 16 期内出现 4~7 次的中热码 (赋予 1.0 满分动能)；
     对出现 >=8 次的过热码施加 0.65 衰减防守 (防高位回调接盘)；
     对 0~1 次深冷码施加 0.30 保护 (非反弹态不盲目买冷)。
  2. 空间高压夹击“影子点位” (Sandwich Shadow Squeeze):
     上一期 b-1 与 b+1 均开出、唯独中间 b 未开出时，形成物理空间挤压，具备极高单点穿透力。
  3. 转移熵攻防模式自适应切换 (Entropy Circuit Breaker):
     - 顺风局 (H <= 1.8): 确定性高，启动“重锤进攻模式”，金胆锐化提权；
     - 逆风局 (H > 2.2): 盘面混沌变盘，启动“防守刹车模式”，四区均衡平铺并预警。
  4. 四区均衡防守大底 (Zone-Balanced Elite 12):
     每象限保底 2 码，形成科学立体攻防体系。
"""

from typing import List, Dict, Any, Tuple
import math
import numpy as np

from backend.modules.markov_line.state_space import StateSpace, StateDefinition
from backend.modules.markov_line.line_calibrator import ResidualReboundSignal


class CandidateBallScore:
    """候选号码综合评分对象"""

    def __init__(
        self,
        ball: int,
        composite_score: float,
        mid_hot_score: float,
        neighbor_boost: float,
        sandwich_boost: float,
        omission_surge_score: float,
        rebound_score: float,
        gaussian_gravity_score: float,
        reason: str,
    ):
        self.ball = ball
        self.composite_score = composite_score
        self.mid_hot_score = mid_hot_score
        self.neighbor_boost = neighbor_boost
        self.sandwich_boost = sandwich_boost
        self.omission_surge_score = omission_surge_score
        self.rebound_score = rebound_score
        self.gaussian_gravity_score = gaussian_gravity_score
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ball": self.ball,
            "composite_score": round(self.composite_score, 4),
            "mid_hot_score": round(self.mid_hot_score, 4),
            "neighbor_boost": round(self.neighbor_boost, 4),
            "sandwich_boost": round(self.sandwich_boost, 4),
            "omission_surge": round(self.omission_surge_score, 4),
            "rebound_score": round(self.rebound_score, 4),
            "gaussian_gravity": round(self.gaussian_gravity_score, 4),
            "reason": self.reason,
        }


class MarkovLineDecoder:
    """终极高分辨力马尔可夫微观动能解码器"""

    def __init__(self, total_balls: int = 80):
        self.total_balls = total_balls
        self.state_space = StateSpace()

    def decode_predictions(
        self,
        predicted_state_probs: np.ndarray,
        rebound_signals: List[ResidualReboundSignal],
        latest_draw: List[int],
        current_omissions: Dict[int, int],
        ball_follow_matrix: np.ndarray,
        recent_draws: List[List[int]] = None,
        transition_entropy: float = 2.0,
    ) -> Dict[str, Any]:
        """
        根据宏观状态概率分布、微观动能场与转移熵攻防自适应解码
        """
        # 步骤 1：定位预测置信度最高的前 2 个宏观状态
        top_state_indices = np.argsort(-predicted_state_probs)[:2]
        top_states: List[Tuple[StateDefinition, float]] = [
            (self.state_space.decode(int(s_idx)), float(predicted_state_probs[s_idx]))
            for s_idx in top_state_indices
        ]
        primary_state, primary_prob = top_states[0]

        is_repeat_regime = (primary_state.momentum_level == "REPEAT_CLUST")
        is_cold_regime = (primary_state.momentum_level == "COLD_REBOUND")

        # 攻防模式判定 (基于转移熵)
        if transition_entropy <= 1.80:
            regime_mode = "AGGRESSIVE_STRIKE"  # 重锤进攻模式 (确定性高)
            regime_desc = "🔥 重锤进攻模式 (状态确定性高，重点出击金胆)"
        elif transition_entropy > 2.20:
            regime_mode = "DEFENSIVE_SHIELD"   # 防守刹车模式 (大环境变盘混沌)
            regime_desc = "🛡️ 防守刹车模式 (大环境离散分散，均衡防守降杠杆)"
        else:
            regime_mode = "BALANCED_TACTIC"    # 常规攻防平衡模式
            regime_desc = "⚖️ 均衡常态推进"

        # 步骤 2：16 期中热黄金带分桶 (16-Period Mid-Hot Regime)
        f16 = np.zeros(self.total_balls + 1, dtype=np.float64)
        if recent_draws:
            w16 = recent_draws[-16:] if len(recent_draws) >= 16 else recent_draws
            for d in w16:
                for b in d:
                    if 1 <= b <= self.total_balls:
                        f16[b] += 1.0

        mid_hot_score = np.zeros(self.total_balls + 1, dtype=np.float64)
        for b in range(1, self.total_balls + 1):
            cnt = f16[b]
            if 4 <= cnt <= 7:
                mid_hot_score[b] = 1.00  # 黄金主力中热号
            elif cnt >= 8:
                mid_hot_score[b] = 0.65  # 过热回调防守
            elif 2 <= cnt <= 3:
                mid_hot_score[b] = 0.55  # 温冷过渡号
            else:
                mid_hot_score[b] = 0.30  # 深冷休眠号

        # 步骤 3：空间邻号连庄与夹击影子点位 (Sandwich Shadow Squeeze)
        latest_set = set(latest_draw)
        neigh = np.zeros(self.total_balls + 1, dtype=np.float64)
        sandwich = np.zeros(self.total_balls + 1, dtype=np.float64)

        for b in range(1, self.total_balls + 1):
            if b in latest_set:
                neigh[b] += 1.00  # 连庄重号
            if (b - 1 in latest_set) or (b + 1 in latest_set):
                neigh[b] += 0.85  # 空间邻号扩散

            # 空间高压夹击判定：左右两端开出，中间唯独缺失 (高穿透力影子点位)
            if (b - 1 in latest_set) and (b + 1 in latest_set) and (b not in latest_set):
                sandwich[b] = 1.80

        # 步骤 4：遗漏动力学爆发非线性波形
        omission_surge = np.zeros(self.total_balls + 1, dtype=np.float64)
        for b in range(1, self.total_balls + 1):
            o = current_omissions.get(b, 0)
            if 3 <= o <= 6:
                omission_surge[b] = 1.00  # 快乐8 黄金理论爆发周期
            elif 7 <= o <= 11:
                omission_surge[b] = 0.85 if is_cold_regime else 0.70
            elif o == 0:
                omission_surge[b] = 0.80 if is_repeat_regime else 0.65
            elif o >= 12:
                omission_surge[b] = 0.80 if is_cold_regime else 0.40
            else:
                omission_surge[b] = 0.40

        # 步骤 5：直线残差均值回归映射
        rebound_map: Dict[int, float] = {}
        max_reb = max((s.rebound_strength for s in rebound_signals), default=1.0)
        max_reb = max(max_reb, 1e-5)
        for s in rebound_signals:
            rebound_map[s.target_id] = float(s.rebound_strength / max_reb)

        # 步骤 6：高斯和值物理重心梯度
        if primary_state.sum_level == "SUM_LOW":
            target_mu = 36.0
        elif primary_state.sum_level == "SUM_HIGH":
            target_mu = 45.0
        else:
            target_mu = 40.5

        gaussian_gravity = np.array([
            math.exp(-((b - target_mu) ** 2) / (2.0 * (22.0 ** 2)))
            for b in range(self.total_balls + 1)
        ], dtype=np.float64)
        gaussian_gravity = gaussian_gravity / np.max(gaussian_gravity)

        # 步骤 6.5：贝叶斯模型平均 (BMA - Bayesian Model Averaging) 全盘期望态势构建
        # 大白话：金胆要锋利(押注主状态)，大底要圆滑(全盘状态概率加权防守丢球)
        bma_gravity = np.zeros(self.total_balls + 1, dtype=np.float64)
        bma_surge = np.zeros(self.total_balls + 1, dtype=np.float64)
        for s_idx, s_prob in enumerate(predicted_state_probs):
            if s_prob < 0.01:
                continue
            s_def = self.state_space.decode(int(s_idx))
            s_mu = 36.0 if s_def.sum_level == "SUM_LOW" else (45.0 if s_def.sum_level == "SUM_HIGH" else 40.5)
            s_cold = (s_def.momentum_level == "COLD_REBOUND")
            s_rep = (s_def.momentum_level == "REPEAT_CLUST")

            for b in range(1, self.total_balls + 1):
                o = current_omissions.get(b, 0)
                if 3 <= o <= 6:
                    s_val = 1.00
                elif 7 <= o <= 11:
                    s_val = 0.85 if s_cold else 0.70
                elif o == 0:
                    s_val = 0.80 if s_rep else 0.65
                elif o >= 12:
                    s_val = 0.80 if s_cold else 0.40
                else:
                    s_val = 0.40

                bma_surge[b] += s_prob * s_val
                bma_gravity[b] += s_prob * math.exp(-((b - s_mu) ** 2) / (2.0 * (22.0 ** 2)))

        if np.max(bma_gravity) > 0:
            bma_gravity /= np.max(bma_gravity)

        # 步骤 7：多动能加权合成 (进攻与防守自适应权值)
        if regime_mode == "AGGRESSIVE_STRIKE":
            w_hot, w_ng, w_sw, w_reb, w_grav = 0.32, 0.30, 0.14, 0.16, 0.08
        else:
            w_hot, w_ng, w_sw, w_reb, w_grav = 0.28, 0.26, 0.12, 0.20, 0.09

        # A. 金胆锐度打分 (Gold Focus - 单点极致穿透)
        candidate_scores: List[CandidateBallScore] = []
        # B. 大底容错打分 (Elite BMA - 贝叶斯期望全盘容错)
        bma_candidate_scores: List[Tuple[int, float]] = []

        for b in range(1, self.total_balls + 1):
            reasons = []
            o = current_omissions.get(b, 0)

            if mid_hot_score[b] >= 0.9:
                reasons.append("16期黄金中热主力")
            if sandwich[b] >= 1.5:
                reasons.append("⚡ 空间夹击高压影子点(穿透提权)")
            elif neigh[b] >= 0.8:
                reasons.append("上期紧邻扩散")

            if 3 <= o <= 6:
                reasons.append(f"黄金周期爆发(遗漏{o}期)")
            elif o == 0 and is_repeat_regime:
                reasons.append("连庄热态核心重号")
            elif o >= 7 and is_cold_regime:
                reasons.append(f"冷号回补激活(遗漏{o}期)")

            reb_s = rebound_map.get(b, 0.0)
            if reb_s > 0.6:
                reasons.append("直线残差均值回归拐点")

            # 金胆单点穿透分
            comp = (
                w_hot * mid_hot_score[b]
                + w_ng * neigh[b]
                + w_sw * sandwich[b]
                + w_reb * omission_surge[b]
                + w_grav * gaussian_gravity[b]
                + 0.05 * reb_s
            )

            # 大底 BMA 期望容错分
            comp_bma = (
                w_hot * mid_hot_score[b]
                + w_ng * neigh[b]
                + w_sw * sandwich[b]
                + w_reb * bma_surge[b]
                + w_grav * bma_gravity[b]
                + 0.05 * reb_s
            )

            primary_reason = " | ".join(reasons) if reasons else "常态平稳推进"

            candidate_scores.append(
                CandidateBallScore(
                    ball=b,
                    composite_score=comp,
                    mid_hot_score=float(mid_hot_score[b]),
                    neighbor_boost=float(neigh[b]),
                    sandwich_boost=float(sandwich[b]),
                    omission_surge_score=float(omission_surge[b]),
                    rebound_score=reb_s,
                    gaussian_gravity_score=float(gaussian_gravity[b]),
                    reason=primary_reason,
                )
            )
            bma_candidate_scores.append((b, comp_bma))

        # 步骤 8：按综合得分降序严格排序
        candidate_scores.sort(key=lambda x: x.composite_score, reverse=True)
        bma_candidate_scores.sort(key=lambda x: x[1], reverse=True)

        # 金胆 Top 5：反扎堆最大分散度精选 (大白话：去重防滑移，别把鸡蛋放一个篮子里)
        top5_gold = self._select_top5_diversified(candidate_scores)

        # 核心大底 Top 12：贝叶斯模型平均 (BMA) + 和值几何形态自适应分区配额
        if primary_state.sum_level == "SUM_LOW":
            quotas = [4, 4, 2, 2]
        elif primary_state.sum_level == "SUM_HIGH":
            quotas = [2, 2, 4, 4]
        else:
            quotas = [3, 3, 3, 3]

        t12_set = set()
        for z in range(4):
            z_balls = [b for b, s in bma_candidate_scores if (b - 1) // 20 == z]
            t12_set.update(z_balls[:quotas[z]])

        # 防守兜底：若某区号码不足，用 BMA 综合最高分顺延补齐至 12 码
        for b, s in bma_candidate_scores:
            if len(t12_set) >= 12:
                break
            t12_set.add(b)

        top12_elite = sorted(list(t12_set))

        return {
            "primary_state": {
                "state_id": primary_state.state_id,
                "state_key": primary_state.state_key,
                "probability": round(primary_prob, 4),
                "description": primary_state.description,
                "sum_level": primary_state.sum_level,
                "odd_level": primary_state.odd_level,
                "momentum_level": primary_state.momentum_level,
            },
            "alternative_states": [
                {
                    "state_id": s.state_id,
                    "state_key": s.state_key,
                    "probability": round(p, 4),
                    "description": s.description,
                }
                for s, p in top_states[1:]
            ],
            "regime_mode": regime_mode,
            "regime_desc": regime_desc,
            "top5_gold": sorted(top5_gold),
            "top12_elite": top12_elite,
            "top_candidates_detail": [c.to_dict() for c in candidate_scores[:15]],
        }

    @staticmethod
    def _select_top5_diversified(candidate_scores: List[CandidateBallScore]) -> List[int]:
        """
        反扎堆最大分散度金胆精选 (Maximal Marginal Relevance / Anti-Clustering Selection)
        大白话：别把鸡蛋放一个篮子里！
        严禁出现三连号（如 51, 52, 53），同一十位区间最多容纳 2 码，防止局部微小滑移导致集体殉爆。
        """
        selected: List[int] = []
        for c in candidate_scores:
            b = c.ball
            if len(selected) == 0:
                selected.append(b)
                continue

            # 1. 连号冲突控制：不允许三连号，全盘最多容纳 1 对二连号
            adj_pairs = sum(
                1 for i in range(len(selected))
                for j in range(i + 1, len(selected))
                if abs(selected[i] - selected[j]) == 1
            )
            has_adj = any(abs(b - x) == 1 for x in selected)

            # 2. 十位区间密度控制：同一十位段 (如 50-59) 最多容纳 2 码
            same_decade = sum(1 for x in selected if (x - 1) // 10 == (b - 1) // 10)

            if (has_adj and adj_pairs >= 1) or same_decade >= 2:
                continue

            selected.append(b)
            if len(selected) == 5:
                break

        # 兜底保障：若筛选后不足 5 码，按综合得分最高顺延补齐
        if len(selected) < 5:
            for c in candidate_scores:
                if c.ball not in selected:
                    selected.append(c.ball)
                if len(selected) == 5:
                    break

        return sorted(selected)
