# -*- coding: utf-8 -*-
"""回溯验证脚本: 最近3期无前视滚动回测
期号: 2026215, 2026216, 2026217
对每一期:
1. 仅使用该期之前的开奖历史 (严格屏蔽当期及未来数据)
2. 运行 Rule Picker V2.0 逻辑生成:
   - 核心 Top4 金胆与选2/选3 组合
   - 稳健精选 8 码大底
3. 打印真实的开奖号码和详细命中情况
"""
import openpyxl, re, sys, statistics
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "跟随+点位+开奖数据.xlsx"
HIST = ROOT / "kl8_history_final.txt"
POINTS_FILE = ROOT / "daily_points.txt"
POINT_FILLS = ("FFFCE4EC", "00FCE4EC")

# 1. 加载开奖历史
draws = {}
if HIST.exists():
    for line in HIST.read_text(encoding="utf-8").splitlines():
        m = re.match(r"date:[^,]+,period:(\d+),numbers:(.+)", line.strip())
        if m:
            draws[int(m.group(1))] = set(int(x) for x in m.group(2).split("-"))

daily_points_map = {}
if POINTS_FILE.exists():
    for line in POINTS_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"date:[^,]+,period:(\d+),points:(.+)", line.strip())
        if m:
            daily_points_map[int(m.group(1))] = set(int(x) for x in m.group(2).split())

# 2. 解析跟随表
wb = openpyxl.load_workbook(XLSX, data_only=False)
ws = wb["跟随号码统计"]
all_rows = list(ws.iter_rows())

periods = {}
for ridx, row in enumerate(all_rows):
    v = str(row[0].value or "").strip()
    m = re.search(r"(\d{7})期[\s\S]*?数据(1|2)", v)
    if not m:
        continue
    iss = int(m.group(1))
    dtype = int(m.group(2))
    pc = periods.setdefault(
        iss,
        {
            "d1": set(),
            "d2": set(),
            "d1_counts": defaultdict(int),
            "d2_counts": defaultdict(int),
            "sides": defaultdict(list),
            "points": set(),
        },
    )
    for off in (1, 6, 11, 16):
        for off2 in range(4):
            idx = ridx + off + off2
            if idx >= len(all_rows):
                continue
            trow = all_rows[idx]
            cells = []
            for c in range(min(10, len(trow))):
                cell = trow[c]
                cv = str(cell.value or "").strip()
                if cv and cv != "nan":
                    if "*" in cv:
                        cells.append((c, int(cv.replace("*", ""))))
                    if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb in POINT_FILLS:
                        pc["points"].add(int(cv.replace("*", "")))
            cells.sort()
            for si, (c, n) in enumerate(cells):
                side = "R" if c >= 5 else "L"
                pc["sides"][n].append(side)
                if dtype == 1:
                    pc["d1"].add(n)
                    pc["d1_counts"][n] += 1
                else:
                    pc["d2"].add(n)
                    pc["d2_counts"][n] += 1

