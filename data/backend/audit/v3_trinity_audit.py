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


class WeightsWithSource(dict):
    """权重字典 + 来源说明 (D2, 2026-09-10)。

    大白话: 三位一体权重到底哪来的——是学习引擎算的, 还是门控冻结后用波动率
    静态兜底的? 以前没人说得清, 界面只能假装它在学习。现在权重字典自己带一张
    "身份证"(weights_source / weights_note), 但仍是 dict 子类, 老的
    `weights['EF']` / `dict(weights)` / `sum(weights.values())` 全部照常工作。
    """

    def __init__(self, *args, source: str = "unknown", note: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.weights_source = source
        self.weights_note = note


def weights_source_of(weights) -> dict:
    """取任意权重对象的来源说明; 没有身份证的返回 'unknown'。"""
    return {
        "weights_source": getattr(weights, "weights_source", "unknown"),
        "weights_note": getattr(weights, "weights_note", ""),
    }

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
                # 2026-11-10：AutonomousLearner 已退役，该状态文件不再更新。
                # 过期权重不得参与打分，展示口径也一并失效 —— 超过 30 天判为无效。
                try:
                    from datetime import datetime as _dtm
                    _upd = str(state.get('updated_at') or '')[:19]
                    if (_dtm.now() - _dtm.strptime(_upd, '%Y-%m-%d %H:%M:%S')).days > 30:
                        return None
                except Exception:
                    return None
                # v4.0: 仅需EF/RW/FO三维键, MK/EO已移除
                return pw
    except Exception:
        pass
    return None


def dynamic_meta_fusion(history, environment: str = 'balanced'):
    """动态元融合: 自动检测最佳权重 (v4.0 - 三维融合EF/RW/FO)

    Args:
        history: 历史开奖
        environment: 环境键 (hot_burst/cold_rebound/balanced/trend_accel/chaotic)。
            2026-10-22 一致性修复 (Bug#4)：原先硬编码 'balanced'，环境识别结果
            从未参与真正打分 —— 现在调用方把识别出的环境传进来，环境自适应才真正生效。

    优先级:
      1. learner_state.json中的学习权重 (闭环连通)
      2. 环境自适应权重 (ScoreComposer 按 environment 档位取 YAML environment_overrides)
      3. 默认权重

    v4.0: MK/EO已移除, 仅使用EF/RW/FO三维
    v3.0: 统一使用 ScoreComposer 管线，消除双重评分。
    """
    if len(history) < 10:
        return (collections.Counter(),
                WeightsWithSource({'EF': 0.40, 'RW': 0.30, 'FO': 0.30},
                                  source="default_insufficient_history",
                                  note=f"历史不足10期 (实际{len(history)}期), 用默认权重兜底"))

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
        best = WeightsWithSource(learner_weights, source="learner",
                                 note="权重来自 learner_state.json 学习权重 (门控开启, 参数在学)")
    else:
        # 2026-10-22 死逻辑清除 (Bug#3)：原「波动率分档」公式为
        #   avg_vol = Σ_periods ( Σ_balls (1[ball∈draw] − 0.25) )² / 80 / n
        # 而每期恰开 20/80 码，内层 Σ = 20×0.75 − 60×0.25 ≡ 0（恒等式，与开奖内容无关），
        # 故 avg_vol 永远是 0.000，三档阈值 (>0.25 / <0.1 / else) 永远只命中「低波动」档。
        # 这是一条数学上不可能 Discriminate 的死分支，却长期把「EF:0.50 RW:0.20 FO:0.30」
        # 冒充环境自适应权重展示给复盘 —— 已移除。
        # 现按传入的环境档位取 ScoreComposer 的 environment_overrides (与真正打分同源)，
        # 下方仍统一以 composer.last_weights 为最终回显准绳。
        try:
            _wt = ScoreComposer()._get_env_weights(environment)
            _env_note = f"环境={environment} 自适应权重"
        except Exception:
            _wt = {'EF': 0.40, 'RW': 0.30, 'FO': 0.30}
            _env_note = "默认权重 (环境权重读取失败)"

        _gate_frozen = True
        try:
            from core.learning_gate import is_learning_enabled
            _gate_frozen = not is_learning_enabled()
        except Exception:
            pass
        _src = "env_static_gate_frozen" if _gate_frozen else "env_static"
        _note = (f"权重来自{_env_note}"
                 + (", 自学习被门控冻结 (WF 95%CI下界<1.0), 这套权重不在学习" if _gate_frozen else ""))
        best = WeightsWithSource(_wt, source=_src, note=_note)

    # 统一使用 ScoreComposer 管线 (环境键透传，环境自适应真正生效)
    composer = ScoreComposer()
    final_scores = composer.compose(raw_scores, environment=environment, volatility=0.15)

    # 2026-10-22 一致性修复 (Bug#2)：上面算出来的 best 只是「展示用权重」，
    # 而 compose 内部按 learner/Loss/环境+波动率自行决定真正打分权重。
    # 历史事故：报告显示 EF:0.50 RW:0.20 FO:0.30，实际打分却是 balanced 0.40/0.30/0.30，
    # 复盘归因与「调参是否合理」的判断全部建立在从未生效的权重上。
    # 现以 composer 实际使用的权重为准回显（拿不到时才退回推算值并如实标注）。
    used = getattr(composer, 'last_weights', None)
    if used and all(k in used for k in ('EF', 'RW', 'FO')):
        if dict(best) != {k: round(float(used[k]), 4) for k in ('EF', 'RW', 'FO')}:
            best = WeightsWithSource(
                {k: used[k] for k in ('EF', 'RW', 'FO')},
                source=best.weights_source + "->composer_actual",
                note=(f"权重以 ScoreComposer 实际打分权重为准 (环境={environment}, volatility=0.15)。"
                      f"原推算显示为 {dict(best)}，与计算不一致已纠正。" + best.weights_note),
            )

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
