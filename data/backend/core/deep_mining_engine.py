# -*- coding: utf-8 -*-
"""
号码深层关联挖掘引擎
====================
完全从原始数据出发，抛开已有分析逻辑，一层一层挖掘号码之间的关联规律。

数据源：
  1. kl8_history_final.txt — 2004期开奖历史
  2. daily_points.txt — 220期点位数据
  3. 跟随+点位+开奖数据.xlsx — 跟随号码统计表（Data1星号 + Data2规律码）

挖掘层次：
  Layer 1: 共现关联 — 哪些号码总是一起中奖？
  Layer 2: 条件概率 — A出现时B出现的概率有多大？
  Layer 3: 遗漏回补 — 冷了多久会回补？回补窗口在哪？
  Layer 4: 点位共振 — 点位号码与开奖号码的交叉规律
  Layer 5: 稳定性评分 — 哪些号码长期稳定命中？
  Layer 6: 跟随星号验证 — Excel星号号码的命中率回测
  Final:   综合精选 — 多层信号叠加，输出5个最优稳定命中
"""
import sys
import os
import re
import collections
import itertools
import math

# ═══════════════════════════════════════════════════════════════
#  数据加载
# ═══════════════════════════════════════════════════════════════
_data_dir = os.path.dirname(os.path.abspath(__file__))
_proj_root = os.path.dirname(_data_dir)
sys.path.insert(0, _data_dir)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def load_history():
    """加载全部开奖历史 (按期号降序, 最新在前) — 委托 utils.history_loader, 消除重复实现"""
    from utils.history_loader import load_history as _load
    return _load()


def load_points():
    """加载点位数据"""
    points = {}
    path = os.path.join(_data_dir, 'daily_points.txt')
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            per_m = re.search(r'period:(\d+)', line)
            pts_m = re.search(r'points:([\d\s]+)', line)
            if pts_m and per_m:
                pts = {int(p) for p in pts_m.group(1).strip().split() if p}
                points[per_m.group(1)] = pts
    return points


def load_excel_stars():
    """从Excel跟随号码统计表读取Data1星号号码（热码标记）"""
    import openpyxl
    path = os.path.join(_data_dir, '跟随+点位+开奖数据.xlsx')
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb['跟随号码统计']
    grid = list(ws.iter_rows(values_only=True))
    wb.close()

    stars_by_issue = {}
    all_nums_by_issue = {}  # data1 全部号码
    data2_by_issue = {}

    BLOCK_OFFSETS = [1, 6, 11, 16]

    for r_idx in range(len(grid)):
        first_val = str(grid[r_idx][0] or "").strip()
        m = re.search(r'(\d{7})[^\d]+(\d)', first_val)
        if not m:
            continue
        issue, dtype = m.group(1), int(m.group(2))

        stars = set()
        all_nums = set()
        d2_nums = set()

        for b_idx, offset in enumerate(BLOCK_OFFSETS):
            for row_off in range(4):
                ri = r_idx + offset + row_off
                if ri >= len(grid):
                    continue
                row_vals = grid[ri]
                # Left (cols 0-3)
                for col_idx in range(0, 4):
                    if col_idx < len(row_vals):
                        val_str = str(row_vals[col_idx] or "").strip().replace('*', '')
                        if val_str.isdigit() and 1 <= int(val_str) <= 80:
                            num = int(val_str)
                            all_nums.add(num)
                            d2_nums.add(num)
                            if '*' in str(row_vals[col_idx] or ""):
                                stars.add(num)
                # Right (cols 5-8)
                for col_idx in range(5, 9):
                    if col_idx < len(row_vals):
                        val_str = str(row_vals[col_idx] or "").strip().replace('*', '')
                        if val_str.isdigit() and 1 <= int(val_str) <= 80:
                            num = int(val_str)
                            all_nums.add(num)
                            d2_nums.add(num)
                            if '*' in str(row_vals[col_idx] or ""):
                                stars.add(num)

        if dtype == 1:
            stars_by_issue[issue] = sorted(stars)
            all_nums_by_issue[issue] = sorted(all_nums)
        elif dtype == 2:
            data2_by_issue[issue] = sorted(d2_nums)

    return stars_by_issue, all_nums_by_issue, data2_by_issue


