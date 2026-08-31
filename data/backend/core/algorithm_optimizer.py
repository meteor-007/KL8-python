# -*- coding: utf-8 -*-
"""
算法模型层优化模块 (Algorithm Optimizer - Layer B)
================================================
4个深度优化方案的统一实现。
迁移至 core/ 子树 — 路径已自动适应

方案7:  马尔可夫链状态转移深度整合
方案9:  贝叶斯后验动态更新
方案10: 蒙特卡洛模拟下期分布
方案11: 遗漏值的非线性衰减模型

[v4.1] 方案8(共现网络)已移除: 连续多期返回空列表，无贡献纯噪声
[v4.1] 方案12(FFT周期检测)已移除: 返回全部80码，无区分度
"""

import os
import json
import collections
import math
import random

# ============================================================================
#  全局常量 — 自动上溯到项目根目录
# ============================================================================
import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
HISTORY_FILE = os.path.join(_PROJ, 'kl8_history_final.txt')
MARKOV_FILE = os.path.join(_PROJ, 'cache', 'daily_markov_predictions.json')
ZONE_RANGES = [(i * 10 + 1, (i + 1) * 10) for i in range(8)]
THEORY_DENSITY = 20.0 / 80.0


def load_hist(limit=None):
    """读取开奖历史, 返回list[dict], 按期号降序 (最新在索引0)。

    v2.2: 委托给 utils.history_loader.load_history()，消除重复实现。
    """
    from utils.history_loader import load_history
    return load_history(limit=limit)


# ==============================
# 方案7: 马尔可夫链状态转移 (降维+平滑修正版)
# ==============================
def plan7_markov_integration(history):
    """
    马尔可夫链状态转移深度整合 — 修正版
    
    修正点:
      1. 状态空间降维: lookback从5降到3 (2³=8种状态 vs 2⁵=32种)
         理由: ~130期数据估计2560个转移概率(80号×32状态)严重欠采样
         降为80×8=640个, 可靠性显著提升
      
      2. Dirichlet先验平滑: 转移概率 = (count + prior) / (total + prior×2)
         先验强度 α=1.0 (Laplace平滑)
         理由: 观测次数为0或1的状态, 其转移概率不可信
         加入先验后, 低观测状态自动回退到先验(≈0.25),
         高观测状态的后验则更接近真实频率
      
      3. 多阶马尔可夫: 同时估计1阶(仅看上1期)和3阶转移概率,
         用加权平均融合, 提升短期预测的稳定性
    """
    print("\n" + "=" * 70 + "\n【方案7】马尔可夫链状态转移 (降维+平滑)\n" + "=" * 70)
    if len(history) < 10:
        return {}

    try:
        from config import get_config
        cfg = get_config()
        lookback = cfg.get('markov.lookback', 3)
        prior_strength = cfg.get('markov.prior_strength', 1.0)
        default_prob = cfg.get('markov.default_prob', 0.25)
        min_obs = cfg.get('markov.min_observations', 3)
    except Exception:
        lookback = 3
        prior_strength = 1.0
        default_prob = 0.25
        min_obs = 3

    # 将历史切片反转为正向时间轴 (老 -> 新)，解决时空倒错
    chronological_hist = list(reversed(history))

    # ── 3阶马尔可夫 (lookback=3) — 全量滑动统计 ──
    states_3 = {}
    for num in range(1, 81):
        for i in range(len(chronological_hist) - lookback):
            pattern = tuple(1 if num in chronological_hist[i + j]['numbers'] else 0 for j in range(lookback))
            if i + lookback < len(chronological_hist):
                next_val = 1 if num in chronological_hist[i + lookback]['numbers'] else 0
            else:
                continue
            if pattern not in states_3:
                states_3[pattern] = {'appear': 0, 'total': 0}
            states_3[pattern]['total'] += 1
            states_3[pattern]['appear'] += next_val

    # ── 1阶马尔可夫 (更稳健的短期信号) ──
    states_1 = {}
    for num in range(1, 81):
        for i in range(len(chronological_hist) - 1):
            cur = 1 if num in chronological_hist[i]['numbers'] else 0
            nxt = 1 if num in chronological_hist[i + 1]['numbers'] else 0
            key = (cur,)
            if key not in states_1:
                states_1[key] = {'appear': 0, 'total': 0}
            states_1[key]['total'] += 1
            states_1[key]['appear'] += nxt

    # 当前模式 (用正向序列的最后几个元素)
    current_patterns_3 = {}
    current_patterns_1 = {}
    for num in range(1, 81):
        current_patterns_3[num] = tuple(1 if num in h['numbers'] else 0 for h in chronological_hist[-lookback:])
        current_patterns_1[num] = (1 if num in chronological_hist[-1]['numbers'] else 0,)

    # 计算转移概率 (带Dirichlet平滑)
    transition_probs = {}
    smooth_details = {}
    for num in range(1, 81):
        # 3阶概率
        cp3 = current_patterns_3[num]
        if cp3 in states_3 and states_3[cp3]['total'] >= min_obs:
            s = states_3[cp3]
            # Dirichlet 平滑: 二分类(出现/未出现), alpha = prior_strength*default_prob,
            # 两类各加 alpha, 分母为 total + 2*alpha
            prob_3 = (s['appear'] + prior_strength * default_prob) \
                / (s['total'] + 2 * prior_strength * default_prob)
        else:
            prob_3 = default_prob  # 不足观测, 回退先验

        # 1阶概率
        cp1 = current_patterns_1[num]
        if cp1 in states_1 and states_1[cp1]['total'] >= min_obs:
            s = states_1[cp1]
            prob_1 = (s['appear'] + prior_strength * default_prob) \
                / (s['total'] + 2 * prior_strength * default_prob)
        else:
            prob_1 = default_prob

        # 融合: 3阶权重0.6, 1阶权重0.4 (3阶更精确但1阶更稳定)
        transition_probs[num] = prob_3 * 0.6 + prob_1 * 0.4
        smooth_details[num] = {'prob_3': round(prob_3, 4), 'prob_1': round(prob_1, 4),
                               'obs_3': states_3.get(cp3, {}).get('total', 0),
                               'obs_1': states_1.get(cp1, {}).get('total', 0)}

    # 按转移概率排序: (概率降序, 号码升序)
    top20 = sorted(transition_probs, key=lambda n: (-transition_probs[n], n))[:20]
    print(f"  马尔可夫Top20 (lookback={lookback}, prior=α{prior_strength}): {top20}")
    # 打印Top5详情
    for n in top20[:5]:
        d = smooth_details[n]
        print(f"    号码{n:02d}: P={transition_probs[n]:.4f} (3阶={d['prob_3']:.4f} obs={d['obs_3']}, 1阶={d['prob_1']:.4f} obs={d['obs_1']})")
    # 保存到文件
    try:
        with open(MARKOV_FILE, 'w') as f:
            json.dump(transition_probs, f)
    except Exception:
        pass
    return {'markov_top20': top20, 'probs': transition_probs, 'smooth_details': smooth_details}


