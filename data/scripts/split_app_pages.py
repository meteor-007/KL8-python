# -*- coding: utf-8 -*-
"""One-shot: split app.js feature clusters into frontend/static/js/pages/*.js"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(ROOT, "frontend", "static", "js", "app.js")
PAGES_DIR = os.path.join(ROOT, "frontend", "static", "js", "pages")

# Inclusive 1-based line ranges to extract into each page module (order = script load order).
# Multiple ranges per module are concatenated in order.
EXTRACTIONS = [
    (
        "jingle",
        [(1710, 1797), (3677, 3696)],
        [
            "jingleSummary", "jingleReview", "jingleRules", "jingleRulesMeta",
            "jingleRuleKindFilter", "jingleRuleSearchKeyword", "jingleLoading",
            "filteredJingleRules", "fetchJingleSummary", "fetchJingleReview",
            "fetchJingleRules", "triggerJingleRun", "jingleReviewPeriods",
            "fetchJingleReviewEnhanced",
        ],
    ),
    (
        "data_hub",
        [(1798, 1883)],
        [
            "spatialPointsSummary", "spatialPointsMatrix", "spatialPointsReview",
            "spatialPointsLoading", "pointsMatrixFilter", "pointsReviewPeriods",
            "filteredPointsMatrix", "fetchSpatialPointsSummary",
            "fetchSpatialPointsMatrix", "fetchSpatialPointsReview",
            "triggerSpatialPointsRun",
        ],
    ),
    (
        "ops",
        [(1885, 2044), (3460, 3675)],
        [
            "dailyPointsInfo", "dailyPointsHistory", "dailyPointsInputText",
            "dailyPointsSelectedBalls", "dailyPointsTargetPeriod", "dailyPointsTargetDate",
            "dailyPointsAutoRun", "dailyPointsSubmitting", "dailyPointsLoading",
            "dailyPointsAnalysis", "fetchDailyPointsInfo", "fetchDailyPointsHistory",
            "toggleDailyPointBall", "syncDailyPointsFromText", "clearDailyPointsInput",
            "submitDailyPointsForm", "triggerDailyPointsSyncAll",
            "triHighSubTab", "triHighHistoryRows", "triHighSummaryData",
            "triHighInputPeriod", "triHighInputDate", "triHighRepeatText",
            "triHighRepeatBalls", "triHighEdgeLeftText", "triHighEdgeLeftBalls",
            "triHighEdgeRightText", "triHighEdgeRightBalls", "triHighColdText",
            "triHighColdBalls", "triHighSaving", "parseTriHighRepeat",
            "parseTriHighEdgeLeft", "parseTriHighEdgeRight", "parseTriHighCold",
            "clearTriHighInputs", "getUnionTriHighCount", "getResonanceWithDailyPoints",
            "fetchTriHighHistory", "fetchTriHighSummary", "saveTriHighRecord",
            "triggerTriHighRun", "selectTriHighQuickPeriod",
        ],
    ),
    (
        "retired",
        [(2046, 2112), (2424, 2509), (2891, 2976)],
        [
            "followSummary", "followReview", "followConditions", "followLoading",
            "followReviewPeriods", "fetchFollowSummary", "fetchFollowReview",
            "fetchFollowConditions", "triggerFollowRun",
            "geminiSummary", "geminiReview", "geminiHistory", "selectedGeminiReport",
            "geminiReportDetail", "geminiLoading", "geminiReviewPeriods",
            "fetchGeminiSummary", "fetchGeminiReview", "fetchGeminiHistory",
            "selectGeminiReport", "triggerGeminiRun",
            "lstmSummary", "lstmReview", "lstmReviewPeriods", "lstmReports",
            "selectedLstmReport", "lstmReportDetail", "lstmLoading",
            "fetchLstmSummary", "fetchLstmReview", "fetchLstmReports",
            "selectLstmReport", "triggerLstmRun",
        ],
    ),
    (
        "suppression",
        [(2114, 2180)],
        [
            "suppressionSummary", "suppressionReview", "suppressionPatterns",
            "suppressionLoading", "suppressionReviewPeriods",
            "fetchSuppressionSummary", "fetchSuppressionReview",
            "fetchSuppressionPatterns", "triggerSuppressionRun",
        ],
    ),
    (
        "point_omission",
        [(2182, 2331)],
        [
            "pointOmissionSummary", "pointOmissionReport", "pointOmissionReportHtml",
            "pointOmissionBacktest", "pointOmissionLoading", "pointOmissionSubTab",
            "getMethodChineseName", "fetchPointOmissionSummary",
            "fetchPointOmissionReport", "fetchPointOmissionBacktest",
            "triggerPointOmissionRun", "setPointOmissionSubTab",
            "isPointOmissionCore", "isPointOmissionExpanded", "isPointOmissionTop5",
            "isPointOmissionDefensive", "getPointOmissionNumScore",
            "getPointOmissionNumMiss", "getPointOmissionMatrixClass",
        ],
    ),
    (
        "gold_pick2",
        [(2511, 2609)],
        [
            "goldPick2Summary", "goldPick2Review", "goldPick2Matrix",
            "goldPick2Logs", "selectedGoldPick2Log", "goldPick2LogDetail",
            "goldPick2Loading", "goldPick2ReviewPeriods",
            "fetchGoldPick2Summary", "fetchGoldPick2Review",
            "fetchGoldPick2Matrix", "fetchGoldPick2Logs",
            "selectGoldPick2Log", "triggerGoldPick2Run",
        ],
    ),
    (
        "aggregation",
        [(2611, 2681)],
        [
            "aggCockpit", "aggHistory", "selectedAggReport", "aggReportDetail",
            "aggLoading", "fetchAggCockpit", "fetchAggHistory",
            "selectAggReport", "triggerAggRun",
        ],
    ),
    (
        "sixteen",
        [(2683, 2888)],
        [
            "sixteenSummary", "sixteenReview", "sixteenReviewPeriods",
            "sixteenHistory", "selectedSixteenReport", "sixteenReportDetail",
            "sixteenLoading", "sixteenMatrixFilter", "filteredSixteenMatrix",
            "setSixteenMatrixFilter", "fetchSixteenSummary", "fetchSixteenReview",
            "fetchSixteenHistory", "selectSixteenReport", "triggerSixteenRun",
            "updateSixteenDistChart",
        ],
    ),
    (
        "cockpit_live",
        [(2978, 3279)],
        [
            "metaGoldSummary", "metaGoldReview", "metaGoldReviewPeriods",
            "metaGoldLoading", "fetchMetaGoldSummary", "fetchMetaGoldReview",
            "funnelSummary", "funnelReview", "funnelReviewPeriods", "funnelLoading",
            "fetchFunnelSummary", "fetchFunnelReview",
            "envRegimeSummary", "fdrAuditSummary", "fdrAuditLoading",
            "moduleCount", "winningCount", "baselineRate", "baselinePct", "pct",
            "qClass", "freshness", "freshnessExpanded", "freshnessLoading",
            "freshnessBadCount", "freshnessMark", "freshnessStateText",
            "freshnessLagText", "fetchFreshness", "moduleRegistry",
            "moduleRegistryLoading", "weeklyAdvice", "weeklyAdviceLoading",
            "fetchModuleRegistry", "fetchWeeklyAdvice", "moduleStatusOf",
            "moduleDisposition", "primeCompositeGate", "psychGameGate",
            "byModuleRows", "voteWeightSum", "registryRows",
            "paperTradingSummary", "fdrAuditPeriods", "paperTradingRolling",
            "fetchEnvRegimeSummary", "fetchFdrAuditSummary",
            "fetchPaperTradingSummary",
        ],
    ),
    (
        "datasource",
        [(3281, 3458)],
        [
            "datasourceSummary", "datasourceReview", "datasourceLogs",
            "selectedDatasourceLog", "datasourceLogDetail", "datasourceLoading",
            "datasourceReviewPeriods", "fetchDatasourceSummary",
            "fetchDatasourceReview", "fetchDatasourceLogs", "selectDatasourceLog",
            "triggerDatasourceRun",
            "datasourceMatrixData", "datasourceMatrixLoading",
            "datasourceMatrixSelectedPeriod", "currentMatrixHighlightMode",
            "matrixHighlightModes", "canPrevDatasourcePeriod",
            "canNextDatasourcePeriod", "fetchDatasourceMatrix",
            "prevDatasourcePeriod", "nextDatasourcePeriod",
            "isCrossIntersection", "getMatrixCellClass",
        ],
    ),
    (
        "reviews_audit",
        [(3698, 3948)],
        [
            "reviewsLedgerData", "reviewsLedgerLimit", "reviewsLedgerLoading",
            "selectedReviewDetail", "showReviewDetailModal", "fetchReviewsLedger",
            "openReviewDetailModal", "closeReviewDetailModal",
            "modulesOverviewData", "modulesOverviewLoading",
            "fetchAllModulesOverview",
            "schedulerStatus", "schedulerLoading", "fetchSchedulerStatus",
            "triggerNightlyRun", "masterReviewData", "masterReviewLoading",
            "masterReviewPeriods", "fetchMasterReview", "triggerMasterReviewRun",
            "evolutionData", "evolutionHistory", "evolutionHistoryStale",
            "evolutionLoading", "fetchEvolutionStatus", "triggerEvolutionRun",
            "selectedEvolutionItem", "showEvolutionModal", "openEvolutionDetail",
            "closeEvolutionDetail",
        ],
    ),
    (
        "unified_brain",
        [(3950, 4012)],
        [
            "unifiedBrainData", "unifiedBrainLoading", "fetchUnifiedBrain",
            "triggerUnifiedBrainRun",
        ],
    ),
]

CTX_DESTRUCTURE = """isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction"""


def dedent_block(text: str, spaces: int = 4) -> str:
    lines = text.splitlines(True)
    out = []
    prefix = " " * spaces
    for line in lines:
        if line.startswith(prefix):
            out.append(line[spaces:])
        else:
            out.append(line)
    return "".join(out)


def wrap_page(name: str, body: str, exports: list[str]) -> str:
    # sixteen: rewrite local chart handle onto shared chartHandles
    body = body.replace(
        "let sixteenDistChart = null;",
        "// chart instance lives on ctx.chartHandles.sixteenDistChart",
    )
    body = re.sub(
        r"\bsixteenDistChart\b",
        "chartHandles.sixteenDistChart",
        body,
    )
    body = body.replace(
        "chartHandles.chartHandles.sixteenDistChart",
        "chartHandles.sixteenDistChart",
    )

    # reviews_audit calls cockpit_live fetchers — bind lazily via ctx
    extra_prelude = ""
    if name == "reviews_audit":
        extra_prelude = """
    const fetchMetaGoldSummary = (...args) => ctx.fetchMetaGoldSummary(...args);
    const fetchFunnelSummary = (...args) => ctx.fetchFunnelSummary(...args);
