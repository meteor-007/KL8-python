# -*- coding: utf-8 -*-
"""
深层关联分析模块 (Deep Association Analyzer)
============================================
对方案2的6维深层触发规则做历史回测验证 + 号码关联挖掘 + 精选输出。

核心能力：
1. 历史回测：对每条规则，逐期验证"规则触发时哪些号码真正命中"
2. 每号命中率：为每个号码在每条规则下计算历史命中率
3. 跨规则共识：识别同时被多条爆发规则推荐的号码
4. 共现关联：挖掘历史中奖号码中的搭档组合
5. 精选输出：从大块号码中精选 Top 5 爆发码 + Top 3 防守码

设计原则：
- 不修改原有评分逻辑（_compute_layer_a_scores 不受影响）
- 纯增量分析层，仅增强报告可读性
- 所有命中率基于历史数据回测，不做主观臆断
"""
import collections
from typing import Dict, List, Set, Tuple, Any
import itertools


# ====================================================================
#  常量
# ====================================================================
RULE_NAMES_HOT = ['rule_hot_rebound', 'rule_hot_b1_streak', 'rule_hot_b0_silent']
RULE_NAMES_COLD = ['rule_cold_overheat', 'rule_cold_b2_kill', 'rule_cold_dropped']
RULE_LABELS = {
    'rule_cold_overheat': '深度过热',
    'rule_cold_b2_kill': 'B2杀熟',
    'rule_cold_dropped': '热度退散',
    'rule_hot_rebound': '蓄力反弹',
    'rule_hot_b1_streak': 'B1连庄',
    'rule_hot_b0_silent': 'B0静默',
}
RULE_SCORES = {
    'rule_cold_overheat': -15,
    'rule_cold_b2_kill': -6,
    'rule_cold_dropped': -5,
    'rule_hot_rebound': +5,
    'rule_hot_b1_streak': +5,
    'rule_hot_b0_silent': +5,
}

# 回测窗口大小（最近N期）
BACKTEST_WINDOW = 100
# 每条规则精选输出数量
TOP_N_PER_RULE = 3
# 最终精选爆发码数量
FINAL_PICK_HOT = 5
# 最终精选防守码数量
FINAL_PICK_COLD = 3


# ====================================================================
#  核心函数
# ====================================================================

def _compute_rules_for_period(data1_by_issue, data2_by_issue, target_iss, prev_iss, prev_prev_iss):
    """
    为指定历史期号计算6条深层触发规则。
    与 plan2_hot_stealth_resonance 中的逻辑完全一致，但参数化目标期号。

    Returns:
        dict: {rule_name: set_of_numbers}
    """
    rules = {
        'rule_cold_overheat': set(),
        'rule_cold_b2_kill': set(),
        'rule_cold_dropped': set(),
        'rule_hot_rebound': set(),
        'rule_hot_b1_streak': set(),
        'rule_hot_b0_silent': set(),
    }

    if not prev_iss or prev_iss not in data1_by_issue or prev_iss not in data2_by_issue:
        return rules

    d1_prev_all = set()
    d1_prev_wins = set()
    d1_prev_pts = set()
    d2_prev_b0_all = set()
    d2_prev_b0_wins = set()
    d2_prev_b1_all = set()
    d2_prev_b1_wins = set()
    d2_prev_b2_all = set()
    d2_prev_b2_wins = set()

    for b_idx in range(4):
        for side in ('left', 'right'):
            if b_idx in data1_by_issue[prev_iss] and side in data1_by_issue[prev_iss][b_idx]:
                for item in data1_by_issue[prev_iss][b_idx][side]:
                    n, is_w, is_p = item[0], item[1], item[2]
                    d1_prev_all.add(n)
                    if is_w:
                        d1_prev_wins.add(n)
                    if is_p:
                        d1_prev_pts.add(n)

            if b_idx in data2_by_issue[prev_iss] and side in data2_by_issue[prev_iss][b_idx]:
                for item in data2_by_issue[prev_iss][b_idx][side]:
                    n, is_w, is_p = item[0], item[1], item[2]
                    if b_idx == 0:
                        d2_prev_b0_all.add(n)
                        if is_w:
                            d2_prev_b0_wins.add(n)
                    elif b_idx == 1:
                        d2_prev_b1_all.add(n)
                        if is_w:
                            d2_prev_b1_wins.add(n)
                    elif b_idx == 2:
                        d2_prev_b2_all.add(n)
                        if is_w:
                            d2_prev_b2_wins.add(n)

    rules['rule_cold_overheat'] = d1_prev_all & d1_prev_pts & d1_prev_wins
    rules['rule_hot_rebound'] = (d1_prev_all & d1_prev_pts) - d1_prev_wins
    rules['rule_cold_b2_kill'] = d2_prev_b2_all & d2_prev_b2_wins
    rules['rule_hot_b1_streak'] = d2_prev_b1_all & d2_prev_b1_wins
    rules['rule_hot_b0_silent'] = d2_prev_b0_all - d2_prev_b0_wins

    if prev_prev_iss and prev_prev_iss in data1_by_issue:
        d1_prev_prev_all = set()
        for b_idx in range(4):
            for side in ('left', 'right'):
                if b_idx in data1_by_issue[prev_prev_iss] and side in data1_by_issue[prev_prev_iss][b_idx]:
                    for item in data1_by_issue[prev_prev_iss][b_idx][side]:
                        d1_prev_prev_all.add(item[0])
        rules['rule_cold_dropped'] = (d1_prev_prev_all - d1_prev_all) - d1_prev_wins

    return rules


