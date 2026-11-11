# -*- coding: utf-8 -*-
"""
unified_brain.py — 快乐8 全栈统一决策解算主脑 (Unified Master Decision Brain)
==========================================================================
【纯物理状态空间概率场联合解算，彻底废除人造线性加权与数人头反模式】：
  1. 接收五大物理特征提取器提供的纯内存统一特征包 (UnifiedFeatureBundle)；
  2. 在 80 维连续状态空间中联合解算能量势场与玻尔兹曼概率分布 P(N_1, ..., N_80)；
     - 时空非线性乘积共振势能：E_resonance = sqrt(F_time * F_space) (时空碰头才算数)；
     - 叠加形态规则激发能：E_total = 2.0 * E_resonance + ln(1 + F_rule)（拓扑项默认系数 0）；
  3. 杀号软参考（独立宪法默认不启用硬势垒）：
     - enable_hard_barrier=True 时才将雷区能量设为 -10^9；默认仅作研究对照；
  4. 玻尔兹曼-吉布斯概率场归一化：
     - 在合法安全区域执行带温控的 Softmax 概率归一化，全盘概率严格和为 1.0；
  5. 一脉相承的层级化实战决策：
     - ① 尖刀金胆 (1 码 / 第一王牌主攻手 / 概率主峰且非雷区)；
     - ② 黄金连体伴随 (定金选2 / 抓连体婴搭档 / 以金胆为锚点顺藤摸瓜找最佳搭档)；
     - ③ 最优 3 码 (主口径进攻火力；旧 Top5/Top12 字段同内容兼容)；
  6. 输出五大特征标准化战力雷达图得分 (0-100) 并持久化结构化资产。
"""
from __future__ import annotations
from backend.utils.paths import get_outputs_dir

import os
import sys
import json
import math
from datetime import datetime
from typing import Dict, List, Set, Any, Tuple, Optional, Union
from dataclasses import dataclass, field

import numpy as np

from .feature_extractors import (
    FeatureEngineeringLayer,
    FeatureEngineeringPipeline,
    UnifiedFeatureBundle,
    NUM_TOTAL
)

# 统一决策资产落盘目录
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BRAIN_OUTPUT_DIR = os.path.join(get_outputs_dir(), "unified_brain")
os.makedirs(BRAIN_OUTPUT_DIR, exist_ok=True)


@dataclass
class UnifiedDecisionResult:
    """
    统一主脑决策成果数据类 (Unified Decision Result Contract)
    """
    target_period: int
    calculated_at: str
    architecture: str
    gold_single: int
    gold_core: int
    gold_pair: List[int]
    top3_gold: List[int]
    top5: List[int]
    top5_assault: List[int]
    top12_balanced: List[int]
    killed_count: int
    killed_numbers: List[int]
    probabilities: Dict[str, float]
    radar_features: Dict[str, float]
    hyperparameters: Dict[str, Any]
    meta_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_period": int(self.target_period),
            "calculated_at": str(self.calculated_at),
            "architecture": str(self.architecture),
            "gold_single": int(self.gold_single),
            "gold_core": int(self.gold_core),
            "gold_pair": [int(x) for x in self.gold_pair],
            "top3_gold": [int(x) for x in self.top3_gold],
            "top5": [int(x) for x in self.top5],
            "top5_assault": [int(x) for x in self.top5_assault],
            "top12_balanced": [int(x) for x in self.top12_balanced],
            "killed_count": int(self.killed_count),
            "killed_numbers": [int(x) for x in self.killed_numbers],
            "probabilities": {str(k): float(v) for k, v in self.probabilities.items()},
            "radar_features": {str(k): float(v) for k, v in self.radar_features.items()},
            "hyperparameters": self.hyperparameters,
            "meta_info": self.meta_info,
        }


