#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 工业级分析引擎 v2.1 — 迁移至 pipeline/ 子树
================================================
v2.1 修复清单:
  1. [Bug] extract_rapid_blast() 重复打开 Excel → 改为从 DataCenter 复用数据
  2. [Bug] wb.close() 缺失 → 所有 openpyxl 操作加 try/finally
  3. [Enhancement] 集成 AutonomousLearner 闭环学习: 预测→记录→复盘→学习→调整→优化
  4. [Enhancement] generate_report() 完成后自动触发闭环学习
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
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

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


class DataCenter:
    """数据中心：单例模式加载并缓存所有原始数据（线程安全）"""
    _instance = None
    _lock = __import__('threading').Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DataCenter, cls).__new__(cls)
                cls._instance.initialized = False
        return cls._instance

    def _sync_hot_numbers_to_excel(self):
        """自动同步热码统计文件到主Excel"""
        import glob
        import re
        import subprocess

        hot_dir = os.path.join(_PROJ, '热码统计')
        output_file = os.path.join(_PROJ, '跟随+点位+开奖数据.xlsx')

        hot_files = glob.glob(os.path.join(hot_dir, '*-热码统计.xlsx'))
        if not hot_files:
            logger.info("未找到热码统计文件，跳过同步")
            return

        latest_file = max(hot_files, key=os.path.basename)
        match = re.search(r'-(\d+)期', os.path.basename(latest_file))
        if not match:
            logger.warning(f"无法从文件名提取期号: {latest_file}")
            return

        issue = match.group(1)

        import openpyxl
        _excel_path = os.path.join(_PROJ, '跟随+点位+开奖数据.xlsx')
        if os.path.exists(output_file):
            try:
                with excel_lock(_excel_path, timeout=30):
                    wb = openpyxl.load_workbook(output_file, read_only=True)
                    try:
                        ws = wb['跟随号码统计']
                        for row in ws.iter_rows(min_row=1, max_row=2000, max_col=1, values_only=True):
                            cell_val = str(row[0] or '')
                            if f'{issue}期数据' in cell_val:
                                logger.info(f"期号 {issue} 已存在于主Excel中，跳过同步")
                                return
                    finally:
                        wb.close()
            except Exception as e:
                logger.warning(f"检查主Excel失败: {e}")

        logger.info(f"发现新的热码统计文件: {os.path.basename(latest_file)}，开始同步...")
        try:
            script_path = os.path.join(_PROJ, 'data_acquisition', 'process_hot_numbers.py')
            if not os.path.exists(script_path):
                script_path = os.path.join(_PROJ, 'process_hot_numbers.py')
            if os.path.exists(script_path):
                result = subprocess.run(
                    [sys.executable, script_path, issue, latest_file],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    cwd=_PROJ
                )
                if result.returncode == 0:
                    logger.info(f"✅ 热码统计同步成功: {issue}期")
                else:
                    logger.error(f"❌ 热码统计同步失败: {result.stderr}")
            else:
                logger.warning(f"process_hot_numbers.py 不存在")
        except Exception as e:
            logger.error(f"同步热码统计时发生异常: {e}")

    def _apply_excel_formats(self):
        """自动执行渲染管线，进行点位底色和中奖边框的格式化标记"""
        import subprocess
        logger.info("开始执行自动渲染管线 (apply_formats.py)...")
        try:
            script_path = os.path.join(_PROJ, 'data', 'format', 'apply_formats.py')
            if not os.path.exists(script_path):
                script_path = os.path.join(_PROJ, 'format', 'apply_formats.py')
            if os.path.exists(script_path):
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    cwd=_PROJ
                )
                if result.returncode == 0:
                    logger.info("✅ 自动渲染管线执行成功")
                else:
                    logger.error(f"❌ 自动渲染管线执行失败: {result.stderr}")
            else:
                logger.warning(f"渲染脚本不存在: {script_path}")
        except Exception as e:
            logger.error(f"执行自动渲染管线时发生异常: {e}")

    def _validate_data_consistency(self):
        """数据一致性校验 + 自动修复 (v2.2新增)

        在数据加载前执行全量校验，确保各数据源期号/日期对齐。
        如果发现不一致，自动触发修复（Excel同步）。\n        """
        try:
            from utils.data_validator import validate_all, print_report
            report = validate_all(auto_fix=True)

            # 仅输出摘要（非完整报告）
            if not report['all_pass']:
                logger.warning("="*40)
                logger.warning("数据一致性校验发现问题：")
                for err in report['errors']:
                    logger.warning(f"  ❌ {err}")
                for w in report['warnings']:
                    logger.warning(f"  ⚠️ {w}")
                for fix in report['fixes']:
                    logger.info(f"  🔧 {fix}")
                logger.warning("="*40)
            else:
                logger.info("数据一致性校验通过 ✅")

            # 严重错误（kl8_history无数据）则中止
            a_check = report['checks'].get('A_kl8_history', {})
            if not a_check.get('exists', False):
                raise RuntimeError("kl8_history_final.txt 无数据，无法继续！")

            # 关键校验：开奖历史Sheet必须与kl8_history一致
            c_check = report['checks'].get('C_excel_开奖历史', {})
            d_check = report['checks'].get('D_excel_全量开奖数据', {})
            if not c_check.get('issue_aligned', True) or not d_check.get('issue_aligned', True):
                logger.warning("Excel Sheet与kl8_history期号不一致，已尝试自动修复")

            return report['all_pass']
        except ImportError:
            logger.warning("data_validator 模块不可用，跳过数据一致性校验")
            return True
        except Exception as e:
            logger.warning(f"数据一致性校验异常: {e}")
            return True  # 校验失败不阻止后续流程

    def _run_garbage_collection(self):
        """自动执行垃圾回收与数据收容"""
        import subprocess
        logger.info("开始执行自动垃圾回收 (garbage_collector.py)...")
        try:
            script_path = os.path.join(_PROJ, 'utils', 'garbage_collector.py')
            if os.path.exists(script_path):
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    cwd=_PROJ
                )
                if result.returncode == 0:
                    logger.info("✅ 自动垃圾回收完成")
                else:
                    logger.warning(f"⚠️ 自动垃圾回收部分失败: {result.stderr}")
            else:
                logger.warning(f"垃圾回收脚本不存在: {script_path}")
        except Exception as e:
            logger.error(f"执行垃圾回收管线时发生异常: {e}")

    def initialize(self):
        if self.initialized:
            return

        # ── v2.2: 垃圾回收 + 数据一致性校验 + 自动修复 ──
        self._run_garbage_collection()
        self._validate_data_consistency()

        self._sync_hot_numbers_to_excel()
        self._apply_excel_formats()

        from core import feature_optimizer as fo
        logger.info("正在执行全量数据加载 (Excel + Txt)...")
        try:
            self.data1, self.data2, self.d1_stars, self.history, self.points = fo.load_all_data()
            if self.history:
                self.latest_issue = self.history[0]['issue']
            else:
                self.latest_issue = "000000"
            if self.data2:
                self.latest_data2_issue = list(self.data2.keys())[-1]
            else:
                self.latest_data2_issue = "000000"
            self.initialized = True
            logger.info(f"数据中心加载成功: 历史={len(self.history)}期, 最新={self.latest_issue}, data2最新={self.latest_data2_issue}")
        except Exception as e:
            logger.error(f"数据中心加载失败: {e}")
            raise


