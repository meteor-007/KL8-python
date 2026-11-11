# -*- coding: utf-8 -*-
"""一次性迁移脚本: 清除 frontend/static/views/*.html 中"编造兜底数字"。

背景: 这些视图是 index.html 的**真源码** (scripts/build_web.py 在服务启动时组装)。
当后端诚实返回 null/缺失时, 模板里的 `|| 47` / `|| 24` / `|| 25` 之类兜底会把
一个具体号码或数字显示给用户, 用户无法区分"真预测"与"无数据"。

本脚本把"编造一个具体值"的兜底改为显式 '--' (真未知)。
纯计数类的 `|| 0` 不在本次范围内 (0 是诚实的"无")。

每条替换断言"恰好命中 1 次", 否则报错退出, 避免误伤。
"""
import io
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VIEWS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "frontend", "static", "views")


def nz(expr, fmt=None):
    """null 安全渲染: expr 为 null 时显示 '--'。"""
    if fmt == "pad":
        return f"{expr} != null ? String({expr}).padStart(2, '0') : '--'"
    if fmt == "tofixed":
        return f"{expr} != null ? {expr}.toFixed(2) : '--'"
    return f"{expr} != null ? {expr} : '--'"


R = []  # (file, old, new)


def add(f, old, new):
    R.append((f, old, new))


# ── cockpit_funnel.html ──
add("cockpit_funnel.html",
    "{{ funnelSummary?.level1_wide_pool?.count || 25 }}",
    "{{ " + nz("funnelSummary?.level1_wide_pool?.count") + " }}")
add("cockpit_funnel.html",
    "{{ funnelSummary?.level2_pure_pool?.count || 18 }}",
    "{{ " + nz("funnelSummary?.level2_pure_pool?.count") + " }}")
add("cockpit_funnel.html",
    "in (funnelSummary?.level3_supreme?.meta_top5 || [47, 10, 20, 33, 35])",
    "in (funnelSummary?.level3_supreme?.meta_top5 || [])")

# ── cockpit_modules_overview.html ──
add("cockpit_modules_overview.html",
    "{{ funnelSummary?.level1_wide_pool?.count || 25 }}",
    "{{ " + nz("funnelSummary?.level1_wide_pool?.count") + " }}")
add("cockpit_modules_overview.html",
    "{{ funnelSummary?.level2_pure_pool?.count || 18 }}",
    "{{ " + nz("funnelSummary?.level2_pure_pool?.count") + " }}")
add("cockpit_modules_overview.html",
    "{{ modulesOverviewData.modules.jingle?.fired_count || 4 }}",
    "{{ " + nz("modulesOverviewData.modules.jingle?.fired_count") + " }}")
add("cockpit_modules_overview.html",
    "EF:{{ modulesOverviewData.modules.trinity?.weights?.EF || 0.4 }} | RW:{{ modulesOverviewData.modules.trinity?.weights?.RW || 0.3 }} | FO:{{ modulesOverviewData.modules.trinity?.weights?.FO || 0.3 }}",
    "EF:{{ modulesOverviewData.modules.trinity?.weights?.EF ?? '--' }} | RW:{{ modulesOverviewData.modules.trinity?.weights?.RW ?? '--' }} | FO:{{ modulesOverviewData.modules.trinity?.weights?.FO ?? '--' }}")
add("cockpit_modules_overview.html",
    "{{ modulesOverviewData.modules.aggregation?.subsystems_count || 5 }}",
    "{{ " + nz("modulesOverviewData.modules.aggregation?.subsystems_count") + " }}")

# ── cockpit_datasource.html ──
add("cockpit_datasource.html",
    "{{ datasourceSummary.non_d2_kills?.length || 13 }}",
    "{{ " + nz("datasourceSummary.non_d2_kills?.length") + " }}")

# ── cockpit_nightly_scheduler.html ──
add("cockpit_nightly_scheduler.html",
    "≥ {{ evolutionData?.resonance_threshold || 2 }} 路点亮",
    "≥ {{ evolutionData?.resonance_threshold ?? '--' }} 路点亮")
add("cockpit_nightly_scheduler.html",
    "{{ evolutionData?.kill_defense_size || 15 }} 码一票否决",
    "{{ evolutionData?.kill_defense_size ?? '--' }} 码一票否决")
add("cockpit_nightly_scheduler.html",
    "≥ {{ evolutionData?.resonance_threshold || 3 }} 路",
    "≥ {{ evolutionData?.resonance_threshold ?? '--' }} 路")
add("cockpit_nightly_scheduler.html",
    "{{ evolutionData?.kill_defense_size || 14 }} 码一票否决",
    "{{ evolutionData?.kill_defense_size ?? '--' }} 码一票否决")
add("cockpit_nightly_scheduler.html",
    "{{ evolutionData?.active_subsystems?.length || 6 }} 席准入",
    "{{ " + nz("evolutionData?.active_subsystems?.length") + " }} 席准入")

# ── cockpit_unified_brain.html ──
add("cockpit_unified_brain.html",
    "({{ unifiedBrainData?.killed_count || 15 }}码)",
    "({{ " + nz("unifiedBrainData?.killed_count") + " }}码)")

# ── cockpit_agg.html ──
add("cockpit_agg.html",
    "{{ aggCockpit.subsystems_count || 7 }} 路",
    "{{ " + nz("aggCockpit.subsystems_count") + " }} 路")

