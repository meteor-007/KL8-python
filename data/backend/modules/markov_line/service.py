# -*- coding: utf-8 -*-
"""
马尔可夫直线校准业务编排服务 (Markov Line Service Layer)
======================================================
统筹调度全流程：
  1. 历史开奖时序加载与校验
  2. 12 维特征抽取与状态空间打标
  3. 动态时间衰减马尔可夫转移矩阵训练
  4. P-P 累积分布直线拟合检验与残差拐点捕捉
  5. 综合解码生成 Top 5 金胆与 Top 12 大底
  6. 历史滚动样本外对账 (Walk-Forward Validation) 与物理落盘
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np

from backend.utils.paths import get_project_root, get_outputs_dir
from backend.utils.history_loader import load_history
from backend.modules.markov_line.feature_extractor import FeatureExtractor
from backend.modules.markov_line.state_space import StateSpace
from backend.modules.markov_line.markov_engine import MarkovEngine
from backend.modules.markov_line.line_calibrator import LineCalibrator
from backend.modules.markov_line.decoder import MarkovLineDecoder
from backend.modules.markov_line.calibrator_optimizer import MarkovHyperparamOptimizer

logger = logging.getLogger("k8quant.markov_line.service")


def get_output_paths() -> Dict[str, str]:
    """获取标准化落盘路径集合"""
    root = get_project_root()
    outputs_dir = get_outputs_dir()
    return {
        "storage_json": os.path.join(outputs_dir, "markov_line_latest.json"),
        "frontend_json": os.path.join(root, "frontend", "static", "markov_line_analysis.json"),
        "report_md": os.path.join(outputs_dir, "reports", "markov_line_report_latest.md"),
    }


def _build_ball_follow_matrix(draws_asc: List[List[int]], total_balls: int = 80) -> np.ndarray:
    """构建球与球之间的单步历史跟随转移矩阵 (80 x 80)"""
    mat = np.zeros((total_balls, total_balls), dtype=np.float64)
    n = len(draws_asc)
    if n < 2:
        return mat

    for t in range(n - 1):
        curr_d = draws_asc[t]
        next_d = draws_asc[t + 1]
        for b1 in curr_d:
            if 1 <= b1 <= total_balls:
                for b2 in next_d:
                    if 1 <= b2 <= total_balls:
                        mat[b1 - 1, b2 - 1] += 1.0

    # 行归一化
    row_sums = mat.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    return mat / row_sums


def run_markov_line_pipeline(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    运行完整的马尔可夫链与特征直线校准预测流水线
    :param limit: 可选的历史期数限制
    :return: 包含完整预测、状态概率、直线校准、残差信号的结构化结果字典
    """
    # 步骤 1：加载历史开奖记录（默认按期号降序返回）
    history_desc = load_history(limit=limit)
    if not history_desc or len(history_desc) < 30:
        raise ValueError("历史开奖数据不足，至少需要 30 期以支撑马尔可夫转移矩阵训练")

    # 转换为按时间从旧到新升序排列
    history_asc = list(reversed(history_desc))
    draws_asc = [entry["numbers"] for entry in history_asc]
    latest_entry = history_asc[-1]
    latest_issue = str(latest_entry["issue"])
    latest_numbers = sorted(latest_entry["numbers"])

    # 计算目标期号 (如 2026252 -> 2026253)
    try:
        target_issue = str(int(latest_issue) + 1)
    except Exception:
        target_issue = f"{latest_issue}_next"

    # 步骤 2：全时序特征提取与状态空间打标
    extractor = FeatureExtractor(total_balls=80)
    features = extractor.extract_full_history(history_asc)

    state_space = StateSpace()
    state_sequence = [state_space.encode(f) for f in features]

    # 计算当前各号码的最新遗漏
    current_omissions: Dict[int, int] = {b: 0 for b in range(1, 81)}
    for b in range(1, 81):
        omit = 0
        for draw in reversed(draws_asc):
            if b in draw:
                break
            omit += 1
        current_omissions[b] = omit

    # 步骤 3：自动超参数寻优 (闭环调优寻找最佳半衰期、平滑系数与二阶权重，把 P-P 曲线拉直至 y=x)
    optimizer = MarkovHyperparamOptimizer(num_states=state_space.num_states)
    tuning_result = optimizer.optimize_parameters(state_sequence, eval_window=80)

    best_hl = tuning_result.best_half_life
    best_alpha = tuning_result.best_alpha
    best_beta = tuning_result.best_beta

    # 步骤 4：以最优超参数构建并训练马尔可夫动态转移引擎
    engine = MarkovEngine(
        num_states=state_space.num_states,
        half_life=best_hl,
        second_order_weight=best_beta,
        smoothing_alpha=best_alpha,
    )
    engine.fit(state_sequence)

    # 步骤 5：推演下一期宏观状态分布
    curr_state_id = state_sequence[-1]
    prev_state_id = state_sequence[-2] if len(state_sequence) >= 2 else None
    next_state_probs = engine.predict_next_state_distribution(
        current_state=curr_state_id,
        prev_state=prev_state_id,
    )
    trans_entropy = engine.compute_state_entropy(next_state_probs)

    # 使用寻优器得到的最优拟合检验结果
    pp_line_result = tuning_result.best_line_fit
    calibrator = optimizer.calibrator

    # B. 80球理论均值水平直线残差分析与拐点捕捉
    rebound_signals = calibrator.detect_residual_rebound_signals(
        history_draws_asc=draws_asc,
        window_size=60,
        total_balls=80,
    )

    # 步骤 6：构建球跟随矩阵并执行反向解码
    follow_matrix = _build_ball_follow_matrix(draws_asc=draws_asc, total_balls=80)
    decoder = MarkovLineDecoder(total_balls=80)
    decode_result = decoder.decode_predictions(
        predicted_state_probs=next_state_probs,
        rebound_signals=rebound_signals,
        latest_draw=latest_numbers,
        current_omissions=current_omissions,
        ball_follow_matrix=follow_matrix,
        recent_draws=draws_asc,
        transition_entropy=trans_entropy,
    )

    # 步骤 7：组装最终标准数据载荷
    final_payload: Dict[str, Any] = {
        "module_name": "markov_line",
        "module_cn": "马尔可夫链与特征直线校准推演引擎",
        "latest_issue": latest_issue,
        "target_issue": target_issue,
        "latest_draw_numbers": latest_numbers,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # 核心输出号码
        "top5_gold": decode_result["top5_gold"],
        "top12_elite": decode_result["top12_elite"],
        # 攻防策略模式
        "regime_mode": decode_result["regime_mode"],
        "regime_desc": decode_result["regime_desc"],
        # 宏观状态转移研判
        "current_state": {
            "state_id": curr_state_id,
            "description": state_space.decode(curr_state_id).description,
        },
        "predicted_primary_state": decode_result["primary_state"],
        "predicted_alternative_states": decode_result["alternative_states"],
        "transition_entropy": round(trans_entropy, 4),
        # 直线校准数据
        "straight_line_calibration": pp_line_result.to_dict(),
        # 自动超参数寻优轨迹与最优参数
        "auto_tuning": tuning_result.to_dict(),
        # 残差拐点反弹前 10 强信号
        "top_rebound_signals": [s.to_dict() for s in rebound_signals[:10]],
        # 详细号码评分透视
        "candidate_details": decode_result["top_candidates_detail"],
    }

    # 步骤 8：落盘保存 JSON 与 Markdown 研报
    paths = get_output_paths()
    for p in paths.values():
        os.makedirs(os.path.dirname(p), exist_ok=True)

    json_text = json.dumps(final_payload, ensure_ascii=False, indent=2)
    with open(paths["storage_json"], "w", encoding="utf-8") as f:
        f.write(json_text)
    with open(paths["frontend_json"], "w", encoding="utf-8") as f:
        f.write(json_text)

    # 生成 Markdown 研报
    _generate_markdown_report(final_payload, paths["report_md"])

    return final_payload