# ═══════════════════════════════════════════════════════════════
#  Layer 1: 共现关联分析
# ═══════════════════════════════════════════════════════════════
def analyze_cooccurrence(history, window=200):
    """
    挖掘1：哪些号码总是一起出现？

    方法：
    - 统计每对号码在同期中奖中的共现次数
    - 计算Lift值 = 实际共现 / 期望共现（期望=独立假设下的概率）
    - Lift > 1 表示正相关，Lift < 1 表示负相关
    """
    pair_counts = collections.Counter()
    num_freq = collections.Counter()
    total_periods = min(window, len(history))

    for h in history[:total_periods]:
        nums = set(h['numbers'])
        for n in nums:
            num_freq[n] += 1
        for a, b in itertools.combinations(sorted(nums), 2):
            pair_counts[(a, b)] += 1

    # 计算Lift
    total_nums = total_periods * 20  # 每期20个号码
    # 修复: 80选20无放回基线下, 两个指定号码同时出现的理论概率 = (20/80)*(19/79) ≈ 0.0601
    # 旧版用 p_a*p_b (放回假设 0.25^2=0.0625) 导致 Lift 系统性高估 ~4%
    expected_null = (20.0 / 80.0) * (19.0 / 79.0)
    lift_results = []
    for (a, b), count in pair_counts.items():
        p_a = num_freq[a] / total_periods
        p_b = num_freq[b] / total_periods
        p_ab = count / total_periods
        expected = expected_null
        lift = p_ab / expected if expected > 0 else 0
        lift_results.append({
            'pair': (a, b),
            'count': count,
            'lift': round(lift, 3),
            'p_a': round(p_a, 3),
            'p_b': round(p_b, 3),
            'p_ab': round(p_ab, 3),
        })

    lift_results.sort(key=lambda x: -x['lift'])
    return lift_results, num_freq, total_periods


# ═══════════════════════════════════════════════════════════════
#  Layer 2: 条件概率分析
# ═══════════════════════════════════════════════════════════════
def analyze_conditional_probability(history, window=200):
    """
    挖掘2：当号码A出现时，号码B也出现的概率。

    方法：
    - P(B|A) = P(A∩B) / P(A)
    - 筛选 P(B|A) 显著高于 P(B) 的组合（信息增益）
    """
    total = min(window, len(history))
    pair_counts = collections.Counter()
    num_freq = collections.Counter()

    for h in history[:total]:
        nums = set(h['numbers'])
        for n in nums:
            num_freq[n] += 1
        for a, b in itertools.combinations(sorted(nums), 2):
            pair_counts[(a, b)] += 1

    # 对每个号码找最佳触发器
    best_triggers = {}  # {num: [(trigger_num, p_b_given_a, p_b, lift)]}
    for target in range(1, 81):
        p_b = num_freq[target] / total
        if p_b == 0:
            continue
        triggers = []
        for trigger in range(1, 81):
            if trigger == target:
                continue
            a, b = (trigger, target) if trigger < target else (target, trigger)
            co_count = pair_counts.get((a, b), 0)
            if co_count < 3:  # 至少共现3次才有统计意义
                continue
            p_a = num_freq[trigger] / total
            p_ab = co_count / total
            p_b_given_a = p_ab / p_a if p_a > 0 else 0
            lift = p_b_given_a / p_b if p_b > 0 else 0
            if lift > 1.2 and p_b_given_a > p_b:
                triggers.append({
                    'trigger': trigger,
                    'p_b_given_a': round(p_b_given_a, 3),
                    'p_b': round(p_b, 3),
                    'lift': round(lift, 3),
                    'co_count': co_count,
                })
        triggers.sort(key=lambda x: -x['lift'])
        if triggers:
            best_triggers[target] = triggers[:3]

    return best_triggers