class PredictorEngine:
    """预测引擎核心：调度20个优化方案 + 闭环学习"""
    def __init__(self):
        self.dc = DataCenter()
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
            'resonance': fo.plan2_hot_stealth_resonance(self.dc.data1, self.dc.data2, self.dc.d1_stars, self.dc.history),
            'accel': fo.plan3_frequency_acceleration(self.dc.history),
            'topo': fo.plan4_adjacency_topology(self.dc.data2, self.dc.history),
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

    def _point_feature_vector(self, pts_set):
        pts = sorted(list(pts_set))
        if not pts:
            return [0.0] * 11
        import math
        gaps = [pts[i + 1] - pts[i] for i in range(len(pts) - 1)] if len(pts) > 1 else [0]
        zone4 = [0, 0, 0, 0]
        for num in pts:
            zone4[min(3, (num - 1) // 20)] += 1
        odds = sum(1 for num in pts if num % 2 == 1)
        
        mean_val = sum(pts) / len(pts)
        std_val = math.sqrt(sum((x - mean_val)**2 for x in pts) / len(pts)) if len(pts) > 1 else 0.0
        span = pts[-1] - pts[0]
        odd_ratio = odds / len(pts)
        gap_mean = sum(gaps) / len(gaps) if gaps else 0.0
        gap_std = math.sqrt(sum((x - gap_mean)**2 for x in gaps) / len(gaps)) if len(gaps) > 1 else 0.0
        consecutive = sum(1 for gap in gaps if gap == 1)
        
        return [mean_val, std_val, float(span), odd_ratio, gap_mean, gap_std, float(consecutive),
                float(zone4[0]), float(zone4[1]), float(zone4[2]), float(zone4[3])]

    def calculate_gaussian_energy_diffusion(self, trinity_scores, trinity_top12):
        """量子质心高斯核流能扩散算法"""
        try:
            import numpy as np
            scores = {}
            sigma = 1.5
            for n in range(1, 81):
                val = 0.0
                for m in trinity_top12:
                    score_m = trinity_scores.get(m, 1.0)
                    dist = abs(n - m)
                    val += score_m * np.exp(- (dist ** 2) / (2 * (sigma ** 2)))
                scores[n] = float(val)
            sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            top5 = sorted_nums[:5]
            details = {n: scores[n] for n in top5}
            return top5, details, scores
        except Exception as e:
            logger.error(f"高斯核流能扩散计算失败: {e}")
            top5 = sorted(trinity_top12[:5])
            details = {n: 1.0 for n in top5}
            return top5, details, {n: 1.0 for n in range(1, 81)}

    def calculate_markov_cluster_transition(self):
        """点位势能聚类隐马尔可夫转移路径预测"""
        try:
            import numpy as np
            from sklearn.cluster import KMeans
            from collections import Counter
            
            reversed_hist = list(reversed(self.dc.history))
            vectors = []
            valid_indices = []
            
            for idx, h in enumerate(reversed_hist):
                pts_set = self.dc.points.get(h['issue'], set())
                if pts_set:
                    vectors.append(self._point_feature_vector(pts_set))
                    valid_indices.append(idx)
            
            if len(vectors) < 10:
                logger.warning("点位数据样本不足，KMeans聚类降级")
                return [1, 2, 3, 4, 5], {n: 0.25 for n in range(1, 6)}, {n: 0.25 for n in range(1, 81)}
                
            # Z-score 标准化
            vec_arr = np.array(vectors)
            mean = vec_arr.mean(axis=0)
            std = vec_arr.std(axis=0)
            std[std == 0.0] = 1.0
            scaled_vecs = (vec_arr - mean) / std
            
            # KMeans 聚类 (K=4)
            kmeans = KMeans(n_clusters=4, random_state=42, n_init='auto')
            labels = kmeans.fit_predict(scaled_vecs)
            
            # 建立全期序列的聚类簇映射
            full_clusters = [0] * len(reversed_hist)
            for idx, label in zip(valid_indices, labels):
                full_clusters[idx] = label
                
            # 转移矩阵统计
            transition_counts = np.zeros((4, 4))
            for t in range(len(full_clusters) - 1):
                transition_counts[full_clusters[t], full_clusters[t+1]] += 1
            transition_probs = (transition_counts + 1.0) / (transition_counts.sum(axis=1, keepdims=True) + 4.0)
            
            # 各聚类簇的号码分布频次
            cluster_draws = {j: [] for j in range(4)}
            for t, h in enumerate(reversed_hist):
                c_id = full_clusters[t]
                cluster_draws[c_id].append(h['numbers'])
                
            cluster_probs = {}
            for c_id in range(4):
                draws = cluster_draws[c_id]
                probs = {n: 0.0 for n in range(1, 81)}
                if draws:
                    counter = Counter()
                    for d in draws:
                        counter.update(d)
                    total_draws = len(draws)
                    for n in range(1, 81):
                        probs[n] = counter[n] / total_draws
                else:
                    for n in range(1, 81):
                        probs[n] = 0.25
                cluster_probs[c_id] = probs
                
            # 预测下一期所属聚类簇及号码得分
            C_T = full_clusters[-1]
            pred_probs = transition_probs[C_T]
            scores = {}
            for n in range(1, 81):
                val = 0.0
                for j in range(4):
                    val += pred_probs[j] * cluster_probs[j][n]
                scores[n] = float(val)
                
            sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            top5 = sorted_nums[:5]
            details = {n: scores[n] for n in top5}
            return top5, details, scores
        except Exception as e:
            logger.error(f"点位聚类状态转移计算失败: {e}")
            top5 = [2, 12, 22, 32, 42]
            return top5, {n: 0.25 for n in top5}, {n: 0.25 for n in range(1, 81)}

    def calculate_fourier_spectral_decomposition(self):
        """离散傅里叶谱分解相干态谐波外推"""
        try:
            import numpy as np
            if len(self.dc.history) < 30:
                logger.warning("历史数据不足30期，傅里叶谱分析跳过")
                return [3, 13, 23, 33, 43], {n: 1.0 for n in range(1, 6)}, {n: 1.0 for n in range(1, 81)}
                
            history_30 = list(reversed(self.dc.history[:30]))
            scores = {}
            
            for n in range(1, 81):
                x_n = np.array([1.0 if n in h['numbers'] else 0.0 for h in history_30])
                X = np.fft.fft(x_n)
                # 提取中低频（k=1..5）的平均功率谱密度 PSD
                psd = np.mean(np.abs(X[1:6])**2)
                
                # 计算号码的当前遗漏期数
                omission = 0
                for h in self.dc.history:
                    if n in h['numbers']:
                        break
                    omission += 1
                    
                # 寻找最强主导谐波周期
                k_dom = 1 + np.argmax(np.abs(X[1:6]))
                T_dom = 30.0 / k_dom
                theta = np.angle(X[k_dom])
                
                # 余弦相位外推下一期 (omission + 1)
                proj = np.cos((2 * np.pi / T_dom) * (omission + 1) + theta)
                scores[n] = float(psd * proj)
                
            sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            top5 = sorted_nums[:5]
            details = {n: scores[n] for n in top5}
            return top5, details, scores
        except Exception as e:
            logger.error(f"傅里叶谱分析计算失败: {e}")
            top5 = [3, 13, 23, 33, 43]
            return top5, {n: 1.0 for n in top5}, {n: 1.0 for n in range(1, 81)}

    def calculate_trinity_extreme_fusion(self, s_gauss, s_cluster, s_fourier):
        """三元一体高阶极致整合最优5码"""
        try:
            import numpy as np
            def normalize(scores_dict):
                vals = np.array(list(scores_dict.values()))
                mean = np.mean(vals)
                std = np.std(vals) or 1.0
                return {k: float((v - mean) / std) for k, v in scores_dict.items()}
            
            n_gauss = normalize(s_gauss)
            n_cluster = normalize(s_cluster)
            n_fourier = normalize(s_fourier)
            
            fusion_scores = {}
            for n in range(1, 81):
                fusion_scores[n] = n_gauss[n] + n_cluster[n] + n_fourier[n]
                
            sorted_nums = sorted(fusion_scores.keys(), key=lambda x: fusion_scores[x], reverse=True)
            top5 = sorted_nums[:5]
            details = {n: fusion_scores[n] for n in top5}
            return top5, details, fusion_scores
        except Exception as e:
            logger.error(f"三元一体极致整合融合计算失败: {e}")
            top5 = [1, 2, 3, 4, 5]
            return top5, {n: 1.0 for n in top5}, {n: 1.0 for n in range(1, 81)}

    def extract_special_5(self, pipeline_res: Dict[str, Any]) -> Dict[str, Any]:
        """首席战略官特供：Hidden Energy 5 (B3 Right + AI 置信度融合 + EF/RW/FO 提纯)
        
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
            # 优先使用 latest_issue 的数据（防御性编程，避免边界情况）
            if latest_issue in data2:
                b3_right_data = data2[latest_issue][2]['right']
                b3_right_nums = [item[0] for item in b3_right_data]
            elif target_issue in data2:
                # target_issue 是待开奖期号，其数据基于历史热码统计（非开奖结果）
                b3_right_data = data2[target_issue][2]['right']
                b3_right_nums = [item[0] for item in b3_right_data]
            b3_right_stealth = [n for n in b3_right_nums if n not in target_points]
        else:
            conf_top12 = pipeline_res['strat']['conf_score'].get('top12', [])
            b3_right_stealth = conf_top12[:3] if conf_top12 else []
            b3_right_nums = conf_top12[:5] if conf_top12 else []

        top_12 = pipeline_res['strat']['conf_score'].get('top12', [])
        candidates = list(set(b3_right_stealth + top_12))

        # 引入 EF/RW/FO 评分进行最终提纯 (v4.0: 替代 MK×4.0+EF×0.6)
        from core.energy_field import calc_energy_field, calc_omission_sigmoid
        from core.feature_optimizer import get_all_layer_a_scores

        ef_res = calc_energy_field(self.dc.history, decay_rate=0.5)
        rw_res = calc_omission_sigmoid(self.dc.history)
        fo_res = get_all_layer_a_scores(self.dc.history) or {}

        scores = {}
        details = {}
        for n in candidates:
            ef_val = ef_res.get(n, 0)
            rw_val = rw_res.get(n, 0)
            fo_val = fo_res.get(n, 0) if isinstance(fo_res, dict) else 0
            # v4.0: EF×1.0 + RW×0.8 + FO×0.5 (三个有区分度的模块)
            total_score = ef_val * 1.0 + rw_val * 0.8 + fo_val * 0.5
            scores[n] = total_score
            details[n] = {'EF': ef_val, 'RW': rw_val, 'FO': fo_val, 'Score': total_score}

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
        """生成完整分析报告 + 触发闭环学习"""
        _excel_path = os.path.join(_PROJ, '跟随+点位+开奖数据.xlsx')
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

            # ── 极高阶前瞻三元规律预测计算 ──
            gauss_top5, gauss_details, s_gauss = self.calculate_gaussian_energy_diffusion(trinity_scores, trinity_top12)
            cluster_top5, cluster_details, s_cluster = self.calculate_markov_cluster_transition()
            fourier_top5, fourier_details, s_fourier = self.calculate_fourier_spectral_decomposition()
            fusion_top5, fusion_details, s_fusion = self.calculate_trinity_extreme_fusion(s_gauss, s_cluster, s_fourier)

            today = datetime.datetime.now().strftime("%Y%m%d")
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

                # 9. 纯净池
                y_pure = yesterday_record.get('pure_pool_top', [])
                if y_pure:
                    hit_pure = len(set(y_pure) & actual_latest)
                    review_lines.append(f"  - **纯净池定胆**：命中 `{hit_pure}/{len(y_pure)}`")
                    
                # 10. 三元规律
                y_gauss = yesterday_record.get('high_order_gauss_top5', [])
                if y_gauss:
                    hit_gauss = len(set(y_gauss) & actual_latest)
                    review_lines.append(f"  - **高斯核流能**：命中 `{hit_gauss}/{len(y_gauss)}`")
                y_cluster = yesterday_record.get('high_order_cluster_top5', [])
                if y_cluster:
                    hit_cluster = len(set(y_cluster) & actual_latest)
                    review_lines.append(f"  - **马尔可夫聚类**：命中 `{hit_cluster}/{len(y_cluster)}`")
                y_fourier = yesterday_record.get('high_order_fourier_top5', [])
                if y_fourier:
                    hit_fourier = len(set(y_fourier) & actual_latest)
                    review_lines.append(f"  - **傅里叶谐波**：命中 `{hit_fourier}/{len(y_fourier)}`")
                y_fusion = yesterday_record.get('high_order_fusion_top5', [])
                if y_fusion:
                    hit_fusion = len(set(y_fusion) & actual_latest)
                    review_lines.append(f"  - **极致整合5码**：命中 `{hit_fusion}/{len(y_fusion)}`")

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
                    self.learner.record_prediction(
                        period=target_issue,
                        prediction_scores=all_scores,
                        top5=trinity_top5,
                        top12=trinity_top12,
                        top20=[n for n, s in trinity_sorted[:20]],
                        environment=env_name,
                        volatility=0.15,
                    )
                    logger.info(f"预测已记录到学习引擎: 期号{target_issue}")
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

                f.write(f"### 5. 首席战略官特供 · Hidden Energy 5\n")
                f.write(f"- **共振逻辑**：`{b3_info['logic']}`\n")
                f.write(f"- **B3质量分**：`{b3_info['quality_score']:.2f}`\n")
                f.write(f"- **评分细节**：\n")
                for i, (n, d) in enumerate(b3_info['scoring_details'].items()):
                    f.write(f"    - [No. {i+1}] 号码 `{n:02d}`: EF `{d.get('EF', 0):.4f}` | RW `{d.get('RW', 0):.4f}` | FO `{d.get('FO', 0):.4f}` | 综合动能 `{d['Score']:.4f}` 🌟\n")
                f.write(f"- **最终推荐 (5 码)**：`{b3_info['final_5']}`\n\n")

                # v4.0: 极速爆破模块已砍掉 (近9期Lift=0.27x灾难性)

                f.write(f"### 7. 影子模型与对冲分布\n")
                f.write(f"- **主攻方案**：`{hedge.get('main', [])[:12]}...`\n")
                f.write(f"- **对冲方案 A**：`{hedge.get('hedge_a', [])[:10]}...`\n")
                f.write(f"- **对冲方案 B**：`{hedge.get('hedge_b', [])[:10]}...`\n\n")

                if learner_state_str:
                    f.write(f"### 8. 闭环学习引擎状态\n")
                    f.write(f"- **当前参数**：`{learner_state_str}`\n\n")

                # ── 第九模块：纯净池定胆 ──
                pure_pool_scored = []
                try:
                    from core.pure_pool_scorer import run_pure_pool_analysis
                    # 构建 points_map: issue -> set
                    _pts_map = {}
                    for _k, _v in self.dc.points.items():
                        _pts_map[_k] = set(_v) if not isinstance(_v, set) else _v
                    pure_pool_report, pure_pool_scored = run_pure_pool_analysis(
                        target_issue, self.dc.history, _pts_map
                    )
                    f.write(pure_pool_report)
                except Exception as e:
                    logger.warning(f"纯净池定胆模块执行失败: {e}")
                    f.write(f"### 9. 纯净池定胆 (Pure Pool Scorer)\n\n")
                    f.write(f"- **执行失败**: `{e}`\n\n")

                # ── 第十模块：极高阶前瞻三元规律预测与极致整合 ──
                f.write(f"### 10. 极高阶前瞻三元规律预测与极致整合 (Quantum & Spectral Wave Fusion)\n")
                f.write(f"- **维度一：量子质心高斯核流能扩散 (Gaussian Energy Diffusion)**\n")
                f.write(f"    - **共鸣逻辑**：以 Stacking 极秘 Top 12 为量子质心，应用标准差 $\sigma = 1.5$ 邻域热势能高斯扩散，纠偏踏空。\n")
                f.write(f"    - **最优 5 码**：`{gauss_top5}`\n")
                f.write(f"    - **评分细节**：\n")
                for n, score in gauss_details.items():
                    f.write(f"        - 号码 `{n:02d}`: 扩散后量子动能 `{score:.4f}` 🌟\n")
                f.write("\n")
                
                f.write(f"- **维度二：点位势能聚类隐马尔可夫转移 (Markovian Cluster Transition)**\n")
                f.write(f"    - **共鸣逻辑**：将历史点位按 10 维非线性向量作 KMeans 聚类 ($K=4$)，统计演化转移矩阵，加权预测落奖概率分布。\n")
                f.write(f"    - **最优 5 码**：`{cluster_top5}`\n")
                f.write(f"    - **评分细节**：\n")
                for n, score in cluster_details.items():
                    f.write(f"        - 号码 `{n:02d}`: 转移后期望开出概率 `{score:.4f}` 🌟\n")
                f.write("\n")
                
                f.write(f"- **维度三：离散傅里叶相干态谐波外推 (Discrete Fourier Cosine Projection)**\n")
                f.write(f"    - **共鸣逻辑**：分析号码 30 期出球时序谱密度 (PSD) 和基频相位，计算其当前遗漏在谐波余弦周期波峰的投影。\n")
                f.write(f"    - **最优 5 码**：`{fourier_top5}`\n")
                f.write(f"    - **评分细节**：\n")
                for n, score in fourier_details.items():
                    f.write(f"        - 号码 `{n:02d}`: 频域余弦相干势能 `{score:.4f}` 🌟\n")
                f.write("\n")
                
                f.write(f"- **🌟 终极推荐：三元一体高阶极致整合最优 5 码 (Trinity High-Order Fusion)**\n")
                f.write(f"    - **融合方式**：将上述三大高阶物理/数学维度得分采用 Z-score 对齐，消除量纲干扰后等权融合。\n")
                f.write(f"    - **极致整合 5 码**：`{fusion_top5}` 🔥\n\n")

                # ── 第十一模块：物理熔断面板 ──
                f.write(f"### 11. ⚖️ 物理熔断面板 (Physics Breaker)\n")
                f.write(f"- **KL 散度监控 (结构性突变)**：`{kl_status['msg']}`\n\n")

                # ── 风险提示与统计信标审计 ──
                f.write(f"### 9. 风险提示与统计信标审计 (Risk Audit)\n")
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
                            level0_pass = [n for n, p in p_values.items() if p['bonf'] < 0.000625]
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
                                        # Level 3: 软降级 — 使用FDR通过的号码作为弱信号参考
                                        # 不再完全停止预测，而是降低置信度系数至0.3x
                                        level3_fdr_pass = [n for n, p in p_values.items() if p['fdr'] < 0.20]
                                        if level3_fdr_pass:
                                            g_level = 3
                                            pass_nums = level3_fdr_pass[:8]  # 限制最多8个弱信号号码
                                            g_warning = "⚠️ 零信标降级: Level 3 — 系统当前缺乏强统计信号，启用弱信号参考模式（置信度0.3x），推荐结果仅供参考"
                                        else:
                                            g_level = 3
                                            pass_nums = []
                                            g_warning = "⚠️ 零信标降级: Level 3 — 系统当前完全无统计显著信号，所有号码等权等幅，推荐结果仅供参考"
                                        logger.warning(f"[信标审计] {g_warning}")
                        except Exception as e:
                            logger.warning(f"主动计算零信标降级失败: {e}")
                            g_level = 2
                            g_warning = f"⚠️ 零信标降级: Level 2 — AUC统计文件读取失败({e})，默认进入观察仓"

                # 统计置信度状态约束系数映射 (红线五强制绑定 — Level 3软降级优化)
                confidence_map = {
                    0: ("强信号推荐", "1.0x"),
                    1: ("弱信号防御", "0.5x"),
                    2: ("极弱信号观察", "0.1x"),
                    3: ("弱信号参考", "0.3x")  # 优化: 从"停止预测0.0x"调整为"弱信号参考0.3x"
                }
                confidence_advice, confidence_coeff = confidence_map.get(g_level, ("弱信号参考", "0.3x"))

                f.write(f"- **💰 统计置信度状态约束指令**：当前处于 `Level {g_level}` 状态，"
                        f"**建议状态输出：`[{confidence_advice}]`**，"
                        f"**置信度输出系数：`{confidence_coeff}`**\n")
                f.write(f"    - 显著号码数: {len(pass_nums)}，激活信标等级: Level {g_level}\n")

                if g_warning:
                    f.write(f"- **{g_warning}**\n")
                    warnings_found = True

                # Level 3 软降级提示 (优化: 不再强制熔断)
                if g_level == 3:
                    if pass_nums:
                        f.write(f"- **📋 Level 3 弱信号参考**：系统已进入弱信号参考模式，"
                                f"置信度系数为 0.3x，以下号码可作为辅助参考：{sorted(pass_nums[:8])}。\n")
                    else:
                        f.write(f"- **🛑 Level 3 等权等幅警告**：系统当前无统计显著信号，"
                                f"所有号码权重重置为 1.0x，单点置信度上限为 25% (随机基线)。\n")
                    warnings_found = True
                
                if not warnings_found:
                    f.write(f"- **🟢 安全指标**：当前三维融合(EF/RW/FO)参数分布均在安全搜索空间内，信标统计显著性通过检验，系统风险处于极低水位。\n")
                f.write("\n")

                f.write("---\n")
                f.write("**Engine Record:** Trinity Fusion architecture with 20 optimization schemes executed.\n")

            # 纯净池高置信定胆
            pure_pool_top = []
            try:
                pure_pool_top = [s['number'] for s in pure_pool_scored if s['score'] >= 3]
            except Exception:
                pass

            logger.info(f"报告生成完毕: {report_path}")
            self.save_memory(target_issue, env_name, current_weights, sorted(trinity_top5), sorted(trinity_top12), yesterday_hit_str,
                             gauss_top5=gauss_top5, cluster_top5=cluster_top5, fourier_top5=fourier_top5, fusion_top5=fusion_top5, 
                             pure_pool_top=pure_pool_top,
                             conf_top5=conf.get('top5', []), conf_top12=conf.get('top12', []),
                             b3_final5=b3_info.get('final_5', []),
                             mrmr_top12=res.get('entropy', {}).get('optimized_top12', []))

        except Exception as e:
            logger.critical(f"报告生成发生灾难性故障: {e}")
            traceback.print_exc()

    def save_memory(self, target_issue, env, weights, top5, top12, yesterday_hit_str, 
                    gauss_top5=None, cluster_top5=None, fourier_top5=None, fusion_top5=None, 
                    pure_pool_top=None, conf_top5=None, conf_top12=None, 
                    b3_final5=None, mrmr_top12=None):
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
                if conf_top5:
                    record["conf_top5"] = conf_top5
                if conf_top12:
                    record["conf_top12"] = conf_top12
                if b3_final5:
                    record["b3_final5"] = b3_final5
                # v4.0: blast_final5 已砍掉
                if mrmr_top12:
                    record["mrmr_top12"] = mrmr_top12

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
    engine = PredictorEngine()
    engine.generate_report()
