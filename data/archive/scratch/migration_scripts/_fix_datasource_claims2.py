# -*- coding: utf-8 -*-
"""第四轮: 清除剩余的数据源性能宣称 (modules_overview / review_datasource)。

数值依据同 _fix_datasource_claims.py 顶部注释 (backend/core/datasource_predictor.py
2026-09-10 全历史审计: D2外部回避 75.32% Lift0.987 p=0.707; B2杀熟 75.99% Lift0.960 p=0.471)。
review_datasource.html 的 live 值存在时优先显示 live, 缺失时改为 '--' (不再回退到假数字)。
"""
import io
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VIEWS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "frontend", "static", "views")

R = [
    # ── cockpit_modules_overview.html ──
    ("cockpit_modules_overview.html",
     "{{ modulesOverviewData.modules.deep_association?.confidence || '🟢 S级 做多爆发25.5%' }}",
     "{{ modulesOverviewData.modules.deep_association?.confidence || '--' }}"),
    ("cockpit_modules_overview.html",
     '<span class="text-[10px] font-mono text-slate-400">单码率 25.5%</span>',
     '<span class="text-[10px] font-mono text-slate-400">单码率 23.9%~26.5% (基线25%, 不显著)</span>'),
    ("cockpit_modules_overview.html",
     '<span class="text-[10px] font-mono text-slate-400">排除准确率 75.9%</span>',
     '<span class="text-[10px] font-mono text-slate-400">排除准确率 76.0% (Lift 0.96, 不显著)</span>'),
    ("cockpit_modules_overview.html",
     '<span>🛡️ D2 外部杀号回避率: <strong class="text-emerald-400 font-bold">76.5%</strong> (外部 13 码高避让)</span>',
     '<span>🛡️ D2 外部杀号回避率: <strong class="text-slate-300 font-bold">75.3%</strong> '
     '<span class="text-slate-500">(基线 75%, Lift 0.99, 不显著)</span></span>'),

    # ── review_datasource.html ── (live 值优先, 缺失显示 '--')
    ("review_datasource.html",
     "{{ (datasourceReview.hot_top5_hit_rate ? (datasourceReview.hot_top5_hit_rate * 100).toFixed(1) : '25.5') }}%",
     "{{ (datasourceReview.hot_top5_hit_rate ? (datasourceReview.hot_top5_hit_rate * 100).toFixed(1) : '--') }}%"),
    ("review_datasource.html",
     "{{ (datasourceReview.non_d2_kill_accuracy ? (datasourceReview.non_d2_kill_accuracy * 100).toFixed(1) : '76.5') }}%",
     "{{ (datasourceReview.non_d2_kill_accuracy ? (datasourceReview.non_d2_kill_accuracy * 100).toFixed(1) : '--') }}%"),
    ("review_datasource.html",
     "{{ (datasourceReview.cold_top5_kill_accuracy ? (datasourceReview.cold_top5_kill_accuracy * 100).toFixed(1) : '75.9') }}%",
     "{{ (datasourceReview.cold_top5_kill_accuracy ? (datasourceReview.cold_top5_kill_accuracy * 100).toFixed(1) : '--') }}%"),
    ("review_datasource.html",
     "{{ row.non_d2_kill_accuracy ? (row.non_d2_kill_accuracy * 100).toFixed(1) + '%' : '76.5%' }}",
     "{{ row.non_d2_kill_accuracy ? (row.non_d2_kill_accuracy * 100).toFixed(1) + '%' : '--' }}"),
]


def main():
    failures = []
    applied = 0
    for fname, old, new in R:
        path = os.path.join(VIEWS, fname)
        with io.open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        cnt = content.count(old)
        if cnt != 1:
            failures.append((fname, old[:70], f"命中 {cnt} 次 (应为 1)"))
            continue
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content.replace(old, new, 1))
        applied += 1

    print(f"✅ 已替换 {applied}/{len(R)} 处")
    if failures:
        print(f"\n❌ {len(failures)} 处未替换:")
        for fname, s, why in failures:
            print(f"   [{fname}] {why}: {s}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