# ═══════════════════════════════════════════════════════════════
#  Layer 3: 遗漏回补周期
# ═══════════════════════════════════════════════════════════════
def analyze_omission_cycle(history, window=500):
    """
    挖掘3：每个号码的遗漏-回补周期。

    方法：
    - 追踪每个号码的历史遗漏序列
    - 计算平均遗漏周期和最大遗漏周期
    - 判断当前遗漏状态：是否在回补窗口内
    """
    total = min(window, len(history))
    # 反向遍历（从最老到最新）
    hist = list(reversed(history[:total]))

    results = {}
    for num in range(1, 81):
        gaps = []  # 每次遗漏的期数
        current_gap = 0
        hit_count = 0
        for h in hist:
            if num in h['numbers']:
                if current_gap > 0:
                    gaps.append(current_gap)
                current_gap = 0
                hit_count += 1
            else:
                current_gap += 1

        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        max_gap = max(gaps) if gaps else 0

        # 当前遗漏（从最新一期开始算）
        current_omission = 0
        for h in history:  # history已降序，最新在前
            if num in h['numbers']:
                break
            current_omission += 1

        # 回补信号：当前遗漏接近或超过平均遗漏周期
        if avg_gap > 0:
            ratio = current_omission / avg_gap
        else:
            ratio = 0

        results[num] = {
            'avg_gap': round(avg_gap, 1),
            'max_gap': max_gap,
            'current_omission': current_omission,
            'ratio': round(ratio, 2),
            'hit_count': hit_count,
            'hit_rate': round(hit_count / total, 3) if total > 0 else 0,
            'gaps': gaps[-20:] if len(gaps) > 20 else gaps,  # 最近的遗漏序列
        }

    return results


# ═══════════════════════════════════════════════════════════════
#  Layer 4: 点位共振
# ═══════════════════════════════════════════════════════════════
def analyze_point_resonance(history, points):
    """
    挖掘4：点位号码与开奖号码的交叉规律。

    方法：
    - 点位命中率：每个点位号码在同期开奖中命中的比例
    - 点位→号码触发：某点位出现时，哪些号码更容易在同期开奖中出现
    """
    # 点位命中率
    point_hit_rate = collections.Counter()
    point_total = collections.Counter()

    for h in history:
        issue = h['issue']
        if issue not in points:
            continue
        wins = set(h['numbers'])
        pts = points[issue]
        for p in pts:
            point_total[p] += 1
            if p in wins:
                point_hit_rate[p] += 1

    # 点位→号码触发表：当点位P出现时，号码N的命中率
    point_to_num = collections.defaultdict(lambda: collections.Counter())
    point_to_num_total = collections.Counter()

    for h in history:
        issue = h['issue']
        if issue not in points:
            continue
        wins = set(h['numbers'])
        pts = points[issue]
        for p in pts:
            point_to_num_total[p] += 1
            for n in wins:
                point_to_num[p][n] += 1

    # 每个点位的Top触发号码
    point_triggers = {}
    for p in range(1, 81):
        total = point_to_num_total.get(p, 0)
        if total < 5:
            continue
        base_rate = 20 / 80  # 0.25
        triggers = []
        for n, count in point_to_num[p].most_common(10):
            rate = count / total
            lift = rate / base_rate
            if lift > 1.1 and count >= 3:
                triggers.append({
                    'num': n,
                    'rate': round(rate, 3),
                    'lift': round(lift, 3),
                    'count': count,
                })
        if triggers:
            point_triggers[p] = triggers[:5]

    # 当前期点位
    latest_issue = history[0]['issue']
    target_issue = str(int(latest_issue) + 1)
    current_points = points.get(target_issue, set())

    return point_hit_rate, point_total, point_triggers, current_points