def _backtest_rules(data1_by_issue, data2_by_issue, history):
    """
    历史回测：对每条规则，逐期计算触发号码 & 下一期实际命中。

    Returns:
        dict: {
            rule_name: {
                'total_triggered': int,        # 该规则总共触发了多少次（期）
                'number_stats': {               # 每个号码的统计
                    num: {
                        'appearances': int,     # 该号码在该规则中出现次数
                        'hits': int,            # 该号码在规则触发后实际命中次数
                        'hit_rate': float,      # 命中率 = hits / appearances
                    }
                },
                'rule_avg_hit_rate': float,     # 该规则整体平均命中率
            }
        }
    """
    common = sorted(set(data1_by_issue) & set(data2_by_issue))
    if len(common) < 3:
        return {}

    hist_by_issue = {h['issue']: set(h['numbers']) for h in history}

    # 初始化结果结构
    backtest = {}
    for rule_name in RULE_LABELS:
        backtest[rule_name] = {
            'total_triggered': 0,
            'number_stats': collections.defaultdict(lambda: {'appearances': 0, 'hits': 0}),
            'rule_total_nums': 0,
            'rule_total_hits': 0,
        }

    # 遍历历史期号（从第3期开始，因为需要 prev_prev_iss）
    # common 按升序排列, common[i] 的 prev 是 common[i-1], prev_prev 是 common[i-2]
    for i in range(2, len(common)):
        target_iss = common[i]
        prev_iss = common[i - 1]
        prev_prev_iss = common[i - 2]

        # 时间连续性修复: data1/data2 可能存在缺期, "共同出现期"并不等于相邻期号。
        # 只有 target 与其前一共同期号相邻 (gap==1) 时才构建 prev 相邻关系,
        # 否则跳过该期 (不能用隔着缺期的期号冒充上一期)。
        try:
            gap_prev = int(target_iss) - int(prev_iss)
            gap_prev_prev = int(prev_iss) - int(prev_prev_iss)
        except (TypeError, ValueError):
            continue
        if gap_prev != 1:
            continue
        if gap_prev_prev != 1:
            # prev_prev 与 prev 不相邻: 不参与需要前前期的 rule_cold_dropped
            prev_prev_iss = None

        # 下一期开奖结果
        next_wins = hist_by_issue.get(target_iss, None)
        if next_wins is None:
            continue

        rules = _compute_rules_for_period(data1_by_issue, data2_by_issue, target_iss, prev_iss, prev_prev_iss)

        for rule_name, nums in rules.items():
            if not nums:
                continue
            backtest[rule_name]['total_triggered'] += 1
            backtest[rule_name]['rule_total_nums'] += len(nums)
            hits_this_period = len(nums & next_wins)
            backtest[rule_name]['rule_total_hits'] += hits_this_period

            for n in nums:
                backtest[rule_name]['number_stats'][n]['appearances'] += 1
                if n in next_wins:
                    backtest[rule_name]['number_stats'][n]['hits'] += 1

    # 计算命中率
    for rule_name in backtest:
        stats = backtest[rule_name]['number_stats']
        for n in stats:
            app = stats[n]['appearances']
            hits = stats[n]['hits']
            stats[n]['hit_rate'] = round(hits / app, 4) if app > 0 else 0.0

        total_nums = backtest[rule_name]['rule_total_nums']
        total_hits = backtest[rule_name]['rule_total_hits']
        backtest[rule_name]['rule_avg_hit_rate'] = round(total_hits / total_nums, 4) if total_nums > 0 else 0.0

    return backtest