"""

    export_obj = ",\n      ".join(exports)
    return f"""/**
 * K8 page module: {name}
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {{
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {{
    console.error('[K8Pages] registry missing — load k8_pages.js first ({name})');
    return;
  }}

  window.K8Pages.register(function (vueApi, ctx) {{
    const {{ ref, reactive, computed, nextTick }} = vueApi;
    const {{
      {CTX_DESTRUCTURE}
    }} = ctx;
{extra_prelude}
{body.rstrip()}

    return {{
      {export_obj}
    }};
  }});
}})();
"""


def main() -> int:
    with open(APP_JS, "r", encoding="utf-8") as f:
        lines = f.readlines()

    os.makedirs(PAGES_DIR, exist_ok=True)

    # Build page files
    all_exports: list[str] = []
    for name, ranges, exports in EXTRACTIONS:
        chunks = []
        for start, end in ranges:
            chunk = "".join(lines[start - 1 : end])
            chunks.append(dedent_block(chunk, 4))
        body = "\n".join(chunks)
        # Indent body one level for inside register function
        indented = "".join(
            ("    " + ln if ln.strip() else ln) for ln in body.splitlines(True)
        )
        page_src = wrap_page(name, indented, exports)
        out_path = os.path.join(PAGES_DIR, f"{name}.js")
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(page_src)
        print(f"Wrote {out_path} ({len(page_src.splitlines())} lines)")
        all_exports.extend(exports)

    # Mark lines for removal (1-based)
    remove = set()
    for _, ranges, _ in EXTRACTIONS:
        for start, end in ranges:
            remove.update(range(start, end + 1))

    # Insert apply block at first extraction line (jingle start)
    insert_at = min(r[0] for _, ranges, _ in EXTRACTIONS for r in ranges)

    # chartHandles + apply destructuring
    export_lines = ",\n      ".join(all_exports)
    apply_block = f"""    // ─── K8 page modules (extracted fetch/state clusters) ───
    const chartHandles = {{ sixteenDistChart: null }};
    const __k8PageBindings = window.K8Pages.apply(
      {{ ref, reactive, computed, watch, nextTick }},
      {{
        isRunning,
        openTab,
        addLog,
        startLogPolling,
        getThemeColors,
        terminalLogs,
        chartHandles,
        fetchPrediction,
        // late-bound wrappers: safe to capture during apply; resolve at call-time
        fetchMetaGoldSummary(...args) {{
          return __k8PageBindings.fetchMetaGoldSummary(...args);
        }},
        fetchFunnelSummary(...args) {{
          return __k8PageBindings.fetchFunnelSummary(...args);
        }}
      }}
    );
    const {{
      {export_lines}
    }} = __k8PageBindings;

"""

    new_lines = []
    for i, line in enumerate(lines, start=1):
        if i == insert_at:
            new_lines.append(apply_block)
        if i in remove:
            continue
        new_lines.append(line)

    # Fix chart references in remaining app.js shell
    text = "".join(new_lines)
    text = text.replace(
        "if (sixteenElem && !sixteenDistChart) {\n        sixteenDistChart = echarts.init(sixteenElem);\n      }",
        "if (sixteenElem && !chartHandles.sixteenDistChart) {\n        chartHandles.sixteenDistChart = echarts.init(sixteenElem);\n      }",
    )
    text = text.replace(
        "if (sixteenDistChart) sixteenDistChart.resize();",
        "if (chartHandles.sixteenDistChart) chartHandles.sixteenDistChart.resize();",
    )

    # psych game early refs stay in app.js; page only has triggers that call fetch* from shell.
    # But we also need fetchPsychologicalGameData in scope for triggers in psychological_game page —
    # those are still in app.js, NOT in page exports. The page factory closes over ctx — need to pass them.
    # Fix: leave psych triggers in app.js instead of extracting, OR pass fetches via ctx.
    # Re-extract: don't put psych/prime triggers in a page that can't see fetchPsychologicalGameData.
    # Actually those triggers are IN the page module and call fetchPsychologicalGameData which is NOT in ctx.
    # Solution: keep psychological_game.js triggers but they need ctx.fetchPsychologicalGameData.
    # Easier: DO NOT extract psychological_game / prime triggers — leave in app.js.

    with open(APP_JS, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    print(f"Updated {APP_JS}: {len(lines)} -> {len(text.splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