# ═══════════════════════════════════════════════════════════════
#  Layer 5: 稳定性评分
# ═══════════════════════════════════════════════════════════════
def analyze_stability(history, window=100):
    """
    挖掘5：哪些号码长期稳定命中？

    方法：
    - 将window期分为5段
    - 每段计算每个号码的命中率
    - 稳定性 = 各段命中率的标准差（越小越稳定）
    - 综合评分 = 平均命中率 / (1 + 标准差)
    """
    total = min(window, len(history))
    segment_size = total // 5
    if segment_size < 10:
        return {}

    segments = []
    for i in range(5):
        start = i * segment_size
        end = start + segment_size if i < 4 else total
        segments.append(history[start:end])

    results = {}
    for num in range(1, 81):
        rates = []
        for seg in segments:
            hits = sum(1 for h in seg if num in h['numbers'])
            rates.append(hits / len(seg))

        avg_rate = sum(rates) / len(rates)
        variance = sum((r - avg_rate) ** 2 for r in rates) / len(rates)
        std = math.sqrt(variance)

        # 稳定得分：平均命中率越高、标准差越小 → 得分越高
        stability_score = avg_rate / (1 + std * 5) if avg_rate > 0 else 0

        results[num] = {
            'avg_rate': round(avg_rate, 3),
            'std': round(std, 3),
            'stability_score': round(stability_score, 3),
            'segment_rates': [round(r, 3) for r in rates],
            'recent_5': sum(1 for h in history[:5] if num in h['numbers']),
            'recent_10': sum(1 for h in history[:10] if num in h['numbers']),
        }

    return results


# ═══════════════════════════════════════════════════════════════
#  Layer 6: 跟随星号验证
# ═══════════════════════════════════════════════════════════════
def analyze_star_validation(history, stars_by_issue):
    """
    挖掘6：Excel跟随号码统计表中星号号码（热码标记）的历史命中率。

    方法：
    - 逐期验证星号号码在当期开奖中的命中率
    - 统计每个号码作为星号时的命中表现
    """
    hist_by_issue = {h['issue']: set(h['numbers']) for h in history}

    star_stats = collections.defaultdict(lambda: {'as_star': 0, 'hit': 0})
    total_periods = 0
    total_stars = 0
    total_hits = 0

    for issue, stars in stars_by_issue.items():
        wins = hist_by_issue.get(issue)
        if wins is None:
            continue
        total_periods += 1
        for s in stars:
            star_stats[s]['as_star'] += 1
            total_stars += 1
            if s in wins:
                star_stats[s]['hit'] += 1
                total_hits += 1

    overall_rate = total_hits / total_stars if total_stars > 0 else 0

    # 每个号码作为星号的命中率
    star_ranked = []
    for num, stats in star_stats.items():
        if stats['as_star'] >= 3:
            rate = stats['hit'] / stats['as_star']
            star_ranked.append({
                'num': num,
                'as_star': stats['as_star'],
                'hit': stats['hit'],
                'rate': round(rate, 3),
                'lift': round(rate / 0.25, 3) if 0.25 > 0 else 0,
            })

    star_ranked.sort(key=lambda x: -x['rate'])

    return star_ranked, overall_rate, total_periods, total_stars, total_hits


