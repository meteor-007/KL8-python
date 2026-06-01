# -*- coding: utf-8 -*-
"""
数据特征层优化模块 (Feature Optimizer - Layer A) - 重构修复版
================================================
迁移至 core/ 子树 — 路径已自动适应
"""
import openpyxl
import re
import os
import collections
import math
import sys
from typing import Dict, List, Any, Set

# ============================================================================
#  全局常量 — 自动上溯到项目根目录
# ============================================================================
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # data/
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)
from utils.excel_lock import excel_lock

EXCEL_FILE = os.path.join(_PROJ, '跟随+点位+开奖数据.xlsx')
HISTORY_FILE = os.path.join(_PROJ, 'kl8_history_final.txt')
POINTS_FILE = os.path.join(_PROJ, 'daily_points.txt')

POINT_FILL = "FFFCE4EC"
BORDER_CLR = "FFD966B3"
BLOCK_OFFSETS = [1, 6, 11, 16]
ZONE_RANGES = [(i * 10 + 1, (i + 1) * 10) for i in range(8)]
THEORY_DENSITY = 20.0 / 80.0

# 模块级缓存，避免重复加载
_data_cache = {}


def clear_data_cache():
    """清除数据缓存，强制下次调用时重新加载"""
    global _data_cache
    _data_cache = {}


def _is_point(cell):
    try:
        return cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb == POINT_FILL
    except Exception:
        return False


def _is_win(cell):
    try:
        b = cell.border
        if not b:
            return False
        for side in (b.left, b.right, b.top, b.bottom):
            if side and side.color and side.color.rgb == BORDER_CLR:
                return True
        return False
    except Exception:
        return False


def _cell_num(cell):
    v = str(cell.value or "").strip().replace('*', '')
    return int(v) if v.isdigit() and 1 <= int(v) <= 80 else None


def load_all_data():
    """一次读取Excel+历史+点位, 全部方案共享。性能优化版：不再读取Excel样式，而是基于原始数据比对。"""
    print("[加载] 正在读取历史与点位数据...")
    
    # 1. 优先提取开奖历史
    history = []
    history_by_issue = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if 'numbers:' not in line:
                    continue
                parts = line.split(',')
                date_s = parts[0].split(':')[1]
                issue_s = parts[1].split(':')[1]
                nums = [int(n) for n in parts[2].split(':')[1].strip().split('-')]
                history.append({'issue': issue_s, 'date': date_s, 'numbers': nums})
                history_by_issue[issue_s] = set(nums)

    # 2. 优先提取点位
    points_by_issue = {}
    if os.path.exists(POINTS_FILE):
        with open(POINTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                per_m = re.search(r'period:(\d+)', line)
                pts_m = re.search(r'points:([\d\s]+)', line)
                if pts_m and per_m:
                    pts = {int(p) for p in pts_m.group(1).strip().split() if p}
                    points_by_issue[per_m.group(1)] = pts

    print("[加载] 正在读取 Excel (只读模式，约 1 秒)...")
    with excel_lock(EXCEL_FILE, timeout=60):
        # 启用 read_only=True，极速读取数据
        wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True, read_only=True)
        try:
            ws = wb['跟随号码统计']

            grid = list(ws.iter_rows(values_only=True))
            max_row_idx = len(grid)

            data2_by_issue = collections.OrderedDict()
            data1_by_issue = collections.OrderedDict()
            data1_star_nums = {}

            for r_idx in range(max_row_idx):
                first_val = str(grid[r_idx][0] or "").strip()
                m = re.search(r'(\d{7})[^\d]+(\d)', first_val)
                if not m:
                    continue
                issue, dtype = m.group(1), int(m.group(2))
                target = data2_by_issue if dtype == 2 else data1_by_issue
                target[issue] = {b: {'left': [], 'right': []} for b in range(4)}
                if dtype == 1:
                    data1_star_nums[issue] = []

                star_nums = set()
                issue_points = points_by_issue.get(issue, set())
                issue_wins = history_by_issue.get(issue, set())

                for b_idx, offset in enumerate(BLOCK_OFFSETS):
                    for row_off in range(4):
                        ri_idx = r_idx + offset + row_off
                        if ri_idx >= max_row_idx:
                            continue
                        
                        row_vals = grid[ri_idx]
                        
                        # Left side (Cols 1-4, indices 0-3)
                        for col_idx in range(0, 4):
                            if col_idx < len(row_vals):
                                val_str = str(row_vals[col_idx] or "").strip().replace('*', '')
                                num = int(val_str) if val_str.isdigit() and 1 <= int(val_str) <= 80 else None
                                if num is not None:
                                    ip = num in issue_points
                                    iw = num in issue_wins
                                    target[issue][b_idx]['left'].append((num, iw, ip))
                                    if dtype == 1 and '*' in str(row_vals[col_idx] or ""):
                                        star_nums.add(num)
                        
                        # Right side (Cols 6-9, indices 5-8)
                        for col_idx in range(5, 9):
                            if col_idx < len(row_vals):
                                val_str = str(row_vals[col_idx] or "").strip().replace('*', '')
                                num = int(val_str) if val_str.isdigit() and 1 <= int(val_str) <= 80 else None
                                if num is not None:
                                    ip = num in issue_points
                                    iw = num in issue_wins
                                    target[issue][b_idx]['right'].append((num, iw, ip))
                                    if dtype == 1 and '*' in str(row_vals[col_idx] or ""):
                                        star_nums.add(num)

                if dtype == 1:
                    data1_star_nums[issue] = sorted(list(star_nums))
        finally:
            wb.close()

    print(f"[完成] D1={len(data1_by_issue)}期 D2={len(data2_by_issue)}期 "
          f"Hist={len(history)}期 Points={len(points_by_issue)}期")
    return data1_by_issue, data2_by_issue, data1_star_nums, history, points_by_issue


