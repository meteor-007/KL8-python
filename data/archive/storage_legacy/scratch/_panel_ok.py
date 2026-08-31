# -*- coding: utf-8 -*-
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

he5 = [11, 12, 33, 74, 79]
trinity5 = [10, 11, 12, 33, 69]
trinity12 = [10, 11, 12, 29, 31, 33, 34, 55, 69, 73, 74, 79]
ai5 = [60, 11, 15, 24, 33]
ai12 = [60, 11, 15, 24, 33, 34, 45, 4, 12, 30, 58, 66]
golden = [10, 11, 12, 33, 69, 73]
mrmr = [77, 33, 12, 39, 69, 38, 30, 20, 42, 27, 6, 11]
pure_hi = [53, 73, 2]
fo5 = [12, 31, 33, 40, 73]
excel5 = [73, 33, 77, 30, 69]
plan2 = [6, 30, 21, 70, 12]

core = {
    "HE5": he5,
    "Trinity5": trinity5,
    "AI5": ai5,
    "mRMR": mrmr,
    "PureHi": pure_hi,
    "Golden": golden,
    "FO5": fo5,
    "Excel5": excel5,
}
pool = defaultdict(list)
for k, nums in core.items():
    for n in nums:
        if k not in pool[n]:
            pool[n].append(k)

FDR = {3, 11, 15, 69}
tiers = {4: [], 3: [], 2: [], 1: []}
for n, srcs in sorted(pool.items(), key=lambda x: (-len(x[1]), x[0])):
    lv = min(4, len(srcs))
    tag = " [FDR]" if n in FDR else ""
    tiers[lv].append((n, srcs, tag))


def fmt(a):
    return " ".join(f"{x:02d}" for x in sorted(a))


def join_src(srcs):
    return "+".join(srcs)


print()
print("=" * 74)
print("  快乐8 每日分析完整面板  |  2026-07-17  |  目标期 2026188")
print("=" * 74)
print()
print("[昨日2026187对账] 开奖 31-72-11-09-62-78-34-38-57-08-75-27-02-55-25-69-12-15-03-33")
print("  * HE5 3/5 Lift=2.40x 命中[12,27,38]")
print("  * Pure 3/5 Lift=2.40x 命中[2,27,69]")
print("  * AI12 5/12 Lift=1.67x 命中[3,9,11,25,57]")
print("  * Trinity5 2/5 Lift=1.60x | mRMR 4/12 Lift=1.33x | 方案2防守3/3")
print("  近10期: HE5=20%(0.80x) Trinity5=20%(0.80x) AI5=32%(1.28x)")
print("  闭环: WF Lift=1.0043冻结 | EF0.40 RW0.30 FO0.30 | 不新增优化")
print()
print("[今日核心推荐 2026188] 平衡震荡 | EF0.50 RW0.20 FO0.30 | B3=0.86 | Level1 0.5x")
print("  KL=0.0716 (-0.56 Sigma 未熔断)")
print("-" * 74)
print(f"  HE5 Hidden Energy5 : {fmt(he5)}")
print("      12 EF=2.47 RW=0.08 FO=24.50 Score=14.79")
print("      33 EF=2.57 RW=0.08 FO=22.16 Score=13.71")
print("      11 EF=2.96 RW=0.08 FO=18.44 Score=12.25")
print("      74 EF=0.52 RW=0.43 FO=21.00 Score=11.36")
print("      79 EF=0.59 RW=0.35 FO=20.00 Score=10.88")
print(f"  AI Top5            : {fmt(ai5)}")
print(f"  AI Top12           : {fmt(ai12)}")
print(f"  Trinity Top5       : {fmt(trinity5)}")
print(f"  Trinity Top12      : {fmt(trinity12)}")
print(f"  Golden Core        : {fmt(golden)}")
print(f"  纯净池高置信       : {fmt(pure_hi)}  (全池 02 15 25 27 33 38 53 69 73)")
print(f"  mRMR Top12         : {fmt(mrmr)}")
print(f"  FO金胆Top5         : {fmt(fo5)}")
print(f"  方案2爆发Top5      : {fmt(plan2)}")
print(f"  Excel精选5         : {fmt(excel5)}")
print("  方案2防守杀号       : 08 16 42")
print()
print("[内部共振提纯]")
print("  **** 钻石级(>=4):")
if tiers[4]:
    for n, s, t in tiers[4]:
        print(f"      {n:02d} <- {join_src(s)}{t}")
else:
    print("      (无)")
print("  ***  金级(3):")
for n, s, t in tiers[3]:
    print(f"      {n:02d} <- {join_src(s)}{t}")
print("  **   银级(2):")
for n, s, t in tiers[2]:
    print(f"      {n:02d} <- {join_src(s)}{t}")
print(f"  *    铜级: {len(tiers[1])}个")
conflict = [n for n in he5 if n not in set(trinity12)]
print(f"  HE5不在Trinity12: {conflict or '无矛盾'}")
print("  优先关注: 11 / 12 / 33 (多模块共振 + HE5核心)")
print("=" * 74)

path = "reports/daily_analysis_report_20260717.md"
t = open(path, encoding="utf-8").read()
t = re.sub(r"\n## 附录 B：内部多模块共振提纯[\s\S]*", "", t)
lines = [
    "\n\n## 附录 B：内部多模块共振提纯 (2026-07-17)\n\n",
    "| 等级 | 号码 | 来源模块 |\n|------|------|----------|\n",
]
for title, items in [("钻石", tiers[4]), ("金", tiers[3]), ("银", tiers[2])]:
    for n, s, tag in items:
        lines.append(f"| {title} | {n:02d} | {join_src(s)}{tag} |\n")
lines.append(f"\n- HE5不在Trinity12: {conflict or '无'}\n")
lines.append("- 优化结论: 维持现状，不新增方案\n")
lines.append("- 近10期 HE5 Lift0.80 / AI5 Lift1.28；昨日HE5爆发3/5 Lift2.40\n")
open(path, "w", encoding="utf-8").write(t + "".join(lines))
print("[已更新] 附录B ->", path)