def _generate_markdown_report(data: Dict[str, Any], file_path: str) -> None:
    """生成详尽的人类可读 Markdown 研报"""
    t5_str = "、".join(f"{x:02d}" for x in data["top5_gold"])
    t12_str = " ".join(f"{x:02d}" for x in data["top12_elite"])
    latest_nums = " ".join(f"{x:02d}" for x in data["latest_draw_numbers"])
    prim_s = data["predicted_primary_state"]
    line_cal = data["straight_line_calibration"]
    tuning = data.get("auto_tuning", {})

    intercept_val = line_cal['intercept']
    if intercept_val < 0:
        eq_str = f"{line_cal['slope']} x - {abs(intercept_val)}"
    else:
        eq_str = f"{line_cal['slope']} x + {intercept_val}"

    md_lines = [
        f"# 📐 马尔可夫链与特征直线校准量化推演研报 (第 {data['target_issue']} 期)",
        f"> **生成时间**：{data['generated_at']}  ",
        f"> **最新开奖期号**：第 {data['latest_issue']} 期，开奖号码：`{latest_nums}`",
        "",
        "---",
        "",
        "## 一、 核心决策输出（核心精选）",
        f"- 👑 **金胆 Top 5（高置信度核心）**：【 **{t5_str}** 】",
        f"- 🛡️ **核心大底 Top 12（防守大底）**：`[ {t12_str} ]`",
        "",
        "---",
        "",
        "## 二、 自动寻优与直线校准闭环（自适应调参拉直至 y=x）",
        f"- **最优半衰期 $\\lambda^*$**：`{tuning.get('best_half_life', 45.0)}` 期（动态匹配近期大环境）",
        f"- **最优平滑系数 $\\alpha^*$**：`{tuning.get('best_alpha', 0.08)}`（防死心眼与噪声抑制）",
        f"- **二阶转移权重 $\\beta^*$**：`{tuning.get('best_beta', 0.25)}`（高阶惯性融合比率）",
        f"- **拟合直线方程**：$y = {eq_str}$",
        rf"- **直线拟合优度 ($R^2$)**：**{line_cal['r_squared']}** （$\ge 0.92$ 即为紧密贴合）",
        rf"- **KS 统计量最大偏差**：`{line_cal['ks_statistic']}` （$\le 0.15$ 判定为无系统性失真）",
        f"- **直线化判定**：**{'✅ 通过（经过自动调优，分布严格拟合成 y=x 直线）' if line_cal['is_straight'] else '⚠️ 告警（微调中）'}**",
        f"- **当前攻防策略模式**：**{data.get('regime_desc', '均衡常态推进')}**",
        "",
        "---",
        "",
        "## 三、 马尔可夫宏观形态转移推演（大白话：大盘面相要往哪跳）",
        f"- **当前所属状态**：状态 {data['current_state']['state_id']}（{data['current_state']['description']}）",
        f"- **下期首选目标状态**：状态 {prim_s['state_id']}（胜率: **{prim_s['probability'] * 100:.2f}%**）",
        f"  - **和值区间预判**：`{prim_s['sum_level']}`",
        f"  - **奇偶偏向预判**：`{prim_s['odd_level']}`",
        f"  - **动能与冷热预判**：`{prim_s['momentum_level']}`",
        f"- **转移熵（确定性指标）**：`{data['transition_entropy']}`（数值越低，出号方向越凝聚）",
        "",
        "---",
        "",
        "## 四、 累积残差均值回归拐点前 5 强（大白话：凹陷触底反弹的买点）",
        "| 球号 | 当前累积残差 (偏离度) | Z-Score (下探倍数) | 反弹拉升强度 | 状态判定 |",
        "| :---: | :---: | :---: | :---: | :---: |",
    ]

    for sig in data["top_rebound_signals"][:5]:
        status_desc = "🚀 强烈拐头向上反弹" if sig["is_rebounding"] else "📉 深度超卖探底蓄势"
        md_lines.append(
            f"| **{sig['target_id']:02d}** | {sig['current_residual']} | {sig['z_score']} | {sig['rebound_strength']} | {status_desc} |"
        )

    md_lines.extend([
        "",
        "---",
        "",
        "## 五、 操盘手风控提示与对账守则",
        "1. **多维共振**：本模块产出的 Top 5 金胆已结合【宏观状态匹配度 35% + 直线残差反弹 30% + 历史跟班 25% + 遗漏回补 10%】。",
        "2. **紧急刹车（物理熔断）**：若 P-P 图检验 $R^2 < 0.85$ 或连续多期大环境出现变盘，系统将自动降低该模块权重，请以防守策略为主。",
    ])

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))


