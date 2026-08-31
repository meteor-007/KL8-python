#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026158期复盘对账脚本"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("  2026158期复盘对账 — 2026-06-18")
print("=" * 70)

# 2026158期实际开奖号码
actual = set([12,63,45,51,37,20,28,11,69,29,15,65,5,77,38,64,55,23,49,79])

# 昨日推荐（从报告中提取）
trinity_top5 = [17, 38, 40, 49, 71]
trinity_top12 = [7, 10, 17, 18, 38, 40, 42, 44, 49, 50, 59, 71]
ai_top5 = [7, 15, 20, 34, 39]
ai_top12 = [7, 15, 20, 34, 39, 49, 64, 5, 4, 18, 30, 42]
golden_core = [7, 10, 17, 18, 38, 42, 44, 49, 71]
he5 = [7, 17, 18, 42, 49]
gauss5 = [40, 41, 17, 18, 49]
cluster5 = [27, 12, 53, 63, 2]
fourier5 = [28, 7, 49, 38, 8]
fusion5 = [49, 7, 39, 41, 8]
mrmr_top12 = [77, 38, 75, 66, 3, 11, 17, 10, 30, 54, 14, 39]
pure_pool = [38, 17, 2]
pure_pool_all = [2, 17, 24, 38, 49, 70, 71, 75]

print(f"\n📋 2026158期开奖号码: {sorted(actual)}")
print(f"   共 {len(actual)} 个号码\n")

# 基线: 20/80 = 25%
baseline = 0.25

def check(name, nums):
    nums_set = set(nums)
    hits = nums_set & actual
    hit_count = len(hits)
    hit_rate = hit_count / len(nums)
    lift = hit_rate / baseline if baseline > 0 else 0
    hit_list = sorted(hits)
    print(f"  {name}: {hit_count}/{len(nums)} 命中 {hit_list}")
    print(f"    命中率={hit_rate*100:.1f}% Lift={lift:.2f}x {'✅' if lift >= 1.0 else '❌'}")
    return hit_count, len(nums), lift

print("═══ 1. 三维融合 ═══")
h, t, l = check("极秘Top5", trinity_top5)
h, t, l = check("极秘Top12", trinity_top12)

print("\n═══ 2. 传统AI ═══")
h, t, l = check("Top5", ai_top5)
h, t, l = check("Top12", ai_top12)

print("\n═══ 3. Golden Core ═══")
h, t, l = check("共振号", golden_core)

print("\n═══ 4. Hidden Energy 5 ═══")
h, t, l = check("HE5", he5)

print("\n═══ 5. 高斯核流能 ═══")
h, t, l = check("高斯5", gauss5)

print("\n═══ 6. 聚类马尔可夫 ═══")
h, t, l = check("聚类5", cluster5)

print("\n═══ 7. 傅里叶谐波 ═══")
h, t, l = check("傅里叶5", fourier5)

print("\n═══ 8. 极致整合 ═══")
h, t, l = check("融合5", fusion5)

print("\n═══ 9. 熵控mRMR ═══")
h, t, l = check("mRMR Top12", mrmr_top12)

print("\n═══ 10. 纯净池定胆 ═══")
h, t, l = check("高置信定胆", pure_pool)
h, t, l = check("纯净池全量", pure_pool_all)

# 近10期统计汇总
print("\n" + "=" * 70)
print("  近10期Lift趋势汇总 (从历史记忆提取)")
print("=" * 70)
# 从记忆中提取
periods_data = [
    ("2026149", 6, 12, "1.60x"),
    ("2026150", 1, 12, "0.33x"),
    ("2026151", 3, 12, "1.00x"),
    ("2026152", 5, 12, "1.67x"),
    ("2026153", 4, 12, "1.33x"),
    ("2026154", 1, 12, "0.33x"),
    ("2026155", 6, 12, "2.00x"),
    ("2026156", 4, 12, "1.33x"),
    ("2026157", 2, 12, "0.67x"),
    ("2026158", 0, 12, "0.00x"),  # 需要计算
]

# 计算本期的Top12命中
trinity_top12_hits = set(trinity_top12) & actual
periods_data[-1] = ("2026158", len(trinity_top12_hits), 12, f"{len(trinity_top12_hits)/12/0.25:.2f}x")

total_hits = sum(p[1] for p in periods_data)
total_picks = sum(p[2] for p in periods_data)
overall_rate = total_hits / total_picks
overall_lift = overall_rate / baseline

print(f"  期号      Top12命中  Lift")
print(f"  {'─'*35}")
for p in periods_data:
    marker = "✅" if float(p[3].replace('x','')) >= 1.0 else "❌"
    print(f"  {p[0]}    {p[1]:2d}/{p[2]:2d}     {p[3]} {marker}")
print(f"  {'─'*35}")
print(f"  近10期合计: {total_hits}/{total_picks} = {overall_rate*100:.1f}% Lift={overall_lift:.2f}x")

# 统计显著性检验 (二项检验)
from scipy import stats
p_value = stats.binom_test(total_hits, total_picks, baseline, alternative='greater') if hasattr(stats, 'binom_test') else 1.0
if p_value == 1.0:
    # 使用较新的scipy API
    try:
        result = stats.binomtest(total_hits, total_picks, baseline, alternative='greater')
        p_value = result.pvalue
    except:
        p_value = 1.0

print(f"  二项检验 p={p_value:.4f} {'✅显著' if p_value < 0.05 else '❌不显著'}")
bonf_p = min(p_value * 80, 1.0)  # Bonferroni
print(f"  Bonferroni校正 p={bonf_p:.4f} {'✅显著' if bonf_p < 0.05 else '❌不显著'}")

print("\n" + "=" * 70)
print("  🏆 2026158期最佳模块")
print("=" * 70)

modules = {
    "HE5": (set(he5) & actual, len(he5)),
    "傅里叶5": (set(fourier5) & actual, len(fourier5)),
    "高斯5": (set(gauss5) & actual, len(gauss5)),
    "聚类5": (set(cluster5) & actual, len(cluster5)),
    "极致整合5": (set(fusion5) & actual, len(fusion5)),
    "Top5": (set(trinity_top5) & actual, len(trinity_top5)),
    "Top12": (set(trinity_top12) & actual, len(trinity_top12)),
    "AI Top5": (set(ai_top5) & actual, len(ai_top5)),
    "Golden Core": (set(golden_core) & actual, len(golden_core)),
}

best = max(modules.items(), key=lambda x: len(x[1][0])/x[1][1] if x[1][1] > 0 else 0)
print(f"  {best[0]}: {len(best[1][0])}/{best[1][1]} 命中 = {sorted(best[1][0])}")

print("\n✅ 复盘对账完成")
