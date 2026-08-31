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
from typing import Dict, List, Any, Set, Optional

# ============================================================================
#  全局常量 — 自动上溯到项目根目录
# ============================================================================
import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()

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
                # numbers 保留原始出球顺序; draw_order 显式标注供 deep_optimizer 序列熵使用
                history.append({'issue': issue_s, 'date': date_s, 'numbers': nums, 'draw_order': list(nums)})
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

    import json
    CACHE_FILE = os.path.join(_PROJ, 'data_cache.json')
    
    use_cache = False
    if os.path.exists(CACHE_FILE) and os.path.exists(EXCEL_FILE) and os.path.exists(POINTS_FILE) and os.path.exists(HISTORY_FILE):
        mtime_cache = os.path.getmtime(CACHE_FILE)
        if (mtime_cache >= os.path.getmtime(EXCEL_FILE) and
            mtime_cache >= os.path.getmtime(POINTS_FILE) and
            mtime_cache >= os.path.getmtime(HISTORY_FILE)):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                data1_by_issue = collections.OrderedDict()
                for issue, b_dict in cache_data['data1'].items():
                    data1_by_issue[issue] = {int(b): v for b, v in b_dict.items()}
                
                data2_by_issue = collections.OrderedDict()
                for issue, b_dict in cache_data['data2'].items():
                    data2_by_issue[issue] = {int(b): v for b, v in b_dict.items()}
                
                data1_star_nums = cache_data['data1_stars']
                use_cache = True
                print("[加载] 已命中 JSON 高速缓存 (0.01秒)")
            except Exception as e:
                print(f"[警告] 读取缓存失败: {e}，将重新解析 Excel")

    if not use_cache:
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
        
        # 将解析结果存入缓存
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'data1': data1_by_issue,
                    'data2': data2_by_issue,
                    'data1_stars': data1_star_nums
                }, f, ensure_ascii=False)
            print("[加载] JSON 缓存已生成。")
        except Exception as e:
            print(f"[警告] 写入缓存失败: {e}")

    print(f"[完成] D1={len(data1_by_issue)}期 D2={len(data2_by_issue)}期 "
          f"Hist={len(history)}期 Points={len(points_by_issue)}期")
    
    # 确保 history 按期号降序排列（最新在前）
    history.sort(key=lambda h: h['issue'], reverse=True)
    
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