def plan1_sliding_window(data2_by_issue):
    """追踪每个Block命中趋势: 上升/峰值/回落/低谷。"""
    issues = sorted(data2_by_issue.keys())
    if len(issues) < 5: return {}
    block_hit_series = {}
    for b_idx in range(4):
        for side in ('left', 'right'):
            key = f"B{b_idx+1}_{side}"; series = []
            for iss in issues:
                cells = data2_by_issue[iss][b_idx][side]
                wins = [c for c in cells if c[1]]
                stealth = [c for c in wins if not c[2]]
                series.append({'issue': iss, 'total_win': len(wins), 'stealth_win': len(stealth)})
            block_hit_series[key] = series
    trend_report = {}
    for key, series in block_hit_series.items():
        overall_avg = sum(s['total_win'] for s in series) / len(series)
        windows = {}
        for w_size in (3, 5, 10):
            if len(series) < w_size: continue
            recent = series[-w_size:]
            avg_win = sum(r['total_win'] for r in recent) / w_size
            dev = (avg_win - overall_avg) / overall_avg * 100 if overall_avg > 0 else 0
            windows[w_size] = {'avg_win': round(avg_win, 2), 'dev%': round(dev, 1)}
        trend_report[key] = {'windows': windows}
    return trend_report


def plan2_hot_stealth_resonance(data1_by_issue, data2_by_issue, data1_star_nums, history):
    """数据1星号热码 × 数据2隐码(规律码)的交叉共振。"""
    print("\n" + "=" * 70 + "\n【方案2】数据1×数据2 深层交互 —— 热隐共振\n" + "=" * 70)
    common = sorted(set(data1_by_issue) & set(data2_by_issue))
    if not common: return {}
    hist_issues = {h['issue'] for h in history}
    latest_iss = common[-1]
    is_future = latest_iss not in hist_issues
    d1_stars = set(data1_star_nums.get(latest_iss, []))
    all_stealth = set(); appear = collections.Counter()
    for b_idx in range(4):
        for side in ('left', 'right'):
            cells = data2_by_issue[latest_iss][b_idx][side]
            if is_future:
                stealth = {c[0] for c in cells if not c[2]}
            else:
                stealth = {c[0] for c in cells if c[1] and not c[2]}
            for n in stealth: appear[n] += 1
            all_stealth.update(stealth)
    resonance = d1_stars & all_stealth
    cross_res = {n for n, c in appear.items() if c >= 2 and n in d1_stars}
    print(f"  最新期{latest_iss}: D1热码{len(d1_stars)}个, D2规律隐码{len(all_stealth)}个")
    print(f"  共振推荐: {sorted(resonance | cross_res)}")
    return {'recommended': sorted(resonance | cross_res)}