# ═══════════════════════════════════════════════════════════════
#  Final: 综合精选
# ═══════════════════════════════════════════════════════════════
def final_synthesis(history, cooccur_lifts, cond_probs, omission_data,
                    point_triggers, current_points, stability_data,
                    star_ranked, stars_by_issue):
    """
    多层信号叠加，精选5个最优稳定命中号码。

    评分维度：
    1. 稳定性得分（Layer 5）— 核心权重 40%
    2. 遗漏回补信号（Layer 3）— 当前遗漏接近平均周期 +20%
    3. 点位共振（Layer 4）— 当前期点位触发 +15%
    4. 星号历史命中（Layer 6）— 作为星号时命中率高 +15%
    5. 共现网络中心度（Layer 1）— 与其他号码有强共现 +10%
    """
    latest_issue = history[0]['issue']
    target_issue = str(int(latest_issue) + 1)

    # 获取当前期星号
    current_stars = set(stars_by_issue.get(target_issue, []))

    # 构建共现网络中心度
    cooccur_center = collections.Counter()
    for item in cooccur_lifts[:100]:  # Top100共现对
        a, b = item['pair']
        if item['lift'] > 1.1:
            cooccur_center[a] += item['lift']
            cooccur_center[b] += item['lift']

    # 归一化共现中心度
    max_center = max(cooccur_center.values()) if cooccur_center else 1
    cooccur_normalized = {n: v / max_center for n, v in cooccur_center.items()}

    # 星号命中率映射
    star_rate_map = {s['num']: s['rate'] for s in star_ranked}

    # 点位触发号码集合
    point_triggered_nums = set()
    for p in current_points:
        if p in point_triggers:
            for t in point_triggers[p]:
                point_triggered_nums.add(t['num'])

    # 综合评分
    candidates = []
    for num in range(1, 81):
        # 1. 稳定性
        stab = stability_data.get(num, {})
        stab_score = stab.get('stability_score', 0)

        # 2. 遗漏回补
        om = omission_data.get(num, {})
        ratio = om.get('ratio', 0)
        # 比率在0.8-2.0之间是最佳回补窗口
        if 0.8 <= ratio <= 2.0:
            om_score = 0.15
        elif ratio > 2.0:
            om_score = 0.10  # 超长遗漏有爆发可能
        elif 0.3 <= ratio < 0.8:
            om_score = 0.05  # 刚回补，不太需要
        else:
            om_score = 0.02

        # 3. 点位共振
        pt_score = 0.10 if num in point_triggered_nums else 0

        # 4. 星号历史
        star_rate = star_rate_map.get(num, 0.25)
        if num in current_stars:
            star_score = (star_rate - 0.25) * 0.6  # 超过基线的部分加权
        else:
            star_score = (star_rate - 0.25) * 0.3  # 非当前星号但历史好

        # 5. 共现中心度
        cooccur_score = cooccur_normalized.get(num, 0) * 0.10

        # 总分
        total = stab_score * 0.40 + om_score + pt_score + max(0, star_score) + cooccur_score

        candidates.append({
            'num': num,
            'total': round(total, 4),
            'stab_score': round(stab_score, 4),
            'stab_rate': stab.get('avg_rate', 0),
            'stab_std': stab.get('std', 0),
            'omission': om.get('current_omission', 0),
            'avg_gap': om.get('avg_gap', 0),
            'om_ratio': ratio,
            'point_triggered': num in point_triggered_nums,
            'is_current_star': num in current_stars,
            'star_hist_rate': round(star_rate, 3),
            'cooccur_center': round(cooccur_normalized.get(num, 0), 3),
            'recent_5': stab.get('recent_5', 0),
            'recent_10': stab.get('recent_10', 0),
        })

    candidates.sort(key=lambda x: -x['total'])
    return candidates


