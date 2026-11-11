# -*- coding: utf-8 -*-
"""
数据源1×数据源2 深层关联与预测引擎 (DataSource Deep Predictor v1.0)
=============================================================================
⚠️ 2026-09-10 全历史审计修正（153 有效期，见 outputs/ds2_deep_analysis/数据源2深度分析报告.md）：
本文件此前声称的命中率（B1连庄 43%/Lift1.72 等）系小样本口径，经全历史检验 +
BH-FDR 多重校正后【无一显著】。以下仅保留实测值（基线：单码命中率 25%，回避率 75%）。

核心做多阵列（实测，全部不显著）:
1. 蓄力反弹 (D1 点位被压制未开 -> 反弹)  实测 26.26%, Lift=1.050, p=0.429
2. B1连庄   (D2 Block 1 连庄)          实测 23.85%, Lift=0.954, p=0.386
3. B0静默   (D2 Block 0 静默反弹)       实测 25.97%, Lift=1.039, p=0.154
4. 跨规则共识码 (多规则共振)             实测 26.49%, Lift=1.059, p=0.502

核心做空阵列（实测，全部不显著）:
1. D2 外部号码 (80 - D2, 12~17 码)      实测回避 75.32%, Lift=0.987, p=0.707
2. B2 杀熟号码 (D2 Block 2)            实测回避 75.99%, Lift=0.960, p=0.471
3. 深度过热号码 (D1 点位连开过热)       实测回避 78.16%, Lift=0.874, p=0.247

黄金连体婴搭档 (选2组合):
- 历史 100 期共现 8~10 次以上的深层规则搭档对。
  注意：共现信号在全量挖掘中无显著预测力（Lift≈1.008，见全量数据挖掘报告）。

结论：本引擎输出仅作结构参考。做多侧 30 期榜实测 0.96x（低于随机），
杀号侧约 1.05x 方向正确但未达显著，均不构成超越随机基线的证据。
"""
import os
import sys
import json
import collections
import itertools
import math
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any, Optional