def plan3_frequency_acceleration(history):
    """号码频次二阶导数 —— 加速度检测。"""
    if len(history) < 15: return {}
    num_stats = {}
    for num in range(1, 81):
        f5 = sum(1 for h in history[:5] if num in h['numbers'])
        f10 = sum(1 for h in history[:10] if num in h['numbers'])
        f20 = sum(1 for h in history[:20] if num in h['numbers'])
        v = (f5/5.0) - (f10/10.0); a = ((f5/5.0)-(f10/10.0)) - ((f10/10.0)-(f20/20.0))
        num_stats[num] = {'acc': a, 'vel': v, 'f5': f5}
    rec = sorted([n for n, s in num_stats.items() if s['acc'] > 0.02 and s['vel'] > 0])
    return {'recommended': rec, 'stats': num_stats}


def plan4_adjacency_topology(data2_by_issue, history):
    """连号/邻号拓扑检测。修正：目标期非点位视为隐码。"""
    print("\n" + "=" * 70 + "\n【方案4】连号/邻号拓扑检测\n" + "=" * 70)
    issues = sorted(data2_by_issue.keys())
    if not issues: return {}
    latest = issues[-1]; hist_issues = {h['issue'] for h in history}
    is_future = latest not in hist_issues
    d2_st = []
    for b_idx in range(4):
        for side in ('left', 'right'):
            for c in data2_by_issue[latest][b_idx][side]:
                if not c[2]:
                    if is_future or c[1]: d2_st.append(c[0])
    d2st = sorted(set(d2_st))
    rec = set()
    for i in range(len(d2st)-1):
        if d2st[i+1] - d2st[i] == 1: rec.add(d2st[i]); rec.add(d2st[i+1])
    for n in d2st:
        rs = str(n)[::-1]
        if len(rs) == 2 and rs[0] != '0':
            rev = int(rs)
            if rev in d2st and n < rev: rec.add(n); rec.add(rev)
    print(f"  拓扑精选: {sorted(rec)}")
    return {'topology_recommended': sorted(rec)}


def plan5_multi_source_points(history, points_by_issue):
    """多源点位融合。修正：精准抓取目标期点位。"""
    print("\n" + "=" * 70 + "\n【方案5】点位信号增强 —— 多源点位融合\n" + "=" * 70)
    latest_issue = int(history[0]['issue']) if history else 0
    target_issue = str(latest_issue + 1)
    s1 = points_by_issue.get(target_issue, set())
    if not s1:
        for i in range(1, 6):
            s1 = points_by_issue.get(str(latest_issue - i), set())
            if s1: break
    print(f"  源1(目标期{target_issue}点位): {len(s1)}个 -> {sorted(s1)}")
    f5 = collections.Counter(n for h in history[:5] for n in h['numbers'])
    s2 = set(n for n, _ in f5.most_common(20))
    votes = collections.Counter()
    for n in s1: votes[n] += 3
    for n in s2: votes[n] += 1
    high = sorted(n for n, v in votes.items() if v >= 3)
    return {'high': high, 'mid': [], 'sources': {'点位': sorted(s1), '频次5': sorted(s2)}}


