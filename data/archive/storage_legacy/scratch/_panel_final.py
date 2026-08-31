# -*- coding: utf-8 -*-
import re, json, os, sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPORT = "reports/daily_analysis_report_20260717.md"
text = open(REPORT, encoding="utf-8").read()

def grab(pat):
    m = re.search(pat, text)
    return [int(x) for x in re.findall(r"\d+", m.group(1))] if m else []

he5 = grab(r"最终推荐 \(5 码\)[：:]\s*`\[([^\]]+)\]`")
trinity5 = grab(r"极秘 Top 5[：:]\s*`\[([^\]]+)\]`")
trinity12 = grab(r"极秘 Top 12[：:]\s*`\[([^\]]+)\]`")
ai5 = grab(r"Top 5 置信度精选[：:]\s*`\[([^\]]+)\]`")
ai12 = grab(r"Top 12 综合拦截[：:]\s*`\[([^\]]+)\]`")
golden = grab(r"高频共振集群[：:]\s*`\[([^\]]+)\]`")
mrmr = grab(r"mRMR Top 12[：:]\s*`\[([^\]]+)\]`")
pure = grab(r"纯净池号码[：:]\s*`\[([^\]]+)\]`")
pure_hi = grab(r"高置信定胆[^\n]*`\[([^\]]+)\]`")
fo5 = grab(r"金胆 Top5[：:]\s*`\[([^\]]+)\]`")
plan2 = [6, 30, 21, 70, 12]
excel5 = [73, 33, 77, 30, 69]

he5_detail = re.findall(
    r"号码 `(\d+)`: EF `([\d.]+)` \| RW `([\d.]+)` \| FO `([\d.]+)` \| 综合动能 `([\d.]+)`",
    text,
)

core = {
    "HE5": he5, "Trinity5": trinity5, "AI5": ai5, "mRMR": mrmr,
    "PureHi": pure_hi or pure[:3], "Golden": golden, "FO5": fo5,
}
pool = defaultdict(list)
for k, nums in core.items():
    for n in nums:
        if k not in pool[n]:
            pool[n].append(k)

FDR = {3, 11, 15, 69}
diamond, gold, silver, copper = [], [], [], []
for n, srcs in sorted(pool.items(), key=lambda x: (-len(x[1]), x[0])):
    tag = " FDR" if n in FDR else ""
    e = (n, srcs, tag)
    if len(srcs) >= 4: diamond.append(e)
    elif len(srcs) == 3: gold.append(e)
    elif len(srcs) == 2: silver.append(e)
    else: copper.append(e)

def fmt(nums):
    return " ".join(f"{n:02d}" for n in sorted(nums)) if nums else "(无)"

actual = {31,72,11,9,62,78,34,38,57,8,75,27,2,55,25,69,12,15,3,33}
y = {
    "HE5":[12,27,38,47,73], "Trinity5":[10,27,29,67,69],
    "Trinity12":[6,10,27,29,40,42,45,47,66,67,69,73],
    "AI5":[7,11,45,67,80], "AI12":[7,11,45,67,80,3,9,25,30,57,58,73],
    "Golden":[6,10,42,45,69,73], "Pure":[2,27,53,69,80],
    "mRMR":[77,33,12,39,69,30,20,27,66,54,42,6],
}

print()
print("=" * 74)
print("  快乐8 每日全流程分析  |  2026-07-17  |  目标期 2026188")
print("=" * 74)
print()
print("[任务2] 2026187 开奖对账")
print("  开奖: 31-72-11-09-62-78-34-38-57-08-75-27-02-55-25-69-12-15-03-33")
print("  " + "-" * 70)
for name, nums in y.items():
    hits = sorted(set(nums) & actual)
    h, k = len(hits), len(nums)
    lift = (h / k) / 0.25
    star = "*" if lift >= 1.5 else " "
    print(f"  {star} {name:12s} {h}/{k:<2d}  Lift={lift:.2f}x  命中{hits}")