# ── cockpit_meta_gold.html ──
add("cockpit_meta_gold.html",
    "{{ (r.lift || 1.0).toFixed(2) }}x",
    "{{ " + nz("r.lift", "tofixed") + " }}x")

# ── cockpit_jingle.html ──
add("cockpit_jingle.html",
    "{{ p.fired_count || 1 }} 条",
    "{{ " + nz("p.fired_count") + " }} 条")

# ── data_psychological_game.html ──
add("data_psychological_game.html",
    "{{ activePsychologicalBacktest?.n_tests || 100 }}",
    "{{ " + nz("activePsychologicalBacktest?.n_tests") + " }}")

# ── data_theme_radar.html ──
add("data_theme_radar.html",
    "Math.round((prediction.weights?.EF || 0.4)*100)",
    "prediction.weights?.EF != null ? Math.round(prediction.weights.EF*100) : '--'")
add("data_theme_radar.html",
    "Math.round((prediction.weights?.RW || 0.3)*100)",
    "prediction.weights?.RW != null ? Math.round(prediction.weights.RW*100) : '--'")
add("data_theme_radar.html",
    "Math.round((prediction.weights?.FO || 0.3)*100)",
    "prediction.weights?.FO != null ? Math.round(prediction.weights.FO*100) : '--'")

# ── review_env_regime.html ──
add("review_env_regime.html",
    "Class {{ envRegimeSummary?.environment_class || 2 }}",
    "Class {{ envRegimeSummary?.environment_class ?? '--' }}")
add("review_env_regime.html",
    "{{ envRegimeSummary?.temperature_score || 65 }}",
    "{{ " + nz("envRegimeSummary?.temperature_score") + " }}")
add("review_env_regime.html",
    "{{ envRegimeSummary?.confidence || 0.65 }}",
    "{{ " + nz("envRegimeSummary?.confidence") + " }}")
add("review_env_regime.html",
    "{{ envRegimeSummary?.recommended_weights?.EF || 0.40 }}",
    "{{ envRegimeSummary?.recommended_weights?.EF ?? '--' }}")
add("review_env_regime.html",
    "{{ envRegimeSummary?.recommended_weights?.RW || 0.30 }}",
    "{{ envRegimeSummary?.recommended_weights?.RW ?? '--' }}")
add("review_env_regime.html",
    "{{ envRegimeSummary?.recommended_weights?.FO || 0.30 }}",
    "{{ envRegimeSummary?.recommended_weights?.FO ?? '--' }}")

# ── review_daily_ledger.html ──
add("review_daily_ledger.html",
    "已沉淀 {{ reviewsLedgerData?.total_count || 47 }}+ 期记录",
    "已沉淀 {{ " + nz("reviewsLedgerData?.total_count") + " }} 期记录")

# ── review_datasource.html ──
add("review_datasource.html",
    "近 {{ datasourceReview?.rows?.length || 30 }} 期逐期样本外实测对账明细",
    "近 {{ " + nz("datasourceReview?.rows?.length") + " }} 期逐期样本外实测对账明细")

# ── data_sixteen_matrix.html ──
add("data_sixteen_matrix.html",
    "{{ sixteenSummary.transition_analysis?.summary?.in_window_count || 60 }}",
    "{{ " + nz("sixteenSummary.transition_analysis?.summary?.in_window_count") + " }}")
add("data_sixteen_matrix.html",
    "{{ sixteenSummary.transition_analysis?.summary?.outgoing_count || 20 }}",
    "{{ " + nz("sixteenSummary.transition_analysis?.summary?.outgoing_count") + " }}")
for _ladder, _n in [("ladder_ice_break", 2), ("ladder_warm_wake", 10),
                    ("ladder_gold_rush", 19), ("ladder_hot_momentum", 23),
                    ("ladder_outgoing_cool", 8)]:
    add("data_sixteen_matrix.html",
        "transition_analysis.ladders?." + _ladder + "?.count || " + str(_n),
        "transition_analysis.ladders?." + _ladder + "?.count ?? '--'")

# ── ops_tri_high_input.html ──
add("ops_tri_high_input.html",
    "String(triHighSummaryData.recommendations?.resonance_gold_single || 24).padStart(2, '0')",
    nz("triHighSummaryData.recommendations?.resonance_gold_single", "pad"))

# ── data_matrix_80.html ──
add("data_matrix_80.html",
    "全部 ({{ matrixFilterCounts.all || 80 }})",
    "全部 ({{ " + nz("matrixFilterCounts.all") + " }})")

# ── common_modals.html ──
add("common_modals.html",
    "近 {{ selectedEvolutionItem.n_reviewed || 30 }} 期滚动",
    "近 {{ " + nz("selectedEvolutionItem.n_reviewed") + " }} 期滚动")


def main():
    failures = []
    applied = 0
    by_file = {}
    for fname, old, new in R:
        path = os.path.join(VIEWS, fname)
        if not os.path.exists(path):
            failures.append((fname, old, "文件不存在"))
            continue
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
        cnt = content.count(old)
        if cnt != 1:
            failures.append((fname, old, f"命中 {cnt} 次 (应为 1)"))
            continue
        content = content.replace(old, new)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
        applied += 1
        by_file[fname] = by_file.get(fname, 0) + 1

    print(f"✅ 已替换 {applied}/{len(R)} 处")
    for fname, c in sorted(by_file.items()):
        print(f"   {fname}: {c} 处")
    if failures:
        print(f"\n❌ {len(failures)} 处未替换:")
        for fname, old, why in failures:
            print(f"   [{fname}] {why}: {old[:90]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
