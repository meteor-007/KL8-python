#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026162期报告完整性验证"""
import json, os

report_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'reports', 'daily_analysis_report_20260621.md')
with open(report_path, 'r', encoding='utf-8') as f:
    content = f.read()

checks = {
    "目标期号=2026162": "2026162" in content,
    "HE5有5码": "[2, 23, 39, 44, 60]" in content,
    "Trinity Top5有数据": "[40, 44, 49, 60, 77]" in content,
    "Trinity Top12有数据": "2, 38, 39, 40, 44, 49" in content,
    "Golden Core有数据": "高频共振集群" in content,
    "熵控优化有输出": "mRMR" in content,
    "环境识别结果": "平衡震荡期" in content,
    "纯净池定胆": "纯净池" in content,
    "极高阶前瞻": "极致整合 5 码" in content,
    "复盘追溯": "2026161期" in content,
    "闭环学习引擎状态": "闭环学习引擎状态" in content,
}

print("=" * 60)
print("  2026162期报告完整性验证")
print("=" * 60)
all_pass = True
for check, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {check}")

print(f"\n{'全部通过 ✅' if all_pass else '有项目未通过 ❌'}")