def plan2_hot_stealth_resonance(data1_by_issue, data2_by_issue, data1_star_nums, history, is_future: Optional[bool] = None):
    """数据1星号热码 × 数据2隐码(规律码)的交叉共振，及多期深层关联触发器。

    is_future: 目标期是否已开奖。None=自动推断 (latest_iss not in hist_issues,
    回测恒 False / 线上可能 True); True/False 时使用显式值, 保证 train/serve 一致。
    """
    print("\n" + "=" * 70 + "\n【方案2】数据1×数据2 深层交互 —— 热隐共振与关联触发\n" + "=" * 70)
    common = sorted(set(data1_by_issue) & set(data2_by_issue))
    if not common: return {}
    hist_issues = {h['issue'] for h in history}
    latest_iss = common[-1]
    if is_future is None:
        is_future = latest_iss not in hist_issues

    # 获取 T-1 期数据提取深层触发器 (Deep Triggers)
    prev_iss = common[-2] if len(common) > 1 else None
    prev_prev_iss = common[-3] if len(common) > 2 else None

    # 绝对防守区 (冷切断)
    rule_cold_overheat = set()   # D1_Pt_Win (Penalty -15)
    rule_cold_b2_kill = set()    # D2_B2_Win (Penalty -6)
    rule_cold_dropped = set()    # D1_Dropped_Loss (Penalty -5)

    # 绝对爆发区 (热追击)
    rule_hot_rebound = set()     # D1_Pt_Loss (Reward +5)
    rule_hot_b1_streak = set()   # D2_B1_Win (Reward +5)
    rule_hot_b0_silent = set()   # D2_B0_Loss (Reward +5)

    if prev_iss:
        d1_prev_all = set()
        d1_prev_wins = set()
        d1_prev_pts = set()
        d2_prev_b0_all = set(); d2_prev_b0_wins = set()
        d2_prev_b1_all = set(); d2_prev_b1_wins = set()
        d2_prev_b2_all = set(); d2_prev_b2_wins = set()

        for b_idx in range(4):
            for side in ('left', 'right'):
                for item in data1_by_issue[prev_iss][b_idx][side]:
                    n, is_w, is_p = item[0], item[1], item[2]
                    d1_prev_all.add(n)
                    if is_w: d1_prev_wins.add(n)
                    if is_p: d1_prev_pts.add(n)

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

        # 1. 深度过热防守 (D1 + Pt + Win)
        rule_cold_overheat = (d1_prev_all & d1_prev_pts & d1_prev_wins)
        # 2. 蓄力反弹爆发 (D1 + Pt + Not Win)
        rule_hot_rebound = (d1_prev_all & d1_prev_pts) - d1_prev_wins
        # 3. B2板块杀熟 (D2_B2 + Win)
        rule_cold_b2_kill = d2_prev_b2_all & d2_prev_b2_wins
        # 4. B1板块连庄 (D2_B1 + Win)
        rule_hot_b1_streak = d2_prev_b1_all & d2_prev_b1_wins
        # 5. B0静默爆发 (D2_B0 + Not Win)
        rule_hot_b0_silent = d2_prev_b0_all - d2_prev_b0_wins

        # 6. 热度退散 (D1 t-2, not D1 t-1, not Win t-1)
        if prev_prev_iss:
            d1_prev_prev_all = set()
            for b_idx in range(4):
                for side in ('left', 'right'):
                    for item in data1_by_issue[prev_prev_iss][b_idx][side]:
                        d1_prev_prev_all.add(item[0])
            rule_cold_dropped = (d1_prev_prev_all - d1_prev_all) - d1_prev_wins

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
    rec = sorted(resonance | cross_res)
    
    print(f"  最新期{latest_iss}: D1热码{len(d1_stars)}个, D2规律隐码{len(all_stealth)}个")
    print(f"  共振推荐: {rec}")
    if prev_iss:
        print(f"  [深层防守] 深度过热(-15): {sorted(rule_cold_overheat)}")
        print(f"  [深层防守] B2杀熟(-6): {sorted(rule_cold_b2_kill)}")
        print(f"  [深层防守] 热度退散(-5): {sorted(rule_cold_dropped)}")
        print(f"  [深层爆发] 蓄力反弹(+5): {sorted(rule_hot_rebound)}")
        print(f"  [深层爆发] B1连庄(+5): {sorted(rule_hot_b1_streak)}")
        print(f"  [深层爆发] B0静默(+5): {sorted(rule_hot_b0_silent)}")

    return {
        'recommended': rec,
        'rule_cold_overheat': sorted(rule_cold_overheat),
        'rule_cold_b2_kill': sorted(rule_cold_b2_kill),
        'rule_cold_dropped': sorted(rule_cold_dropped),
        'rule_hot_rebound': sorted(rule_hot_rebound),
        'rule_hot_b1_streak': sorted(rule_hot_b1_streak),
        'rule_hot_b0_silent': sorted(rule_hot_b0_silent)
    }


def plan3_frequency_acceleration(history):
    """号码频次二阶导数 —— 加速度检测。"""
    if len(history) < 15: return {}
    num_stats = {}
    for num in range(1, 81):
        f5 = sum(1 for h in history[:5] if num in h['numbers'])
        f10 = sum(1 for h in history[:10] if num in h['numbers'])
        f20 = sum(1 for h in history[:20] if num in h['numbers'])
        f20_den = min(len(history), 20)  # 历史不足20期时用实际期数作分母, 避免系统性低估
        v = (f5/5.0) - (f10/10.0); a = ((f5/5.0)-(f10/10.0)) - ((f10/10.0)-(f20/f20_den))
        num_stats[num] = {'acc': a, 'vel': v, 'f5': f5}
    rec = sorted([n for n, s in num_stats.items() if s['acc'] > 0.02 and s['vel'] > 0])
    return {'recommended': rec, 'stats': num_stats}