# ==============================
# 方案8: 号码共现网络 — [v4.1] 已移除
# ==============================
# 原因: 连续多期返回空列表，无贡献纯噪声
# 保留函数签名以防外部调用报错，返回空结果

def plan8_cooccurrence_network(history):
    """[v4.1] 已废弃: 连续多期返回空列表，无贡献纯噪声"""
    print("\n[方案8] 共现网络 — 已移除(v4.1): 连续多期返回空列表，无贡献纯噪声)")
    return {}


# ==============================
# 方案9: 贝叶斯后验动态更新 (Beta-Binomial 共轭推断)
# ==============================
def plan9_bayesian_update(history):
    """
    贝叶斯后验动态更新 — 修正版 (Beta-Binomial 共轭推断)
    
    原理:
      先验: P(num出现) ~ Beta(α₀, β₀), 其中 α₀=5, β₀=15
      均值 = α₀/(α₀+β₀) = 5/20 = 0.25 = 理论频率(20/80)
      
      观测: 最近N期中该号码出现k次
      后验: P(num出现|数据) ~ Beta(α₀+k, β₀+N-k)
      后验均值 = (α₀+k) / (α₀+β₀+N)
      
      使用指数时间衰减加权: 近期观测权重更高,
      等效观测次数 = Σ(decay^i * indicator(num in h_i))
      
    修正点:
      - 旧版: posterior = prior * likelihood (未归一化, 不是合法概率)
      - 新版: 使用Beta-Binomial共轭, 后验是合法的概率分布,
              且所有号码后验之和合理(自动归一化到0-1区间)
    """
    print("\n" + "=" * 70 + "\n【方案9】贝叶斯后验动态更新 (Beta-Binomial)\n" + "=" * 70)
    if len(history) < 5:
        return {}

    try:
        from config import get_config
        cfg = get_config()
        alpha_0 = cfg.get('bayesian.prior_alpha', 5.0)
        beta_0 = cfg.get('bayesian.prior_beta', 15.0)
        window = cfg.get('bayesian.likelihood_window', 20)
        decay = cfg.get('bayesian.decay_factor', 0.7)
    except Exception:
        alpha_0 = 5.0
        beta_0 = 15.0
        window = 20
        decay = 0.7

    prior_mean = alpha_0 / (alpha_0 + beta_0)  # = 0.25
    posteriors = {}
    credible_intervals = {}

    for num in range(1, 81):
        # 计算衰减加权的等效观测次数
        weighted_appear = 0.0
        weighted_absent = 0.0
        for i, h in enumerate(history[:window]):
            w = decay ** i
            if num in h['numbers']:
                weighted_appear += w
            else:
                weighted_absent += w

        # 后验参数
        alpha_post = alpha_0 + weighted_appear
        beta_post = beta_0 + weighted_absent
        posterior_mean = alpha_post / (alpha_post + beta_post)

        posteriors[num] = posterior_mean

        # 95%可信区间的近似 (Beta分布)
        # 使用正态近似: mean ± 1.96 * sqrt(var)
        var_post = (alpha_post * beta_post) / ((alpha_post + beta_post) ** 2 * (alpha_post + beta_post + 1))
        ci_lower = max(0, posterior_mean - 1.96 * var_post ** 0.5)
        ci_upper = min(1, posterior_mean + 1.96 * var_post ** 0.5)
        credible_intervals[num] = (round(ci_lower, 4), round(ci_upper, 4))

    # 后验概率 > 先验 的号码 (信号号码)
    above_prior = sorted(n for n in range(1, 81) if posteriors[n] > prior_mean)
    # (后验降序, 号码升序) 复合排序
    top20 = sorted(range(1, 81), key=lambda n: (-posteriors[n], n))[:20]

    print(f"  先验均值: {prior_mean:.4f} (Beta({alpha_0:.0f},{beta_0:.0f}))")
    print(f"  高于先验的号码: {len(above_prior)}个")
    print(f"  贝叶斯Top20: {top20}")
    # 打印Top5的可信区间
    for n in top20[:5]:
        ci = credible_intervals[n]
        print(f"    号码{n:02d}: 后验={posteriors[n]:.4f} 95%CI=[{ci[0]:.4f}, {ci[1]:.4f}]")

    return {'bayes_top20': top20, 'posteriors': posteriors, 'credible_intervals': credible_intervals}


