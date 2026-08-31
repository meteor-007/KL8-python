# -*- coding: utf-8 -*-
"""
深度优化引擎 (Deep Optimizer - Layers B/C)
========================================
DEPRECATED (v3.0): 仅供 feature_optimizer FO 层内部调用。
日报与子系统不再直接引用 plan17–22 独立输出。

语义化命名方案 (消除编号冲突):
  原Plan17 → deep_entropy_boost    (序列熵增检测)
  原Plan18 → deep_stride_collision (Stride-Row空间碰撞)
  原Plan19 → deep_adversarial_filter (奇点对抗过滤)
  原Plan20 → deep_cluster_accel    (集群加速器)
  原Plan21 → deep_momentum_score   (横截面动能)
  原Plan22 → deep_omission_harmonics (遗漏谐波)

注意: strategy_optimizer.py 中的 plan17/18/19 是不同函数, 已存在编号冲突。
本文件使用 deep_ 前缀消歧, 同时保留旧名作为别名确保向后兼容。
"""
import math
import collections
import numpy as np

def deep_entropy_boost(history_draw_order):
    """别名: plan17_sequence_entropy"""
    return _deep_entropy_boost_impl(history_draw_order)

# 向后兼容别名
plan17_sequence_entropy = deep_entropy_boost

def _deep_entropy_boost_impl(history_draw_order):
    """
    方案 17: 序列熵增检测
    分析原始出球顺序的混杂度 (Shannon Entropy)

    注意: 各加载器可能已把 entry['numbers'] 按升序排序 (如 main_v2.load_history),
    因此优先使用 entry.get('draw_order') 即原始出球顺序计算相邻球号差值;
    若加载器未提供 draw_order 字段, 则退化为"排序后间距熵",
    此时目标为"号码在数值轴上的间距分布规律"而非原始出球混杂度。
    """
    results = {}
    history = history_draw_order[:20] 
    for entry in history:
        # 优先原始出球顺序; 不可得时退回已排序 numbers (排序后间距熵)
        order = entry.get('draw_order') or entry['numbers']
        deltas = [order[i+1] - order[i] for i in range(len(order)-1)]
        counts = collections.Counter(deltas)
        total = len(deltas)
        entropy = -sum((count/total) * math.log2(count/total) for count in counts.values())
        issue_key = entry.get('period') or entry.get('issue', 'unknown')
        results[issue_key] = round(entropy, 3)
    
    all_ents = list(results.values())
    if not all_ents:
        # 无有效历史: 返回空建议而非除零崩溃
        return {'entropies': {}, 'boost_suggestion': []}
    avg_entropy = sum(all_ents) / len(all_ents)
    last_issue = sorted(results.keys())[-1]
    last_ent = results[last_issue]
    
    boost_nums = []
    if last_ent < avg_entropy * 0.9:
        # 极度规律后的反弹 -> 推荐最近遗漏最长的号码（统计驱动）
        omission_scores = {}
        for n in range(1, 81):
            gap = 0
            for h in history_draw_order[:20]:
                if n in h['numbers']:
                    break
                gap += 1
            omission_scores[n] = gap
        sorted_by_omission = sorted(omission_scores, key=lambda x: -omission_scores[x])
        boost_nums = sorted_by_omission[:20]
    elif last_ent > avg_entropy * 1.1:
        # 极度混乱后的收敛 -> 推荐最近5期频率最高的号码（统计驱动）
        freq = collections.Counter(n for h in history_draw_order[:5] for n in h['numbers'])
        boost_nums = [n for n, _ in freq.most_common(20)]
    
    return {'entropies': results, 'boost_suggestion': boost_nums}

def deep_stride_collision(stride_matrices):
    """别名: plan18_stride_row_collision"""
    return _deep_stride_collision_impl(stride_matrices)

# 向后兼容别名
plan18_stride_row_collision = deep_stride_collision

def _deep_stride_collision_impl(stride_matrices):
    """Stride-Row 空间碰撞检测

    修复: 旧版将带星号标记的号码字符串 (如 '5*') 和不带星号的 ('5')
    视为不同 key 进行计数, 导致碰撞检测失效。
    新版: 先清洗为纯数字再统计碰撞。
    """
    collision_scores = collections.Counter()
    for row_idx in range(4):
        clean_nums = []        # 清洗后的号码列表
        starred_nums = set()   # 带星号的号码集合
        pos_map = collections.defaultdict(list)
        for win_idx in range(4):
            if win_idx in stride_matrices:
                nums_in_row = stride_matrices[win_idx][row_idx]
                for pos, n in enumerate(nums_in_row):
                    n_str = str(n)
                    clean_n = int(n_str.replace('*', ''))
                    if '*' in n_str:
                        starred_nums.add(clean_n)
                    clean_nums.append(clean_n)
                    pos_map[clean_n].append(pos)
        counts = collections.Counter(clean_nums)
        for num, count in counts.items():
            if count >= 2:
                # 星号号码碰撞权重更高
                multiplier = 1.5 if num in starred_nums else 1.0
                collision_scores[num] += (count * multiplier)
            positions = pos_map.get(num, [])
            if len(set(positions)) < len(positions):
                collision_scores[num] += 3.0
    return dict(collision_scores)

