# -*- coding: utf-8 -*-
"""
数据1右侧点位共振规律深度挖掘方案
=================================
v2.0 修复: 移除对不存在的 analyze_val_logic 模块的依赖，
改用 feature_optimizer.load_all_data() 提取右侧数据和点位。
"""
import re
import sys
import os
import collections

_PROJ = os.path.dirname(os.path.abspath(__file__))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from audit.v3_trinity_audit import calc_energy_field
from core.algorithm_optimizer import plan7_markov_integration
from core.feature_optimizer import load_all_data


def _get_target_issue():
    """自动从 kl8_history_final.txt 读取最新期号，+1 得到目标期号"""
    history_path = os.path.join(_PROJ, 'kl8_history_final.txt')
    if not os.path.exists(history_path):
        return None, None
    with open(history_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = re.search(r'period:(\d+)', line)
            if m:
                latest = m.group(1)
                return str(int(latest) + 1), latest
    return None, None


def _parse_points(points_file=None):
    """解析点位数据，返回 {issue: set(numbers)} 字典"""
    if points_file is None:
        points_file = os.path.join(_PROJ, 'daily_points.txt')
    if not os.path.exists(points_file):
        return {}
    points_by_issue = {}
    with open(points_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            per_m = re.search(r'period:(\d+)', line)
            pts_m = re.search(r'points:([\d\s]+)', line)
            if pts_m and per_m:
                pts = {int(p) for p in pts_m.group(1).strip().split() if p}
                points_by_issue[per_m.group(1)] = pts
    return points_by_issue


def main():
    print("=" * 60)
    print(" 数据1右侧区域(B1-B4) x 点位标记 深度共振精选 (5码方案)")
    print("=" * 60)
    
    # 目标期号：自动计算
    target_issue, latest_issue = _get_target_issue()
    if not target_issue:
        print("[错误] 无法获取目标期号，请确认历史数据文件存在")
        return
    print(f"针对目标期号 {target_issue} 执行深度分析...")

    # 1. 通过 load_all_data 获取 data2 右侧数据
    data1_by_issue, data2_by_issue, d1_stars, history, points_by_issue = load_all_data()

    # 2. 提取右侧号码
    r_nums = []
    for issue_key in [target_issue, latest_issue]:
        if issue_key in data2_by_issue:
            for b_idx in range(4):
                right_data = data2_by_issue[issue_key][b_idx]['right']
                r_nums.extend([item[0] for item in right_data])
            if r_nums:
                if issue_key != target_issue:
                    print(f"  [fallback] {target_issue}期无右侧数据，使用{issue_key}期数据")
                break

    # 3. 获取点位
    pts = points_by_issue.get(target_issue, set())
    if not pts:
        print(f"  [fallback] {target_issue}期无今日点位，使用{latest_issue}期点位数据")
        pts = points_by_issue.get(latest_issue, set())

    # 4. 交集
    intersect = [n for n in r_nums if n in pts]
    print(f"[共振] {target_issue}期 右侧点位共振号码 (共{len(intersect)}个):")
    print(f"   {sorted(intersect)}")
    
    # 5. 用隐能量场(EF)和马尔可夫链(MK)提纯
    mk_res = plan7_markov_integration(history)
    ef_res = calc_energy_field(history, decay_rate=0.5)
    
    scores = {}
    details = {}
    for n in intersect:
        mk_val = mk_res['probs'].get(n, 0) if mk_res and 'probs' in mk_res else 0
        ef_val = ef_res.get(n, 0)
        mk_score = mk_val * 4.0
        ef_score = ef_val * 0.6
        total_score = mk_score + ef_score
        scores[n] = total_score
        details[n] = {'MK': mk_val, 'EF': ef_val, 'Total': total_score}
        
    sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    top_5 = sorted_nums[:5]
    
    print("\n[提纯] 经过隐能量场(EF)与马尔可夫链(MK)双重权重提纯：")
    for rank, n in enumerate(sorted_nums):
        d = details[n]
        marker = "[精选]" if rank < 5 else ""
        print(f"   [No. {rank+1}] 号码: {n:02d} | MK: {d['MK']:.4f} | EF: {d['EF']:.4f} | 综合动能: {d['Total']:.4f} {marker}")
            
    print("\n============================================================")
    print(f"[推荐] 5码方案 ({target_issue}): {sorted(top_5)}")
    print("============================================================")

if __name__ == '__main__':
    main()
