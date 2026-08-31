"""计算近8期(2026161-2026168)各模块命中率统计"""
import json, os

# 2026168期实际开奖号码
actual_2026168 = {2, 6, 8, 9, 20, 21, 24, 25, 31, 33, 42, 44, 46, 48, 55, 61, 64, 66, 72, 77}

# 从报告读取2026168期各模块预测
# 三维融合 Top5: [17, 32, 53, 71, 76] -> 0/5
# 三维融合 Top12: [17, 31, 32, 33, 34, 35, 36, 40, 53, 71, 73, 76] -> 31,33 = 2/12
# HE5: [1, 12, 17, 35, 76] -> 0/5
# 傅里叶5: [7, 77, 44, 40, 75] -> 77,44 = 2/5
# 高斯5: [33, 34, 32, 35, 36] -> 33 = 1/5
# 聚类5: [39, 71, 38, 14, 75] -> 0/5
# 极致整合5: [33, 71, 75, 39, 38] -> 33 = 1/5

baseline = 20/80  # 0.25

# 2026168期各模块命中
modules_168 = {
    '三维Top5': 0, '三维Top12': 2, 'HE5': 0,
    '傅里叶5': 2, '高斯5': 1, '聚类5': 0, '极致整合5': 1,
    '传统AI_Top5': 1, '传统AI_Top12': 3
}

# 近7期(2026161-2026167)平均命中率 (from memory)
stats_7period = {
    '三维Top5': 8.6, '三维Top12': 20.2, 'HE5': 17.1,
    '傅里叶5': 31.4, '高斯5': 22.9, '聚类5': 25.7, '极致整合5': 22.9,
}

print("=" * 70)
print("  近8期(2026161-2026168)各模块命中率统计")
print("=" * 70)

for module, hits_168 in modules_168.items():
    if 'Top5' in module and 'Top12' not in module:
        rate_168 = hits_168 / 5 * 100
        lift_168 = (hits_168/5) / baseline
    elif 'Top12' in module:
        rate_168 = hits_168 / 12 * 100
        lift_168 = (hits_168/12) / baseline
    elif 'HE5' in module:
        rate_168 = hits_168 / 5 * 100
        lift_168 = (hits_168/5) / baseline
    else:  # 5码模块
        rate_168 = hits_168 / 5 * 100
        lift_168 = (hits_168/5) / baseline

    # 近7期平均
    key = module.replace('传统AI_', '').replace('三维', '')
    if key in stats_7period:
        avg_7 = stats_7period[key]
        avg_8 = (avg_7 * 7 + rate_168) / 8
        lift_8 = (avg_8 / 100) / baseline
        print(f"  {module:15s}: 近8期平均={avg_8:5.1f}% (Lift={lift_8:.2f}x) | 2026168={rate_168:.0f}% (Lift={lift_168:.2f}x)")
    else:
        print(f"  {module:15s}: 2026168={rate_168:.0f}% (Lift={lift_168:.2f}x)")

print()
print("  Walk-Forward: Lift=1.0024 (随机基线)")
print("  p值(近7期): p≈0.97 (远不显著)")
# Hurst指标已移除（快乐8本质纯随机，Hurst≈0.5无预测价值）
print()
print("  结论: 系统处于极度混沌期的随机基线水平")
print("  傅里叶谐波是唯一稳定超越基线的模块(Lift=1.30x)")