def get_latest_markov_line_data() -> Dict[str, Any]:
    """获取最新推演数据（优先读缓存，无缓存则自动执行流水线）"""
    paths = get_output_paths()
    if os.path.exists(paths["frontend_json"]):
        try:
            with open(paths["frontend_json"], "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return run_markov_line_pipeline()


def get_markov_line_review(n: int = 30) -> Dict[str, Any]:
    """
    执行样本外滚动回测 (Walk-Forward Validation) 对账
    【核心原则】：严格屏蔽未来数据！在推演第 t 期时，算法仅允许访问第 0 至 t-1 期。
    在每一个历史窗口动态调用自动调优器获取当期最优超参并预测。
    """
    history_desc = load_history(limit=n + 80)
    if not history_desc or len(history_desc) < n + 20:
        return {"error": "历史样本不足，无法执行滚动回测"}

    history_asc = list(reversed(history_desc))
    total_test_issues = n
    start_idx = len(history_asc) - total_test_issues

    top5_hits: List[int] = []
    top12_hits: List[int] = []
    audit_logs: List[Dict[str, Any]] = []

    # 命中频次分布桶
    top5_hit_dist: Dict[str, int] = {str(k): 0 for k in range(6)}
    top12_hit_dist: Dict[str, int] = {str(k): 0 for k in range(13)}

    for idx in range(start_idx, len(history_asc)):
        # 严格切片：仅使用截止当期前的数据，物理隔绝未来
        train_data = history_asc[:idx]
        actual_draw = history_asc[idx]
        actual_numbers = set(actual_draw["numbers"])
        target_issue = str(actual_draw["issue"])

        # 1. 训练切片特征抽取与状态编码
        extractor = FeatureExtractor(total_balls=80)
        feats = extractor.extract_full_history(train_data)
        space = StateSpace()
        seq = [space.encode(f) for f in feats]

        # 2. 逐期闭环超参数寻优 (无未来信息)
        optimizer = MarkovHyperparamOptimizer(num_states=space.num_states)
        tuning = optimizer.optimize_parameters(seq, eval_window=60)

        # 3. 最优参数拟合与推演
        engine = MarkovEngine(
            num_states=space.num_states,
            half_life=tuning.best_half_life,
            smoothing_alpha=tuning.best_alpha,
            second_order_weight=tuning.best_beta,
        )
        engine.fit(seq)

        curr_s = seq[-1]
        prev_s = seq[-2] if len(seq) >= 2 else None
        p_dist = engine.predict_next_state_distribution(curr_s, prev_s)

        calibrator = LineCalibrator()
        draws_train = [entry["numbers"] for entry in train_data]
        rebound_sigs = calibrator.detect_residual_rebound_signals(draws_train, window_size=60)

        # 遗漏表统计
        omits = {b: 0 for b in range(1, 81)}
        for b in range(1, 81):
            omit = 0
            for d in reversed(draws_train):
                if b in d:
                    break
                omit += 1
            omits[b] = omit

        follow_mat = _build_ball_follow_matrix(draws_train, 80)
        decoder = MarkovLineDecoder(80)
        dec = decoder.decode_predictions(
            predicted_state_probs=p_dist,
            rebound_signals=rebound_sigs,
            latest_draw=draws_train[-1],
            current_omissions=omits,
            ball_follow_matrix=follow_mat,
            recent_draws=draws_train,
            transition_entropy=engine.compute_state_entropy(p_dist),
        )

        t5 = dec["top5_gold"]
        t12 = dec["top12_elite"]

        hit5 = len(set(t5) & actual_numbers)
        hit12 = len(set(t12) & actual_numbers)

        top5_hits.append(hit5)
        top12_hits.append(hit12)

        top5_hit_dist[str(hit5)] = top5_hit_dist.get(str(hit5), 0) + 1
        top12_hit_dist[str(hit12)] = top12_hit_dist.get(str(hit12), 0) + 1

        # 计算截至当期的滚动累计均值
        cum_hit5 = float(np.mean(top5_hits))
        cum_hit12 = float(np.mean(top12_hits))

        audit_logs.append({
            "issue": target_issue,
            "top5": t5,
            "top12": t12,
            "actual_draw": sorted(list(actual_numbers)),
            "hit5": hit5,
            "hit12": hit12,
            "cum_hit5": round(cum_hit5, 3),
            "cum_hit12": round(cum_hit12, 3),
            "tuned_half_life": tuning.best_half_life,
            "tuned_alpha": tuning.best_alpha,
            "tuned_r2": round(tuning.best_r2, 4),
        })

    avg_hit5 = float(np.mean(top5_hits)) if top5_hits else 0.0
    avg_hit12 = float(np.mean(top12_hits)) if top12_hits else 0.0
    # 随机基准：单球 25% 概率。Top 5 期望命中 = 5 * 0.25 = 1.25 码；Top 12 期望命中 = 12 * 0.25 = 3.0 码
    lift5 = float(avg_hit5 / 1.25) if avg_hit5 > 0 else 0.0
    lift12 = float(avg_hit12 / 3.0) if avg_hit12 > 0 else 0.0

    # 胜率指标：Top 5 命中 >= 2 码的期数占比；Top 12 命中 >= 4 码的期数占比
    win_rate_top5_ge2 = float(sum(1 for h in top5_hits if h >= 2) / total_test_issues)
    win_rate_top12_ge4 = float(sum(1 for h in top12_hits if h >= 4) / total_test_issues)

    review_result = {
        "test_periods": total_test_issues,
        "avg_top5_hits": round(avg_hit5, 3),
        "avg_top12_hits": round(avg_hit12, 3),
        "random_baseline_top5": 1.25,
        "random_baseline_top12": 3.0,
        "lift_top5": round(lift5, 3),
        "lift_top12": round(lift12, 3),
        "win_rate_top5_ge2": round(win_rate_top5_ge2 * 100, 1),
        "win_rate_top12_ge4": round(win_rate_top12_ge4 * 100, 1),
        "is_alpha_valid": bool(lift5 >= 1.05 and lift12 >= 1.0),
        "top5_hit_distribution": top5_hit_dist,
        "top12_hit_distribution": top12_hit_dist,
        "audit_logs": audit_logs,
    }

    # 持久化落盘保存滚动回测结果
    try:
        root = get_project_root()
        rev_path1 = os.path.join(get_outputs_dir(), "markov_line_review.json")
        rev_path2 = os.path.join(root, "frontend", "static", "markov_line_review.json")
        os.makedirs(os.path.dirname(rev_path1), exist_ok=True)
        os.makedirs(os.path.dirname(rev_path2), exist_ok=True)
        rev_str = json.dumps(review_result, ensure_ascii=False, indent=2)
        with open(rev_path1, "w", encoding="utf-8") as f:
            f.write(rev_str)
        with open(rev_path2, "w", encoding="utf-8") as f:
            f.write(rev_str)
    except Exception as e:
        logger.warning(f"保存滚动回测结果异常: {e}")

    return review_result
