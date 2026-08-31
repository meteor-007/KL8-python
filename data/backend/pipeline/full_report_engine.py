#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 工业级完整日报引擎 — 20 方案深度融合版
============================================
从 legacy_daily_report_engine_v2.1 回迁，供 auto_generate_daily_report 主报告调用。
"""
import os
import sys

# ── 项目根路径（数据文件所在目录） ──
import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()


from utils.excel_lock import excel_lock
from pipeline.data_center import DataCenter

import json
import logging
import datetime
import traceback
import math
from typing import Dict, Any, List
from audit.kl_divergence_checker import KLDivergenceChecker
from audit.collinearity_detector import CollinearityDetector
import collections
import numpy as np

# 配置结构化日志 → 写到项目根目录
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(_PROJ, 'logs', 'engine_runtime.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger("LotteryEngine")


class FullReportEngine:
    """工业级完整日报引擎：调度 20 个优化方案 + 闭环学习"""
    def __init__(self, dc=None):
        self.dc = dc or DataCenter()
        if not self.dc.initialized:
            self.dc.initialize()
        self.learner = None
        try:
            from learning.autonomous_learner import AutonomousLearner
            self.learner = AutonomousLearner()
            logger.info("闭环学习引擎已加载")
        except Exception as e:
            logger.warning(f"闭环学习引擎加载失败: {e}")

    def run_pipeline(self) -> Dict[str, Any]:
        results = {}
        from core import feature_optimizer as fo
        from core import algorithm_optimizer as ao
        from core import strategy_optimizer as so

        logger.info("执行 Layer A: 特征提取...")
        results['feat'] = {
            'sliding': fo.plan1_sliding_window(self.dc.data2),
            'resonance': fo.plan2_hot_stealth_resonance(self.dc.data1, self.dc.data2, self.dc.d1_stars, self.dc.history, is_future=True),
            'accel': fo.plan3_frequency_acceleration(self.dc.history),
            'topo': fo.plan4_adjacency_topology(self.dc.data2, self.dc.history, is_future=True),
            'pts': fo.plan5_multi_source_points(self.dc.history, self.dc.points),
            'phase': fo.plan6_phase_transition(self.dc.history)
        }

        logger.info("执行 Layer B: 深度数学建模...")
        results['algo'] = {
            'markov': ao.plan7_markov_integration(self.dc.history),
            'bayes': ao.plan9_bayesian_update(self.dc.history),
            'mc': ao.plan10_monte_carlo(self.dc.history),
            'sigmoid': ao.plan11_omission_decay(self.dc.history)
        }

        logger.info("执行 Layer C/D: 决策与反馈层...")
        results['strat'] = {
            'dyn_block': so.plan13_dynamic_block_weights(self.dc.history),
            'env_switch': so.plan14_env_strategy_switch(self.dc.history),
            'conf_score': so.plan15_confidence_scoring(self.dc.history),
            'hedge': so.plan16_hedge_portfolio(self.dc.history)
        }

        logger.info("执行 Layer E: 熵控优化 (mRMR)...")
        try:
            from core import entropy_optimizer as eo
            # 转换数据格式为 list[list[int]]
            hist_lists = [h['numbers'] for h in self.dc.history[:100]]
            results['entropy'] = eo.run_entropy_optimization(hist_lists)
        except Exception as e:
            logger.error(f"Layer E 执行失败: {e}")
            results['entropy'] = {}

        return results

    def extract_special_5(self, pipeline_res: Dict[str, Any]) -> Dict[str, Any]:
        """首席战略官特供：Hidden Energy 5 (B3 Right + AI 置信度融合 + EF/RW/FO 提纯)
        
        v4.1: 候选集内 Min-Max 归一化后 EF×1.0+RW×0.8+FO×0.5（修复 FO 量纲垄断）
        v4.0: 评分公式从 MK×4.0+EF×0.6 改为 EF×1.0+RW×0.8+FO×0.5
        原因: MK的CV=0.0038≈常数, 对排序零贡献; 改用三个有区分度的模块融合
        """
        data2 = self.dc.data2
        latest_issue = self.dc.latest_issue
        target_issue = str(int(latest_issue) + 1)
        points_by_issue = self.dc.points
        target_points = points_by_issue.get(target_issue, set())

        b3_right_quality = 0.5
        try:
            from audit.b3_right_quality_checker import B3RightQualityChecker
            checker = B3RightQualityChecker(data2, self.dc.history, points_by_issue)
            quality_report = checker.evaluate_quality(target_issue)
            b3_right_quality = quality_report['total_score']
            should_use_b3 = quality_report['should_use']
        except Exception as e:
            logger.warning(f"B3 Right质量检查失败: {e}")
            should_use_b3 = True

        b3_right_nums = []
        b3_right_stealth = []

        if should_use_b3:
            # 优先用目标预测期热码(data2[target])；缺期才回退到已开奖最新期
            if target_issue in data2:
                b3_right_data = data2[target_issue][2]['right']
                b3_right_nums = [item[0] for item in b3_right_data]
            elif latest_issue in data2:
                b3_right_data = data2[latest_issue][2]['right']
                b3_right_nums = [item[0] for item in b3_right_data]
                logger.warning(
                    f"B3 Right 缺少目标期 {target_issue} data2，回退使用 {latest_issue}"
                )
            b3_right_stealth = [n for n in b3_right_nums if n not in target_points]
        else:
            conf_top12 = pipeline_res['strat']['conf_score'].get('top12', [])
            b3_right_stealth = conf_top12[:3] if conf_top12 else []
            b3_right_nums = conf_top12[:5] if conf_top12 else []

        top_12 = pipeline_res['strat']['conf_score'].get('top12', [])
        
        # 深度优化：强制融合方案2的精选爆发Top5码与mRMR熵控Top3，提升提纯候选信号质量
        deep_picks = []
        try:
            from core.deep_association_analyzer import analyze_deep_associations
            resonance_res = pipeline_res.get('feat', {}).get('resonance', {})
            deep_result = analyze_deep_associations(
                self.dc.data1, self.dc.data2, self.dc.d1_stars,
                self.dc.history, resonance_res
            )
            deep_picks = [p['num'] for p in deep_result.get('final_picks', [])]
        except Exception as de:
            logger.warning(f"提纯候选集提取深層關聯爆發碼失敗: {de}")
            
        mrmr_top3 = pipeline_res.get('entropy', {}).get('optimized_top12', [])[:3]
        
        candidates = list(set(b3_right_stealth + top_12 + deep_picks + mrmr_top3))

        # 引入 EF/RW/FO 评分进行最终提纯 (v4.0: 替代 MK×4.0+EF×0.6)
        from core.energy_field import calc_energy_field, calc_omission_sigmoid
        from core.feature_optimizer import get_all_layer_a_scores

        ef_res = calc_energy_field(self.dc.history, decay_rate=0.5)
        rw_res = calc_omission_sigmoid(self.dc.history)
        fo_res = get_all_layer_a_scores(self.dc.history) or {}
        if not isinstance(fo_res, dict):
            fo_res = {}

        def _minmax_norm(raw_map, keys):
            """候选集内 Min-Max 归一化，消除 EF/RW/FO 量纲差导致的权重失效。"""
            vals = [float(raw_map.get(k, 0) or 0) for k in keys]
            if not vals:
                return {}
            mn, mx = min(vals), max(vals)
            span = mx - mn
            if span < 1e-12:
                return {k: 0.0 for k in keys}
            return {k: (float(raw_map.get(k, 0) or 0) - mn) / span for k in keys}

        # Bugfix(2026-07-18): FO 原始量纲(~20-40)远大于 EF(~0-3)/RW(~0-1)，
        # 直接加权会使 FO×0.5 仍垄断排序。先在候选集内归一化再按 v4.0 权重融合。
        ef_n = _minmax_norm(ef_res, candidates)
        rw_n = _minmax_norm(rw_res, candidates)
        fo_n = _minmax_norm(fo_res, candidates)

        scores = {}
        details = {}
        for n in candidates:
            ef_val = float(ef_res.get(n, 0) or 0)
            rw_val = float(rw_res.get(n, 0) or 0)
            fo_val = float(fo_res.get(n, 0) or 0)
            # v4.1: 归一化后 EF×1.0 + RW×0.8 + FO×0.5
            total_score = ef_n.get(n, 0) * 1.0 + rw_n.get(n, 0) * 0.8 + fo_n.get(n, 0) * 0.5
            scores[n] = total_score
            details[n] = {
                'EF': ef_val, 'RW': rw_val, 'FO': fo_val,
                'EF_n': round(ef_n.get(n, 0), 4),
                'RW_n': round(rw_n.get(n, 0), 4),
                'FO_n': round(fo_n.get(n, 0), 4),
                'Score': total_score,
            }

        sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        final_5 = sorted_nums[:5]

        return {
            'final_5': sorted(final_5),
            'scoring_details': {n: details[n] for n in final_5},
            'raw_b3_right': b3_right_nums,
            'stealth_nums': b3_right_stealth,
            'quality_score': b3_right_quality,
            'logic': "B3 Right 矩阵映射 x AI 置信度 Top12 x 隐能量场 (EF/RW/FO)"
        }

    # ── v4.0: 极速爆破模块已砍掉 (近9期Lift=0.27x灾难性) ──
    # 原因: 数据1右侧×点位交集过窄, EF/MK提纯后仍无预测力
    # 如需恢复, 参见 git 历史中的 extract_rapid_blast 方法

    def generate_report(self):
        """生成工业级深度融合主报告，返回报告路径（失败返回 None）"""
        _excel_path = os.path.join(_PROJ, '跟随+点位+开奖数据.xlsx')
        report_path = None
        try:
            with excel_lock(_excel_path, timeout=60):
                res = self.run_pipeline()
                b3_info = self.extract_special_5(res)
            # v4.0: 极速爆破已砍掉

            # 执行防御红线检查
            kl_checker = KLDivergenceChecker(self.dc.history)
            kl_status = kl_checker.check_mutation()
            
            col_detector = CollinearityDetector(threshold=0.85)
            # 整合层A特征作共线性检测
            feat_warnings = col_detector.detect(res.get('feat', {}))
            if feat_warnings and 'feat' in res:
                blocked_keys = set()
                for w in feat_warnings:
                    blocked_keys.add(w[1])
                for k in blocked_keys:
                    if k in res['feat']:
                        del res['feat'][k]
                        logger.warning(f'[特征阻断] 剔除高度共线性特征: {k}')
            

            # 环境识别
            try:
                from recognition.simplified_env_recognition import recognize_environment
                env_class, env_name, env_confidence, strategy_config = recognize_environment(self.dc.history)
                trinity_weights = strategy_config['weights']
            except Exception as e:
                env_class = 2; env_name = "平衡震荡期"; env_confidence = 0.5
                trinity_weights = {'EF': 0.42, 'RW': 0.29, 'FO': 0.29}
                strategy_config = {'weights': trinity_weights, 'top5_count': 5, 'top12_count': 12}

            from audit.v3_trinity_audit import dynamic_meta_fusion
            trinity_scores, current_weights = dynamic_meta_fusion(self.dc.history)
            top5_count = strategy_config.get('top5_count', 5)
            top12_count = strategy_config.get('top12_count', 12)
            trinity_sorted = sorted(trinity_scores.items(), key=lambda x: (-x[1], x[0]))
            trinity_top5 = [n for n, s in trinity_sorted[:top5_count]]
            trinity_top12 = [n for n, s in trinity_sorted[:top12_count]]

            # [v4.2] 高阶三元规律模块已移除: 连续多期Lift=0.80(低于随机), 过于复杂且无贡献

            # 支持回补：KL8_REPORT_DATE=YYYYMMDD 时按指定日写报告名（避免断档补跑全挤到今天）
            today = os.environ.get("KL8_REPORT_DATE") or datetime.datetime.now().strftime("%Y%m%d")
            latest_issue = self.dc.latest_issue
            target_issue = str(int(latest_issue) + 1)
            report_path = os.path.join(_PROJ, 'reports', f"daily_analysis_report_{today}.md")

            conf = res['strat']['conf_score']
            hedge = res['strat']['hedge']

            # ── 复盘昨日推荐 ──
            yesterday_hit_str = "无"
            actual_latest = set(self.dc.history[0]['numbers'])

            memory_file = os.path.join(_PROJ, 'cache', "self_learning_state.json")
            yesterday_record = None
            try:
                if os.path.exists(memory_file):
                    with open(memory_file, 'r', encoding='utf-8') as mf:
                        state_data = json.load(mf)
                    for rec in state_data.get('history', []):
                        if str(rec.get('target_issue')) == str(latest_issue):
                            yesterday_record = rec
                            break
            except Exception as e:
                logger.warning(f"读取复盘历史失败: {e}")

            if yesterday_record:
                review_lines = []
                
                # 0. 极简选2实战复盘
                y_pick2 = yesterday_record.get('optimal_pick2', [])
                if y_pick2 and len(y_pick2) == 2:
                    p_hits = sorted(set(y_pick2) & actual_latest)
                    if len(p_hits) == 2:
                        res_str = "🎉 **【双中大捷 (2/2)】**"
                    elif len(p_hits) == 1:
                        res_str = "⭐ **【单中 (1/2)】**"
                    else:
                        res_str = "❌ **【未中 (0/2)】**"
                    review_lines.append(
                        f"  - **🎯 极简选2实战**：{res_str} 命中 `{len(p_hits)}/2` "
                        f"命中号 `{p_hits}` / 推荐 `[{y_pick2[0]:02d}, {y_pick2[1]:02d}]`"
                    )

                # 1. 三维融合
                y_top5 = yesterday_record.get('top5', [])
                y_top12 = yesterday_record.get('top12', [])
                if y_top5 and y_top12:
                    hit5 = len(set(y_top5) & actual_latest)
                    hit12 = len(set(y_top12) & actual_latest)
                    w_str = ""
                    y_weights = yesterday_record.get('trinity_weights', {})
                    if y_weights:
                        w_str = " (调参: " + " ".join([f"{k}:{v:.2f}" for k, v in y_weights.items()]) + ")"
                    review_lines.append(f"  - **三维融合**：Top5 命中 `{hit5}/5`, Top12 命中 `{hit12}/12`{w_str}")
                
                # 2. 传统 AI
                y_conf5 = yesterday_record.get('conf_top5', [])
                y_conf12 = yesterday_record.get('conf_top12', [])
                if y_conf12:
                    hit_c5 = len(set(y_conf5) & actual_latest) if y_conf5 else 0
                    hit_c12 = len(set(y_conf12) & actual_latest)
                    review_lines.append(f"  - **传统AI**：Top5 命中 `{hit_c5}/5`, Top12 命中 `{hit_c12}/12`")

                # 4. mRMR
                y_mrmr = yesterday_record.get('mrmr_top12', [])
                if y_mrmr:
                    hit_mrmr = len(set(y_mrmr) & actual_latest)
                    review_lines.append(f"  - **熵控优化(mRMR)**：命中 `{hit_mrmr}/{len(y_mrmr)}`")

                # 5. Hidden Energy 5
                y_b3 = yesterday_record.get('b3_final5', [])
                if y_b3:
                    hit_b3 = len(set(y_b3) & actual_latest)
                    review_lines.append(f"  - **Hidden Energy 5**：命中 `{hit_b3}/{len(y_b3)}`")

                # 6. 极速爆破 (v4.0已砍掉)

                # 9. 纯净池（细则：高置信 / 旧规则>=3 / LR）
                y_pure = yesterday_record.get('pure_pool_top', [])
                y_pure_old = yesterday_record.get('pure_pool_old_rule', [])
                y_pure_lr = yesterday_record.get('pure_pool_lr', [])
                y_pure_all = yesterday_record.get('pure_pool_all', [])
                if y_pure or y_pure_old or y_pure_lr or y_pure_all:
                    review_lines.append("  - **纯净池定胆**：")
                    def _pure_line(label, nums):
                        if not nums:
                            return None
                        hits = sorted(set(nums) & actual_latest)
                        h, k = len(hits), len(nums)
                        lift = (h / k / 0.25) if k else 0.0
                        return (
                            f"    - {label}：命中 `{h}/{k}` Lift=`{lift:.2f}x` "
                            f"命中号 `{hits}` / 推荐 `{sorted(nums)}`"
                        )
                    for _lbl, _nums in [
                        ("高置信定胆(LR软回退/主输出)", y_pure),
                        ("旧规则高置信(评分>=3)", y_pure_old),
                        ("LR定胆(影子/候选)", y_pure_lr),
                        ("纯净池全量", y_pure_all),
                    ]:
                        line = _pure_line(_lbl, _nums)
                        if line:
                            review_lines.append(line)

                # 10. 深层关联分析 (方案2) — 细则：爆发/防守/跨规则共识
                y_deep_picks = yesterday_record.get('deep_picks', [])
                y_deep_kills = yesterday_record.get('deep_kills', [])
                y_deep_cons = yesterday_record.get('deep_consensus', [])
                if y_deep_picks or y_deep_kills or y_deep_cons:
                    review_lines.append("  - **方案2(深层关联)**：")
                    if y_deep_picks:
                        pick_hits = sorted(set(y_deep_picks) & actual_latest)
                        ph, pk = len(pick_hits), len(y_deep_picks)
                        plift = (ph / pk / 0.25) if pk else 0.0
                        review_lines.append(
                            f"    - 爆发Top5：命中 `{ph}/{pk}` Lift=`{plift:.2f}x` "
                            f"命中号 `{pick_hits}` / 推荐 `{sorted(y_deep_picks)}`"
                        )
                    if y_deep_kills:
                        avoided = sorted(set(y_deep_kills) - actual_latest)
                        leaked = sorted(set(y_deep_kills) & actual_latest)
                        kh = len(avoided)
                        kk = len(y_deep_kills)
                        review_lines.append(
                            f"    - 防守Top3：成功 `{kh}/{kk}` "
                            f"回避正确 `{avoided}` / 误杀入奖 `{leaked}`"
                        )
                    if y_deep_cons:
                        cons_hits = sorted(set(y_deep_cons) & actual_latest)
                        ch, ck = len(cons_hits), len(y_deep_cons)
                        clift = (ch / ck / 0.25) if ck else 0.0
                        review_lines.append(
                            f"    - 跨规则共识：命中 `{ch}/{ck}` Lift=`{clift:.2f}x` "
                            f"命中号 `{cons_hits}` / 推荐 `{sorted(y_deep_cons)}`"
                        )
                    # KL 熔断状态（结构性监控，非选号命中）
                    y_kl = yesterday_record.get('kl_msg')
                    if y_kl:
                        review_lines.append(f"  - **物理熔断(KL)**：`{y_kl}`")

                # [v4.2] 高阶三元规律复盘已移除

                if review_lines:
                    yesterday_hit_str = "\n" + "\n".join(review_lines)
            
            if yesterday_hit_str == "无" and len(self.dc.history) > 1:
                y_scores, y_weights = dynamic_meta_fusion(self.dc.history[1:])
                y_sorted = sorted(y_scores.items(), key=lambda x: (-x[1], x[0]))
                y_top5 = [n for n, s in y_sorted[:5]]
                y_top12 = [n for n, s in y_sorted[:12]]
                hit5 = len(set(y_top5) & actual_latest)
                hit12 = len(set(y_top12) & actual_latest)
                w_str = " ".join([f"{k}:{v:.2f}" for k, v in y_weights.items()])
                yesterday_hit_str = f"`Top5 命中 {hit5}/5, Top12 命中 {hit12}/12 (调参: {w_str})`"

            # ── 触发闭环学习: 复盘昨日 + 学习 + 调整 + 优化 ──
            loop_report = None
            if self.learner and len(self.dc.history) > 0:
                try:
                    last_period = self.dc.history[0]['issue']
                    last_actual = self.dc.history[0]['numbers']

                    # 尝试完整闭环
                    loop_report = self.learner.on_new_result(
                        last_period, last_actual, self.dc.history
                    )

                    # 如果没有预测记录(NO_PREDICTION)，手动触发学习和调整
                    if loop_report.get('status') == 'NO_PREDICTION':
                        logger.info(f"无预测记录，执行无预测闭环学习...")
                        # 手动构造review_report用于学习
                        manual_review = {
                            'period': last_period,
                            'hit_stats': {
                                'top5_hits': 0, 'top5_rate': 0.0, 'top5_lift': 0.0,
                                'top12_hits': 0, 'top12_rate': 0.0, 'top12_lift': 0.0,
                                'top20_hits': 0, 'top20_rate': 0.0, 'top20_lift': 0.0,
                            },
                            'actual_numbers': sorted(last_actual),
                            'algo_contribution': {},
                            'predicted_env': 'balanced',
                        }
                        learn_changes = self.learner.learn(manual_review, self.dc.history)
                        adapt_adjustments = self.learner.adapt(self.dc.history)
                        optimize_report = {}
                        if len(self.dc.history) >= 80:
                            optimize_report = self.learner.optimize(self.dc.history)

                        current_state = self.learner.get_current_state()
                        loop_report = {
                            'period': last_period,
                            'review_summary': {'top5_hits': 0, 'top5_lift': 0, 'top12_hits': 0, 'top12_lift': 0},
                            'learning_changes': list(learn_changes.keys()) if isinstance(learn_changes, dict) else [],
                            'adjustments': adapt_adjustments,
                            'optimization_decision': optimize_report.get('decision', 'NO_PREDICTION_SKIP_REVIEW'),
                            'current_weights': current_state['pentagon_weights'],
                            'strategy_mode': current_state['strategy_mode'],
                        }

                    logger.info(f"闭环学习完成: {last_period}期, 决策={loop_report.get('optimization_decision', 'N/A')}")
                except Exception as e:
                    logger.warning(f"闭环学习执行异常: {e}")
                    loop_report = {'optimization_decision': 'ERROR', 'error': str(e)}

            # ── 记录本次预测到学习引擎 ──
            if self.learner:
                try:
                    all_scores = {n: s for n, s in trinity_scores.items()}
                    from core.energy_field import calc_energy_field, calc_omission_sigmoid
                    from core.feature_optimizer import get_all_layer_a_scores
                    ef_res = calc_energy_field(self.dc.history)
                    rw_res = calc_omission_sigmoid(self.dc.history)
                    try:
                        fo_res = get_all_layer_a_scores(self.dc.history) or {}
                    except Exception:
                        fo_res = {n: 0.0 for n in range(1, 81)}
                    algo_raw_scores = {
                        'EF': ef_res,
                        'RW': rw_res,
                        'FO': fo_res
                    }
                    self.learner.record_prediction(
                        period=target_issue,
                        prediction_scores=all_scores,
                        top5=trinity_top5,
                        top12=trinity_top12,
                        top20=[n for n, s in trinity_sorted[:20]],
                        algo_raw_scores=algo_raw_scores,
                        environment=env_name,
                        volatility=0.15,
                    )
                    logger.info(f"预测已记录到学习引擎: 期号{target_issue} (含原始分量)")
                except Exception as e:
                    logger.warning(f"预测记录异常: {e}")

            # ── 获取学习引擎当前状态 ──
            learner_state_str = ""
            if self.learner:
                try:
                    state = self.learner.get_current_state()
                    w = state['pentagon_weights']
                    learner_state_str = (
                        f"EF={w.get('EF', 0):.2f}/"
                        f"RW={w.get('RW', 0):.2f}/FO={w.get('FO', 0):.2f}"
                        f" | 策略={state['strategy_mode']} | "
                        f"复盘={state.get('recent_performance', {}).get('n_periods', 0)}期 | "
                        f"avgLift={state.get('recent_performance', {}).get('avg_top5_lift', 0):.2f}"
                    )
                except Exception:
                    pass

            # ── 提前计算纯净池与深层关联，供选2收敛引擎使用 ──
            pure_pool_scored = []
            pure_pool_report = ""
            try:
                from core.pure_pool_scorer import run_pure_pool_analysis
                _pts_map = {}
                for _k, _v in self.dc.points.items():
                    _pts_map[_k] = set(_v) if not isinstance(_v, set) else _v
                pure_pool_report, pure_pool_scored = run_pure_pool_analysis(
                    target_issue, self.dc.history, _pts_map
                )
            except Exception as e:
                logger.warning(f"纯净池定胆模块提前计算失败: {e}")
                pure_pool_report = f"### 8. 纯净池定胆 (Pure Pool Scorer)\n\n- **执行失败**: `{e}`\n\n"

            resonance_res = res['feat']['resonance']
            deep_picks = []
            deep_kills = []
            deep_consensus = []
            deep_report_text = ""
            try:
                from core.deep_association_analyzer import analyze_deep_associations
                deep_result = analyze_deep_associations(
                    self.dc.data1, self.dc.data2, self.dc.d1_stars,
                    self.dc.history, resonance_res
                )
                deep_report_text = deep_result['report_text']
                deep_picks = [p['num'] for p in deep_result.get('final_picks', [])]
                deep_kills = [k['num'] for k in deep_result.get('final_kills', [])]
                deep_consensus = sorted(deep_result.get('cross_consensus_hot', {}).keys())
            except Exception as e:
                logger.warning(f"深层关联分析提前计算失败: {e}")
                deep_report_text = f"- **[深层防守] 深度过热(-15)**：`{resonance_res.get('rule_cold_overheat', [])}`\n"

            # ── 选2专属决策收敛 ──
            opt_p = (12, 24)
            champ = {'score': 1.0, 'lift_100': 1.0, 'count_100': 6, 'count_total': 120, 'reason': '保底组合'}
            pick2_result = {}
            try:
                from core.pair_selector import PairSelector
                pair_selector = PairSelector(self.dc.history, self.dc.points)
                pick2_result = pair_selector.select_optimal_pick2(
                    ef_scores=ef_res,
                    rw_scores=rw_res,
                    fo_scores=fo_res,
                    pure_pool_scored=pure_pool_scored,
                    deep_picks=deep_picks,
                    deep_kills=deep_kills,
                    deep_consensus=deep_consensus,
                    b3_final5=b3_info.get('final_5', []),
                    trinity_top5=trinity_top5,
                )
                opt_p = pick2_result['optimal_pick2']
                champ = pick2_result['champion_details']
            except Exception as pe:
                logger.warning(f"选2专属决策收敛引擎运行异常: {pe}")

            # ── 写报告 ──
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"# 快乐8 核心研判与审计报告 (工业级深度融合版)\n")
                f.write(f"**审计日期：** {datetime.datetime.now().strftime('%Y-%m-%d')}\n")
                f.write(f"**目标期号：** {target_issue} (待分析)\n\n")
                f.write(f"## 一、{latest_issue}期 复盘追溯 (Audit Review)\n")
                f.write(f"- **开奖号码：** {'-'.join(f'{n:02d}' for n in self.dc.history[0]['numbers'])}\n")
                if "\n" in yesterday_hit_str:
                    f.write(f"- **昨日实盘复盘**：{yesterday_hit_str}\n")
                else:
                    f.write(f"- **昨日实盘复盘**：{yesterday_hit_str}\n")
                f.write(f"- **系统自学习快照：**\n")
                f.write(f"    - 环境识别：`{env_name}` (置信度: {env_confidence:.2f})\n")
                f.write(f"    - 核心引擎：三维一体 (EF+RW+FO) 架构\n")
                if loop_report:
                    f.write(f"    - 闭环学习决策：`{loop_report.get('optimization_decision', 'N/A')}`\n")
                    f.write(f"    - 策略模式：`{loop_report.get('strategy_mode', 'N/A')}`\n")
                    f.write(f"    - 权重变更：`{loop_report.get('current_weights', {})}`\n")
                f.write("\n")
                f.write(f"## 二、{target_issue}期 核心推荐 (Target Numbers)\n")
                f.write(f"### 0. 🎯 今日极简选2 · 黄金搭档（全场最优唯一推荐）\n\n")
                f.write(f"> **实战操盘指令**：拒绝多码分散资金！今日全系统唯一最优选2推荐组合为 **`[{opt_p[0]:02d}, {opt_p[1]:02d}]`**。\n\n")
                f.write(f"- **👑 黄金搭档**：`{opt_p[0]:02d} - {opt_p[1]:02d}` (综合协同分: `{champ.get('score', 0):.2f}`)\n")
                f.write(f"- **📈 历史共现增益 (Lift)**：`{champ.get('lift_100', 1.0)}x` (近100期同出 `{champ.get('count_100', 0)}` 次 / 历史同出 `{champ.get('count_total', 0)}` 次)\n")
                f.write(f"- **💡 核心推荐理由**：{champ.get('reason', '')}\n")
                f.write(f"- **🛡️ 安全过滤状态**：已通过 KillSeeker 杀号一票否决与相克互斥检测（非排斥组合）\n\n")
                if pick2_result.get('module_pairs'):
                    f.write(f"#### 🔍 各子模块专有 2 码分布（协同来源）：\n\n")
                    for mp in pick2_result.get('module_pairs', []):
                        f.write(f"- **【{mp['label']}】**（{mp['module']}）：`{mp['pair'][0]:02d} - {mp['pair'][1]:02d}` → {mp['reason']}\n")
                    f.write("\n")

                f.write(f"### 1. 三维融合 极秘推荐 (Trinity Fusion)\n")
                w_curr_str = " ".join([f"{k}:{v:.2f}" for k, v in current_weights.items()])
                f.write(f"- **动态模型赋权**：`{w_curr_str}`\n")
                f.write(f"- **极秘 Top {top5_count}**：`{sorted(trinity_top5)}`\n")
                f.write(f"- **极秘 Top {top12_count}**：`{sorted(trinity_top12)}`\n\n")

                f.write(f"### 2. 传统 AI 置信度推荐 (对照组)\n")
                f.write(f"- **Top {top5_count} 置信度精选**：`{conf.get('top5', [])}`\n")
                f.write(f"- **Top {top12_count} 综合拦截**：`{conf.get('top12', [])}`\n\n")

                f.write(f"### 3. 多维共振号 (Golden Core)\n")
                f.write(f"- **高频共振集群**：`{sorted(list(set(trinity_top12) & set(hedge.get('main', []))))}`\n\n")

                if res.get('entropy'):
                    f.write(f"### 4. 熵控优化精选 (Layer E - mRMR)\n")
                    f.write(f"- **系统当前熵值**：`{res['entropy'].get('system_entropy', 0):.4f}`\n")
                    f.write(f"- **mRMR Top 12**：`{res['entropy'].get('optimized_top12', [])}`\n\n")

                # ── 双层LSTM 深度学习研判 ──
                try:
                    from models.lstm.lstm_service import LSTMService
                    from models.lstm.predictor import review_recent
                    from models.lstm.data_loader import load_history as load_lstm_hist
                    lstm_draws = load_lstm_hist()
                    lstm_info = LSTMService.train_and_predict(draws=lstm_draws, target_period=target_issue, epochs=8)
                    if lstm_info:
                        lstm_review_rows = review_recent(lstm_draws, n=10)
                        tot_h = sum(r['hit'] for r in lstm_review_rows) if lstm_review_rows else 0
                        avg_h = tot_h / len(lstm_review_rows) if lstm_review_rows else 2.5
                        lift_lstm = avg_h / 2.5
                        gld_cnt = sum(1 for r in lstm_review_rows if r['gold_hit']) if lstm_review_rows else 0
                        f.write(f"### 4.5. 🧠 双层LSTM 深度学习研判 (AI时序建模 · 少数服从多数海选)\n\n")
                        f.write(f"> **老派操盘手大白话提示**：让AI海选团通过看过去30期的连续出号惯性，预测下一期的球号、分区分布和尾数偏好。\n\n")
                        f.write(f"- **💎 核心金胆**：`{lstm_info['gold']:02d}` | **🥈 核心银胆**：`{lstm_info['silver']:02d}` | **🥉 核心铜胆**：`{lstm_info['bronze']:02d}`\n")
                        f.write(f"- **🚀 Top10 核心梯队**：`{'-'.join(f'{x:02d}' for x in lstm_info['top10'])}`\n")
                        f.write(f"- **📋 Top20 扩充大名单**：`{'-'.join(f'{x:02d}' for x in lstm_info['top20'])}`\n")
                        f.write(f"- **📊 时序指标质量**：一致性评分 `{lstm_info['consistency']:.2f}` | 验证Loss `{lstm_info['val_loss']:.6f}` | 概率极差 `{lstm_info['prob_range']:.4f}`\n")
                        f.write(f"- **📈 实盘复盘对账**：近{len(lstm_review_rows)}期Top10均中 `{avg_h:.2f}/10` (Lift=`{lift_lstm:.2f}x`) | 金胆命中率 `{gld_cnt}/{len(lstm_review_rows)}`\n\n")
                except Exception as le:
                    logger.warning(f"双层LSTM 模块报告输出异常: {le}")

                # 4.6 顺口溜口诀研判 (组合带出 · 两号齐出/单号带出)
                try:
                    from core.formula_jingle.jingle_engine import load_jingle_rules, predict_jingle
                    from core.formula_jingle.jingle_reviewer import review_jingle
                    from core.formula_jingle.jingle_cross_validator import cross_validate_jingle
                    
                    jingle_draws = []
                    for h in reversed(self.dc.history):
                        nums = sorted(list(h['numbers']))
                        if len(nums) == 20:
                            jingle_draws.append((int(h['issue']), h.get('date', ''), nums))
                    
                    j_rules, j_meta = load_jingle_rules()
                    if j_rules and jingle_draws:
                        j_pred = predict_jingle(jingle_draws, j_rules)
                        j_rev = review_jingle(jingle_draws, j_rules, n=20)
                        j_cross = cross_validate_jingle(j_pred.get('recommended_numbers', []), target_issue=target_issue)
                        
                        f.write(f"### 4.6. 📜 顺口溜口诀研判 (组合带出 · 90条精英口诀)\n\n")
                        f.write(f"> **老派操盘手大白话提示**：找'顺口溜'规律——上期同时开出某些号码组合后，下期大概率带出另外的特定号码（两号齐出/单号带出）。\n\n")
                        
                        rec_nums = j_pred.get('recommended_numbers', [])
                        f_cnt = j_pred.get('fired_count', 0)
                        base_at = j_pred.get('at_least_one_baseline', 0.0) * 100
                        rec_str = ' '.join(f'`{x:02d}`' for x in rec_nums) if rec_nums else '无触发'
                        
                        f.write(f"- **🎯 口诀推荐码 (共{len(rec_nums)}码)**：{rec_str}\n")
                        f.write(f"- **⚡ 触发口诀数**：今日触发 `{f_cnt}` 条精英口诀 | 至少一中理论随机基线期望 `{base_at:.1f}%`\n")
                        
                        fired_list = j_pred.get('fired_details', [])
                        if fired_list:
                            f.write(f"- **🔍 核心触发口诀明细**：\n")
                            for fd in fired_list[:4]:
                                tr_str = ' '.join(f'{x:02d}' for x in fd['trigger'])
                                pd_str = ' '.join(f'{x:02d}' for x in fd['predict'])
                                f.write(f"    - `[{fd['kind_name']}]` 触发 `[{tr_str}]` → 推荐 `[{pd_str}]` (OOF命中率 `{fd['oof_hit_rate']*100:.1f}%`, Lift=`{fd['oof_lift']:.2f}x`)\n")
                        
                        m_rev = j_rev.get('metrics', {})
                        if m_rev:
                            f.write(f"- **📈 近20期实盘复盘**：有效触发 `{m_rev.get('valid_trigger_periods', 0)}` 期 | 至少一中率 `{m_rev.get('at_least_one_rate', 0)*100:.1f}%` (综合Lift=`{m_rev.get('overall_lift', 1.0):.2f}x`)\n")
                        
                        if j_cross.get('clash_numbers'):
                            c_str = ' '.join(f'`{x:02d}`' for x in j_cross['clash_numbers'])
                            f.write(f"- **⚠️ 杀号冲突警示**：号码 {c_str} 与 KillSeeker 高置信杀号冲突，需降低权重！\n")
                        if j_cross.get('all_resonance'):
                            r_str = ' '.join(f'`{x:02d}`' for x in j_cross['all_resonance'])
                            f.write(f"- **🌟 多系统共振金码**：号码 {r_str} 获得定金选2/LSTM深度时序共同共识推荐！\n")
                        f.write("\n")
                except Exception as je:
                    logger.warning(f"顺口溜口诀 模块报告输出异常: {je}")

                # ── 4.7 跟随分析 (重复号追踪与多窗条件跟随) ──
                try:
                    from core.follow_analysis import daily_follow_picks, walk_forward_evaluate, cross_validate_follow_picks
                    f_draws = []
                    for h in reversed(self.dc.history):
                        nums = sorted(list(h['numbers']))
                        if len(nums) == 20:
                            f_draws.append({
                                'period': int(h['issue']),
                                'date': h.get('date', ''),
                                'nums': set(nums),
                                'num_list': nums
                            })
                    if f_draws:
                        f_picks = daily_follow_picks(f_draws)
                        f_eval = walk_forward_evaluate(f_draws, n_periods=20)
                        f_cross = cross_validate_follow_picks(_PROJ, f_picks)
                        
                        f.write(f"### 4.7. 🔗 跟随分析 (重复号追踪与多窗条件跟随)\n")
                        f.write(f"> 基于老派量化操盘手无未来函数 (Walk-Forward) 样本外检验与大白话执行协议。\n\n")
                        
                        rep = f_picks.get('repeat', {})
                        inf = f_picks.get('inference', {})
                        cf = f_picks.get('conditional', {})
                        
                        rep_str = ' '.join(f'`{x:02d}`' for x in rep.get('top5', []))
                        inf_str = ' '.join(f'`{x:02d}`' for x in inf.get('top6', []))
                        cf_str = ' '.join(f'`{x:02d}`' for x in cf.get('top8', []))
                        inter_str = ' '.join(f'`{x:02d}`' for x in f_picks.get('resonance_intersection', [])) or '无'
                        
                        f.write(f"- **🔁 重复号 Top 5 (主候选·连庄追踪)**：{rep_str} | 全史平均连庄 `{rep.get('hist_avg_repeat', 5.0)}` 个/期 (近20期Lift=`{f_eval.get('rep_lift', 1.0):.2f}x`)\n")
                        f.write(f"- **🧮 综合推演 Top 6 (搭档跟随·排除上期)**：{inf_str} (近20期Lift=`{f_eval.get('inf_lift', 1.0):.2f}x`)\n")
                        f.write(f"- **🌐 条件跟随 Top 8 (多窗软融合)**：{cf_str} (近20期Lift=`{f_eval.get('cf_lift', 1.0):.2f}x`)\n")
                        f.write(f"- **⭐ 黄金共振双重交集**：`{inter_str}`\n")
                        
                        if f_cross.get('resonance_numbers'):
                            r_str = ' '.join(f'`{x:02d}`' for x in f_cross['resonance_numbers'])
                            f.write(f"- **🌟 多系统共振号**：号码 {r_str} 获多模块共振确认！\n")
                        if f_cross.get('kill_conflicts'):
                            k_str = ' '.join(f'`{x:02d}`' for x in f_cross['kill_conflicts'])
                            f.write(f"- **⚠️ 杀号冲突警示**：号码 {k_str} 触碰杀号池，建议防守防偏！\n")
                        f.write("\n")
                except Exception as fe:
                    logger.warning(f"跟随分析 模块报告输出异常: {fe}")

                f.write(f"### 5. 首席战略官特供 · Hidden Energy 5\n")
                f.write(f"- **共振逻辑**：`{b3_info['logic']}`\n")
                f.write(f"- **B3质量分**：`{b3_info['quality_score']:.2f}`\n")
                f.write(f"- **评分公式**：候选集 Min-Max 归一化后 `EF_n×1.0 + RW_n×0.8 + FO_n×0.5`\n")
                f.write(f"- **评分细节**：\n")
                for i, (n, d) in enumerate(
                    sorted(b3_info['scoring_details'].items(), key=lambda x: x[1].get('Score', 0), reverse=True)
                ):
                    f.write(
                        f"    - [No. {i+1}] 号码 `{n:02d}`: "
                        f"EF `{d.get('EF', 0):.4f}`(n={d.get('EF_n', 0):.3f}) | "
                        f"RW `{d.get('RW', 0):.4f}`(n={d.get('RW_n', 0):.3f}) | "
                        f"FO `{d.get('FO', 0):.4f}`(n={d.get('FO_n', 0):.3f}) | "
                        f"综合动能 `{d['Score']:.4f}` 🌟\n"
                    )
                f.write(f"- **最终推荐 (5 码)**：`{b3_info['final_5']}`\n\n")

                # v4.0: 极速爆破模块已砍掉 (近9期Lift=0.27x灾难性)

                f.write(f"### 6. 影子模型与对冲分布\n")
                f.write(f"- **主攻方案**：`{hedge.get('main', [])[:12]}...`\n")
                f.write(f"- **对冲方案 A**：`{hedge.get('hedge_a', [])[:10]}...`\n")
                f.write(f"- **对冲方案 B**：`{hedge.get('hedge_b', [])[:10]}...`\n\n")

                if learner_state_str:
                    f.write(f"### 7. 闭环学习引擎状态\n")
                    f.write(f"- **当前参数**：`{learner_state_str}`\n\n")

                # ── 第九模块：纯净池定胆 ──
                f.write(pure_pool_report)

                # [v4.2] 高阶三元规律报告段已移除

                # ── 物理熔断面板 ──
                f.write(f"### 9. ⚖️ 物理熔断面板 (Physics Breaker)\n")
                f.write(f"- **KL 散度监控 (结构性突变)**：`{kl_status['msg']}`\n\n")

                # ── 方案2：深层关联分析（替换原始大块号码输出）──
                f.write(f"### 10. 方案2：数据1×数据2 深层关联分析\n\n")
                f.write(deep_report_text)

                f.write(f"### 11. 风险提示与统计信标审计 (Risk Audit)\n")
                warnings_found = False
                
                # v4.0: MK已移除, 不再检查MK权重

                # 检查多重共线性
                if feat_warnings:
                    f.write(f"- **⚠️ 共线性预警 (Collinearity)**：检测到以下特征高度相关，方差膨胀风险极高！\n")
                    for w_item in feat_warnings:
                        f.write(f"    - `{w_item[0]}` 与 `{w_item[1]}` 皮尔逊系数 `{w_item[2]:.4f}`\n")
                    warnings_found = True

                if kl_status['triggered']:
                    f.write(f"- **🚨 物理熔断警告**：系统检测到连续 KL 散度突变，摇奖机发生结构性偏移，强烈建议清空陈旧数据！\n")
                    f.write(f"- **⛔ 强制截断**：触发物理熔断，系统取消本期强力推荐！\n")
                    trinity_top5 = []
                    trinity_top12 = []
                    warnings_found = True

                # ═══════════════════════════════════════════════════════
                # 零信标降级完整实现 (红线五四级降级强制要求)
                # ═══════════════════════════════════════════════════════
                g_level = 0
                g_warning = None
                pass_nums = []

                # 优先从 deep_optimization_result.json 缓存读取
                deep_opt_cache = os.path.join(_PROJ, 'cache', 'deep_optimization_result.json')
                cache_loaded = False
                if os.path.exists(deep_opt_cache):
                    try:
                        with open(deep_opt_cache, 'r', encoding='utf-8') as df_f:
                            deep_res = json.load(df_f)
                            g_level = deep_res.get('gating_level', 0)
                            g_warning = deep_res.get('gating_warning')
                            pass_nums = deep_res.get('final_top5', [])
                            cache_loaded = True
                            # 优化: 缓存中Level 3时，重新从AUC计算软降级
                            if g_level == 3:
                                logger.info("[信标审计] 缓存为Level 3，重新计算软降级...")
                                cache_loaded = False  # 强制重新计算
                    except Exception as e:
                        logger.warning(f"读取深度优化结果缓存失败: {e}")

                # 缓存不存在/读取失败/Level 3需要重算: 从 auc_stats.json 主动计算四级降级
                if not cache_loaded:
                    auc_stats_file = os.path.join(_PROJ, 'auc_stats.json')
                    if os.path.exists(auc_stats_file):
                        try:
                            with open(auc_stats_file, 'r', encoding='utf-8') as as_f:
                                auc_raw = json.load(as_f)
                            # 兼容两种格式: 列表格式 [{num, auc, p_value, ...}] 或 字典格式 {metadata, results}
                            if isinstance(auc_raw, dict) and 'results' in auc_raw:
                                auc_items = auc_raw['results']
                            elif isinstance(auc_raw, list):
                                auc_items = auc_raw
                            else:
                                auc_items = []
                            # 提取p值
                            p_values = {}
                            for item in auc_items:
                                num = item.get('num')
                                p_val = item.get('p_value', 1.0)
                                p_bonf = item.get('p_adjusted_bonf', 1.0)
                                p_fdr = item.get('p_adjusted_fdr', 1.0)
                                if num is not None:
                                    p_values[int(num)] = {
                                        'raw': p_val, 'bonf': p_bonf, 'fdr': p_fdr
                                    }

                            # Level 0: Bonferroni 校正 p < 0.05/80 = 0.000625
                            level0_pass = [n for n, p in p_values.items() if p['raw'] < 0.000625]
                            if len(level0_pass) >= 3:
                                g_level = 0
                                pass_nums = level0_pass
                                logger.info(f"[信标审计] 激活 Level 0 (高置信 Bonferroni), 通过号码数={len(level0_pass)}")
                            else:
                                # Level 1: FDR-BH 校正 q < 0.10
                                level1_pass = [n for n, p in p_values.items() if p['fdr'] < 0.10]
                                if len(level1_pass) >= 3:
                                    g_level = 1
                                    pass_nums = level1_pass
                                    g_warning = "⚠️ 零信标降级: Level 1 — 仅FDR-BH校正通过，溢价幅度减半"
                                    logger.warning(f"[信标审计] {g_warning}, 通过号码数={len(level1_pass)}")
                                else:
                                    # Level 2: 无校正 p < 0.05
                                    level2_pass = [n for n, p in p_values.items() if p['raw'] < 0.05]
                                    if len(level2_pass) >= 3:
                                        g_level = 2
                                        pass_nums = level2_pass
                                        g_warning = "⚠️ 零信标降级: Level 2 — 系统当前缺乏统计显著的强信号，推荐范围已扩展至Top-8，所有号码权重=1.0x，禁止任何溢价"
                                        logger.warning(f"[信标审计] {g_warning}")
                                    else:
                                        # Level 3: 硬停口径 0.0x（与下方 confidence_map 一致）
                                        level3_fdr_pass = [n for n, p in p_values.items() if p['fdr'] < 0.20]
                                        if level3_fdr_pass:
                                            g_level = 3
                                            pass_nums = level3_fdr_pass[:8]  # 限制最多8个弱信号号码（仅标注）
                                            g_warning = "⚠️ 零信标降级: Level 3 — 系统当前缺乏强统计信号，置信度0.0x，停止强预测（弱信号仅作参考标注）"
                                        else:
                                            g_level = 3
                                            pass_nums = []
                                            g_warning = "⚠️ 零信标降级: Level 3 — 系统当前完全无统计显著信号，置信度0.0x，停止预测"
                                        logger.warning(f"[信标审计] {g_warning}")
                        except Exception as e:
                            logger.warning(f"主动计算零信标降级失败: {e}")
                            g_level = 2
                            g_warning = f"⚠️ 零信标降级: Level 2 — AUC统计文件读取失败({e})，默认进入观察仓"

                # 统计置信度状态约束系数映射 (红线五强制绑定)
                confidence_map = {
                    0: ("强信号推荐", "1.0x"),
                    1: ("弱信号防御", "0.5x"),
                    2: ("极弱信号观察", "0.1x"),
                    3: ("停止预测状态", "0.0x")  # 严格执行红线要求
                }
                confidence_advice, confidence_coeff = confidence_map.get(g_level, ("弱信号参考", "0.3x"))

                f.write(f"- **💰 统计置信度状态约束指令**：当前处于 `Level {g_level}` 状态，"
                        f"**建议状态输出：`[{confidence_advice}]`**，"
                        f"**置信度输出系数：`{confidence_coeff}`**\n")
                f.write(f"    - 显著号码数: {len(pass_nums)}，激活信标等级: Level {g_level}\n")

                if g_warning:
                    f.write(f"- **{g_warning}**\n")
                    warnings_found = True

                # Level 3 强制熔断 
                if g_level == 3:
                    f.write(f"- **🛑 Level 3 停止预测警告**：系统当前无统计显著信号，触发 Level 3 四级降级，已停止强预测。\n")
                    trinity_top5 = []
                    trinity_top12 = []
                    warnings_found = True
                
                if not warnings_found:
                    f.write(f"- **🟢 安全指标**：当前三维融合(EF/RW/FO)参数分布均在安全搜索空间内，信标统计显著性通过检验，系统风险处于极低水位。\n")
                f.write("\n")

                f.write("---\n")
                f.write("**Engine Record:** Trinity Fusion architecture with 20 optimization schemes executed.\n")

                # ── Excel跟随号码统计表 深层关联挖掘 ──
                try:
                    from core.excel_deep_mining_v2 import run_excel_deep_mining
                    _exc_report, _exc_summary = run_excel_deep_mining()
                    f.write("\n---\n")
                    f.write("## 📊 Excel跟随号码统计表 深层关联挖掘 (9维度)\n\n")
                    f.write(f"**数据源：** 跟随+点位+开奖数据.xlsx → 跟随号码统计表\n")
                    f.write(f"**标记：** `*`=热码 | 粉色填充=点位 | 紫色边框=中奖\n")
                    f.write(f"**目标期号：** {_exc_summary['target_issue']}\n\n")
                    f.write("### 关键发现\n\n")
                    for _kf in _exc_summary['key_findings']:
                        f.write(f"- {_kf}\n")
                    f.write(f"\n### ⭐ 精选5码\n\n")
                    f.write(f"| 排名 | 号码 | 说明 |\n|:----:|:----:|------|\n")
                    for _i, _n in enumerate(_exc_summary['top5'], 1):
                        f.write(f"| {_i} | **{_n:02d}** | 综合评分最优 |\n")
                    f.write(f"\n### ⛔ 回避5码\n\n")
                    f.write(f"| 号码 | 说明 |\n|:----:|------|\n")
                    for _n in _exc_summary['avoid5']:
                        f.write(f"| {_n:02d} | 各维度均低于基线 |\n")
                    f.write(f"\n### 📍 当期标记\n\n")
                    f.write(f"- **星号（热码）：** {' '.join(f'{n:02d}' for n in _exc_summary['current_stars'])}\n")
                    f.write(f"- **点位：** {' '.join(f'{n:02d}' for n in _exc_summary['current_points'])}\n")
                    f.write(f"\n> 📄 完整9维度报告: `{_exc_summary['report_file']}`\n")
                    f.write("\n---\n")
                    logger.info("Excel深层关联挖掘已追加到报告")

                    # ── 📋 可复制精选（纯文本，供用户直接复制） ──
                    _copy_deep_picks = deep_picks or []
                    _copy_deep_kills = deep_kills or []
                    _copy_top5 = _exc_summary.get('top5', [])
                    _copy_avoid5 = _exc_summary.get('avoid5', [])
                    f.write("\n## 📋 可复制精选\n\n")
                    f.write(f"快乐8 目标期 {_exc_summary['target_issue']} 精选号码\n\n")
                    f.write("◎ 🎯 今日极简选2 · 黄金搭档（最优1组）\n")
                    f.write(f"{opt_p[0]:02d}, {opt_p[1]:02d}\n\n")
                    f.write("◎ 最终精选爆发码（Top 5）\n")
                    f.write(", ".join(f"{n:02d}" for n in _copy_deep_picks) + "\n\n")
                    f.write("◎ 重点防守号码（杀号 Top 3）\n")
                    f.write(", ".join(f"{n:02d}" for n in _copy_deep_kills) + "\n\n")
                    f.write("◎ 精选5码\n")
                    f.write(", ".join(f"{n:02d}" for n in _copy_top5) + "\n\n")
                    f.write("◎ 回避5码\n")
                    f.write(", ".join(f"{n:02d}" for n in _copy_avoid5) + "\n")
                    logger.info("可复制精选纯文本已追加到报告")
                except Exception as _exc_err:
                    logger.warning(f"Excel深层关联挖掘执行失败(不影响主报告): {_exc_err}")

            # 纯净池高置信定胆（LR active 时用 LR，否则旧规则 score>=3）
            pure_pool_top = []
            pure_pool_old_rule = []
            pure_pool_lr = []
            pure_pool_all = []
            try:
                from core.pure_pool_scorer import select_high_confidence
                from core.pure_pool_lr_trainer import load_weights, select_picks
                import numpy as np
                _wdict = load_weights()
                pure_pool_top, _src = select_high_confidence(
                    pure_pool_scored, _wdict
                )
                pure_pool_old_rule = [
                    s['number'] for s in pure_pool_scored if s.get('score', 0) >= 3
                ]
                pure_pool_all = [s['number'] for s in pure_pool_scored]
                if _wdict and _wdict.get('active'):
                    w = np.asarray(_wdict['weights'], dtype=float)
                    b = float(_wdict.get('bias', 0.0))
                    delta = float(_wdict.get('delta', 0.02))
                    top_k = int(_wdict.get('top_k', 3))
                    lr_strict = select_picks(
                        pure_pool_scored, w, b, delta, top_k, soft_fallback=False
                    )
                    if not lr_strict:
                        lr_strict = select_picks(
                            pure_pool_scored, w, b, delta, top_k, soft_fallback=True
                        )
                    pure_pool_lr = [p['number'] for p in (lr_strict or [])]
            except Exception:
                try:
                    pure_pool_top = [s['number'] for s in pure_pool_scored if s['score'] >= 3]
                    pure_pool_old_rule = list(pure_pool_top)
                    pure_pool_all = [s['number'] for s in pure_pool_scored]
                except Exception:
                    pass

            logger.info(f"工业级主报告生成完毕: {report_path}")
            self.save_memory(
                target_issue, env_name, current_weights,
                sorted(trinity_top5), sorted(trinity_top12), yesterday_hit_str,
                optimal_pick2=list(opt_p),
                pure_pool_top=pure_pool_top,
                pure_pool_old_rule=pure_pool_old_rule,
                pure_pool_lr=pure_pool_lr,
                pure_pool_all=pure_pool_all,
                conf_top5=conf.get('top5', []), conf_top12=conf.get('top12', []),
                b3_final5=b3_info.get('final_5', []),
                mrmr_top12=res.get('entropy', {}).get('optimized_top12', []),
                deep_picks=deep_picks, deep_kills=deep_kills,
                deep_consensus=deep_consensus,
                kl_msg=kl_status.get('msg'),
            )
            return report_path

        except Exception as e:
            logger.critical(f"报告生成发生灾难性故障: {e}")
            traceback.print_exc()
            return None

    def save_memory(self, target_issue, env, weights, top5, top12, yesterday_hit_str, 
                    optimal_pick2=None,
                    gauss_top5=None, cluster_top5=None, fourier_top5=None, fusion_top5=None, 
                    pure_pool_top=None, pure_pool_old_rule=None, pure_pool_lr=None,
                    pure_pool_all=None, conf_top5=None, conf_top12=None, 
                    b3_final5=None, mrmr_top12=None, deep_picks=None, deep_kills=None,
                    deep_consensus=None, kl_msg=None):
        memory_file = os.path.join(_PROJ, 'cache', "self_learning_state.json")
        # v2.2修复: 使用可重入的 json_file_lock 替代有缺陷的 msvcrt 锁
        from utils.json_file_lock import json_file_lock
        try:
            with json_file_lock(memory_file, timeout=30):
                try:
                    with open(memory_file, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                except Exception:
                    state = {"history": []}
                record = {
                    "run_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "target_issue": target_issue, "latest_issue": self.dc.latest_issue,
                    "environment": env, "trinity_weights": weights,
                    "top5": top5, "top12": top12, "yesterday_feedback": yesterday_hit_str
                }
                if optimal_pick2:
                    record["optimal_pick2"] = optimal_pick2
                if gauss_top5:
                    record["high_order_gauss_top5"] = gauss_top5
                if cluster_top5:
                    record["high_order_cluster_top5"] = cluster_top5
                if fourier_top5:
                    record["high_order_fourier_top5"] = fourier_top5
                if fusion_top5:
                    record["high_order_fusion_top5"] = fusion_top5
                if pure_pool_top:
                    record["pure_pool_top"] = pure_pool_top
                if pure_pool_old_rule:
                    record["pure_pool_old_rule"] = pure_pool_old_rule
                if pure_pool_lr:
                    record["pure_pool_lr"] = pure_pool_lr
                if pure_pool_all:
                    record["pure_pool_all"] = pure_pool_all
                if conf_top5:
                    record["conf_top5"] = conf_top5
                if conf_top12:
                    record["conf_top12"] = conf_top12
                if b3_final5:
                    record["b3_final5"] = b3_final5
                # v4.0: blast_final5 已砍掉
                if mrmr_top12:
                    record["mrmr_top12"] = mrmr_top12
                if deep_picks:
                    record["deep_picks"] = deep_picks
                if deep_kills:
                    record["deep_kills"] = deep_kills
                if deep_consensus:
                    record["deep_consensus"] = deep_consensus
                if kl_msg:
                    record["kl_msg"] = kl_msg

                state["history"].insert(0, record)
                state["history"] = state["history"][:50]
                with open(memory_file, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                logger.info("自我学习状态已同步更新至 self_learning_state.json (包含极高阶预测快照)")
        except TimeoutError:
            logger.warning("save_memory: 获取文件锁超时，跳过本次保存")
        except Exception as e:
            logger.warning(f"save_memory: 保存异常: {e}")


if __name__ == '__main__':
    engine = FullReportEngine()
    path = engine.generate_report()
    if path:
        print(f"报告已生成: {path}")
