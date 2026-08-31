#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告回填工具 — 补充缺失的历史日期报告
用法: python pipeline/backfill_reports.py
"""
import os
import sys

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()


import json
import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BackfillReports")


def backfill_report(report_date_str, target_period, latest_history_period):
    """
    为指定日期生成回填报告。
    
    核心思路：临时截断 DataCenter 的 history 到 target_period-1 期，
    然后调用 generate_report() 逻辑，但覆盖文件名为历史日期。
    
    Args:
        report_date_str: 报告日期，如 "20260610"
        target_period: 预测目标期号，如 "2026151"
        latest_history_period: 截断到的历史期号，如 "2026150"
    """
    # 该模块依赖已移除的旧版 PredictorEngine, 当前引擎接口为 DailyReportOrchestrator/FullReportEngine,
    # 旧引擎方法(calculate_gaussian_energy_diffusion 等)已不存在, 无法直接运行。
    try:
        from pipeline.auto_generate_daily_report import DataCenter
    except Exception as _e:  # noqa
        raise RuntimeError(
            "backfill_reports 依赖的旧版 PredictorEngine 已被移除, "
            "本模块已废弃, 请迁移到 daily_report_orchestrator/FullReportEngine 后再使用。"
        ) from _e
    from audit.kl_divergence_checker import KLDivergenceChecker
    from audit.collinearity_detector import CollinearityDetector
    from audit.v3_trinity_audit import dynamic_meta_fusion
    from utils.excel_lock import excel_lock
    
    # 先重置单例，确保干净初始化
    DataCenter._instance = None
    
    engine = None  # PredictorEngine 已移除, 后续逻辑不可达
    raise RuntimeError(
        "backfill_reports 依赖的旧版 PredictorEngine 已被移除, 本模块已废弃, 无法生成回填报告。"
    )
    
    # 截断历史数据到目标期号
    original_history = engine.dc.history
    truncated_history = [
        h for h in original_history 
        if int(h.get('issue', '9999999')) <= int(latest_history_period)
    ]
    # 按期号降序排列（最新在前）
    truncated_history.sort(key=lambda x: int(x['issue']), reverse=True)
    
    if not truncated_history:
        logger.error(f"截断后无历史数据: latest_history_period={latest_history_period}")
        return False
    
    # 临时替换引擎的历史数据
    engine.dc.history = truncated_history
    engine.dc.latest_issue = latest_history_period
    
    logger.info(f"截断历史: {len(original_history)} -> {len(truncated_history)} 期, "
                f"最新期号={latest_history_period}")
    
    _excel_path = os.path.join(ENGINE_PROJ, '跟随+点位+开奖数据.xlsx')
    try:
        with excel_lock(_excel_path, timeout=60):
            res = engine.run_pipeline()
            b3_info = engine.extract_special_5(res)
            # v4.0: 极速爆破已砍掉
        
        # 防御红线
        kl_checker = KLDivergenceChecker(engine.dc.history)
        kl_status = kl_checker.check_mutation()
        
        col_detector = CollinearityDetector(threshold=0.85)
        feat_warnings = col_detector.detect(res.get('feat', {}))
        

        
        # 环境识别
        try:
            from recognition.simplified_env_recognition import recognize_environment
            env_class, env_name, env_confidence, strategy_config = recognize_environment(engine.dc.history)
            trinity_weights = strategy_config['weights']
        except Exception as e:
            env_class = 2; env_name = "平衡震荡期"; env_confidence = 0.5
            trinity_weights = {'EF': 0.42, 'RW': 0.29, 'FO': 0.29}
            strategy_config = {'weights': trinity_weights, 'top5_count': 5, 'top12_count': 12}
        
        trinity_scores, current_weights = dynamic_meta_fusion(engine.dc.history)
        top5_count = strategy_config.get('top5_count', 5)
        top12_count = strategy_config.get('top12_count', 12)
        trinity_sorted = sorted(trinity_scores.items(), key=lambda x: (-x[1], x[0]))
        trinity_top5 = [n for n, s in trinity_sorted[:top5_count]]
        trinity_top12 = [n for n, s in trinity_sorted[:top12_count]]
        
        # 高阶计算
        gauss_top5, gauss_details, s_gauss = engine.calculate_gaussian_energy_diffusion(trinity_scores, trinity_top12)
        cluster_top5, cluster_details, s_cluster = engine.calculate_markov_cluster_transition()
        fourier_top5, fourier_details, s_fourier = engine.calculate_fourier_spectral_decomposition()
        fusion_top5, fusion_details, s_fusion = engine.calculate_trinity_extreme_fusion(s_gauss, s_cluster, s_fourier)
        
        # 使用传入的历史日期
        report_path = os.path.join(ENGINE_PROJ, 'reports', f"daily_analysis_report_{report_date_str}.md")
        
        conf = res['strat']['conf_score']
        hedge = res['strat']['hedge']
        
        # 复盘
        yesterday_hit_str = "无"
        actual_latest = set(engine.dc.history[0]['numbers'])
        
        memory_file = os.path.join(ENGINE_PROJ, 'cache', "self_learning_state.json")
        yesterday_record = None
        try:
            if os.path.exists(memory_file):
                with open(memory_file, 'r', encoding='utf-8') as mf:
                    state_data = json.load(mf)
                for rec in state_data.get('history', []):
                    if str(rec.get('target_issue')) == str(latest_history_period):
                        yesterday_record = rec
                        break
        except Exception as e:
            logger.warning(f"读取复盘历史失败: {e}")
        
        if yesterday_record:
            review_lines = []
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
            
            y_conf5 = yesterday_record.get('conf_top5', [])
            y_conf12 = yesterday_record.get('conf_top12', [])
            if y_conf12:
                hit_c5 = len(set(y_conf5) & actual_latest) if y_conf5 else 0
                hit_c12 = len(set(y_conf12) & actual_latest)
                review_lines.append(f"  - **传统AI**：Top5 命中 `{hit_c5}/5`, Top12 命中 `{hit_c12}/12`")
            
            y_mrmr = yesterday_record.get('mrmr_top12', [])
            if y_mrmr:
                hit_mrmr = len(set(y_mrmr) & actual_latest)
                review_lines.append(f"  - **熵控优化(mRMR)**：命中 `{hit_mrmr}/{len(y_mrmr)}`")
            
            y_b3 = yesterday_record.get('b3_final5', [])
            if y_b3:
                hit_b3 = len(set(y_b3) & actual_latest)
                review_lines.append(f"  - **Hidden Energy 5**：命中 `{hit_b3}/{len(y_b3)}`")
            
            # 6. 极速爆破 (v4.0已砍掉)
            
            y_pure = yesterday_record.get('pure_pool_top', [])
            if y_pure:
                hit_pure = len(set(y_pure) & actual_latest)
                review_lines.append(f"  - **纯净池定胆**：命中 `{hit_pure}/{len(y_pure)}`")
            
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
        
        if yesterday_hit_str == "无" and len(engine.dc.history) > 1:
            y_scores, y_weights = dynamic_meta_fusion(engine.dc.history[1:])
            y_sorted = sorted(y_scores.items(), key=lambda x: (-x[1], x[0]))
            y_top5 = [n for n, s in y_sorted[:5]]
            y_top12 = [n for n, s in y_sorted[:12]]
            hit5 = len(set(y_top5) & actual_latest)
            hit12 = len(set(y_top12) & actual_latest)
            w_str = " ".join([f"{k}:{v:.2f}" for k, v in y_weights.items()])
            yesterday_hit_str = f"`Top5 命中 {hit5}/5, Top12 命中 {hit12}/12 (调参: {w_str})`"
        
        # 闭环学习 (回填模式下跳过，避免污染学习状态)
        loop_report = None
        learner_state_str = ""
        
        # ── 写报告 ──
        report_date_display = f"{report_date_str[:4]}-{report_date_str[4:6]}-{report_date_str[6:8]}"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 快乐8 核心研判与审计报告 (工业级深度融合版)\n")
            f.write(f"**审计日期：** {report_date_display}\n")
            f.write(f"**目标期号：** {target_period} (待分析)\n\n")
            f.write(f"## 一、{latest_history_period}期 复盘追溯 (Audit Review)\n")
            f.write(f"- **开奖号码：** {'-'.join(f'{n:02d}' for n in engine.dc.history[0]['numbers'])}\n")
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
            f.write(f"## 二、{target_period}期 核心推荐 (Target Numbers)\n")
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
            
            # v4.0: 极速爆破模块已砍掉
            
            f.write(f"### 7. 影子模型与对冲分布\n")
            f.write(f"- **主攻方案**：`{hedge.get('main', [])[:12]}...`\n")
            f.write(f"- **对冲方案 A**：`{hedge.get('hedge_a', [])[:10]}...`\n")
            f.write(f"- **对冲方案 B**：`{hedge.get('hedge_b', [])[:10]}...`\n\n")
            
            if learner_state_str:
                f.write(f"### 8. 闭环学习引擎状态\n")
                f.write(f"- **当前参数**：`{learner_state_str}`\n\n")
            
            # 纯净池定胆
            pure_pool_scored = []
            try:
                from core.pure_pool_scorer import run_pure_pool_analysis
                _pts_map = {}
                for _k, _v in engine.dc.points.items():
                    _pts_map[_k] = set(_v) if not isinstance(_v, set) else _v
                pure_pool_report, pure_pool_scored = run_pure_pool_analysis(
                    target_period, engine.dc.history, _pts_map
                )
                f.write(pure_pool_report)
            except Exception as e:
                logger.warning(f"纯净池定胆模块执行失败: {e}")
                f.write(f"### 9. 纯净池定胆 (Pure Pool Scorer)\n\n")
                f.write(f"- **执行失败**: `{e}`\n\n")
            
            # 高阶模块
            f.write(f"### 10. 极高阶前瞻三元规律预测与极致整合 (Quantum & Spectral Wave Fusion)\n")
            f.write(f"- **维度一：量子质心高斯核流能扩散 (Gaussian Energy Diffusion)**\n")
            f.write(f"    - **共鸣逻辑**：以 Stacking 极秘 Top 12 为量子质心，应用标准差 $\\sigma = 1.5$ 邻域热势能高斯扩散，纠偏踏空。\n")
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
            
            f.write(f"### 11. ⚖️ 物理熔断面板 (Physics Breaker)\n")
            f.write(f"- **KL 散度监控 (结构性突变)**：`{kl_status['msg']}`\n\n")
            
            # 风险审计
            f.write(f"### 9. 风险提示与统计信标审计 (Risk Audit)\n")
            warnings_found = False
            
            # v4.0: MK已移除, 不再检查MK权重
            
            if feat_warnings:
                f.write(f"- **⚠️ 共线性预警 (Collinearity)**：检测到以下特征高度相关，方差膨胀风险极高！\n")
                for w_item in feat_warnings:
                    f.write(f"    - `{w_item[0]}` 与 `{w_item[1]}` 皮尔逊系数 `{w_item[2]:.4f}`\n")
                warnings_found = True
            
            if kl_status['triggered']:
                f.write(f"- **🚨 物理熔断警告**：系统检测到连续 KL 散度突变，摇奖机发生结构性偏移，强烈建议清空陈旧数据！\n")
                warnings_found = True
            
            # 零信标降级
            g_level = 0
            g_warning = None
            pass_nums = []
            
            deep_opt_cache = os.path.join(ENGINE_PROJ, 'cache', 'deep_optimization_result.json')
            cache_loaded = False
            if os.path.exists(deep_opt_cache):
                try:
                    with open(deep_opt_cache, 'r', encoding='utf-8') as df_f:
                        deep_res = json.load(df_f)
                        g_level = deep_res.get('gating_level', 0)
                        g_warning = deep_res.get('gating_warning')
                        pass_nums = deep_res.get('final_top5', [])
                        cache_loaded = True
                        if g_level == 3:
                            cache_loaded = False
                except Exception as e:
                    logger.warning(f"读取深度优化结果缓存失败: {e}")
            
            if not cache_loaded:
                auc_stats_file = os.path.join(ENGINE_PROJ, 'auc_stats.json')
                if os.path.exists(auc_stats_file):
                    try:
                        with open(auc_stats_file, 'r', encoding='utf-8') as as_f:
                            auc_raw = json.load(as_f)
                        if isinstance(auc_raw, dict) and 'results' in auc_raw:
                            auc_items = auc_raw['results']
                        elif isinstance(auc_raw, list):
                            auc_items = auc_raw
                        else:
                            auc_items = []
                        p_values = {}
                        for item in auc_items:
                            num = item.get('num')
                            p_val = item.get('p_value', 1.0)
                            p_bonf = item.get('p_adjusted_bonf', 1.0)
                            p_fdr = item.get('p_adjusted_fdr', 1.0)
                            if num is not None:
                                p_values[int(num)] = {'raw': p_val, 'bonf': p_bonf, 'fdr': p_fdr}
                        
                        level0_pass = [n for n, p in p_values.items() if p['raw'] < 0.000625]
                        if len(level0_pass) >= 3:
                            g_level = 0; pass_nums = level0_pass
                        else:
                            level1_pass = [n for n, p in p_values.items() if p['fdr'] < 0.10]
                            if len(level1_pass) >= 3:
                                g_level = 1; pass_nums = level1_pass
                                g_warning = "⚠️ 零信标降级: Level 1 — 仅FDR-BH校正通过，溢价幅度减半"
                            else:
                                level2_pass = [n for n, p in p_values.items() if p['raw'] < 0.05]
                                if len(level2_pass) >= 3:
                                    g_level = 2; pass_nums = level2_pass
                                    g_warning = "⚠️ 零信标降级: Level 2 — 系统当前缺乏统计显著的强信号"
                                else:
                                    level3_fdr_pass = [n for n, p in p_values.items() if p['fdr'] < 0.20]
                                    if level3_fdr_pass:
                                        g_level = 3; pass_nums = level3_fdr_pass[:8]
                                        g_warning = "⚠️ 零信标降级: Level 3 — 系统当前缺乏强统计信号"
                                    else:
                                        g_level = 3; pass_nums = []
                                        g_warning = "⚠️ 零信标降级: Level 3 — 系统当前完全无统计显著信号"
                    except Exception as e:
                        logger.warning(f"主动计算零信标降级失败: {e}")
                        g_level = 2
                        g_warning = f"⚠️ 零信标降级: Level 2 — AUC统计文件读取失败({e})，默认进入观察仓"
            
            confidence_map = {
                0: ("强信号推荐", "1.0x"),
                1: ("弱信号防御", "0.5x"),
                2: ("极弱信号观察", "0.1x"),
                3: ("弱信号参考", "0.3x")
            }
            confidence_advice, confidence_coeff = confidence_map.get(g_level, ("弱信号参考", "0.3x"))
            
            f.write(f"- **💰 统计置信度状态约束指令**：当前处于 `Level {g_level}` 状态，"
                    f"**建议状态输出：`[{confidence_advice}]`**，"
                    f"**置信度输出系数：`{confidence_coeff}`**\n")
            f.write(f"    - 显著号码数: {len(pass_nums)}，激活信标等级: Level {g_level}\n")
            
            if g_warning:
                f.write(f"- **{g_warning}**\n")
                warnings_found = True
            
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
            f.write(f"**Engine Record:** Trinity Fusion architecture with 20 optimization schemes executed. "
                    f"[Backfill report for {report_date_display}]\n")
        
        logger.info(f"回填报告生成完毕: {report_path}")
        return True
        
    except Exception as e:
        logger.error(f"回填报告生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """补充缺失的报告"""
    # 定义需要补充的报告：日期 -> (目标期号, 最新历史期号)
    missing_reports = {
        "20260610": ("2026151", "2026150"),  # 6月10日预测2026151期，历史到2026150
    }
    
    for date_str, (target_period, latest_history_period) in missing_reports.items():
        report_path = os.path.join(_PROJ, 'reports', f"daily_analysis_report_{date_str}.md")
        if os.path.exists(report_path):
            logger.info(f"报告已存在，跳过: {report_path}")
            continue
        
        logger.info(f"开始生成回填报告: 日期={date_str}, 目标期号={target_period}, "
                    f"最新历史期号={latest_history_period}")
        success = backfill_report(date_str, target_period, latest_history_period)
        if success:
            logger.info(f"✅ 回填成功: daily_analysis_report_{date_str}.md")
        else:
            logger.error(f"❌ 回填失败: daily_analysis_report_{date_str}.md")


if __name__ == '__main__':
    main()