def plan4_adjacency_topology(data2_by_issue, history, is_future: Optional[bool] = None):
    """连号/邻号拓扑检测。修正：目标期非点位视为隐码。

    is_future: 目标期是否已开奖。None=自动推断; True/False 时使用显式值。
    """
    print("\n" + "=" * 70 + "\n【方案4】连号/邻号拓扑检测\n" + "=" * 70)
    issues = sorted(data2_by_issue.keys())
    if not issues: return {}
    latest = issues[-1]; hist_issues = {h['issue'] for h in history}
    if is_future is None:
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

# is_future 一致性守卫: 强制特征构建函数显式接受 is_future 参数,
# 防止回测恒 False 而线上读取目标期行的 train/serve 偏差。
try:
    from core.walk_forward_validator import assert_is_future_consistent
except ImportError:
    from walk_forward_validator import assert_is_future_consistent


# ... (保持常量不变) ...

def _filter_scoped_data(data1, data2, d1_stars, points, allowed_issues):
    """Walk-Forward: 仅保留训练窗口内期号的 Excel/点位切片"""
    data1_f = collections.OrderedDict((k, data1[k]) for k in data1 if k in allowed_issues)
    data2_f = collections.OrderedDict((k, data2[k]) for k in data2 if k in allowed_issues)
    d1_stars_f = {k: v for k, v in d1_stars.items() if k in allowed_issues}
    points_f = {k: v for k, v in points.items() if k in allowed_issues}
    return data1_f, data2_f, d1_stars_f, points_f


def _compute_layer_a_scores(hist, data1_by_issue, data2_by_issue, d1_stars_map, points_by_issue, is_future: Optional[bool] = None):
    """Layer A 得分计算核心 (与 Excel/历史/点位数据解耦)

    is_future: 目标期是否已开奖。WF 回测 (history_only=True) 由调用方传 False;
    线上不传 (None), 由 plan2/plan4 内部推断 (目标期不在历史时得 True)。
    """
    assert_is_future_consistent(plan2_hot_stealth_resonance, [])
    assert_is_future_consistent(plan4_adjacency_topology, [])
    r2 = plan2_hot_stealth_resonance(data1_by_issue, data2_by_issue, d1_stars_map, hist, is_future=is_future)
    r3 = plan3_frequency_acceleration(hist)
    r4 = plan4_adjacency_topology(data2_by_issue, hist, is_future=is_future)
    r5 = plan5_multi_source_points(hist, points_by_issue)
    r6 = plan6_phase_transition(hist)

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
                row_nums = [left_all[i][0] for i in range(start, min(start + 4, len(left_all)))]
                row_nums += [right_all[i][0] for i in range(start, min(start + 4, len(right_all)))]
                stride_m[win_idx][b_idx] = [f"{n}*" if n in d1_stars else str(n) for n in row_nums]

    import core.deep_optimizer as deep_opt
    r17 = deep_opt.plan17_sequence_entropy(hist)
    r18_scores = deep_opt.plan18_stride_row_collision(stride_m)
    r20 = deep_opt.plan20_cluster_accelerator(hist)
    r21_moments = deep_opt.plan21_momentum_score(hist)
    r22_harmonics = deep_opt.plan22_omission_harmonics(hist)

    scores = collections.Counter()
    for n in r2.get('recommended', []):
        scores[n] += 5
    
    # --- 方案2 新增6维深层触发器 (Data1/Data2 关联) ---
    for n in r2.get('rule_cold_overheat', []):
        scores[n] -= 15   # 强防守信号：断崖式冷却
    for n in r2.get('rule_cold_b2_kill', []):
        scores[n] -= 6    # B2板块杀熟
    for n in r2.get('rule_cold_dropped', []):
        scores[n] -= 5    # 热度退散

    for n in r2.get('rule_hot_rebound', []):
        scores[n] += 5    # 蓄力反弹爆发
    for n in r2.get('rule_hot_b1_streak', []):
        scores[n] += 5    # B1板块连庄
    for n in r2.get('rule_hot_b0_silent', []):
        scores[n] += 5    # B0板块静默爆发

    for n in r3.get('recommended', []):
        scores[n] += 2
    for n in r4.get('topology_recommended', []):
        scores[n] += 2
    for n in r5.get('high', []):
        scores[n] += 4
    for n in r6.get('phase_refined', []):
        scores[n] += 3
    if r17.get('boost_suggestion'):
        for n in r17['boost_suggestion']:
            scores[n] += 2
    for n, s in r18_scores.items():
        scores[n] += (s + 5)
    for n in r20.get('accelerated', []):
        if n in scores:
            scores[n] *= 1.6
        else:
            scores[n] += 3
    for n, m in r21_moments.items():
        if m > 1.2:
            scores[n] += (m * 2)
    for n in r22_harmonics:
        scores[n] += 4

    # ── 唯一入口 (唯一评分路径): 6维规则分 + 深度方案 + plan19 对抗过滤 ──
    # run_all 与 get_all_layer_a_scores 必须经由本函数, 保证日报与 FO 基线附录
    # 对同一期的输出完全一致 (修复双流水线分歧)。
    # 应用方案 19 的对抗过滤: 剔除热点陷阱号码
    sorted_scores = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:30]
    top_30_nums = [n for n, s in sorted_scores]
    filtered_nums, removed_traps = deep_opt.plan19_adversarial_filter(top_30_nums, hist)
    # 陷阱号码从得分表中移除, 使下游 Top-K 排名与 run_all 的最终推荐一致
    for n in removed_traps:
        scores.pop(n, None)

    return scores