def _compute_cooccurrence(history, top_n=30):
    """
    计算历史中奖号码的共现矩阵，找出最频繁的号码搭档。

    Returns:
        dict: {(a, b): co_count} 其中 a < b
    """
    pair_counts = collections.Counter()
    num_freq = collections.Counter()

    recent = history[:BACKTEST_WINDOW]
    for h in recent:
        nums = sorted(set(h['numbers']))
        for n in nums:
            num_freq[n] += 1
        for a, b in itertools.combinations(nums, 2):
            pair_counts[(a, b)] += 1

    return pair_counts, num_freq


def _find_partners(num, pair_counts, pool, top_k=3):
    """找出指定号码在推荐池中的最佳搭档。"""
    partners = []
    for other in pool:
        if other == num:
            continue
        a, b = (num, other) if num < other else (other, num)
        count = pair_counts.get((a, b), 0)
        if count > 0:
            partners.append((other, count))
    partners.sort(key=lambda x: -x[1])
    return partners[:top_k]


def _rank_numbers_in_rule(nums, backtest_stats, rule_name, descending=True):
    """
    根据历史命中率对规则内的号码排序。

    Args:
        descending: True=命中率高的排前（爆发规则），False=命中率低的排前（防守规则）

    Returns:
        list of (num, hit_rate, appearances, hits)
    """
    rule_stats = backtest_stats.get(rule_name, {})
    number_stats = rule_stats.get('number_stats', {})

    ranked = []
    for n in nums:
        ns = number_stats.get(n, {'appearances': 0, 'hits': 0, 'hit_rate': 0.0})
        ranked.append((n, ns['hit_rate'], ns['appearances'], ns['hits']))

    # 按命中率排序，然后按出现次数排序
    if descending:
        ranked.sort(key=lambda x: (-x[1], -x[2], x[0]))
    else:
        ranked.sort(key=lambda x: (x[1], -x[2], x[0]))
    return ranked