# ═══════════════════════════════════════════════════════════════
#  报告生成
# ═══════════════════════════════════════════════════════════════
def generate_report(history, points, stars_by_issue,
                    cooccur_lifts, cond_probs, omission_data,
                    point_hit_rate, point_total, point_triggers, current_points,
                    stability_data, star_ranked, overall_star_rate,
                    star_total_periods, star_total_stars, star_total_hits,
                    final_picks):
    """生成完整的深层关联挖掘报告"""
    lines = []
    latest_issue = history[0]['issue']
    target_issue = str(int(latest_issue) + 1)

    lines.append("# 号码深层关联挖掘报告")
    lines.append(f"**分析期号：** {target_issue}")
    lines.append(f"**数据基础：** {len(history)}期开奖历史 + {len(points)}期点位 + Excel跟随统计")
    lines.append("")

    # ═══════════════════════════════════════════════════
    lines.append("## 一、共现关联挖掘")
    lines.append("")
    lines.append(f"**分析窗口：** 近200期")
    lines.append(f"**发现：** 共 {len(cooccur_lifts)} 个号码对有共现记录")
    lines.append("")

    # Top 15 强共现对
    strong_pairs = [p for p in cooccur_lifts if p['lift'] > 1.2 and p['count'] >= 5][:15]
    if strong_pairs:
        lines.append("### Top 15 强共现搭档（Lift > 1.2）")
        lines.append("")
        lines.append("| 号码A | 号码B | 共现次数 | Lift值 | 含义 |")
        lines.append("|:-----:|:-----:|:-------:|:------:|------|")
        for p in strong_pairs:
            a, b = p['pair']
            meaning = f"当{a:02d}出现时，{b:02d}出现概率提升{((p['lift']-1)*100):.0f}%"
            lines.append(f"| {a:02d} | {b:02d} | {p['count']}次 | {p['lift']:.2f}x | {meaning} |")
        lines.append("")

    # ═══════════════════════════════════════════════════
    lines.append("## 二、条件概率挖掘")
    lines.append("")
    lines.append("**方法：** 当号码A出现时，号码B也出现的概率，找出信息增益最大的触发关系。")
    lines.append("")

    # 找出最强触发链
    top_triggers = []
    for target, triggers in cond_probs.items():
        if triggers:
            best = triggers[0]
            top_triggers.append({
                'target': target,
                'trigger': best['trigger'],
                'p_b_given_a': best['p_b_given_a'],
                'p_b': best['p_b'],
                'lift': best['lift'],
                'co_count': best['co_count'],
            })
    top_triggers.sort(key=lambda x: -x['lift'])

    if top_triggers:
        lines.append("### Top 15 触发关系（Lift > 1.3）")
        lines.append("")
        lines.append("| 触发号 | → 目标号 | P(目标|触发) | P(目标) | Lift | 含义 |")
        lines.append("|:------:|:-------:|:-----------:|:-------:|:----:|------|")
        for t in top_triggers[:15]:
            meaning = f"若{t['trigger']:02d}出，则{t['target']:02d}出概率从{t['p_b']:.0%}→{t['p_b_given_a']:.0%}"
            lines.append(f"| {t['trigger']:02d} | → {t['target']:02d} | {t['p_b_given_a']:.0%} | {t['p_b']:.0%} | {t['lift']:.2f}x | {meaning} |")
        lines.append("")

    # ═══════════════════════════════════════════════════
    lines.append("## 三、遗漏回补周期")
    lines.append("")
    lines.append("**方法：** 追踪每个号码的历史遗漏序列，计算平均遗漏周期和当前遗漏状态。")
    lines.append("")

    # 找出当前在回补窗口内的号码
    in_window = []
    over_due = []
    for num in range(1, 81):
        om = omission_data[num]
        if om['avg_gap'] > 0 and om['ratio'] >= 0.8:
            in_window.append((num, om))
        if om['avg_gap'] > 0 and om['ratio'] >= 1.5:
            over_due.append((num, om))

    in_window.sort(key=lambda x: -x[1]['ratio'])

    if in_window:
        lines.append("### 当前处于回补窗口的号码（遗漏比 ≥ 0.8）")
        lines.append("")
        lines.append("| 号码 | 当前遗漏 | 平均周期 | 比率 | 历史命中率 | 近10期 | 状态 |")
        lines.append("|:----:|:-------:|:-------:|:----:|:---------:|:------:|------|")
        for num, om in in_window[:20]:
            if om['ratio'] >= 2.0:
                status = "🔴超期待补"
            elif om['ratio'] >= 1.5:
                status = "🟠即将回补"
            elif om['ratio'] >= 1.0:
                status = "🟡进入窗口"
            else:
                status = "🟢关注"
            lines.append(f"| {num:02d} | {om['current_omission']}期 | {om['avg_gap']:.0f}期 | {om['ratio']:.1f}x | {om['hit_rate']:.0%} | {om.get('hit_count',0)}次 | {status} |")
        lines.append("")

    # ═══════════════════════════════════════════════════
    lines.append("## 四、点位共振分析")
    lines.append("")
    lines.append(f"**当前期点位（{target_issue}）：** {sorted(current_points)}")
    lines.append("")

    # 当前点位号码的历史命中率
    lines.append("### 当期点位号码历史命中率")
    lines.append("")
    lines.append("| 点位号 | 作为点位出现次数 | 同期命中次数 | 命中率 | Lift |")
    lines.append("|:------:|:--------------:|:-----------:|:------:|:----:|")
    for p in sorted(current_points):
        total = point_total.get(p, 0)
        hits = point_hit_rate.get(p, 0)
        rate = hits / total if total > 0 else 0
        lift = rate / 0.25 if 0.25 > 0 else 0
        tag = "✅" if lift > 1.1 else "⚠️" if lift < 0.9 else ""
        lines.append(f"| {p:02d} | {total}次 | {hits}次 | {rate:.0%} | {lift:.2f}x {tag} |")
    lines.append("")

    # 点位触发的号码
    triggered = set()
    for p in current_points:
        if p in point_triggers:
            for t in point_triggers[p]:
                triggered.add((t['num'], t['lift'], t['count']))

    if triggered:
        triggered = sorted(triggered, key=lambda x: -x[1])
        lines.append("### 点位触发号码（当点位出现时，这些号码更容易中奖）")
        lines.append("")
        lines.append("| 号码 | 触发Lift | 共现次数 | 来源点位 |")
        lines.append("|:----:|:--------:|:-------:|:---------|")
        # 需要重建来源
        num_sources = collections.defaultdict(list)
        for p in current_points:
            if p in point_triggers:
                for t in point_triggers[p]:
                    num_sources[t['num']].append(p)
        for num, lift, count in triggered[:10]:
            src = ", ".join(f"{p:02d}" for p in num_sources[num])
            lines.append(f"| {num:02d} | {lift:.2f}x | {count}次 | {src} |")
        lines.append("")

    # ═══════════════════════════════════════════════════
    lines.append("## 五、稳定性评分")
    lines.append("")
    lines.append("**方法：** 将近100期分5段，计算每段命中率的均值和标准差。稳定性评分 = 均值/(1+标准差×5)。")
    lines.append("")

    stable_nums = [(num, data) for num, data in stability_data.items()]
    stable_nums.sort(key=lambda x: -x[1]['stability_score'])

    lines.append("### Top 15 最稳定号码")
    lines.append("")
    lines.append("| 号码 | 稳定性评分 | 平均命中率 | 标准差 | 5段命中率 | 近5期 | 近10期 |")
    lines.append("|:----:|:---------:|:---------:|:------:|---------|:------:|:------:|")
    for num, data in stable_nums[:15]:
        seg_str = " / ".join(f"{r:.0%}" for r in data['segment_rates'])
        lines.append(f"| {num:02d} | {data['stability_score']:.3f} | {data['avg_rate']:.0%} | {data['std']:.3f} | {seg_str} | {data['recent_5']} | {data['recent_10']} |")
    lines.append("")

    # ═══════════════════════════════════════════════════
    lines.append("## 六、跟随星号验证")
    lines.append("")
    lines.append(f"**验证窗口：** {star_total_periods}期")
    lines.append(f"**整体表现：** 星号号码共{star_total_stars}个，命中{star_total_hits}个，命中率{overall_star_rate:.1%}（基线25%）")
    lines.append("")

    good_stars = [s for s in star_ranked if s['lift'] > 1.1 and s['as_star'] >= 5][:10]
    if good_stars:
        lines.append("### 历史表现优秀的星号号码（Lift > 1.1）")
        lines.append("")
        lines.append("| 号码 | 作为星号次数 | 命中次数 | 命中率 | Lift |")
        lines.append("|:----:|:-----------:|:-------:|:------:|:----:|")
        for s in good_stars:
            lines.append(f"| {s['num']:02d} | {s['as_star']}次 | {s['hit']}次 | {s['rate']:.0%} | {s['lift']:.2f}x |")
        lines.append("")

    # ═══════════════════════════════════════════════════
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 最终精选：5个最优稳定命中")
    lines.append("")
    lines.append("**综合评分公式：**")
    lines.append("- 稳定性得分 × 40%")
    lines.append("- 遗漏回补信号 +15%")
    lines.append("- 点位共振 +10%")
    lines.append("- 星号历史命中 +15%")
    lines.append("- 共现网络中心度 +10%")
    lines.append("")

    lines.append("| 排名 | 号码 | 综合评分 | 稳定性 | 当前遗漏 | 回补窗口 | 点位触发 | 当前星号 | 星号历史 | 近5/10期 |")
    lines.append("|:----:|:----:|:-------:|:------:|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|")
    for i, pick in enumerate(final_picks[:5], 1):
        om_tag = "✅" if 0.8 <= pick['om_ratio'] <= 2.0 else "—"
        pt_tag = "✅" if pick['point_triggered'] else "—"
        star_tag = "✅" if pick['is_current_star'] else "—"
        lines.append(
            f"| {i} | **{pick['num']:02d}** | {pick['total']:.3f} | "
            f"{pick['stab_rate']:.0%}(σ{pick['stab_std']:.2f}) | "
            f"{pick['omission']}期/{pick['avg_gap']:.0f} | {om_tag} | "
            f"{pt_tag} | {star_tag} | {pick['star_hist_rate']:.0%} | "
            f"{pick['recent_5']}/{pick['recent_10']} |"
        )
    lines.append("")

    # 防守号码
    lines.append("### ⛔ 重点回避号码（综合评分最低）")
    lines.append("")
    lines.append("| 号码 | 综合评分 | 稳定性 | 当前遗漏 | 说明 |")
    lines.append("|:----:|:-------:|:------:|:-------:|------|")
    for pick in final_picks[-5:]:
        lines.append(
            f"| {pick['num']:02d} | {pick['total']:.3f} | "
            f"{pick['stab_rate']:.0%}(σ{pick['stab_std']:.2f}) | "
            f"{pick['omission']}期 | 稳定性低/长期不命中 |"
        )
    lines.append("")

    lines.append("---")
    lines.append("*报告由深层关联挖掘引擎生成 — 从2004期原始数据逐层挖掘*")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════════