def plan6_phase_transition(history):
    """区间相变检测。"""
    if len(history) < 5: return {}
    def zone_temps(nums):
        return {f"{z0:02d}-{z1:02d}": sum(1 for n in nums if z0 <= n <= z1) for z0, z1 in ZONE_RANGES}
    t_now = zone_temps(history[0]['numbers']); t_old = zone_temps(history[1]['numbers'])
    refined = set()
    for z_str, tn in t_now.items():
        to = t_old[z_str]
        if tn >= 4 and to <= 2:
            z0, z1 = map(int, z_str.split('-'))
            refined.update(range(z0, z1 + 1))
    return {'phase_refined': sorted(refined)}


try:
    import core.deep_optimizer as deep_opt
except ImportError:
    import deep_optimizer as deep_opt


# ... (保持常量不变) ...

def get_all_layer_a_scores(history=None):
    """供外部调用的全量得分获取接口。"""
    global _data_cache
    
    if not _data_cache:
        try:
            _data_cache['data1'], _data_cache['data2'], _data_cache['d1_stars'], \
            _data_cache['history'], _data_cache['points'] = load_all_data()
        except Exception:
            return {n: 0.0 for n in range(1, 81)}
    
    if history is not None:
        hist = history
    else:
        hist = _data_cache['history']

    data1_by_issue = _data_cache['data1']
    data2_by_issue = _data_cache['data2']
    d1_stars_map = _data_cache['d1_stars']
    points_by_issue = _data_cache['points']

    r2 = plan2_hot_stealth_resonance(data1_by_issue, data2_by_issue, d1_stars_map, hist)
    r3 = plan3_frequency_acceleration(hist)
    r4 = plan4_adjacency_topology(data2_by_issue, hist)
    r5 = plan5_multi_source_points(hist, points_by_issue)
    r6 = plan6_phase_transition(hist)
    
    # 构建 stride_m
    stride_m = {w: [[] for _ in range(4)] for w in range(4)}
    issues = sorted(data2_by_issue.keys())
    if issues:
        latest_iss = issues[-1]
        d1_stars = set(d1_stars_map.get(latest_iss, []))
        for b_idx in range(4):
            left_all = data2_by_issue[latest_iss][b_idx]['left']
            right_all = data2_by_issue[latest_iss][b_idx]['right']
            for win_idx in range(4):
                start = win_idx * 4
                row_nums = [left_all[i][0] for i in range(start, min(start+4, len(left_all)))]
                row_nums += [right_all[i][0] for i in range(start, min(start+4, len(right_all)))]
                stride_m[win_idx][b_idx] = [f"{n}*" if n in d1_stars else str(n) for n in row_nums]

    import core.deep_optimizer as deep_opt
    r17 = deep_opt.plan17_sequence_entropy(hist)
    r18_scores = deep_opt.plan18_stride_row_collision(stride_m)
    r20 = deep_opt.plan20_cluster_accelerator(hist)
    r21_moments = deep_opt.plan21_momentum_score(hist)
    r22_harmonics = deep_opt.plan22_omission_harmonics(hist)

    scores = collections.Counter()
    for n in r2.get('recommended', []): scores[n] += 5
    for n in r3.get('recommended', []): scores[n] += 2
    for n in r4.get('topology_recommended', []): scores[n] += 2
    for n in r5.get('high', []): scores[n] += 4
    for n in r6.get('phase_refined', []): scores[n] += 3
    if r17.get('boost_suggestion'):
        for n in r17['boost_suggestion']: scores[n] += 2
    for n, s in r18_scores.items(): scores[n] += (s + 5)
    for n in r20.get('accelerated', []):
        if n in scores: scores[n] *= 1.6
        else: scores[n] += 3
    for n, m in r21_moments.items():
        if m > 1.2: scores[n] += (m * 2)
    for n in r22_harmonics: scores[n] += 4
    
    return scores