print("  >> HE5/Pure 爆发 3/5 (Lift 2.40x); AI12=5/12 (1.67x); 方案2防守 3/3")
print()
print("[近10期趋势]  HE5=20%(Lift0.80)  Trinity5=20%(0.80)  AI5=32%(1.28)")
print("[闭环学习]    WF Lift=1.0043 < 1.1 → 自学习冻结 | EF0.40/RW0.30/FO0.30 | balanced")
print("[任务3]       整体未显著优于随机基线，不新增优化方案，维持现状。")
print()
print("=" * 74)
print("[今日核心推荐] 目标期 2026188")
print("  环境=平衡震荡期 | 动态权重 EF:0.50 RW:0.20 FO:0.30 | B3=0.86")
print("  信标=Level 1 (0.5x 弱信号防御) | KL=0.0716 (-0.56 Sigma, 未熔断)")
print("  " + "-" * 70)
print(f"  [HE5] Hidden Energy 5 : {fmt(he5)}")
for n, ef, rw, fo, sc in he5_detail:
    print(f"         {int(n):02d}  EF={ef}  RW={rw}  FO={fo}  Score={sc}")
print(f"  [AI ] Top5            : {fmt(ai5)}")
print(f"  [AI ] Top12           : {fmt(ai12)}")
print(f"  [TRI] Trinity Top5    : {fmt(trinity5)}")
print(f"  [TRI] Trinity Top12   : {fmt(trinity12)}")
print(f"  [GC ] Golden Core     : {fmt(golden)}")
print(f"  [PURE]纯净池(全)      : {fmt(pure)}")
print(f"  [PURE]高置信定胆      : {fmt(pure_hi)}")
print(f"  [MRMR] mRMR Top12     : {fmt(mrmr)}")
print(f"  [FO ] FO金胆Top5      : {fmt(fo5)}")
print(f"  [P2 ] 方案2爆发Top5   : {fmt(plan2)}")
print(f"  [XL ] Excel精选5      : {fmt(excel5)}")
print(f"  [KILL]方案2防守       : 16 42 08")
print()
print("=" * 74)
print("[任务4.5] 内部多模块共振提纯")
print("  " + "-" * 70)

def show(title, items, limit=20):
    print(f"  {title}")
    if not items:
        print("    (无)")
        return
    for n, srcs, tag in items[:limit]:
        print(f"    {n:02d}  <-  {'+'.join(srcs)}{tag}")

show("**** 钻石级 (>=4模块)", diamond)
show("***  金级   (3模块)", gold)
show("**   银级   (2模块)", silver, 15)
print(f"  *    铜级独有: {len(copper)} 个 (单模块信号, 不建议重仓)")
conflict = [n for n in he5 if n not in set(trinity12)]
print("  " + "-" * 70)
print(f"  三维自洽 HE5不在Trinity12: {conflict if conflict else '无矛盾'}")
print("  权重风险: EF=0.50 触顶(<=0.50), RW偏低0.20 — 可接受, 不调参")
print("  提纯结论: 钻石/金级优先; 区分力待下期回验, 阈值维持>=4")
print()
print("=" * 74)
print("[修复记录]")
print("  1. process_hot_numbers.py: shape异常由静默return改为raise RuntimeError")
print("  2. 抓取补齐 2026187; 热码/跟随同步至 2026188; 格式化双期完成")
print("  3. Rapid Blast / deep_resonance 已移除, 无残留活动代码")
print()
print("[报告] reports/daily_analysis_report_20260717.md")
print("=" * 74)

# 追加附录B(若尚未存在)
if "附录 B：内部多模块共振提纯" not in text:
    lines = ["\n\n## 附录 B：内部多模块共振提纯 (2026-07-17)\n\n"]
    lines.append("| 等级 | 号码 | 来源模块 |\n|------|------|----------|\n")
    for title, items in [("钻石", diamond), ("金", gold), ("银", silver)]:
        for n, srcs, tag in items:
            lines.append(f"| {title} | {n:02d} | {'+'.join(srcs)}{tag} |\n")
    lines.append(f"\n- HE5∉Trinity12: {conflict or '无'}\n")
    lines.append("- 优化结论: 维持现状，不新增方案\n")
    lines.append("- 近10期: HE5 Lift0.80 / AI5 Lift1.28；昨日HE5爆发3/5\n")
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write("".join(lines))
    print("[已追加] 附录B")
else:
    print("[附录B] 已存在, 跳过")