def run_backtest_for_period(target_iss):
    # 严格屏蔽当期及未来开奖数据: 仅使用 < target_iss 的历史
    history_draws = {k: v for k, v in draws.items() if k < target_iss}
    actual_draw = draws.get(target_iss, set())
    
    pc = periods.get(target_iss)
    if not pc:
        print(f"期号 {target_iss} 无数据")
        return

    # 1. 连体共现矩阵 (严格基于 target_iss 前 45 期)
    valid_issues = sorted(i for i in history_draws if target_iss - 45 <= i < target_iss)
    co = defaultdict(lambda: defaultdict(int))
    for ti in valid_issues:
        nums = history_draws[ti]
        for n1 in nums:
            for n2 in nums:
                if n1 != n2:
                    co[n1][n2] += 1
    n_wins = len(valid_issues)

    # 2. 候选池打分
    pool = pc["d1"] | pc["d2"]
    prev = history_draws.get(target_iss - 1, set())
    
    base_scores = {}
    tag_map = {}
    for n in pool:
        t = n % 10
        z = (n - 1) // 10
        sides = pc["sides"][n]
        r_count = sides.count("R")
        is_fill_point = n in pc["points"]
        is_daily_point = n in daily_points_map.get(target_iss, set())
        is_point = is_fill_point or is_daily_point

        if prev and n in prev:
            base_scores[n] = 0.0
            tag_map[n] = "重号⚠(排除)"
            continue
        if t == 2 and z in (5, 6, 7):
            base_scores[n] = 0.2
            tag_map[n] = "尾2区5-7✗(极低)"
            continue
        if z == 6:
            base_scores[n] = 0.5
            tag_map[n] = "弱区61-70✗"
            continue
        if z == 4:
            base_scores[n] = 0.8
            tag_map[n] = "弱区41-50✗"
            continue

        tags = []
        if t in (6, 0):
            base = 1.2
            tags.append(f"弱尾{t}")
        elif t in (4, 1):
            base = 1.6
            tags.append(f"平尾{t}")
        else:
            base = 2.0

        score = base
        if t == 2 and z in (0, 1, 2, 3):
            score = 6.0
            tags.append("R1尾2区0-3★")
        elif t == 8 and z in (0, 1, 2, 3, 7):
            score = 5.2
            tags.append("优质尾8")
        elif t == 2:
            score = 4.8
            tags.append("R2尾2")
        elif t in (7, 3, 9):
            score = 4.3
            tags.append(f"优质尾{t}")

        if r_count >= 2:
            score += 1.2
            tags.append(f"双R右侧({r_count})")
        elif r_count == 1:
            score += 0.8
            tags.append("右侧R")
        else:
            score -= 0.5
            tags.append("纯左L")

        if is_point:
            score += 0.35
            tags.append("点位背书")
        if pc["d1_counts"][n] > 0 and pc["d2_counts"][n] > 0:
            score += 0.30
            tags.append("双数据共振")

        base_scores[n] = score
        tag_map[n] = "+".join(tags)

    # 连体提携
    sorted_initial = sorted(base_scores.items(), key=lambda kv: -kv[1])
    top_kings = [n for n, sc in sorted_initial[:2] if sc >= 5.0]
    final_scores = dict(base_scores)

    if top_kings and n_wins >= 10:
        for n in pool:
            if n not in top_kings and final_scores[n] > 1.0:
                boost = 0.0
                for king in top_kings:
                    pair_cnt = co[king][n]
                    actual_rate = pair_cnt / n_wins
                    if actual_rate >= 0.12:
                        boost += 0.50
                        tag_map[n] += "+连体搭档"
                    elif actual_rate <= 0.02:
                        boost -= 0.30
                final_scores[n] += boost

    # 动态控温
    prev_5 = [history_draws.get(target_iss - k, set()) for k in range(1, 6) if (target_iss - k) in history_draws]
    if prev_5:
        for n in pool:
            hits_5 = sum(1 for d in prev_5 if n in d)
            if hits_5 >= 3:
                final_scores[n] -= 0.60
                tag_map[n] += "+过热控温"
            elif hits_5 in (1, 2):
                final_scores[n] += 0.25
            elif hits_5 == 0 and final_scores[n] < 4.0:
                final_scores[n] -= 0.30

    ranked = [(final_scores[n], n, tag_map[n]) for n in pool]
    ranked.sort(key=lambda kv: (-kv[0], kv[1]))

    # 取各层号码
    top4 = [n for _, n, _ in ranked[:4]]
    top8 = [n for _, n, _ in ranked[:8]]
    
    # 构造组合
    pair1 = (top4[0], top4[1]) if len(top4) >= 2 else ()
    pair2 = (top4[0], top4[3]) if len(top4) >= 4 else ()
    trio1 = (top4[0], top4[1], top4[3]) if len(top4) >= 4 else ()
    trio2 = (top4[0], top4[2], top4[3]) if len(top4) >= 4 else ()

    print("=" * 70)
    print(f"【目标期: {target_iss} 期 无前视回测】 (开奖时间前真实预测状态)")
    print(f"当期实际开奖 ({len(actual_draw)}码): {sorted(actual_draw)}")
    print("-" * 70)
    
    # 1. 核心定金选2 / 选3 命中详情
    print("🎯 【1. 定金选2 / 选3 核心组合命中详情】")
    p1_hit = sum(1 for x in pair1 if x in actual_draw)
    p2_hit = sum(1 for x in pair2 if x in actual_draw)
    t1_hit = sum(1 for x in trio1 if x in actual_draw)
    t2_hit = sum(1 for x in trio2 if x in actual_draw)
    
    p1_status = "🎉【全中 2/2】" if p1_hit == 2 else f"命中 {p1_hit}/2"
    p2_status = "🎉【全中 2/2】" if p2_hit == 2 else f"命中 {p2_hit}/2"
    t1_status = "🔥【中2-3码】" if t1_hit >= 2 else f"命中 {t1_hit}/3"
    t2_status = "🔥【中2-3码】" if t2_hit >= 2 else f"命中 {t2_hit}/3"

    print(f"  • 双飞组 1 [{pair1[0]:02d} - {pair1[1]:02d}]: {p1_status} (中: {[x for x in pair1 if x in actual_draw]})")
    print(f"  • 双飞组 2 [{pair2[0]:02d} - {pair2[1]:02d}]: {p2_status} (中: {[x for x in pair2 if x in actual_draw]})")
    print(f"  • 核心选3-A [{trio1[0]:02d} - {trio1[1]:02d} - {trio1[2]:02d}]: {t1_status} (中: {[x for x in trio1 if x in actual_draw]})")
    print(f"  • 核心选3-B [{trio2[0]:02d} - {trio2[1]:02d} - {trio2[2]:02d}]: {t2_status} (中: {[x for x in trio2 if x in actual_draw]})")
    
    # 2. 稳健精选 8 码大底命中详情
    print("\n🛡️ 【2. 稳健精选 8 码大底命中详情】")
    top8_hit_nums = [x for x in top8 if x in actual_draw]
    print(f"  • 预测 8 码: {' '.join(f'{x:02d}' for x in top8)}")
    print(f"  • 实际命中: {' '.join(f'{x:02d}' for x in sorted(top8_hit_nums))} ({len(top8_hit_nums)}/8 = {len(top8_hit_nums)/8:.1%})")
    print("  • 8码明细评分与中奖情况:")
    for idx, (sc, n, tstr) in enumerate(ranked[:8], 1):
        hit_mark = "✅ 命中" if n in actual_draw else "❌ 未出"
        print(f"    第{idx}名 [{n:02d}] (得分 {sc:4.2f}): {hit_mark} | 标签: {tstr}")
    print()

for iss in [2026215, 2026216, 2026217]:
    run_backtest_for_period(iss)
