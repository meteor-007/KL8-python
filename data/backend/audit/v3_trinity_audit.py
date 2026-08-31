# -*- coding: utf-8 -*-
"""
三维融合审计模块 (Trinity Audit) — v4.0
================================
DEPRECATED (v3.0): 日报已统一走 main_v2.run_pipeline() + ScoreComposer。
本模块保留供历史脚本/对照实验，勿在新代码中引用。

v4.0: MK/EO已移除, 仅保留EF/RW/FO三维融合
v3.0 统一评分管线重构:

核心评分函数已迁移至 core/energy_field.py + core/score_composer.py，
本模块仅保留兼容性代理接口 + 审计辅助功能。

变更日志:
  - calc_energy_field → 迁移到 core/energy_field.py
  - run_weight → 委托给 core/score_composer.ScoreComposer
  - dynamic_meta_fusion → 委托给 core/score_composer.ScoreComposer
  - 保留旧接口兼容性（backward compatible）
"""
import collections
import os
import json
import math
import numpy as np

from core.feature_optimizer import load_all_data
from core.algorithm_optimizer import plan7_markov_integration

# ── 兼容性: 保留旧接口，内部委托到 core/energy_field.py ──

def calc_energy_field(history, decay_rate=0.5, diffusion_factor=0.4):
    """计算号码的能量场分布——隐能量场 (兼容接口)

    实际实现已迁移到 core/energy_field.py
    """
    from core.energy_field import calc_energy_field as _calc
    return _calc(history, decay_rate, diffusion_factor)


def run_weight(history, w_ef=0.4, w_rw=0.3, w_fo=0.3):
    """三维融合权重计算 (v4.0: 仅EF/RW/FO三维, MK/EO已移除)

    实际实现已统一到 core/score_composer.ScoreComposer
    """
    from core.energy_field import calc_energy_field, calc_omission_sigmoid
    from core.score_composer import ScoreComposer

    # v4.0: 仅计算EF/RW/FO三维
    ef_scores = calc_energy_field(history)
    rw_scores = calc_omission_sigmoid(history)

    try:
        from core.feature_optimizer import get_all_layer_a_scores
        fo_scores = get_all_layer_a_scores(history)
    except ImportError:
        fo_scores = {n: 0.0 for n in range(1, 81)}

    raw_scores = {
        'EF': ef_scores,
        'RW': rw_scores,
        'FO': fo_scores,
    }

    # 使用 ScoreComposer 统一管线
    composer = ScoreComposer()
    # v4.0: 仅EF/RW/FO三维权重
    override_weights = {
        'EF': w_ef, 'RW': w_rw, 'FO': w_fo
    }
    final_scores = composer.compose(
        raw_scores,
        environment='balanced',
        volatility=0.15,
    )

    # 因为 ScoreComposer 使用 learner/Loss 权重而非传入的 w_mk 等，
    # 如果需要严格使用传入权重，直接手动加权（兼容旧行为）
    if not composer._learner_weights and not composer._loss_weights:
        # 没有外部权重，使用传入的权重手动加权（保持旧接口行为）
        from core.score_composer import ScoreComposer as SC
        norm_fn = SC._normalize_percentile
        normalized = {dim: norm_fn(scores) if scores else {n: 0.5 for n in range(1, 81)}
                      for dim, scores in raw_scores.items()}
        weights = override_weights
        total_w = sum(weights.values())
        if total_w > 0:
            weights = {k: v / total_w for k, v in weights.items()}

        result = collections.Counter()
        for n in range(1, 81):
            s = 0.0
            for dim, norm_scores in normalized.items():
                w = weights.get(dim, 0)
                s += w * norm_scores.get(n, 0.0)
            result[n] = round(s, 6)
        return result

    return final_scores


def _load_learner_weights():
    """从learner_state.json读取学习引擎的当前权重 (闭环连通)
    
    注意: 必须与 ScoreComposer._load_learner_weights() 保持一致的门控逻辑，
    否则显示的权重与实际计算使用的权重不一致。
    """
    try:
        from core.learning_gate import is_learning_enabled
        if not is_learning_enabled():
            return None
    except Exception:
        pass
    try:
        learner_state_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'cache', 'learner_state.json'
        )
        if os.path.exists(learner_state_file):
            with open(learner_state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            pw = state.get('pentagon_weights', {})
            if pw and all(k in pw for k in ('EF', 'RW', 'FO')):
                # v4.0: 仅需EF/RW/FO三维键, MK/EO已移除
                return pw
    except Exception:
        pass
    return None


def dynamic_meta_fusion(history):
    """动态元融合: 自动检测最佳权重 (v4.0 - 三维融合EF/RW/FO)

    优先级:
      1. learner_state.json中的学习权重 (闭环连通)
      2. 基于波动率的环境自适应权重
      3. 默认权重

    v4.0: MK/EO已移除, 仅使用EF/RW/FO三维
    v3.0: 统一使用 ScoreComposer 管线，消除双重评分。
    """
    if len(history) < 10:
        return collections.Counter(), {'EF': 0.40, 'RW': 0.30, 'FO': 0.30}

    from core.energy_field import calc_energy_field, calc_omission_sigmoid
    from core.score_composer import ScoreComposer

    # v4.0: MK/EO已移除, 仅计算EF/RW/FO三维分数
    ef_scores = calc_energy_field(history)
    rw_scores = calc_omission_sigmoid(history)

    try:
        from core.feature_optimizer import get_all_layer_a_scores
        fo_scores = get_all_layer_a_scores(history)
    except ImportError:
        fo_scores = {n: 0.0 for n in range(1, 81)}

    raw_scores = {
        'EF': ef_scores,
        'RW': rw_scores,
        'FO': fo_scores,
    }

    # 确定当前使用的权重（用于返回值）
    learner_weights = _load_learner_weights()
    if learner_weights:
        best = dict(learner_weights)
    else:
        # 基于波动率的环境自适应权重
        recent = history[:10]
        avg_vol = sum(
            sum((1 if n in h['numbers'] else 0) - 0.25 for n in range(1, 81)) ** 2 / 80
            for h in recent
        ) / len(recent) if recent else 0

        if avg_vol > 0.25:
            best = {'EF': 0.30, 'RW': 0.35, 'FO': 0.35}
        elif avg_vol < 0.1:
            best = {'EF': 0.50, 'RW': 0.20, 'FO': 0.30}
        else:
            best = {'EF': 0.40, 'RW': 0.30, 'FO': 0.30}

    # 统一使用 ScoreComposer 管线
    composer = ScoreComposer()
    final_scores = composer.compose(raw_scores, environment='balanced', volatility=0.15)

    return final_scores, best


if __name__ == '__main__':
    d1, d2, d1s, hist, pts = load_all_data()
    scores, weights = dynamic_meta_fusion(hist)
    sorted_scores = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:20]
    top_5 = [n for n, s in sorted_scores[:5]]
    top_12 = [n for n, s in sorted_scores[:12]]
    print(f"动态权重: EF={weights['EF']:.2f}, RW={weights['RW']:.2f}, FO={weights['FO']:.2f}")
    print(f"Top 5: {top_5}")
    print(f"Top 12: {top_12}")