def analyze_deep_associations(data1_by_issue, data2_by_issue, d1_stars_map,
                               history, current_rules):
    """
    主分析函数：对方案2的6条规则做深层关联分析。

    Args:
        data1_by_issue: Data1 字典
        data2_by_issue: Data2 字典
        d1_stars_map: Data1 星号号码映射
        history: 历史开奖列表
        current_rules: plan2_hot_stealth_resonance 的返回值（当前期号的规则触发结果）

    Returns:
        dict: 结构化分析结果，包含：
            - backtest: 回测统计
            - rule_rankings: 每条规则内号码的排名
            - cross_rule_consensus: 跨规则共识号码
            - cooccurrence_partners: 推荐池内的搭档组合
            - final_picks: 最终精选推荐
            - final_kills: 最终精选防守
            - report_text: 格式化的报告文本
    """
    # 1. 历史回测
    backtest = _backtest_rules(data1_by_issue, data2_by_issue, history)

    # 2. 每条规则内号码排名
    rule_rankings = {}
    for rule_name in RULE_LABELS:
        nums = current_rules.get(rule_name, [])
        if nums:
            # 爆发规则按命中率降序（高的优先），防守规则按命中率升序（低的优先杀）
            descending = rule_name in RULE_NAMES_HOT
            ranked = _rank_numbers_in_rule(set(nums), backtest, rule_name, descending=descending)
            rule_rankings[rule_name] = ranked

    # 3. 跨规则共识分析
    hot_rule_nums = {}  # {num: [rule_names]}
    for rule_name in RULE_NAMES_HOT:
        for n in current_rules.get(rule_name, []):
            if n not in hot_rule_nums:
                hot_rule_nums[n] = []
            hot_rule_nums[n].append(rule_name)

    cold_rule_nums = {}
    for rule_name in RULE_NAMES_COLD:
        for n in current_rules.get(rule_name, []):
            if n not in cold_rule_nums:
                cold_rule_nums[n] = []
            cold_rule_nums[n].append(rule_name)

    # 跨规则共识：同时出现在2+条爆发规则中的号码
    cross_consensus_hot = {n: rules for n, rules in hot_rule_nums.items() if len(rules) >= 2}
    # 同时出现在2+条防守规则中的号码
    cross_consensus_cold = {n: rules for n, rules in cold_rule_nums.items() if len(rules) >= 2}
    # 冲突号码：同时出现在爆发和防守规则中
    conflict_nums = set(hot_rule_nums.keys()) & set(cold_rule_nums.keys())

    # 4. 共现关联分析
    pair_counts, num_freq = _compute_cooccurrence(history)

    # 5. 最终精选
    # 爆发码精选：综合命中率 × 规则数 × 共现强度
    hot_pool = set()
    for rule_name in RULE_NAMES_HOT:
        hot_pool.update(current_rules.get(rule_name, []))

    hot_candidates = []
    for n in hot_pool:
        # 基础分：跨规则共识加分
        rules_n = hot_rule_nums.get(n, [])
        consensus_bonus = len(rules_n) * 0.1

        # 命中率：取该号码在所有爆发规则中的最高命中率
        max_hit_rate = 0.0
        total_appearances = 0
        for rule_name in rules_n:
            ns = backtest.get(rule_name, {}).get('number_stats', {}).get(n, {})
            hr = ns.get('hit_rate', 0.0)
            max_hit_rate = max(max_hit_rate, hr)
            total_appearances += ns.get('appearances', 0)

        # 冲突惩罚
        conflict_penalty = -0.15 if n in conflict_nums else 0

        # 近期活跃度
        recent_freq = sum(1 for h in history[:20] if n in h['numbers']) / 20.0

        # 综合评分
        composite = max_hit_rate + consensus_bonus + conflict_penalty + recent_freq * 0.1

        hot_candidates.append({
            'num': n,
            'composite': round(composite, 4),
            'hit_rate': round(max_hit_rate, 4),
            'rules': rules_n,
            'appearances': total_appearances,
            'recent_freq': round(recent_freq, 4),
            'conflict': n in conflict_nums,
        })

    hot_candidates.sort(key=lambda x: -x['composite'])
    final_picks = hot_candidates[:FINAL_PICK_HOT]

    # 防守码精选
    cold_pool = set()
    for rule_name in RULE_NAMES_COLD:
        cold_pool.update(current_rules.get(rule_name, []))

    cold_candidates = []
    for n in cold_pool:
        rules_n = cold_rule_nums.get(n, [])
        consensus_bonus = len(rules_n) * 0.1

        # 防守规则命中率越低 = 越该杀
        max_hit_rate = 1.0
        total_appearances = 0
        for rule_name in rules_n:
            ns = backtest.get(rule_name, {}).get('number_stats', {}).get(n, {})
            hr = ns.get('hit_rate', 0.5)
            max_hit_rate = min(max_hit_rate, hr)
            total_appearances += ns.get('appearances', 0)

        recent_freq = sum(1 for h in history[:20] if n in h['numbers']) / 20.0

        # 防守评分：命中率越低分越高（越该杀）
        composite = (1.0 - max_hit_rate) + consensus_bonus - recent_freq * 0.1

        cold_candidates.append({
            'num': n,
            'composite': round(composite, 4),
            'hit_rate': round(max_hit_rate, 4),
            'rules': rules_n,
            'appearances': total_appearances,
            'recent_freq': round(recent_freq, 4),
        })

    cold_candidates.sort(key=lambda x: -x['composite'])
    final_kills = cold_candidates[:FINAL_PICK_COLD]

    # 6. 共现搭档分析（在精选爆发码之间）
    final_pick_nums = {p['num'] for p in final_picks}
    partners = []
    for n in final_pick_nums:
        p_list = _find_partners(n, pair_counts, final_pick_nums - {n}, top_k=2)
        for other, count in p_list:
            partners.append((n, other, count))
    partners.sort(key=lambda x: -x[2])

    # 7. 生成报告文本
    report_text = _generate_report_text(
        backtest, rule_rankings, cross_consensus_hot, cross_consensus_cold,
        conflict_nums, partners, final_picks, final_kills, current_rules
    )

    return {
        'backtest': backtest,
        'rule_rankings': rule_rankings,
        'cross_consensus_hot': cross_consensus_hot,
        'cross_consensus_cold': cross_consensus_cold,
        'conflict_nums': conflict_nums,
        'cooccurrence_partners': partners,
        'final_picks': final_picks,
        'final_kills': final_kills,
        'report_text': report_text,
    }


