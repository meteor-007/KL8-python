# -*- coding: utf-8 -*-
"""临时：汇总近10期报告复盘命中 + 对账2026187"""
import re
import glob
import os

reports = sorted(glob.glob("reports/daily_analysis_report_*.md"), reverse=True)[:12]
print("=" * 70)
print("  近10期报告复盘段命中趋势")
print("=" * 70)

pattern_he5 = re.compile(r"Hidden Energy 5.*?命中\s*`?(\d+)/(\d+)`?", re.S)
pattern_t5 = re.compile(r"三维融合.*?Top5\s*命中\s*`?(\d+)/(\d+)`?", re.S)
pattern_ai5 = re.compile(r"传统AI.*?Top5\s*命中\s*`?(\d+)/(\d+)`?", re.S)

he_vals, t5_vals, ai_vals = [], [], []
for r in reports[:10]:
    text = open(r, encoding="utf-8").read()
    m_issue = re.search(r"目标期号[：:]\s*\**(\d{7})", text)
    issue = m_issue.group(1) if m_issue else "?"
    date = os.path.basename(r).replace("daily_analysis_report_", "").replace(".md", "")
    he = pattern_he5.search(text)
    t5 = pattern_t5.search(text)
    ai = pattern_ai5.search(text)
    he_s = f"{he.group(1)}/{he.group(2)}" if he else "N/A"
    t5_s = f"{t5.group(1)}/{t5.group(2)}" if t5 else "N/A"
    ai_s = f"{ai.group(1)}/{ai.group(2)}" if ai else "N/A"
    if he:
        he_vals.append(int(he.group(1)) / int(he.group(2)))
    if t5:
        t5_vals.append(int(t5.group(1)) / int(t5.group(2)))
    if ai:
        ai_vals.append(int(ai.group(1)) / int(ai.group(2)))
    print(f"  {date} 目标{issue} | HE5={he_s:>5}  Trinity5={t5_s:>5}  AI5={ai_s:>5}")

def avg_lift(rates):
    if not rates:
        return None
    return (sum(rates) / len(rates)) / 0.25

print("-" * 70)
if he_vals:
    print(f"  HE5 近{len(he_vals)}期均命中率={sum(he_vals)/len(he_vals):.1%}  Lift={avg_lift(he_vals):.2f}x")
if t5_vals:
    print(f"  Trinity5 近{len(t5_vals)}期均命中率={sum(t5_vals)/len(t5_vals):.1%}  Lift={avg_lift(t5_vals):.2f}x")
if ai_vals:
    print(f"  AI5 近{len(ai_vals)}期均命中率={sum(ai_vals)/len(ai_vals):.1%}  Lift={avg_lift(ai_vals):.2f}x")
print("=" * 70)