# ==============================
# 方案10: 蒙特卡洛约束抽样模拟
# ==============================
def plan10_monte_carlo(history):
    """
    蒙特卡洛约束抽样模拟 — 修正版
    
    修正点:
      - 旧版: 用历史频率作为抽样权重 → 循环论证, 只能重现输入分布
      - 新版: 使用约束抽样 (Constrained Sampling), 组合三种信号:
        1. 均匀基线 (物理先验): 80选20的等概率基线
        2. 区间均衡约束: 每个区间(1-10,...,71-80)期望出2.5个号,
           对低于期望的区间施加回补权重
        3. 尾数均衡约束: 每个尾数(0-9)期望出2个号,
           对低于期望的尾数施加回补权重
        4. 遗漏回补约束: 长遗漏号码的Sigmoid回补权重
        
      三种信号按配置权重混合, 避免了循环论证,
      同时引入了结构性信息(区间/尾数均衡是物理约束, 非经验规律)
    """
    print("\n" + "=" * 70 + "\n【方案10】蒙特卡洛约束抽样模拟\n" + "=" * 70)
    if len(history) < 5:
        return {}

    try:
        from config import get_config
        cfg = get_config()
        n_sim = cfg.get('monte_carlo.n_simulations', 5000)
        zone_w = cfg.get('monte_carlo.constrained.zone_balance_weight', 0.3)
        tail_w = cfg.get('monte_carlo.constrained.tail_balance_weight', 0.2)
        omit_w = cfg.get('monte_carlo.constrained.omission_boost_weight', 0.3)
        uniform_w = cfg.get('monte_carlo.constrained.uniform_weight', 0.2)
    except Exception:
        n_sim = 5000
        zone_w, tail_w, omit_w, uniform_w = 0.3, 0.2, 0.3, 0.2

    recent = history[:5]  # 用最近5期计算结构约束

    # ── 信号1: 均匀基线 ──
    uniform_scores = {n: 1.0 for n in range(1, 81)}

    # ── 信号2: 区间均衡回补 ──
    zone_counts = collections.Counter()
    for h in recent:
        for n in h['numbers']:
            zone_counts[(n - 1) // 10] += 1
    expected_zone = len(recent) * 2.5  # 每区间期望2.5个/期 × 5期
    zone_scores = {}
    for n in range(1, 81):
        z = (n - 1) // 10
        deficit = max(0, expected_zone - zone_counts.get(z, 0))
        zone_scores[n] = 1.0 + deficit / expected_zone

    # ── 信号3: 尾数均衡回补 ──
    tail_counts = collections.Counter()
    for h in recent:
        for n in h['numbers']:
            tail_counts[n % 10] += 1
    expected_tail = len(recent) * 2.0  # 每尾数期望2个/期 × 5期
    tail_scores = {}
    for n in range(1, 81):
        t = n % 10
        deficit = max(0, expected_tail - tail_counts.get(t, 0))
        tail_scores[n] = 1.0 + deficit / expected_tail

    # ── 信号4: 遗漏Sigmoid回补 ──
    omission_scores = {}
    for n in range(1, 81):
        gap = 0
        for h in history[:50]:
            if n in h['numbers']:
                break
            gap += 1
        omission_scores[n] = 1.0 / (1.0 + math.exp(-0.3 * (gap - 8)))

    # ── 合成抽样权重 ──
    weights = {}
    for n in range(1, 81):
        weights[n] = (uniform_scores[n] * uniform_w +
                      zone_scores[n] * zone_w +
                      tail_scores[n] * tail_w +
                      omission_scores[n] * omit_w)

    # ── 蒙特卡洛模拟 ──
    # 基于最新期号生成确定性种子，确保同次预测可复现，不同期号结果不同
    # 修复: Python 3 的 hash() 默认启用 PYTHONHASHSEED 随机化，不可复现
    # 改用 hashlib 确定性哈希
    import hashlib
    latest_issue = history[0]['issue'] if history else 'default'
    seed = int(hashlib.md5(str(latest_issue).encode('utf-8')).hexdigest()[:8], 16) & 0x7FFFFFFF
    rng = random.Random(seed)
    weight_list = [weights[n] for n in range(1, 81)]
    sim_counts = collections.Counter()
    for _ in range(n_sim):
        picked = set()
        remaining = list(range(80))  # 0-79 代表 1-80
        remaining_weights = list(weight_list)
        while len(picked) < 20 and remaining:
            # 从剩余号码中按权重抽样
            chosen_idx = rng.choices(range(len(remaining)),
                                     weights=remaining_weights, k=1)[0]
            picked.add(remaining[chosen_idx] + 1)  # +1: 0-indexed → 1-indexed
            # 移除已选号码 (无放回)
            remaining.pop(chosen_idx)
            remaining_weights.pop(chosen_idx)

        for n in picked:
            sim_counts[n] += 1

    sim_freq = {n: sim_counts.get(n, 0) / n_sim for n in range(1, 81)}
    # (频率降序, 号码升序) 复合排序
    top20 = sorted(sim_freq, key=lambda n: (-sim_freq[n], n))[:20]
    print(f"  约束抽样Top20 (模拟{n_sim}次): {top20}")
    print(f"  权重配比: 均匀={uniform_w:.0%} 区间回补={zone_w:.0%} 尾数回补={tail_w:.0%} 遗漏回补={omit_w:.0%}")
    return {'mc_top20': top20, 'sim_freq': sim_freq}


# ==============================
# 方案11: 遗漏值的非线性衰减
# ==============================
def _omission_score(num, history, gamma=0.85):
    """计算号码的遗漏衰减得分, gamma是衰减因子"""
    score = 0.0
    for i, h in enumerate(history):
        if num in h['numbers']:
            score += gamma ** i
    return score


def plan11_omission_decay(history):
    """
    遗漏值的非线性衰减模型。
    号码长期未出现时, 衰减得分会趋近于0, 反弹概率增加。
    """
    print("\n" + "=" * 70 + "\n【方案11】遗漏值与反弹概率\n" + "=" * 70)
    if len(history) < 10:
        return {}
    scores = {n: _omission_score(n, history) for n in range(1, 81)}
    max_s = max(scores.values()) if scores else 1

    bounce_probs = {}
    for n in range(1, 81):
        s = scores[n]
        omission = sum(1 for h in history if n not in h['numbers'])
        # 遗漏越长且得分越低 → 反弹概率越大
        raw = (1 - s / max_s) * (omission / len(history))
        bounce_probs[n] = raw

    # (概率降序, 号码升序) 复合排序
    top20 = sorted(bounce_probs, key=lambda n: (-bounce_probs[n], n))[:20]
    print(f"  遗漏反弹Top20: {top20}")
    return {'decay_top20': top20}


# ==============================
# 方案12: 自相关周期性检测 — [v4.1] 已移除
# ==============================
# 原因: 返回全部80码，无区分度，对评分无贡献
# 保留函数签名以防外部调用报错，返回空结果

def plan12_fft_periodicity(history):
    """[v4.1] 已废弃: 返回全部80码，无区分度"""
    print("\n[方案12] FFT周期检测 — 已移除(v4.1): 返回全部80码，无区分度)")
    return {}


# ==============================
# 统一运行入口
# ==============================
def run_all():
    history = load_hist()
    r7 = plan7_markov_integration(history)
    r9 = plan9_bayesian_update(history)
    r10 = plan10_monte_carlo(history)
    r11 = plan11_omission_decay(history)
    return {'markov': r7, 'bayes': r9, 'mc': r10, 'decay': r11}


if __name__ == '__main__':
    run_all()