def _generate_report_text(backtest, rule_rankings, consensus_hot, consensus_cold,
                          conflict_nums, partners, final_picks, final_kills, current_rules):
    """生成格式化的 Markdown 报告文本。"""
    lines = []

    # ── 规则回测验证表 ──
    lines.append("#### 📊 规则回测验证（近100期历史命中率）")
    lines.append("")
    lines.append("| 规则 | 本期触发数 | 历史平均命中率 | 精选Top3 (命中率) |")
    lines.append("|------|----------|-------------|-----------------|")

    for rule_name in ['rule_hot_rebound', 'rule_hot_b1_streak', 'rule_hot_b0_silent',
                       'rule_cold_overheat', 'rule_cold_b2_kill', 'rule_cold_dropped']:
        label = RULE_LABELS[rule_name]
        current_nums = current_rules.get(rule_name, [])
        bt = backtest.get(rule_name, {})
        avg_rate = bt.get('rule_avg_hit_rate', 0.0)
        triggered = bt.get('total_triggered', 0)

        rankings = rule_rankings.get(rule_name, [])
        if rankings:
            parts = []
            for n, hr, app, hits in rankings[:TOP_N_PER_RULE]:
                if app == 0:
                    parts.append(f"{n}(无历史数据)")
                else:
                    parts.append(f"{n}({hr:.0%}×{app})")
            top3_str = " / ".join(parts)
        else:
            top3_str = "无历史数据"

        lines.append(f"| {label} | {len(current_nums)}码 | {avg_rate:.1%} ({triggered}期) | {top3_str} |")

    lines.append("")
    lines.append("> 命中率格式：号码(命中率×出现次数)，命中率=该号在此规则触发后实际开奖命中的比例")
    lines.append("")

    # ── 跨规则共识 ──
    if consensus_hot:
        lines.append("#### ⭐ 跨规则共识号码（多规则同时推荐）")
        lines.append("")
        for n, rules in sorted(consensus_hot.items(), key=lambda x: -len(x[1])):
            rule_labels = " + ".join(RULE_LABELS[r] for r in rules)
            # 找最高命中率
            max_hr = 0.0
            for r in rules:
                ns = backtest.get(r, {}).get('number_stats', {}).get(n, {})
                max_hr = max(max_hr, ns.get('hit_rate', 0.0))
            conflict_tag = " ⚠️同时被防守规则标记" if n in conflict_nums else ""
            lines.append(f"- 号码 `{n:02d}`: {rule_labels} → 历史最高命中率 {max_hr:.0%}{conflict_tag}")
        lines.append("")

    # ── 号码关联挖掘 ──
    if partners:
        lines.append("#### 🔗 号码关联挖掘（历史共现搭档）")
        lines.append("")
        shown = set()
        for a, b, count in partners[:5]:
            key = (min(a, b), max(a, b))
            if key in shown:
                continue
            shown.add(key)
            lines.append(f"- 黄金搭档: `{a:02d}-{b:02d}` (近{BACKTEST_WINDOW}期共现 {count}次)")
        lines.append("")

    # ── 最终精选推荐 ──
    lines.append("#### 🎯 最终精选爆发码（Top 5）")
    lines.append("")
    lines.append("| 排名 | 号码 | 综合评分 | 历史命中率 | 触发规则 | 近20期活跃 |")
    lines.append("|:----:|:----:|:-------:|:---------:|---------|:---------:|")
    for i, pick in enumerate(final_picks, 1):
        rule_str = " + ".join(RULE_LABELS[r] for r in pick['rules'])
        conflict_tag = " ⚠️" if pick['conflict'] else ""
        lines.append(
            f"| {i} | **{pick['num']:02d}**{conflict_tag} | {pick['composite']:.3f} | "
            f"{pick['hit_rate']:.0%} | {rule_str} | {pick['recent_freq']:.0%} |"
        )
    lines.append("")

    # ── 最终精选防守码 ──
    if final_kills:
        lines.append("#### ⛔ 重点防守号码（杀号 Top 3）")
        lines.append("")
        lines.append("| 排名 | 号码 | 防守评分 | 历史命中率 | 触发规则 | 说明 |")
        lines.append("|:----:|:----:|:-------:|:---------:|---------|------|")
        for i, kill in enumerate(final_kills, 1):
            rule_str = " + ".join(RULE_LABELS[r] for r in kill['rules'])
            lines.append(
                f"| {i} | **{kill['num']:02d}** | {kill['composite']:.3f} | "
                f"{kill['hit_rate']:.0%} | {rule_str} | 命中率低，建议回避 |"
            )
        lines.append("")

    # ── 规则原始数据（折叠显示）──
    lines.append("<details>")
    lines.append("<summary>📋 6维规则原始触发号码（点击展开）</summary>")
    lines.append("")
    for rule_name in ['rule_hot_rebound', 'rule_hot_b1_streak', 'rule_hot_b0_silent',
                       'rule_cold_overheat', 'rule_cold_b2_kill', 'rule_cold_dropped']:
        label = RULE_LABELS[rule_name]
        score = RULE_SCORES[rule_name]
        nums = current_rules.get(rule_name, [])
        tag = "爆发" if score > 0 else "防守"
        lines.append(f"- **[{tag}] {label}({score:+d})**：`{sorted(nums)}`")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    return "\n".join(lines)