def run_all():
    data1_by_issue, data2_by_issue, d1_stars_map, history, points_by_issue = load_all_data()

    # --- 原有方案 ---
    r2 = plan2_hot_stealth_resonance(data1_by_issue, data2_by_issue, d1_stars_map, history)
    r3 = plan3_frequency_acceleration(history)
    r4 = plan4_adjacency_topology(data2_by_issue, history)
    r5 = plan5_multi_source_points(history, points_by_issue)
    r6 = plan6_phase_transition(history)

    # --- 新增深度方案 (方案 17, 18, 19) ---
    # 结构映射：stride_m[win_idx][cycle_idx] = [8 numbers (L4+R4)]
    stride_m = {w: [[] for _ in range(4)] for w in range(4)}
    issues = sorted(data2_by_issue.keys())
    if issues:
        latest_iss = issues[-1]
        d1_stars = set(d1_stars_map.get(latest_iss, []))
        for b_idx in range(4): # Cycle (0,1,2,3)
            left_all = data2_by_issue[latest_iss][b_idx]['left']   # 16 items
            right_all = data2_by_issue[latest_iss][b_idx]['right'] # 16 items
            
            for win_idx in range(4): # Window (0,1,2,3)
                start = win_idx * 4
                row_nums = []
                # 提取该窗口在当前 Cycle 的 Left 4 和 Right 4
                for i in range(4):
                    if start + i < len(left_all):
                        row_nums.append(left_all[start + i][0])
                for i in range(4):
                    if start + i < len(right_all):
                        row_nums.append(right_all[start + i][0])
                
                # 标记星号
                star_row = [f"{n}*" if n in d1_stars else str(n) for n in row_nums]
                stride_m[win_idx][b_idx] = star_row

    r17 = deep_opt.plan17_sequence_entropy(history)
    r18_scores = deep_opt.plan18_stride_row_collision(stride_m)
    r20 = deep_opt.plan20_cluster_accelerator(history)
    r21_moments = deep_opt.plan21_momentum_score(history)
    r22_harmonics = deep_opt.plan22_omission_harmonics(history)

    scores = collections.Counter()
    for n in r2.get('recommended', []): scores[n] += 5
    for n in r3.get('recommended', []): scores[n] += 2
    for n in r4.get('topology_recommended', []): scores[n] += 2
    for n in r5.get('high', []): scores[n] += 4
    for n in r6.get('phase_refined', []): scores[n] += 3
    
    # 应用方案 17 的 Entropy Boost
    if r17.get('boost_suggestion'):
        for n in r17['boost_suggestion']: scores[n] += 2
    
    # 应用方案 18 的碰撞 Boost
    for n, s in r18_scores.items(): 
        scores[n] += (s + 5)

    # 应用方案 20 的集群加速 (极强信号)
    for n in r20.get('accelerated', []):
        if n in scores:
            scores[n] *= 1.6 # 增强倍增系数 (1.5 -> 1.6)
        else:
            scores[n] += 3

    # 应用方案 21 的动能加成
    for n, m in r21_moments.items():
        if m > 1.2: scores[n] += (m * 2)

    # 应用方案 22 的遗漏谐波
    for n in r22_harmonics:
        scores[n] += 4

    sorted_scores = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:30]
    
    # 应用方案 19 的对抗过滤
    top_30_nums = [n for n, s in sorted_scores]
    filtered_nums, removed_traps = deep_opt.plan19_adversarial_filter(top_30_nums, history)
    
    # 重新构建 Top 5/12
    final_top_5 = filtered_nums[:5]
    final_top_12 = filtered_nums[:12]

    print("\n" + "=" * 70)
    print(f"★★★ AI 核心推荐号码 (Top 5): {sorted(final_top_5)}")
    print(f"★★★ AI 综合拦截号码 (Top 12): {sorted(final_top_12)}")
    if removed_traps:
        print(f"  [对抗过滤] 已剔除热点陷阱: {removed_traps[:5]}")
    print("=" * 70)


if __name__ == '__main__':
    run_all()
