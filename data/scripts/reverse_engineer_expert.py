# -*- coding: utf-8 -*-
"""
逆向工程原图作者的选号真经：
逐一核对 media_1790769254282.png 中 2026262 期（基准 2026261）所有被标记的号码！
红底、黄底、红框分别具体是哪几个？它们在 16 期窗口、出窗、遗漏、012路中的物理规律是什么？
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()
# 2026262 期
draw_idx = [i for i, d in enumerate(engine.draws) if d["period"] == 2026262][0]
base_idx = draw_idx - 1
base_draw = engine.draws[base_idx]
print(f"基准期号: {base_draw['period']}, 预测目标: 2026262")

# 实开号码
actual_262 = engine.draws[draw_idx]["nums"]
print(f"2026262 实开: {actual_262}")

# 从图中读取到的决算清单:
# 红底命中清单: 20 33 44 49 54 61 80 (7码)
# 红框命中清单: 33 44 54 61 80 (5码)
# 红框一共 11 码, 命中 5 码!
# 红底一共 20 码, 命中 7 码!
# 黄底一共 16 码, 命中 5 码!

# 我们来看看图中的标记:
# 出现7次:
# 剩余: 50(普通), 73(红底白字)
# 出现6次:
# 出窗: 29(红底), 51(红底), 53(红底), 54(黄底红框), 78(普通)
# 剩余: 2(普通), 4(红框), 62(普通), 65(普通), 66(普通), 72(普通), 74(普通), 76(普通)
# 出现5次:
# 出窗: 10(红底)
# 剩余: 1(普通), 13(红框), 26(普通), 28(普通), 52(普通), 61(黄底红框)
# 出现4次:
# 出窗: 18(红底), 56(黄底), 80(黄底红框)
# 剩余: 5(黄底), 7(黄底), 11(普通), 17(红框), 24(红底), 33(黄底红框), 41(普通), 42(红框), 44(黄底红框), 46(普通), 47(红底), 49(红底红框), 57(普通), 59(红框), 60(黄底), 79(黄底)
# 出现3次:
# 出窗: 3(红底), 16(黄底), 20(红底), 58(普通), 70(普通), 75(红底)
# 剩余: 6, 9, 15, 19, 21, 22, 30(黄底), 34, 36, 38, 39, 40, 43, 48, 55, 68

# 我们把图中所有被标色的号码提取出来:
# 红框号码 (一共11码):
# 出现6次出窗: 54
# 出现6次剩余: 4
# 出现5次剩余: 13, 61
# 出现4次出窗: 80
# 出现4次剩余: 17, 33, 42, 44, 49, 59
# 刚好 1 + 1 + 2 + 1 + 6 = 11 码!
expert_red_border = [54, 4, 13, 61, 80, 17, 33, 42, 44, 49, 59]
print(f"\n★ 原图专家的 11 码红框金胆: {sorted(expert_red_border)}")
print(f"  命中 {len(set(expert_red_border) & set(actual_262))} 码: {sorted(list(set(expert_red_border) & set(actual_262)))}")

# 我们来查一下这 11 个红框金胆在 2026261 期的属性:
window_16 = engine.draws[base_idx - 15 : base_idx + 1]
outgoing_set = set(window_16[0]["nums"])
last_set = set(base_draw["nums"])
from collections import Counter
fc = Counter()
for d in window_16:
    fc.update(d["nums"])

omissions = {}
for n in range(1, 81):
    om = 0
    for b in range(base_idx, -1, -1):
        if n in engine.draws[b]["nums_set"]:
            break
        om += 1
    omissions[n] = om

print("\n--- 深度剖析这 11 个神仙红框金胆的底层物理特征 ---")
print(f"{'Num':>4}  {'Freq':>5}  {'Omiss':>6}  {'Out?':>5}  {'Repeat?':>8}  {'012':>4}  {'Zone':>5}  {'Hit262?':>8}")
for n in sorted(expert_red_border):
    is_hit = "YES" if n in actual_262 else "no"
    is_out = "出窗" if n in outgoing_set else "剩余"
    is_rep = "连庄" if n in last_set else "非重"
    print(f"{n:>4}  {fc[n]:>5}  {omissions[n]:>6}  {is_out:>5}  {is_rep:>8}  {n%3:>4}  {(n-1)//10+1:>5}  {is_hit:>8}")