# backend/modules/datasource/ -> backend/
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT_DIR = os.path.dirname(_BASE_DIR)
for _p in [_BASE_DIR, _ROOT_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.paths import get_project_root, data_path
from utils.history_loader import load_history
from core.excel_deep_mining_v2 import load_excel_full

RULE_LABELS = {
    'rule_hot_rebound': '蓄力反弹',
    'rule_hot_b1_streak': 'B1连庄',
    'rule_hot_b0_silent': 'B0静默',
    'rule_cold_overheat': '深度过热',
    'rule_cold_b2_kill': 'B2杀熟',
    'rule_cold_dropped': '热度退散',
}


def load_structured_datasources():
    """加载并结构化数据源1与数据源2"""
    records = load_excel_full()
    data1_by_issue = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    data2_by_issue = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    d2_full_nums_by_issue = collections.defaultdict(set)

    for r in records:
        target_dict = data1_by_issue if r['dtype'] == 1 else data2_by_issue
        target_dict[r['issue']][r['block']][r['side']].append((r['num'], r['is_win'], r['is_point'], r['is_star']))
        if r['dtype'] == 2:
            d2_full_nums_by_issue[r['issue']].add(r['num'])

    return data1_by_issue, data2_by_issue, d2_full_nums_by_issue


def compute_rules_for_target(data1_by_issue, data2_by_issue, prev_iss, prev_prev_iss):
    """根据上期与前前期数据，推演当前目标期的6大规则触发号码"""
    rules = {
        'rule_hot_rebound': set(),
        'rule_hot_b1_streak': set(),
        'rule_hot_b0_silent': set(),
        'rule_cold_overheat': set(),
        'rule_cold_b2_kill': set(),
        'rule_cold_dropped': set(),
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
                    if is_w: d1_prev_wins.add(n)
                    if is_p: d1_prev_pts.add(n)

            if b_idx in data2_by_issue[prev_iss] and side in data2_by_issue[prev_iss][b_idx]:
                for item in data2_by_issue[prev_iss][b_idx][side]:
                    n, is_w, is_p = item[0], item[1], item[2]
                    if b_idx == 0:
                        d2_prev_b0_all.add(n)
                        if is_w: d2_prev_b0_wins.add(n)
                    elif b_idx == 1:
                        d2_prev_b1_all.add(n)
                        if is_w: d2_prev_b1_wins.add(n)
                    elif b_idx == 2:
                        d2_prev_b2_all.add(n)
                        if is_w: d2_prev_b2_wins.add(n)

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


def predict_datasource_deep(target_period: Optional[int] = None) -> Dict[str, Any]:
    """
    执行数据源1与数据源2的高置信深度预测推演
    """
    history = load_history()
    if not history:
        return {}

    data1_by_issue, data2_by_issue, d2_full_nums = load_structured_datasources()
    common_issues = sorted(list(set(data1_by_issue.keys()) & set(data2_by_issue.keys())), key=lambda x: int(x))

    if not common_issues:
        return {}

    latest_excel_iss = common_issues[-1]
    prev_excel_iss = common_issues[-2] if len(common_issues) >= 2 else None

    if target_period is None:
        target_period = int(history[0]['issue']) + 1

    # 2026-11-10 修复：Excel 里已经含有"目标期"那一行（今天要预测的期），它还没有开奖结果
    # （is_win 全 0）。原实现直接拿它当 prev_iss，导致依赖上期开奖的三条规则
    # （b1_streak / cold_overheat / cold_b2_kill）恒空、rebound 退化成 data1∩点位，
    # 且这个退化结果还被当成真实推荐写进前瞻账。此处与 Walk-Forward 对齐：
    # 规则锚点必须是目标期的「前一已开奖期」，绝不能用目标期自己。
    _target_key = str(int(target_period))
    if _target_key in common_issues:
        _ti = common_issues.index(_target_key)
        rule_prev_iss = common_issues[_ti - 1] if _ti >= 1 else None
        rule_prev_prev_iss = common_issues[_ti - 2] if _ti >= 2 else None
    else:
        rule_prev_iss = latest_excel_iss
        rule_prev_prev_iss = prev_excel_iss

    rules = compute_rules_for_target(data1_by_issue, data2_by_issue, rule_prev_iss, rule_prev_prev_iss)

    # 1. 跨规则共识识别
    hot_counts = collections.Counter()
    for rname in ['rule_hot_rebound', 'rule_hot_b1_streak', 'rule_hot_b0_silent']:
        for n in rules[rname]:
            hot_counts[n] += 1

    consensus_numbers = [n for n, c in hot_counts.items() if c >= 2]
    consensus_numbers.sort(key=lambda n: (-hot_counts[n], n))

    # 2. 爆发候选精选 (最优 3 码)
    # 权重优先: 跨规则共识 > B1连庄(43%) > 蓄力反弹(35%) > B0静默(37%)
    hot_scored = {}
    for n, cnt in hot_counts.items():
        score = cnt * 3.0
        if n in rules['rule_hot_b1_streak']: score += 4.3
        if n in rules['rule_hot_rebound']: score += 3.5
        if n in rules['rule_hot_b0_silent']: score += 3.7
        hot_scored[n] = score

    top_hot_numbers = sorted(hot_scored.keys(), key=lambda n: -hot_scored[n])[:3]

    # 3. 黄金连体婴搭档挖掘（杀号产品已退役，不再产出防守杀号池）
    recent_draws = history[:100]
    pair_counts = collections.Counter()
    for h in recent_draws:
        nums = sorted(list(h['numbers']))
        for a, b in itertools.combinations(nums, 2):
            pair_counts[(a, b)] += 1

    best_pair = None
    best_pair_count = -1
    pool_for_pair = top_hot_numbers if len(top_hot_numbers) >= 2 else (top_hot_numbers + consensus_numbers)
    if len(pool_for_pair) >= 2:
        for a, b in itertools.combinations(pool_for_pair, 2):
            pair = (min(a, b), max(a, b))
            cnt = pair_counts.get(pair, 0)
            if cnt > best_pair_count:
                best_pair_count = cnt
                best_pair = pair

    if not best_pair and len(top_hot_numbers) >= 2:
        best_pair = (top_hot_numbers[0], top_hot_numbers[1])

    gold_pair_list = list(best_pair) if best_pair else []
    consensus_set = set(consensus_numbers)
    gold_set = set(gold_pair_list)

    # 下一期最可能号码：复用 hot_scored，叠加共识/搭档加分（不做杀号降权）
    next_likely = []
    candidate_scores = dict(hot_scored)
    for n in consensus_set | gold_set | set(top_hot_numbers):
        candidate_scores.setdefault(n, 0.0)
    for n, base in candidate_scores.items():
        score = float(base)
        sources = []
        if n in consensus_set:
            score += 2.0
            sources.append('共识')
        if n in gold_set:
            score += 1.0
            sources.append('黄金搭档')
        if n in rules.get('rule_hot_b1_streak', set()):
            sources.append('B1连庄')
        if n in rules.get('rule_hot_rebound', set()):
            sources.append('蓄力反弹')
        if n in rules.get('rule_hot_b0_silent', set()):
            sources.append('B0静默')
        if not sources and base > 0:
            sources.append('爆发分')
        next_likely.append({
            'ball': int(n),
            'score': round(score, 2),
            'sources': sources,
            'kill_flags': [],
            'in_consensus': n in consensus_set,
            'in_gold_pair': n in gold_set,
            'in_top_hot': n in set(top_hot_numbers),
        })
    next_likely.sort(key=lambda x: (-x['score'], x['ball']))
    next_likely = next_likely[:3]

    result = {
        'target_period': target_period,
        'latest_excel_issue': latest_excel_iss,
        'anchor_period': rule_prev_iss,  # 规则锚点=目标期的前一已开奖期（与 Walk-Forward 同口径）
        'consensus_numbers': consensus_numbers,
        'top_hot_numbers': top_hot_numbers,
        'top3_gold': list(top_hot_numbers),
        'gold_pair': gold_pair_list,
        'gold_pair_cooccur_100': best_pair_count if best_pair else 0,
        'rules_detail': {k: sorted(list(v)) for k, v in rules.items()},
        'hot_scores': {str(k): round(float(v), 2) for k, v in hot_scored.items()},
        'next_likely_numbers': next_likely,
        'evidence_note': '结构推荐（非显著超额）；样本外热码 Lift 接近随机基线，仅作形态参考。杀号产品已退役。',
    }

    # 持久化输出（storage/outputs，禁止写根目录 outputs/）
    from backend.utils.paths import get_outputs_dir
    out_dir = os.path.join(get_outputs_dir(), 'deep_association')
    os.makedirs(out_dir, exist_ok=True)

    json_file = os.path.join(out_dir, f'深层关联预测_{target_period}.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    txt_file = os.path.join(out_dir, f'深层关联预测_{target_period}.txt')
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"=== 快乐8 目标期 {target_period} 数据源1×2深层关联预测 ===\n")
        f.write(f"[精选爆发最优3码]: " + ", ".join(f"{n:02d}" for n in top_hot_numbers) + "\n")
        f.write(f"[跨规则共识金胆]: " + (", ".join(f"{n:02d}" for n in consensus_numbers) if consensus_numbers else "无") + "\n")
        if best_pair:
            f.write(f"[黄金连体婴选2]: [{best_pair[0]:02d}-{best_pair[1]:02d}] (近100期共现 {best_pair_count} 次)\n")
        f.write("[下一期最可能最优3码]: " + ", ".join(
            f"{x['ball']:02d}({x['score']})" for x in next_likely[:3]
        ) + "\n")

    md_file = os.path.join(out_dir, f'深层关联分析_{target_period}.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(f"# 快乐8 目标期 {target_period} 数据源1×数据源2 深度关联量化研报\n\n")
        f.write(f"> 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据源锚定期: {latest_excel_iss}\n\n")
        f.write("## 一、核心做多与金胆推荐\n")
        f.write(f"- **🎯 最终精选爆发码 (最优3码)**: `" + " ".join(f"{n:02d}" for n in top_hot_numbers) + "`\n")
        f.write(f"- **⭐ 跨规则共识金胆**: `" + (" ".join(f"{n:02d}" for n in consensus_numbers) if consensus_numbers else "无") + "`\n")
        if best_pair:
            f.write(f"- **👑 黄金连体婴选2搭档**: `[{best_pair[0]:02d} - {best_pair[1]:02d}]` (近100期同出 {best_pair_count} 次)\n\n")
        f.write("## 二、规则触发明细（杀号产品已退役，仅列热侧规则）\n")
        for rk, rlabel in RULE_LABELS.items():
            if "cold" in rk or "kill" in rk.lower():
                continue
            rnums = rules.get(rk, set())
            f.write(f"- **[{rlabel}]** ({len(rnums)}码): `" + (" ".join(f"{n:02d}" for n in sorted(list(rnums))) if rnums else "无") + "`\n")

    return result


def walk_forward_review_datasource(n_review: int = 30) -> Dict[str, Any]:
    """
    数据源1×2 样本外滚动对账（严格屏蔽未来数据）。

    对目标期 T：仅用 T-1 / T-2 的 Excel 结构与开奖标记推演规则，
    再用 T 的真实开奖对账。绝不读取 T 期及之后的 Excel/开奖。
    """
    history = load_history()
    hist_map = {str(h['issue']): set(h['numbers']) for h in history}
    # 兼容 issue 为 int / str
    for h in history:
        hist_map[h['issue']] = set(h['numbers'])

    data1_by_issue, data2_by_issue, d2_full_nums = load_structured_datasources()
    common_issues = sorted(
        list(set(data1_by_issue.keys()) & set(data2_by_issue.keys())),
        key=lambda x: int(x),
    )

    if len(common_issues) < 5:
        return {
            'total_evaluated': 0,
            'no_lookahead': True,
            'evidence_note': '共同期数不足，无法做 Walk-Forward 对账。',
            'rows': [],
        }

    start_idx = max(2, len(common_issues) - n_review)

    hot_hits_list = []
    rows = []

    for i in range(start_idx, len(common_issues)):
        target_iss = common_issues[i]
        prev_iss = common_issues[i - 1]
        prev_prev_iss = common_issues[i - 2] if i >= 2 else None

        actual = hist_map.get(target_iss) or hist_map.get(str(target_iss))
        if not actual:
            continue

        # 仅用 prev / prev_prev —— 目标期 Excel 与开奖一律不入规则
        rules = compute_rules_for_target(data1_by_issue, data2_by_issue, prev_iss, prev_prev_iss)

        hot_counts = collections.Counter()
        for rname in ['rule_hot_rebound', 'rule_hot_b1_streak', 'rule_hot_b0_silent']:
            for n in rules[rname]:
                hot_counts[n] += 1

        hot_scored = {}
        for n, cnt in hot_counts.items():
            score = cnt * 3.0
            if n in rules['rule_hot_b1_streak']:
                score += 4.3
            if n in rules['rule_hot_rebound']:
                score += 3.5
            if n in rules['rule_hot_b0_silent']:
                score += 3.7
            hot_scored[n] = score

        top_hot = sorted(hot_scored.keys(), key=lambda n: -hot_scored[n])[:3]
        h_hit = len(set(top_hot) & actual) if top_hot else 0
        if top_hot:
            hot_hits_list.append((h_hit, len(top_hot)))

        hit_balls = sorted(set(top_hot) & actual)
        rows.append({
            'period': target_iss,
            'target_period': target_iss,
            'anchor_period': prev_iss,
            'top_hot': top_hot,
            'top3_gold': top_hot,
            'hot_top5': top_hot,
            'hot_hits': h_hit,
            'hot_hit_balls': hit_balls,
            'actual_numbers': sorted(actual),
            'no_lookahead': True,
        })

    tot_hot_h = sum(x[0] for x in hot_hits_list)
    tot_hot_c = sum(x[1] for x in hot_hits_list)
    avg_hot_hit = tot_hot_h / len(hot_hits_list) if hot_hits_list else 0
    hot_rate = tot_hot_h / tot_hot_c if tot_hot_c else 0
    # 最优3码随机期望命中 ≈ 3 * 20/80 = 0.75
    hot_lift = (avg_hot_hit / 0.75) if avg_hot_hit else 0.0

    rows_desc = list(reversed(rows))

    return {
        'total_evaluated': len(rows),
        'n_review': n_review,
        'no_lookahead': True,
        'hot_top5_mean_hits': round(avg_hot_hit, 2),
        'hot_top3_mean_hits': round(avg_hot_hit, 2),
        'hot_single_rate': round(hot_rate, 4),
        'hot_top5_hit_rate': round(hot_rate, 4),
        'hot_lift': round(hot_lift, 2),
        'baseline_hot_hits': 0.75,
        'baseline_hot_rate': 0.25,
        'non_d2_kill_accuracy': 0.75,
        'evidence_note': (
            '仅评估最优3码爆发侧；杀号/D2回避产品已退役。'
            'Walk-Forward：预测目标期 T 仅使用 T-1/T-2 结构，再与 T 真实开奖对账。'
        ),
        'rows': rows_desc,
    }