def run():
    print("=" * 70)
    print("号码深层关联挖掘引擎 — 从原始数据出发")
    print("=" * 70)

    # 加载数据
    print("\n[1/8] 加载开奖历史...")
    history = load_history()
    print(f"  → {len(history)}期，最新{history[0]['issue']}期")

    print("[2/8] 加载点位数据...")
    points = load_points()
    print(f"  → {len(points)}期点位")

    print("[3/8] 加载Excel跟随号码统计...")
    stars_by_issue, all_nums_by_issue, data2_by_issue = load_excel_stars()
    print(f"  → Data1星号{len(stars_by_issue)}期, Data2规律码{len(data2_by_issue)}期")

    # 逐层挖掘
    print("\n[4/8] Layer 1: 共现关联挖掘...")
    cooccur_lifts, num_freq, cooccur_periods = analyze_cooccurrence(history)
    strong = [p for p in cooccur_lifts if p['lift'] > 1.2 and p['count'] >= 5]
    print(f"  → 发现{len(strong)}个强共现对（Lift>1.2）")

    print("[5/8] Layer 2: 条件概率挖掘...")
    cond_probs = analyze_conditional_probability(history)
    strong_triggers = sum(1 for v in cond_probs.values() if v and v[0]['lift'] > 1.3)
    print(f"  → 发现{strong_triggers}个强触发关系（Lift>1.3）")

    print("[6/8] Layer 3: 遗漏回补周期...")
    omission_data = analyze_omission_cycle(history)
    in_window = sum(1 for om in omission_data.values() if 0.8 <= om['ratio'] <= 2.0 and om['avg_gap'] > 0)
    print(f"  → {in_window}个号码处于回补窗口")

    print("[7/8] Layer 4-6: 点位共振 + 稳定性 + 星号验证...")
    pt_hit, pt_total, pt_triggers, current_pts = analyze_point_resonance(history, points)
    stability_data = analyze_stability(history)
    star_ranked, overall_star_rate, sp, ss, sh = analyze_star_validation(history, stars_by_issue)
    print(f"  → 点位触发{len(pt_triggers)}个号码, 星号整体命中率{overall_star_rate:.1%}")

    print("[8/8] Final: 综合精选...")
    final_picks = final_synthesis(
        history, cooccur_lifts, cond_probs, omission_data,
        pt_triggers, current_pts, stability_data,
        star_ranked, stars_by_issue
    )
    print(f"  → Top 5: {[p['num'] for p in final_picks[:5]]}")

    # 生成报告
    print("\n" + "=" * 70)
    print("生成报告...")
    print("=" * 70)

    report = generate_report(
        history, points, stars_by_issue,
        cooccur_lifts, cond_probs, omission_data,
        pt_hit, pt_total, pt_triggers, current_pts,
        stability_data, star_ranked, overall_star_rate,
        sp, ss, sh, final_picks
    )

    # 输出到文件
    output_path = os.path.join(_data_dir, 'reports', 'deep_association_mining_report.md')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n报告已保存: {output_path}")
    print("\n" + "=" * 70)
    print("报告预览")
    print("=" * 70)
    print(report)

    return report


if __name__ == '__main__':
    run()