class UnifiedDecisionBrain:
    """
    全栈统一决策主脑 (Unified Master Decision Brain)
    大白话：全局智能操盘总指挥部。
    基于五大物理特征，在 80 维状态空间联合解算能量势场与玻尔兹曼概率分布，输出一脉相承四级层级决策。
    """

    def __init__(self, data_root: Optional[str] = None,
                 output_dir: Optional[str] = None):
        """
        Args:
            data_root: 项目根目录
            output_dir: 决策资产落盘目录。默认 None = 生产目录 outputs/unified_brain
                (同时双向同步前端静态资产)。测试请显式传入临时目录, 否则单元测试
                会把合成结果写进生产归档 (曾污染出 target_period=2026299 的幻影期)。
        """
        self.data_root = data_root or _PROJ_ROOT
        self.output_dir = output_dir or BRAIN_OUTPUT_DIR
        self.is_production_output = (output_dir is None)
        if self.output_dir != BRAIN_OUTPUT_DIR:
            os.makedirs(self.output_dir, exist_ok=True)
        self.feature_layer = FeatureEngineeringLayer(self.data_root)
        self.pipeline = self.feature_layer.pipeline

    def compute_radar_features(
        self,
        bundle: UnifiedFeatureBundle,
        top_indices: List[int],
        valid_indices: np.ndarray,
        killed_indices: np.ndarray
    ) -> Dict[str, float]:
        """
        计算 5 大物理维度雷达图标准化战力得分 (0-100)
        大白话：给今天五个维度的战况打分（0到100分），看哪方面底气最足。
        - 时序惯性 (time_inertia): 主力号码的时序动量与冷热势头强度
        - 空间能量 (spatial_energy): 局部聚类高斯核流能充沛度
        - 形态规则 (rule_activation): 90条经典口诀与形态反弹共鸣深度
        - 拓扑共现 (topological_energy): 历史共现图谱牵引与搭档粘性
        - 防守安全 (defense_strength): 防守雷区过滤深度与大盘安全度
        """
        eval_indices = top_indices[:5] if len(top_indices) >= 5 else list(range(NUM_TOTAL))

        # 1. 时序惯性得分 (0-100)
        if len(eval_indices) > 0 and np.any(bundle.time_inertia > 0):
            t_val = float(np.mean(bundle.time_inertia[eval_indices]))
            time_score = min(100.0, max(0.0, t_val * 100.0))
        else:
            time_score = 50.0

        # 2. 空间能量得分 (0-100)
        if len(eval_indices) > 0 and np.any(bundle.spatial_energy > 0):
            s_val = float(np.mean(bundle.spatial_energy[eval_indices]))
            spatial_score = min(100.0, max(0.0, s_val * 100.0))
        else:
            spatial_score = 50.0

        # 3. 形态规则得分 (0-100)
        if len(eval_indices) > 0 and np.any(bundle.rule_activation > 0):
            r_val = float(np.mean(bundle.rule_activation[eval_indices]))
            rule_score = min(100.0, max(0.0, r_val * 100.0))
        else:
            rule_score = 40.0

        # 4. 拓扑共现得分 (0-100)
        if len(eval_indices) > 0 and np.any(bundle.topological_energy > 0):
            topo_val = float(np.mean(bundle.topological_energy[eval_indices]))
            topo_score = min(100.0, max(0.0, topo_val * 100.0))
        else:
            topo_score = 50.0

        # 5. 防守安全得分 (0-100)
        safe_ratio = len(valid_indices) / float(NUM_TOTAL)
        defense_score = min(100.0, max(0.0, safe_ratio * 100.0))

        return {
            "time_inertia": round(time_score, 1),
            "spatial_energy": round(spatial_score, 1),
            "rule_activation": round(rule_score, 1),
            "topological_energy": round(topo_score, 1),
            "defense_strength": round(defense_score, 1),
        }

    def solve_bundle(
        self,
        bundle: UnifiedFeatureBundle,
        temperature: float = 1.0,
        enable_hard_barrier: bool = False
    ) -> Dict[str, Any]:
        """
        直接接收强类型 UnifiedFeatureBundle，在 80 维状态空间执行纯物理概率解算与层级化决策
        :param bundle: M1 交付的统一特征包
        :param temperature: 玻尔兹曼热力学温度 T (默认 1.0, 范围 [0.05, 50.0])
        :param enable_hard_barrier: 是否启用杀号硬势垒阻断 (独立宪法默认 False，仅研究模式按需开启)
        :return: 包含完整四级决策与概率分布的结构化字典
        """
        # 0. 基础校验
        bundle.validate()
        f_time = bundle.time_inertia
        f_space = bundle.spatial_energy
        f_rule = bundle.rule_activation
        f_topo = bundle.topological_energy
        co_matrix = bundle.cooccurrence_matrix
        f_mask = bundle.defense_mask

        # 1. 物理势能场非线性解算 (Nonlinear Potential Resonance)
        # 时空乘积产生超线性共振 (大白话：时空碰头才算数，两者双高能量爆发，单项为零共振消除)
        resonance_energy = np.sqrt(np.clip(f_time * f_space, 0.0, None))

        # 叠加形态规则激发能（拓扑共现已证伪，独立宪法归零）
        total_energy = resonance_energy * 2.0 + np.log1p(np.clip(f_rule, 0.0, None)) + 0.0 * f_topo

        # 2. 杀号硬掩码物理归零势垒投影 (Hard Barrier Projection - 独立宪法默认关闭，仅实验研究模式开启)
        killed_indices = np.where(~f_mask)[0]
        raw_potentials = np.copy(total_energy)
        if enable_hard_barrier or len(killed_indices) > 0:
            valid_indices = np.where(f_mask)[0]
            if len(killed_indices) > 0:
                raw_potentials[killed_indices] = -1e9
        else:
            valid_indices = np.arange(NUM_TOTAL)

        # 3. 玻尔兹曼-吉布斯概率分布 (Softmax with Temperature)
        # 大白话：按热度算真实胜率，全盘概率加起来严格等于 1.0
        temp = max(float(temperature), 1e-4)
        full_probs = np.zeros(NUM_TOTAL, dtype=np.float64)

        if len(valid_indices) > 0:
            valid_energies = raw_potentials[valid_indices]
            max_energy = np.max(valid_energies)
            # 防止数值下溢/溢出
            scaled_energies = (valid_energies - max_energy) / temp
            scaled_energies = np.clip(scaled_energies, -80.0, 80.0)
            exp_energy = np.exp(scaled_energies)
            sum_exp = np.sum(exp_energy)
            if sum_exp > 0:
                probs_valid = exp_energy / sum_exp
            else:
                probs_valid = np.ones(len(valid_indices), dtype=np.float64) / len(valid_indices)
            full_probs[valid_indices] = probs_valid
        else:
            # 极端异常防崩溃回退：若所有号码全被杀（理论不可能），等概率均分
            full_probs = np.ones(NUM_TOTAL, dtype=np.float64) / NUM_TOTAL

        # 4. 生成一脉相承四级层级化决策清单 (Hierarchical Decisions)
        last_draw_set = set(bundle.meta_info.get("last_draw_numbers", []))

        if len(valid_indices) > 0:
            sorted_valid = sorted(valid_indices, key=lambda idx: full_probs[idx], reverse=True)
        else:
            sorted_valid = list(range(NUM_TOTAL))

        # 4.1 💎 尖刀核心金胆 (1码 / 第一王牌主攻手 / 概率场主峰)
        gold_idx = int(sorted_valid[0])
        gold_num = gold_idx + 1
        gold_is_repeat = gold_num in last_draw_set

        # 4.2 👑 黄金连体伴随 (定金选2 / 抓连体婴搭档 / 冷热对冲)
        # 以金胆为锚点，在剩余安全候选球中顺藤摸瓜寻找与金胆共现粘性最大且自身概率优秀的最佳搭档：
        # 严格执行【冷热对冲】：若金胆本身已是上一期重号，搭档坚决杜绝重号，强制选择高共现温态/回补球！
        best_partner_idx = None
        max_partner_score = -1e18

        for cand_idx in sorted_valid[1:]:
            cand_idx = int(cand_idx)
            cand_num = cand_idx + 1
            # 冷热对冲防线：若金胆已是重号，候选搭档若是重号则直接跳过，防止陷入“双重号”低概率泥潭
            if gold_is_repeat and (cand_num in last_draw_set):
                continue

            co_score = float(co_matrix[gold_idx, cand_idx]) if co_matrix.shape == (NUM_TOTAL, NUM_TOTAL) else 0.0
            cand_prob = float(full_probs[cand_idx])
            partner_score = cand_prob * (1.0 + math.log1p(max(0.0, co_score)))
            if partner_score > max_partner_score:
                max_partner_score = partner_score
                best_partner_idx = cand_idx

        # 极端兜底防御
        if best_partner_idx is not None:
            partner_num = int(best_partner_idx + 1)
        elif len(sorted_valid) > 1:
            partner_num = int(sorted_valid[1] + 1)
        else:
            partner_num = 2 if gold_num != 2 else 1

        gold_pair = [int(gold_num), int(partner_num)]

        # 4.3 🎯 最优 3 码（主口径；旧 Top5/Top12 字段同内容兼容）
        # 快乐8单期平均重号为4-5个(25%)。最优3码中限制最多1个重号，防止全盘追昨天的热号
        top3_nums = []
        repeat_count = 0
        max_repeats_in_top3 = 1

        for idx in sorted_valid:
            num = int(idx) + 1
            is_rep = num in last_draw_set
            if is_rep and repeat_count >= max_repeats_in_top3:
                continue
            top3_nums.append(num)
            if is_rep:
                repeat_count += 1
            if len(top3_nums) == 3:
                break

        # 若因重号被过滤导致不足3个，用剩余有效高概率球补齐
        if len(top3_nums) < 3:
            for idx in sorted_valid:
                num = int(idx) + 1
                if num not in top3_nums:
                    top3_nums.append(num)
                if len(top3_nums) == 3:
                    break

        # 4.4 ⚔️ 进取型 Top 5 突击战队 (Top 5 assault, 严格遵守契约与重号防泥潭)
        top5_nums = []
        repeat_count_5 = 0
        max_repeats_in_top5 = 2
        for idx in sorted_valid:
            num = int(idx) + 1
            is_rep = num in last_draw_set
            if is_rep and repeat_count_5 >= max_repeats_in_top5:
                continue
            top5_nums.append(num)
            if is_rep:
                repeat_count_5 += 1
            if len(top5_nums) == 5:
                break

        if len(top5_nums) < 5:
            for idx in sorted_valid:
                num = int(idx) + 1
                if num not in top5_nums:
                    top5_nums.append(num)
                if len(top5_nums) == 5:
                    break

        # 4.5 🛡️ 8分区均衡底仓 Top 12 (Balanced 12 across 8 zones, 保证 >=6 分区覆盖)
        top12_nums = []
        zone_best = {}
        for idx in sorted_valid:
            num = int(idx) + 1
            zone = (num - 1) // 10
            if zone not in zone_best:
                zone_best[zone] = num

        # 先按各分区领头羊的综合胜率排序，依次入选保底底仓
        sorted_zones = sorted(zone_best.keys(), key=lambda z: full_probs[zone_best[z] - 1], reverse=True)
        for z in sorted_zones:
            top12_nums.append(zone_best[z])
            if len(top12_nums) == 8:
                break

        # 剩余名额从全局最高概率号码中按序补齐至 12 码
        for idx in sorted_valid:
            num = int(idx) + 1
            if num not in top12_nums:
                top12_nums.append(num)
            if len(top12_nums) == 12:
                break
        top12_nums = sorted(top12_nums)

        # 5. 计算五大物理维度标准化战力得分 (0-100)
        radar_features = self.compute_radar_features(
            bundle=bundle,
            top_indices=sorted_valid,
            valid_indices=valid_indices,
            killed_indices=killed_indices
        )

        # 6. 整理杀号雷区号码
        killed_numbers_sorted = sorted([int(i) + 1 for i in killed_indices])

        # 7. 组装决策结果
        target_period = int(bundle.target_period)
        hyperparams = bundle.meta_info.get("hyperparams", {})
        hyperparams_dict = {
            "sigma": float(hyperparams.get("sigma", 2.50)),
            "lambda_decay": float(hyperparams.get("lambda_decay", 0.95)),
            "temperature": float(temp),
            "kill_size": int(hyperparams.get("kill_size", len(killed_indices))),
        }

        decision_obj = UnifiedDecisionResult(
            target_period=target_period,
            calculated_at=datetime.now().isoformat(),
            architecture="Unified Quantum Decision Brain (Research Only)",
            gold_single=int(gold_num),
            gold_core=int(gold_num),
            gold_pair=[int(gold_pair[0]), int(gold_pair[1])],
            top3_gold=[int(x) for x in top3_nums],
            top5=[int(x) for x in top5_nums],
            top5_assault=[int(x) for x in top5_nums],
            top12_balanced=[int(x) for x in top12_nums],
            killed_count=int(len(killed_indices)),
            killed_numbers=killed_numbers_sorted,
            probabilities={str(i + 1): float(full_probs[i]) for i in range(NUM_TOTAL)},
            radar_features=radar_features,
            hyperparameters=hyperparams_dict,
            meta_info={
                "role": "research_only",
                "experimental": True,
                "enable_hard_barrier": enable_hard_barrier,
                "draw_date": bundle.draw_date,
                "safe_count": int(len(valid_indices)),
                "radar_scores": radar_features,
                **bundle.meta_info
            }
        )

        res_dict = decision_obj.to_dict()

        # 8. 自动落盘决策资产与 Markdown 战报
        self._save_assets(res_dict)

        return res_dict

    def solve_period(
        self,
        target_period: int,
        sigma: float = 2.5,
        lambda_decay: float = 0.95,
        kill_size: int = 15,
        temperature: float = 1.0,
        enable_hard_barrier: bool = False,
        rule_weights: Optional[Dict[str, float]] = None,
        engine_weights: Optional[Dict[str, float]] = None,
        topo_window: int = 50,
        **kwargs
    ) -> Dict[str, Any]:
        """
        对指定期号执行全流程特征提取与实验性主脑解算
        :param target_period: 待预测的目标期号 (例如 2026234)
        :param sigma: 空间高斯核宽 (默认 2.5)
        :param lambda_decay: 时序衰减半衰期 (默认 0.95)
        :param kill_size: 杀号硬掩码规模 (默认 15)
        :param temperature: 玻尔兹曼温度 (默认 1.0)
        :param enable_hard_barrier: 是否启用硬掩码势垒阻断 (默认 False)
        :param rule_weights: 口诀规则动态权重字典
        :param engine_weights: 杀号子引擎动态权重字典
        :param topo_window: 拓扑共现回溯窗口
        :return: 包含层级决策与概率分布的结构化字典
        """
        # 1. 组装超参数
        hyperparams = {
            "sigma": float(sigma),
            "lambda_decay": float(lambda_decay),
            "kill_size": int(kill_size),
            "temperature": float(temperature),
            "topo_window": int(topo_window),
            "enable_hard_barrier": bool(enable_hard_barrier),
            "kill_soft_reference_only": not bool(enable_hard_barrier),
        }
        if rule_weights:
            hyperparams["rule_weights"] = rule_weights
        if engine_weights:
            hyperparams["kill_engine_weights"] = engine_weights
        hyperparams.update(kwargs)

        # 2. 纯内存调度流水线提取五大物理特征包
        bundle = self.feature_layer.extract_bundle(target_period, hyperparams=hyperparams)

        # 3. 统一概率主脑解算并输出
        return self.solve_bundle(bundle, temperature=temperature, enable_hard_barrier=enable_hard_barrier)

    def _save_assets(self, res: Dict[str, Any]) -> Tuple[str, str]:
        """
        持久化保存 JSON 资产与老派量化操盘手大白话 Markdown 研报
        """
        period = res["target_period"]
        json_path = os.path.join(self.output_dir, f"unified_decision_{period}.json")
        report_path = os.path.join(self.output_dir, f"unified_decision_report_{period}.md")

        # 1. 保存结构化 JSON 资产 (outputs/unified_brain 与 frontend/static 保持双向同步)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)

            # 同步更新前端静态资产 (仅生产落盘时; 测试沙箱不得触碰线上资产)
            static_frontend_path = os.path.join(self.data_root, "frontend", "static", "unified_decision_latest.json")
            if self.is_production_output and os.path.exists(os.path.dirname(static_frontend_path)):
                with open(static_frontend_path, "w", encoding="utf-8") as sf:
                    json.dump(res, sf, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存主脑决策 JSON 资产失败: {e}")

        # 2. 生成专业大白话 Markdown 研报
        radar = res.get("radar_features", {})
        lines = [
            f"# 🧬 快乐8 统一决策主脑全局推演研报 (第 {period} 期)",
            f"> 推演时间: {res.get('calculated_at', datetime.now().isoformat())} | 架构模式: **研究用特征合成（非实战主推 · 独立宪法）**",
            "",
            "## 👑 一脉相承 · 层级化实战决策清单 (老派操盘手实战部署)",
            "",
            "### 1. 💎 尖刀核心金胆 (第一王牌主攻手)",
            f"> **`【 {str(res['gold_single']).zfill(2)} 】`** (80维物理状态空间概率第一最高峰，确定性先锋)",
            "",
            "### 2. 👑 极简选2 · 黄金连体搭档 (抓连体婴最佳搭档)",
            f"> **`[ {str(res['gold_pair'][0]).zfill(2)} - {str(res['gold_pair'][1]).zfill(2)} ]`** (以金胆为锚点选取搭档；拓扑共现项默认归零)",
            "",
            "### 3. 🌟 最优 3 码 (主口径进攻火力)",
            f"> **`{' - '.join(str(x).zfill(2) for x in (res.get('top3_gold') or res.get('top5') or []))}`** (全盘连续概率能量最高的 3 个安全优势号码)",
            "",
            f"### 4. 📎 杀号参考列表（默认未硬否决 · 仅研究标注 {res.get('killed_count', len(res.get('killed_numbers', [])))} 码)",
            f"> `{' '.join(str(x).zfill(2) for x in res.get('killed_numbers', []))}` (独立宪法: enable_hard_barrier=False 时不改概率，仅对照)",
            "",
            "---",
            "## 📊 五大物理维度战力雷达图评分 (0-100 标准化指数)",
            f"- ⏱️ **时序惯性 (看冷热势头)**: `{radar.get('time_inertia', 0.0)} / 100`",
            f"- 🌐 **空间能量 (蹭聚类热度)**: `{radar.get('spatial_energy', 0.0)} / 100`",
            f"- 📜 **形态规则 (老经验出击)**: `{radar.get('rule_activation', 0.0)} / 100`",
            f"- 🔗 **拓扑共现 (找搭档跟班)**: `{radar.get('topological_energy', 0.0)} / 100`",
            f"- 🛡️ **防守强度 (踩刹车防守)**: `{radar.get('defense_strength', 0.0)} / 100`",
            "",
            "---",
            "## 🔬 统一决策主脑物理推演核心原理",
            "1. **彻底拒绝人造加权比 (大白话：不搞和稀泥加权)**: 废除任何 `w1*A + w2*B`，采用时空乘积非线性共振 `sqrt(Time * Space)`，时空碰头才爆发；",
            "2. **杀号默认软参考 (独立宪法)**: 默认不启用硬势垒；杀号列表仅研究对照，不否决主峰；",
            "3. **选2搭档**: 以概率主峰为锚选取搭档；共现拓扑权重已归零；",
            "4. **主口径最优 3 码**: 不再维护独立 Top5/Top12 大底产品面。"
        ]

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            print(f"⚠️ 保存主脑决策研报 Markdown 失败: {e}")

        return json_path, report_path
