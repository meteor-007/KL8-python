# -*- coding: utf-8 -*-
"""今日推荐内部提纯 + 美观控制台面板"""
import re
import json
import os
from collections import defaultdict

REPORT = "reports/daily_analysis_report_20260717.md"
text = open(REPORT, encoding="utf-8").read()

def grab_list(patterns, default=None):
    for p in patterns:
        m = re.search(p, text, re.S)
        if m:
            raw = m.group(1)
            nums = [int(x) for x in re.findall(r"\d+", raw)]
            return nums
    return default or []

he5 = grab_list([r"最终推荐 \(5 码\)[：:]\s*`\[([^\]]+)\]`", r"Hidden Energy 5[\s\S]*?最终推荐.*?`\[([^\]]+)\]`"])
trinity5 = grab_list([r"极秘 Top 5[：:]\s*`\[([^\]]+)\]`"])
trinity12 = grab_list([r"极秘 Top 12[：:]\s*`\[([^\]]+)\]`"])
ai5 = grab_list([r"Top 5 置信度精选[：:]\s*`\[([^\]]+)\]`"])
ai12 = grab_list([r"Top 12 综合拦截[：:]\s*`\[([^\]]+)\]`"])
golden = grab_list([r"高频共振集群[：:]\s*`\[([^\]]+)\]`"])
mrmr = grab_list([r"mRMR Top 12[：:]\s*`\[([^\]]+)\]`"])
pure = grab_list([r"纯净池号码[：:]\s*`\[([^\]]+)\]`"])
env = re.search(r"环境识别[：:`\s]*`?([^`\n(]+)", text)
env_name = env.group(1).strip() if env else "?"
weights = re.search(r"动态模型赋权[：:]\s*`([^`]+)`", text)
w_str = weights.group(1) if weights else "?"
b3 = re.search(r"B3质量分[：:]\s*`?([\d.]+)", text)
b3_score = b3.group(1) if b3 else "?"
level = re.search(r"当前处于 `?(Level \d)`?", text)
level_s = level.group(1) if level else "?"
kl = re.search(r"当前KL散度:\s*([\d.]+)", text)
kl_s = kl.group(1) if kl else "?"

# 极高阶
gauss = grab_list([r"量子质心.*?最优\s*5\s*码[：:]\s*`?\[([^\]]+)\]`", r"gauss_top5[^\[]*\[([^\]]+)\]"], [])
cluster = grab_list([r"点位势能.*?最优\s*5\s*码[：:]\s*`?\[([^\]]+)\]`"], [])
fourier = grab_list([r"离散傅里叶.*?最优\s*5\s*码[：:]\s*`?\[([^\]]+)\]`"], [])
fusion = grab_list([r"终极推荐[：:]\s*`?\[([^\]]+)\]`", r"三元一体.*?最优\s*5\s*码[：:]\s*`?\[([^\]]+)\]`"], [])

# 从 self_learning_state 补极高阶
sl_path = "cache/self_learning_state.json"
if os.path.exists(sl_path):
    try:
        sl = json.load(open(sl_path, encoding="utf-8"))
        snap = sl.get("latest_high_order") or sl.get("high_order") or {}
        if not isinstance(snap, dict):
            snap = {}
        gauss = gauss or snap.get("gauss_top5") or sl.get("gauss_top5") or []
        cluster = cluster or snap.get("cluster_top5") or sl.get("cluster_top5") or []
        fourier = fourier or snap.get("fourier_top5") or sl.get("fourier_top5") or []
        fusion = fusion or snap.get("fusion_top5") or sl.get("fusion_top5") or []
    except Exception:
        pass

# HE5 明细
he5_detail = re.findall(
    r"号码 `(\d+)`: EF `([\d.]+)` \| RW `([\d.]+)` \| FO `([\d.]+)` \| 综合动能 `([\d.]+)`",
    text,
)

modules = {
    "HE5": he5,
    "Trinity5": trinity5,
    "Trinity12": trinity12,
    "AI5": ai5,
    "AI12": ai12,
    "Golden": golden,
    "mRMR": mrmr,
    "Pure": pure,
    "Gauss": gauss,
    "Cluster": cluster,
    "Fourier": fourier,
    "Fusion5": fusion,
}