def get_all_layer_a_scores(history=None, history_only=False, is_future: Optional[bool] = None):
    """供外部调用的全量得分获取接口。

    history_only=True 时 (Walk-Forward): 仅使用 history 窗口内的 Excel/点位切片，
    避免全局 _data_cache 造成前瞻偏差；is_future 强制传 False (回测目标期未开奖)。
    is_future 参数: 显式控制 plan2/plan4 的 is_future 语义; 默认 None 走自动推断。
    """
    global _data_cache

    if history_only:
        if not history:
            return {n: 0.0 for n in range(1, 81)}
        allowed = {h['issue'] for h in history}
        if not _data_cache:
            try:
                _data_cache['data1'], _data_cache['data2'], _data_cache['d1_stars'], \
                _data_cache['history'], _data_cache['points'] = load_all_data()
            except Exception:
                return {n: 0.0 for n in range(1, 81)}
        data1, data2, d1_stars, points = _filter_scoped_data(
            _data_cache['data1'], _data_cache['data2'], _data_cache['d1_stars'],
            _data_cache['points'], allowed)
        return _compute_layer_a_scores(history, data1, data2, d1_stars, points, is_future=False)

    if not _data_cache:
        try:
            _data_cache['data1'], _data_cache['data2'], _data_cache['d1_stars'], \
            _data_cache['history'], _data_cache['points'] = load_all_data()
        except Exception:
            return {n: 0.0 for n in range(1, 81)}

    hist = history if history is not None else _data_cache['history']
    return _compute_layer_a_scores(
        hist,
        _data_cache['data1'],
        _data_cache['data2'],
        _data_cache['d1_stars'],
        _data_cache['points'],
        is_future=is_future,
    )


def run_all():
    """FO 基线附录入口 — 委托 _compute_layer_a_scores (唯一评分路径)。

    与 get_all_layer_a_scores / 日报共用同一套逻辑 (6维规则分 + 深度方案 + plan19 过滤),
    保证对同一期输出完全一致。不再自行拼装评分, 避免双流水线分歧。
    """
    data1_by_issue, data2_by_issue, d1_stars_map, history, points_by_issue = load_all_data()

    # ── 唯一入口: 与 get_all_layer_a_scores 共用 _compute_layer_a_scores ──
    scores = _compute_layer_a_scores(
        history, data1_by_issue, data2_by_issue, d1_stars_map, points_by_issue
    )

    # 重建 Top 5/12 (plan19 过滤已在 _compute_layer_a_scores 内完成)
    sorted_scores = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    top_30_nums = [n for n, s in sorted_scores[:30]]
    filtered_nums, removed_traps = deep_opt.plan19_adversarial_filter(top_30_nums, history)

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
