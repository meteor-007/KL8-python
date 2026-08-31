# -*- coding: utf-8 -*-
"""规则选号器命中率提升深度探索与回测脚本
探索维度:
1. 特征重要性与特征挖掘 (双数据共现、跟随频次、左右侧强信号、遗漏层级、区尾交互)
2. 动态自适应权重 vs 静态阶梯分层
3. 动态金胆池截断 (Top 5 / Top 8 / Top 12 分层胜率对比)
4. 区域离散度约束与防扎堆过滤
"""
import openpyxl, re, sys, math, statistics
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'): 
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "跟随+点位+开奖数据.xlsx"
HIST_FILE = ROOT / "kl8_history_final.txt"
POINTS_FILE = ROOT / "daily_points.txt"

POINT_FILLS = ("FFFCE4EC", "00FCE4EC")

# 1. 加载开奖历史
draws = {}
if HIST_FILE.exists():
    for line in HIST_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"date:[^,]+,period:(\d+),numbers:(.+)", line.strip())
        if m:
            draws[int(m.group(1))] = set(int(x) for x in m.group(2).split("-"))

# 2. 加载 daily_points.txt (点位号)
daily_points_map = {}
if POINTS_FILE.exists():
    for line in POINTS_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"date:[^,]+,period:(\d+),points:(.+)", line.strip())
        if m:
            daily_points_map[int(m.group(1))] = set(int(x) for x in m.group(2).split())

# 3. 解析跟随号码统计表
wb = openpyxl.load_workbook(DATA_FILE, data_only=False)
ws = wb['跟随号码统计']
all_rows = list(ws.iter_rows())

period_data = {}
for idx, row in enumerate(all_rows):
    v = str(row[0].value or "").strip()
    m = re.search(r'(\d{7})期[\s\S]*?数据(1|2)', v)
    if not m: 
        continue
    iss = int(m.group(1))
    dtype = int(m.group(2))
    if iss not in period_data:
        period_data[iss] = {
            'd1': set(), 'd2': set(), 
            'd1_counts': defaultdict(int), 'd2_counts': defaultdict(int),
            'sides': defaultdict(list), 
            'fill_points': set(),
            'star_ranks': defaultdict(list)
        }
    pdata = period_data[iss]
    for b_idx, off in enumerate([1, 6, 11, 16]):
        for ro in range(4):
            if idx + off + ro >= len(all_rows): 
                continue
            trow = all_rows[idx + off + ro]
            cells = []
            for c in range(min(10, len(trow))):
                cell = trow[c]
                cv = str(cell.value or "").strip()
                if cv and cv != 'nan':
                    if '*' in cv:
                        num = int(cv.replace('*', ''))
                        cells.append((c, num))
                    if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb in POINT_FILLS:
                        pdata['fill_points'].add(int(cv.replace('*', '')))
            cells.sort()
            for si, (c, n) in enumerate(cells):
                side = 'R' if c >= 5 else 'L'
                pdata['sides'][n].append(side)
                pdata['star_ranks'][n].append(si)
                if dtype == 1:
                    pdata['d1'].add(n)
                    pdata['d1_counts'][n] += 1
                else:
                    pdata['d2'].add(n)
                    pdata['d2_counts'][n] += 1

issues = sorted(i for i in period_data if i in draws and (i - 1) in draws)
print(f"有效回测期数: {len(issues)} 期 (从 {issues[0]} 到 {issues[-1]})")

# ═══ 探索1: 基础特征与命中率单变量分析 ═══
print("\n" + "=" * 60)
print("【特征单变量分析 (单兵作战能力)】")
print("=" * 60)

stats = defaultdict(lambda: [0, 0]) # name -> [hits, total]

for iss in issues:
    draw = draws[iss]
    prev_draw = draws.get(iss - 1, set())
    prev_draw2 = draws.get(iss - 2, set())
    pdata = period_data[iss]
    pool = pdata['d1'] | pdata['d2']
    
    # 算每个号码的最近遗漏
    # 简易遗漏统计
    for n in pool:
        hit = 1 if n in draw else 0
        z = (n - 1) // 10
        t = n % 10
        is_repeat = (n in prev_draw)
        is_repeat2 = (n in prev_draw2)
        is_in_d1 = (n in pdata['d1'])
        is_in_d2 = (n in pdata['d2'])
        is_dual = is_in_d1 and is_in_d2
        is_fill_point = (n in pdata['fill_points'])
        is_daily_point = (n in daily_points_map.get(iss, set()))
        sides = pdata['sides'][n]
        is_right = ('R' in sides)
        r_count = sides.count('R')
        total_freq = pdata['d1_counts'][n] + pdata['d2_counts'][n]
        
        # 记录特征统计
        stats["全部候选池"][0] += hit; stats["全部候选池"][1] += 1
        stats[f"尾数_{t}"][0] += hit; stats[f"尾数_{t}"][1] += 1
        stats[f"区间_区{z}({z*10+1:02d}-{(z+1)*10:02d})"][0] += hit; stats[f"区间_区{z}({z*10+1:02d}-{(z+1)*10:02d})"][1] += 1
        
        # 重号属性
        if is_repeat:
            stats["上期重号(遗漏0)"][0] += hit; stats["上期重号(遗漏0)"][1] += 1
        else:
            stats["非重号(遗漏>=1)"][0] += hit; stats["非重号(遗漏>=1)"][1] += 1
            
        # 双数据共现 (共振)
        if is_dual:
            stats["双数据共振(D1∩D2)"][0] += hit; stats["双数据共振(D1∩D2)"][1] += 1
        else:
            stats["单数据出现(仅D1或仅D2)"][0] += hit; stats["单数据出现(仅D1或仅D2)"][1] += 1
            
        # 频次特征
        if total_freq >= 3:
            stats["总频次>=3次"][0] += hit; stats["总频次>=3次"][1] += 1
        elif total_freq == 2:
            stats["总频次==2次"][0] += hit; stats["总频次==2次"][1] += 1
        else:
            stats["总频次==1次"][0] += hit; stats["总频次==1次"][1] += 1
            
        # 左右侧特征
        if is_right:
            stats["含右侧R"][0] += hit; stats["含右侧R"][1] += 1
            if r_count >= 2:
                stats["右侧R出现>=2次"][0] += hit; stats["右侧R出现>=2次"][1] += 1
        else:
            stats["纯左侧L"][0] += hit; stats["纯左侧L"][1] += 1
            
        # 点位号特征
        if is_fill_point:
            stats["Excel品红底色点位"][0] += hit; stats["Excel品红底色点位"][1] += 1
        if is_daily_point:
            stats["daily_points点位"][0] += hit; stats["daily_points点位"][1] += 1
        if is_fill_point and is_daily_point:
            stats["双重点位背书(底色+文本)"][0] += hit; stats["双重点位背书(底色+文本)"][1] += 1