# 内部共振：核心模块
core_keys = ["HE5", "Trinity5", "AI5", "mRMR", "Pure", "Fusion5", "Golden"]
pool = defaultdict(list)
for k in core_keys:
    for n in modules[k]:
        if k not in pool[n]:
            pool[n].append(k)

# AUC
auc_boost = set()
auc_path = "auc_stats.json"
if os.path.exists(auc_path):
    try:
        auc = json.load(open(auc_path, encoding="utf-8"))
        # flexible structure
        data = auc.get("numbers") or auc.get("auc") or auc
        if isinstance(data, dict):
            for n, v in data.items():
                try:
                    nn = int(n)
                    val = float(v) if not isinstance(v, dict) else float(v.get("auc", 0.5))
                    if val > 0.52:
                        auc_boost.add(nn)
                except Exception:
                    pass
    except Exception:
        pass

FDR_SIG = {3, 11, 15, 69}

diamond, gold, silver, copper = [], [], [], []
for n, srcs in sorted(pool.items(), key=lambda x: (-len(x[1]), x[0])):
    lvl = len(srcs)
    if n in auc_boost:
        lvl += 1
    tag = ""
    if n in FDR_SIG:
        tag = " [FDR显著]"
    if n in auc_boost:
        tag += " [AUC↑]"
    entry = (n, srcs, tag)
    if len(srcs) >= 4:
        diamond.append(entry)
    elif len(srcs) == 3:
        gold.append(entry)
    elif len(srcs) == 2:
        silver.append(entry)
    else:
        copper.append(entry)

# 昨日对账
actual_187 = {31, 72, 11, 9, 62, 78, 34, 38, 57, 8, 75, 27, 2, 55, 25, 69, 12, 15, 3, 33}
y_preds = {
    "HE5": [12, 27, 38, 47, 73],
    "Trinity5": [10, 27, 29, 67, 69],
    "Trinity12": [6, 10, 27, 29, 40, 42, 45, 47, 66, 67, 69, 73],
    "AI5": [7, 11, 45, 67, 80],
    "AI12": [7, 11, 45, 67, 80, 3, 9, 25, 30, 57, 58, 73],
    "Golden": [6, 10, 42, 45, 69, 73],
    "Pure": [2, 27, 53, 69, 80],
    "mRMR": [77, 33, 12, 39, 69, 30, 20, 27, 66, 54, 42, 6],
}

W = 72
print()
print("╔" + "═" * W + "╗")
print("║" + "快乐8 每日全流程分析 — 2026-07-17 / 目标期 2026188".center(W - 4) + "║")
print("╠" + "═" * W + "╣")

print("║  【任务2】2026187 开奖对账".ljust(W) + "║")
print("║  开奖: 31-72-11-09-62-78-34-38-57-08-75-27-02-55-25-69-12-15-03-33".ljust(W) + "║")
print("║  " + "-" * (W - 4))
for name, nums in y_preds.items():
    hits = sorted(set(nums) & actual_187)
    h, k = len(hits), len(nums)
    lift = (h / k) / 0.25 if k else 0
    mark = "★" if lift >= 1.5 else ("·" if lift >= 1.0 else " ")
    line = f"  {mark} {name:12s} {h}/{k}  Lift={lift:.2f}x  命中{hits}"
    print("║" + line.ljust(W) + "║")
print("║  ★ HE5=3/5(2.40x)  Pure=3/5(2.40x)  AI12=5/12(1.67x)  昨日核心模块爆发".ljust(W) + "║")
print("╠" + "═" * W + "╣")

print("║  【近10期趋势】HE5均命中20%(Lift0.80) | Trinity5=20%(0.80) | AI5=32%(1.28)".ljust(W) + "║")
print("║  【闭环学习】WF Lift=1.0043 < 1.1 → 自学习冻结 | 权重 EF0.40/RW0.30/FO0.30 | balanced".ljust(W) + "║")
print("║  【任务3】经统计检验，当前整体未显著优于随机基线，不建议新增优化方案，维持现状。".ljust(W) + "║")
print("╠" + "═" * W + "╣")

print("║  【今日核心推荐 · 目标期 2026188】".ljust(W) + "║")
print(f"║  环境: {env_name} | 三维权重: {w_str} | B3质量: {b3_score} | 信标: {level_s}(0.5x)".ljust(W) + "║")
print(f"║  KL散度: {kl_s}".ljust(W) + "║")
print("║  " + "-" * (W - 4))

