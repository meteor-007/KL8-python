# -*- coding: utf-8 -*-
"""规则选号器 — 多种升级策略回测对比
对比策略:
1. 原版 rule_picker (基线)
2. 升级版规则 V1 (精细分层 + 尾9纳新 + 弱尾0/6/4深度压制 + 多重右侧强加权)
3. 升级版规则 V2 (V1 + 动态冷热势头/遗漏回补修正 + 动态共现搭档加成)
4. 综合分层评估 (Top4 金胆率 / Top8 精选率 / Top12 大底率)
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

daily_points_map = {}
if POINTS_FILE.exists():
    for line in POINTS_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"date:[^,]+,period:(\d+),points:(.+)", line.strip())
        if m:
            daily_points_map[int(m.group(1))] = set(int(x) for x in m.group(2).split())

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

# ----------------- 策略1: 原版 rule_picker -----------------
def score_v0(n, iss, pdata):
    prev = draws.get(iss - 1, set())
    t = n % 10
    z = (n - 1) // 10
    sides = pdata['sides'][n]
    is_point = (n in pdata['fill_points'])
    
    if prev and n in prev:
        return 0.0
    if t == 2 and z in (5, 6, 7):
        return 0.5
    if 41 <= n <= 50 or 61 <= n <= 70:
        return 1.0
    score = 2.0
    if "R" in sides:
        score = 3.0
    if t in (7, 8, 3):
        score = 4.0 + (1.0 if "R" in sides else 0.0)
    if t == 2:
        score = 5.0
    if t == 2 and z in (0, 1, 2, 3):
        score = 6.0
    if is_point:
        score += 0.25
    return score

# ----------------- 策略2: 优化版 V1 (规则精细化) -----------------
def score_v1(n, iss, pdata):
    prev = draws.get(iss - 1, set())
    t = n % 10
    z = (n - 1) // 10
    sides = pdata['sides'][n]
    r_count = sides.count('R')
    is_point = (n in pdata['fill_points']) or (n in daily_points_map.get(iss, set()))
    
    # 1. 绝对死区与重号严控
    if prev and n in prev:
        return 0.0 # 重号直接排除
    if t == 2 and z in (5, 6, 7):
        return 0.2 # 52, 62, 72 极低
    if z == 6: # 61-70 区断崖弱区 (命中率仅18.6%)
        return 0.5
    if z == 4: # 41-50 区弱区
        return 0.8
    if t in (6, 0): # 尾6和尾0表现极其疲软 (21%左右)
        base = 1.2
    elif t in (4, 1):
        base = 1.6
    else:
        base = 2.0
        
    score = base
    
    # 2. 尾数层级 (纳新尾9，精分优质尾)
    if t == 2 and z in (0, 1, 2, 3):
        score = 6.0 # R1 王牌
    elif t == 8 and z in (0, 1, 2, 3, 7):
        score = 5.2 # 尾8 优质区
    elif t == 2:
        score = 4.8
    elif t in (7, 3, 9): # 尾7, 尾3, 尾9 (27%左右)
        score = 4.3
    
    # 3. 左右侧强弱修饰 (双R加权更高，纯L降权)
    if r_count >= 2:
        score += 1.2 # 双重右侧强信号
    elif r_count == 1:
        score += 0.8 # 单右侧
    else:
        score -= 0.5 # 纯左侧降权
        
    # 4. 点位与频次背书
    if is_point:
        score += 0.35
    if pdata['d1_counts'][n] > 0 and pdata['d2_counts'][n] > 0:
        score += 0.3 # 双数据共振
        
    return score

# ----------------- 策略3: 优化版 V2 (V1 + 近期动态走势 + 选2连体共现) -----------------
# 预计算前N期的共现矩阵
def get_cooccur(iss, window=40):
    train_issues = [i for i in issues if iss - window <= i < iss]
    co = defaultdict(lambda: defaultdict(int))
    freq = defaultdict(int)
    for ti in train_issues:
        nums = draws[ti]
        for n1 in nums:
            freq[n1] += 1
            for n2 in nums:
                if n1 != n2:
                    co[n1][n2] += 1
    return co, freq, len(train_issues)

def score_v2_ranked(pool, iss, pdata):
    # 先算出 V1 初始分
    scores = {n: score_v1(n, iss, pdata) for n in pool}
    sorted_initial = sorted(scores.items(), key=lambda kv: -kv[1])
    
    # 找出初始分最高的前2个王牌金胆
    top_kings = [n for n, sc in sorted_initial[:2] if sc >= 5.0]
    
    # 如果有王牌金胆，根据历史连体共现（MK跟班/双元协同）提携搭档
    if top_kings:
        co, freq, n_wins = get_cooccur(iss, window=45)
        if n_wins > 0:
            for n in scores:
                if n not in top_kings:
                    # 算与王牌金胆的平均共现提升
                    boost = 0.0
                    for king in top_kings:
                        pair_cnt = co[king][n]
                        # 理论期望共现率约为 20/80 * 19/79 ≈ 0.06
                        actual_rate = pair_cnt / n_wins
                        if actual_rate >= 0.12: # 显著高共现
                            boost += 0.5
                        elif actual_rate <= 0.02: # 严重相克
                            boost -= 0.3
                    scores[n] += boost
                    
    # 近期走势微调: 计算该号码过去5期的出号频率 (避免3连出过度透支，抓1-2期温热回补)
    prev_5 = [draws.get(iss - k, set()) for k in range(1, 6)]
    for n in scores:
        hits_5 = sum(1 for d in prev_5 if n in d)
        if hits_5 >= 3: # 5期出3次，热度过载，均值回归降温
            scores[n] -= 0.6
        elif hits_5 == 1 or hits_5 == 2: # 温号正当时
            scores[n] += 0.25
        elif hits_5 == 0: # 遗漏5期以上冷号
            # 冷号如果没有强规则背书，不盲目抓
            if scores[n] < 4.0:
                scores[n] -= 0.3
                
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked

# ═══ 全量 Walk-Forward 回测评估 ═══
print("\n" + "=" * 65)
print("【策略实盘 Walk-Forward 回测对比 (无前视逐期滚动)】")
print("=" * 65)

# 我们从第 30 期开始作为严格无前视测试集
test_issues = issues[30:]
print(f"回测测试区间: {test_issues[0]} 到 {test_issues[-1]} (共 {len(test_issues)} 期)")

metrics = {
    "V0_基线": {"top4": [], "top8": [], "top12": []},
    "V1_规则精细化": {"top4": [], "top8": [], "top12": []},
    "V2_动态协同版": {"top4": [], "top8": [], "top12": []},
}

for iss in test_issues:
    draw = draws[iss]
    pdata = period_data[iss]
    pool = list(pdata['d1'] | pdata['d2'])
    
    # 1. V0
    v0_ranked = sorted([(score_v0(n, iss, pdata), n) for n in pool], key=lambda kv: (-kv[0], kv[1]))
    v0_picks = [n for _, n in v0_ranked]
    metrics["V0_基线"]["top4"].append(len(set(v0_picks[:4]) & draw))
    metrics["V0_基线"]["top8"].append(len(set(v0_picks[:8]) & draw))
    metrics["V0_基线"]["top12"].append(len(set(v0_picks[:12]) & draw))
    
    # 2. V1
    v1_ranked = sorted([(score_v1(n, iss, pdata), n) for n in pool], key=lambda kv: (-kv[0], kv[1]))
    v1_picks = [n for _, n in v1_ranked]
    metrics["V1_规则精细化"]["top4"].append(len(set(v1_picks[:4]) & draw))
    metrics["V1_规则精细化"]["top8"].append(len(set(v1_picks[:8]) & draw))
    metrics["V1_规则精细化"]["top12"].append(len(set(v1_picks[:12]) & draw))
    
    # 3. V2
    v2_ranked = score_v2_ranked(pool, iss, pdata)
    v2_picks = [n for n, _ in v2_ranked]
    metrics["V2_动态协同版"]["top4"].append(len(set(v2_picks[:4]) & draw))
    metrics["V2_动态协同版"]["top8"].append(len(set(v2_picks[:8]) & draw))
    metrics["V2_动态协同版"]["top12"].append(len(set(v2_picks[:12]) & draw))

print(f"\n{'策略名称':<16} | {'Top4 金胆命中':>12} (命中率) | {'Top8 精选命中':>12} (命中率) | {'Top12 大底命中':>13} (命中率)")
print("-" * 75)
for name, res in metrics.items():
    m4 = statistics.mean(res["top4"])
    r4 = m4 / 4.0
    m8 = statistics.mean(res["top8"])
    r8 = m8 / 8.0
    m12 = statistics.mean(res["top12"])
    r12 = m12 / 12.0
    print(f"{name:<16} | {m4:>6.2f} 个 ({r4:>6.2%}) | {m8:>6.2f} 个 ({r8:>6.2%}) | {m12:>7.2f} 个 ({r12:>6.2%})")

# 算一下最近30期的短期爆发表现
print("\n" + "=" * 65)
print("【近 30 期短期爆发表现 (近期实战盘面)】")
print("=" * 65)
print(f"{'策略名称':<16} | {'Top4 金胆命中':>12} (命中率) | {'Top8 精选命中':>12} (命中率) | {'Top12 大底命中':>13} (命中率)")
print("-" * 75)
for name, res in metrics.items():
    m4 = statistics.mean(res["top4"][-30:])
    r4 = m4 / 4.0
    m8 = statistics.mean(res["top8"][-30:])
    r8 = m8 / 8.0
    m12 = statistics.mean(res["top12"][-30:])
    r12 = m12 / 12.0
    print(f"{name:<16} | {m4:>6.2f} 个 ({r4:>6.2%}) | {m8:>6.2f} 个 ({r8:>6.2%}) | {m12:>7.2f} 个 ({r12:>6.2%})")