print(f"{'特征维度':<26} {'样本数':>6} {'命中数':>6} {'命中率':>8} {'相比大盘提升':>10}")
print("-" * 62)
base_h, base_t = stats["全部候选池"]
base_rate = base_h / base_t if base_t > 0 else 0.25

for k, (h, n) in sorted(stats.items(), key=lambda kv: -(kv[1][0]/kv[1][1] if kv[1][1]>0 else 0)):
    if n >= 20:
        rate = h / n
        lift = (rate - base_rate) / base_rate * 100
        print(f"{k:<26} {n:>6d} {h:>6d} {rate:>7.2%} {lift:>+9.1f}%")

# ═══ 探索2: 组合高胜率规则特征交叉 ═══
print("\n" + "=" * 60)
print("【多重特征强共振 (金胆特征组合挖掘)】")
print("=" * 60)

combo_stats = defaultdict(lambda: [0, 0])

for iss in issues:
    draw = draws[iss]
    prev_draw = draws.get(iss - 1, set())
    pdata = period_data[iss]
    pool = pdata['d1'] | pdata['d2']
    
    for n in pool:
        hit = 1 if n in draw else 0
        z = (n - 1) // 10
        t = n % 10
        is_repeat = (n in prev_draw)
        is_dual = (n in pdata['d1']) and (n in pdata['d2'])
        is_fill_point = (n in pdata['fill_points'])
        is_daily_point = (n in daily_points_map.get(iss, set()))
        sides = pdata['sides'][n]
        is_right = ('R' in sides)
        total_freq = pdata['d1_counts'][n] + pdata['d2_counts'][n]
        
        # 1. 经典R1: 尾2 + 0-3区 + 非重
        if t == 2 and z in (0,1,2,3) and not is_repeat:
            combo_stats["R1 (尾2_区0-3_非重)"][0] += hit; combo_stats["R1 (尾2_区0-3_非重)"][1] += 1
            if is_dual:
                combo_stats["R1 + 双数据共振"][0] += hit; combo_stats["R1 + 双数据共振"][1] += 1
            if is_right:
                combo_stats["R1 + 右侧"][0] += hit; combo_stats["R1 + 右侧"][1] += 1
            if is_daily_point or is_fill_point:
                combo_stats["R1 + 点位"][0] += hit; combo_stats["R1 + 点位"][1] += 1

        # 2. 尾7/8/3 优质组合
        if t in (7, 8, 3) and not is_repeat and z not in (4, 6):
            combo_stats["尾7/8/3_非弱区_非重"][0] += hit; combo_stats["尾7/8/3_非弱区_非重"][1] += 1
            if is_right:
                combo_stats["尾7/8/3_非弱区_非重 + 右侧"][0] += hit; combo_stats["尾7/8/3_非弱区_非重 + 右侧"][1] += 1
            if is_dual:
                combo_stats["尾7/8/3_非弱区_非重 + 双数据共振"][0] += hit; combo_stats["尾7/8/3_非弱区_非重 + 双数据共振"][1] += 1
            if is_daily_point or is_fill_point:
                combo_stats["尾7/8/3_非弱区_非重 + 点位"][0] += hit; combo_stats["尾7/8/3_非弱区_非重 + 点位"][1] += 1

        # 3. 双数据共振 + 非重 + 非弱区
        if is_dual and not is_repeat and z not in (4, 6):
            combo_stats["双数据共振_非弱区_非重"][0] += hit; combo_stats["双数据共振_非弱区_非重"][1] += 1
            if is_right:
                combo_stats["双数据共振_非弱区_非重 + 右侧"][0] += hit; combo_stats["双数据共振_非弱区_非重 + 右侧"][1] += 1

        # 4. 点位 + 非重 + 非弱区 + 右侧
        if (is_daily_point or is_fill_point) and not is_repeat and z not in (4, 6) and is_right:
            combo_stats["点位+右侧+非弱区_非重"][0] += hit; combo_stats["点位+右侧+非弱区_非重"][1] += 1

print(f"{'组合规则':<32} {'样本数':>6} {'命中数':>6} {'命中率':>8} {'提升幅度':>10}")
print("-" * 66)
for k, (h, n) in sorted(combo_stats.items(), key=lambda kv: -(kv[1][0]/kv[1][1] if kv[1][1]>0 else 0)):
    if n >= 15:
        rate = h / n
        lift = (rate - base_rate) / base_rate * 100
        print(f"{k:<32} {n:>6d} {h:>6d} {rate:>7.2%} {lift:>+9.1f}%")