def fmt_nums(nums):
    return " ".join(f"{n:02d}" for n in sorted(nums)) if nums else "(无)"

print(f"║  🏆 Hidden Energy 5 : {fmt_nums(he5)}".ljust(W) + "║")
for n, ef, rw, fo, sc in he5_detail:
    print(f"║     · {int(n):02d}  EF={ef} RW={rw} FO={fo} Score={sc}".ljust(W) + "║")
print(f"║  🎯 AI Top5         : {fmt_nums(ai5)}".ljust(W) + "║")
print(f"║  🎯 AI Top12        : {fmt_nums(ai12)}".ljust(W) + "║")
print(f"║  🛡️ Trinity Top5    : {fmt_nums(trinity5)}".ljust(W) + "║")
print(f"║  🛡️ Trinity Top12   : {fmt_nums(trinity12)}".ljust(W) + "║")
print(f"║  🔮 Golden Core     : {fmt_nums(golden)}".ljust(W) + "║")
print(f"║  💎 纯净池定胆      : {fmt_nums(pure)}".ljust(W) + "║")
print(f"║  📐 mRMR Top12      : {fmt_nums(mrmr)}".ljust(W) + "║")
if fusion:
    print(f"║  🌊 极高阶整合5     : {fmt_nums(fusion)}".ljust(W) + "║")
if gauss:
    print(f"║     高斯5={fmt_nums(gauss)} 聚类5={fmt_nums(cluster)} 傅里叶5={fmt_nums(fourier)}".ljust(W) + "║")
print("╠" + "═" * W + "╣")

print("║  【任务4.5】内部多模块共振提纯".ljust(W) + "║")

def print_tier(title, items):
    print(f"║  {title}".ljust(W) + "║")
    if not items:
        print("║     (无)".ljust(W) + "║")
        return
    for n, srcs, tag in items:
        print(f"║     {n:02d} ← {'+'.join(srcs)}{tag}".ljust(W) + "║")

print_tier("⭐⭐⭐⭐ 钻石级 (≥4模块)", diamond)
print_tier("⭐⭐⭐ 金级 (3模块)", gold)
print_tier("⭐⭐ 银级 (2模块)", silver[:12])
print(f"║  ⭐ 铜级独有: {len(copper)}个 (略)".ljust(W) + "║")

# 三维自洽
ef_dom = []
for n, ef, rw, fo, sc in he5_detail:
    if float(ef) >= float(rw) and float(ef) >= float(fo) / 20:  # FO scale large
        ef_dom.append(int(n))
t12 = set(trinity12)
conflict = [n for n in he5 if n not in t12]
print("║  " + "-" * (W - 4))
print(f"║  三维自洽: HE5∉Trinity12 → {conflict if conflict else '无矛盾'}".ljust(W) + "║")
print(f"║  权重均衡: {w_str} (任一维>0.5需警惕)".ljust(W) + "║")
print("╠" + "═" * W + "╣")
print("║  【结论】优先关注钻石/金级共振号；HE5昨日爆发，近10期仍偏弱，维持架构不增复杂度。".ljust(W) + "║")
print("║  报告: reports/daily_analysis_report_20260717.md".ljust(W) + "║")
print("╚" + "═" * W + "╝")
print()

# 写提纯附录到报告
appendix = ["\n\n## 附录 B：内部多模块共振提纯 (2026-07-17)\n"]
appendix.append("| 等级 | 号码 | 来源模块 |\n|------|------|----------|\n")
for title, items in [("钻石", diamond), ("金", gold), ("银", silver)]:
    for n, srcs, tag in items:
        appendix.append(f"| {title} | {n:02d} | {'+'.join(srcs)}{tag} |\n")
appendix.append(f"\n- HE5∉Trinity12矛盾号: {conflict or '无'}\n")
appendix.append(f"- 信标等级: {level_s}\n")
appendix.append(f"- 优化结论: 维持现状，不新增方案\n")
with open(REPORT, "a", encoding="utf-8") as f:
    f.write("".join(appendix))
print("[已追加] 附录B 内部提纯 →", REPORT)
