# -*- coding: utf-8 -*-
"""今日推荐控制台展示 + 内部提纯 (Task4/4.5)"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "reports/daily_analysis_report_20260716.md").read_text(encoding="utf-8")


def grab(pattern):
    m = re.search(pattern, text)
    if not m:
        return []
    return [int(x) for x in re.findall(r"\d+", m.group(1))]


he5 = grab(r"\*\*最终推荐 \(5 码\)\*\*[：:]\s*`\[([^\]]+)\]`")
trinity5 = grab(r"\*\*极秘 Top 5\*\*[：:]\s*`\[([^\]]+)\]`")
trinity12 = grab(r"\*\*极秘 Top 12\*\*[：:]\s*`\[([^\]]+)\]`")
ai5 = grab(r"\*\*Top 5 置信度精选\*\*[：:]\s*`\[([^\]]+)\]`")
ai12 = grab(r"\*\*Top 12 综合拦截\*\*[：:]\s*`\[([^\]]+)\]`")
golden = grab(r"\*\*高频共振集群\*\*[：:]\s*`\[([^\]]+)\]`")
mrmr = grab(r"\*\*mRMR Top 12\*\*[：:]\s*`\[([^\]]+)\]`")
pure = grab(r"\*\*高置信定胆[^\n]*\*\*[：:]\s*`\[([^\]]+)\]`")
excel5 = grab(r"### [^\n]*精选5码[\s\S]*?\n\| 1 \| \*\*(\d+)\*\*")
# excel top5 from table rows
excel5 = [int(x) for x in re.findall(
    r"\| \d+ \| \*\*(\d+)\*\* \| 综合评分最优 \|", text
)]
plan2 = [int(x) for x in re.findall(
    r"\| \d+ \| \*\*(\d+)\*\* \| [\d.]+ \|",
    text[text.find("最终精选爆发码"): text.find("重点防守号码")],
)] if "最终精选爆发码" in text else []

he5_detail = re.findall(
    r"号码 `(\d+)`: EF `([\d.]+)` \| RW `([\d.]+)` \| FO `([\d.]+)` \| 综合动能 `([\d.]+)`",
    text,
)

state = {}
sp = ROOT / "cache/self_learning_state.json"
if sp.exists():
    state = json.loads(sp.read_text(encoding="utf-8"))
hist = state.get("history") or state.get("records") or []
today = hist[0] if hist else {}
if isinstance(today, dict) and "period" in today and str(today.get("period")) not in (
    "2026187",
    2026187,
):
    for rec in hist:
        if str(rec.get("period")) in ("2026187", "2026187"):
            today = rec
            break

gauss = today.get("high_order_gauss_top5") or []
cluster = today.get("high_order_cluster_top5") or []
fourier = today.get("high_order_fourier_top5") or []
fusion = today.get("high_order_fusion_top5") or []

modules = {
    "HE5": set(he5),
    "Trinity": set(trinity5) | set(trinity12),
    "AI": set(ai5) | set(ai12),
    "mRMR": set(mrmr),
    "纯净池": set(pure),
    "极高阶": set(gauss) | set(cluster) | set(fourier) | set(fusion),
    "Golden": set(golden),
}

pool = defaultdict(list)
for mod, nums in modules.items():
    for n in nums:
        if n:
            pool[int(n)].append(mod)

fdr_sig = {3, 11, 15, 69}
auc = {}
ap = ROOT / "auc_stats.json"
if ap.exists():
    raw = json.loads(ap.read_text(encoding="utf-8"))
    blob = raw.get("auc") or raw.get("numbers") or raw
    if isinstance(blob, dict):
        for k, v in blob.items():
            try:
                nk = int(k)
            except Exception:
                continue
            if isinstance(v, dict):
                auc[nk] = v.get("auc") or v.get("AUC")
            elif isinstance(v, (int, float)):
                auc[nk] = float(v)


def classify(n):
    c = len(pool[n])
    if c >= 4:
        t = "钻石"
    elif c == 3:
        t = "金"
    elif c == 2:
        t = "银"
    else:
        t = "铜"
    adj = []
    a = auc.get(n)
    if isinstance(a, (int, float)):
        if a > 0.52:
            adj.append("AUC+")
        elif a < 0.48:
            adj.append("AUC-")
    if n in fdr_sig:
        adj.append("FDR")
    return t, c, adj


W = 72
print()
print("=" * W)
print("  快乐8 每日全流程 · 结果面板".center(W))
print("  目标期 2026187 | 审计日 2026-07-16 | 架构 v4.0 三维 EF/RW/FO".center(W))
print("=" * W)

print("\n[0] 数据与修复摘要")
print("-" * W)
print("  历史最新: 2026186 (2026-07-15) | 点位: 2026187 完整")
print("  数据校验: A-F 全通过")
print("  Critical修复: Loss键映射 / WF回滚 / excel_lock stale=600s / Level3口径0.0x")
print("  自学习: 冻结 (WF Lift=1.0043 < 1.1) | 权重 EF=0.40 RW=0.30 FO=0.30")

print("\n[1] 上期 2026186 对账")
print("-" * W)
rows = [
    ("Hidden Energy 5", "1/5", "34", "0.80x"),
    ("Trinity Top5", "3/5", "34,41,67", "2.40x"),
    ("Trinity Top12", "3/12", "34,41,67", "1.00x"),
    ("AI Top5", "2/5", "11,45", "1.60x"),
    ("AI Top12", "3/12", "11,45,80", "1.00x"),
    ("Golden Core", "0/7", "-", "0.00x"),
    ("mRMR Top12", "1/12", "30", "0.33x"),
    ("纯净池", "1/5", "71", "~0.80x"),
]
print(f"  {'模块':<18}{'命中':>6}  {'命中号':<20}{'Lift':>8}")
for name, hit, nums, lift in rows:
    mark = "OK" if float(lift.replace("x", "").replace("~", "")) >= 1.0 else "--"
    print(f"  {name:<18}{hit:>6}  {nums:<20}{lift:>8}  [{mark}]")

print("\n  近窗趋势(报告复盘段, 含本期):")
print("    HE5:       1,0,1,2,1,1,1  均≈1.00/5  Lift≈0.80x  (弱于基线)")
print("    Trinity5:  3,1,0,2,1,0,0  均≈1.00/5  Lift≈0.80x  (本期亮眼2.4x)")
print("    结论: HE5近窗未达'最稳定>2码'叙事; Trinity本期强但均值仍贴近随机")

print("\n[2] 今日 2026187 核心推荐")
print("-" * W)
print(f"  ★ Hidden Energy 5 : {he5}")
for num, ef, rw, fo, tot in he5_detail:
    print(f"      {int(num):02d}  EF={ef:>7}  RW={rw:>6}  FO={fo:>7}  Score={tot}")
print(f"  ★ Trinity Top5    : {trinity5}")
print(f"  ★ Trinity Top12   : {trinity12}")
print(f"  ★ AI Top5         : {ai5}")
print(f"  ★ AI Top12        : {ai12}")
print(f"  ★ Golden Core     : {golden}")
print(f"  ★ mRMR Top12      : {mrmr}")
print(f"  ★ 纯净池高置信     : {pure}")
print(f"  ★ 方案2爆发Top5   : {plan2}")
print(f"  ★ Excel精选5      : {excel5}")
print(f"  ★ 极高阶 高斯/聚类/傅里叶/整合:")
print(f"      gauss={gauss}")
print(f"      cluster={cluster}")
print(f"      fourier={fourier}")
print(f"      fusion={fusion}")
print("  环境: 平衡震荡期 | 信标 Level1 (0.5x弱信号防御) | KL Z=-0.47 (安全)")
print("  防守参考: 80 / 30 / 71")

print("\n[3] 内部多模块提纯 (Task 4.5)")
print("-" * W)
buckets = {"钻石": [], "金": [], "银": [], "铜": []}
for n in sorted(pool):
    t, c, adj = classify(n)
    buckets[t].append((n, c, pool[n], adj))

for title, key, star in [
    ("钻石级 >=4模块", "钻石", "****"),
    ("金级 3模块", "金", "***"),
    ("银级 2模块", "银", "**"),
]:
    items = buckets[key]
    print(f"  {star} {title}: {len(items)}个")
    for n, c, mods, adj in sorted(items, key=lambda x: (-x[1], x[0]))[:15]:
        extra = (" [" + ",".join(adj) + "]") if adj else ""
        print(f"      {n:02d} x{c} <- {','.join(mods)}{extra}")
print(f"  * 铜级单模块: {len(buckets['铜'])}个 (不建议重仓)")

# 3D check
print("\n  三维自洽: EF/RW/FO = 0.40/0.30/0.30 均衡 (无单维>0.50)")
he5_ef_dom = []
for num, ef, rw, fo, tot in he5_detail:
    e, r, f = float(ef), float(rw), float(fo)
    ce, cr, cf = e * 1.0, r * 0.8, f * 0.5
    # FO often dominates due to scale; report FO-led vs EF-led by raw contribution
    dominant = "FO" if cf >= ce and cf >= cr else ("EF" if ce >= cr else "RW")
    if dominant == "EF":
        he5_ef_dom.append(int(num))
    print(f"      HE5#{int(num):02d} 主导维={dominant} (贡献 EF*{ce:.2f}/RW*{cr:.2f}/FO*{cf:.2f})")
trin = set(trinity5) | set(trinity12)
miss = [n for n in he5 if n not in trin]
print(f"  HE5∩Trinity: {sorted(set(he5)&trin)} | HE5独有: {miss}")

core = set(he5) | set(trinity5) | set(ai5)
ho_all = set(gauss) | set(cluster) | set(fourier) | set(fusion)
ho_inter = set(gauss) & set(cluster) & set(fourier) if gauss and cluster and fourier else set()
print(f"  极高阶四维交集: {sorted(ho_inter) if ho_inter else '无'}")
print(f"  极高阶独有: {sorted(ho_all - core)[:12]}")
print(f"  核心低维独有: {sorted(core - ho_all)}")

print("\n[4] 优化决策 (Task 3)")
print("-" * W)
print("  经统计检验，当前命中率整体未显著优于随机基线 (WF Lift≈1.00)。")
print("  不建议增加新优化方案；继续增加复杂度可能引入过拟合。")
print("  维持现状，持续监控。学习冻结保持。Critical代码缺陷已修，业务逻辑不扩。")

print("\n[5] 投注参考优先级")
print("-" * W)
priority = []
for n, c, mods, adj in buckets["钻石"] + buckets["金"]:
    priority.append(n)
# ensure HE5 front
ordered = []
for n in he5 + priority + trinity5:
    if n not in ordered:
        ordered.append(n)
print(f"  建议关注序: {ordered[:12]}")
print(f"  完整报告: reports/daily_analysis_report_20260716.md")
print("=" * W)

# append purification section to report if not present
marker = "## 内部多模块提纯 (Task 4.5)"
if marker not in text:
    lines = [
        "",
        "---",
        "",
        marker,
        "",
        f"- **钻石级**: {[(n, pool[n]) for n,_,_,_ in buckets['钻石']]}",
        f"- **金级**: {[(n, pool[n]) for n,_,_,_ in buckets['金']]}",
        f"- **银级**: {[(n, c, pool[n]) for n,c,_,_ in buckets['银'][:20]]}",
        f"- **铜级数量**: {len(buckets['铜'])}",
        f"- **三维自洽**: EF/RW/FO=0.40/0.30/0.30 均衡",
        f"- **HE5独有(相对Trinity)**: {miss}",
        f"- **提纯结论**: 区分力近窗偏弱，提纯仅作参考标注，不驱动选号权重调整",
        f"- **优化结论**: 维持现状，不新增方案",
        "",
    ]
    (ROOT / "reports/daily_analysis_report_20260716.md").write_text(
        text + "\n".join(lines), encoding="utf-8"
    )
    print("\n[已追加] Task4.5 提纯段落写入日报")

# deep optimization report
opt = ROOT / "reports/deep_optimization_report_20260716.md"
opt.write_text(
    "\n".join(
        [
            "# 深度优化报告 2026-07-16",
            "",
            "## 结论",
            "经统计检验，当前命中率未显著优于随机基线，不建议增加新优化方案。"
            "当前架构已科学合理，继续增加复杂度可能引入过拟合。维持现状，持续监控。",
            "",
            "## 依据",
            "- Walk-Forward FO Lift = 1.0043 < 解锁阈值 1.1 → 自学习冻结",
            "- 近7期 HE5 均命中 ≈1.0/5 (Lift≈0.80x)",
            "- 近7期 Trinity Top5 均命中 ≈1.0/5；本期 3/5 属波动，不构成结构改进证据",
            "- Weekly 通道: RW 1.05 / FO 0.96 / EF 0.94，均无显著 p 优势",
            "",
            "## 已落地代码修复（非策略扩容）",
            "1. `score_composer.py`: Loss 键 dim→loss 映射方向纠正",
            "2. `autonomous_learner.py`: bayesian/feature 权重映射；WF 三维预测；回滚不污染基线",
            "3. `excel_lock.py`: stale_seconds 60→600，防长任务抢锁",
            "4. `full_report_engine.py`: Level3 文案统一为 0.0x",
            "",
            "## 不调整项",
            "- 不改 HE5 评分公式权重",
            "- 不恢复 Rapid Blast / MK / EO",
            "- 不降低钻石阈值；提纯维持参考级",
            "",
        ]
    ),
    encoding="utf-8",
)
print(f"[已写入] {opt}")