def deep_adversarial_filter(primary_recommendations, history):
    """别名: plan19_adversarial_filter"""
    return _deep_adversarial_filter_impl(primary_recommendations, history)

# 向后兼容别名
plan19_adversarial_filter = deep_adversarial_filter

def _deep_adversarial_filter_impl(primary_recommendations, history):
    """
    方案 19: 奇点对抗过滤 (重构版)
    引入集群保护机制，避免误杀处于强趋势中的热码。
    """
    f10 = collections.Counter(n for h in history[:10] for n in h['numbers'])
    limit = 10 * 0.25 * 1.6 # 略微放宽限制
    potential_traps = {n for n, c in f10.items() if c > limit}
    
    # 集群识别：如果一个号码周围 3 个号位内有 3 个以上的热码，视为集群，不予剔除
    protected_hot = set()
    for n in potential_traps:
        cluster_count = sum(1 for neighbor in range(max(1, n-3), min(81, n+4)) if neighbor in potential_traps)
        if cluster_count >= 3:
            protected_hot.add(n)
    
    final_traps = potential_traps - protected_hot
    filtered = [n for n in primary_recommendations if n not in final_traps]
    removed = [n for n in primary_recommendations if n in final_traps]
    
    return filtered, removed

def deep_cluster_accel(history):
    """别名: plan20_cluster_accelerator"""
    return _deep_cluster_accel_impl(history)

plan20_cluster_accelerator = deep_cluster_accel

def _deep_cluster_accel_impl(history):
    """
    方案 20: 集群加速器
    识别近期正在形成的强力集群并给予指数级权重。
    """
    if len(history) < 3: return {}
    # 统计最近 3 期的 Zone 密度
    zone_stats = collections.defaultdict(list)
    for h in history[:3]:
        zc = collections.Counter((n-1)//10 for n in h['numbers'])
        for z in range(8):
            zone_stats[z].append(zc.get(z, 0))
    
    accelerated_nums = []
    for z, hits in zone_stats.items():
        # 如果最近 3 期命中数持续上升或维持在高位(>4)
        if sum(hits) >= 12 or (hits[0] >= hits[1] >= 4):
            accelerated_nums.extend(range(z*10 + 1, (z+1)*10 + 1))
            
    return {'accelerated': accelerated_nums}

def deep_momentum_score(history):
    """别名: plan21_momentum_score"""
    return _deep_momentum_score_impl(history)

plan21_momentum_score = deep_momentum_score

def _deep_momentum_score_impl(history):
    """
    方案 21: 横截面动能 (Momentum Score)
    计算号码的短期爆发力 vs 长期均值。
    """
    if len(history) < 50: return {}
    scores = {}
    for num in range(1, 81):
        f5 = sum(1 for h in history[:5] if num in h['numbers'])
        f20 = sum(1 for h in history[:20] if num in h['numbers'])
        f50 = sum(1 for h in history[:50] if num in h['numbers'])
        
        # 动能 = (短期频次 / 长期频次) * 衰减系数
        long_term_avg = max(f50 / 50.0, 0.05)
        momentum = (f5 / 5.0) / long_term_avg
        
        # 排除过热透支 (动能过高可能即将回落，除非是超强连号)
        if momentum > 3.0: momentum = 1.0 
        scores[num] = round(momentum, 2)
        
    return scores

def deep_omission_harmonics(history):
    """别名: plan22_omission_harmonics"""
    return _deep_omission_harmonics_impl(history)

plan22_omission_harmonics = deep_omission_harmonics

def _deep_omission_harmonics_impl(history):
    """
    方案 22: 遗漏谐波对冲 (Omission Harmonics)
    识别处于 7, 14, 21 等周期遗漏点的“谐波”号码。
    """
    last_appearance = {}
    for i, h in enumerate(history):
        for n in h['numbers']:
            if n not in last_appearance:
                last_appearance[n] = i
    
    harmonics = []
    for n, omission in last_appearance.items():
        if omission in [6, 7, 8, 13, 14, 15, 20, 21, 22]:
            harmonics.append(n)
            
    return harmonics


if __name__ == '__main__':
    # 模拟测试
    print("Deep Optimizer Implementation Ready.")
