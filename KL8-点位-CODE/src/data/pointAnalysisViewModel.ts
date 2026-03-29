import {
  analyzeClusterDynamics,
  analyzeComplexSequence,
  analyzeCyclicPatterns,
  analyzeGraphNetwork,
  analyzeHeatZones,
  analyzeMarkov,
  analyzeVolatility,
  backtestRuleSet,
  buildUnifiedDecisionSummary,
  countHitsInRecent,
  compareEnhancedBacktest,
  computeEntropy,
  computeScoreCards,
  detectMarketRegime,
  expandPositions,
  getCooccurrenceTop,
  getFinalRecommendation,
  getPositionStats,
  getPreviousHighUnopened,
  getRiskWarnings,
  type ConflictSignal,
  type EnhancedBacktestComparison,
  type ExpertConsensusInput,
  type FeatureContributionBreakdown,
  type FinalRecommendation,
  type MarketRegime,
  type PositionStat,
  type RiskWarning,
  type RuleBacktestResult,
  type ScoreCard,
  type UnifiedDecisionSummary,
} from './analysisEngine';
import type { ExpertDashboardData } from './dataLoader';

export type PointAnalysisSectionKey =
  | 'overview'
  | 'distribution'
  | 'structure'
  | 'dynamics'
  | 'regime'
  | 'validation'
  | 'decision';

export interface PointAnalysisSectionDefinition {
  key: PointAnalysisSectionKey;
  label: string;
  icon: string;
  description: string;
}

export interface TechnicalInsightCard {
  title: string;
  summary: string;
  confidence: '高' | '中' | '低';
}

export interface EvidenceMetric {
  label: string;
  value: string;
  detail?: string;
}

export interface ValidationSummary {
  bestRule: string;
  weakestRule: string;
  average30Window: number;
  average60Window: number;
  average120Window: number;
  enhancedLift30: number;
  enhancedLift60: number;
  enhancedLift120: number;
  enhancedPassed: boolean;
}

export interface PointCalibrationSummary {
  bins: Array<{
    scoreRange: string;
    sampleSize: number;
    observedHitRate: number;
    predictedHitRate: number;
    calibratedConfidence: '高' | '中' | '低';
    reliable: boolean;
  }>;
  overallReliable: boolean;
}

export interface PointAnalysisDashboardModel {
  sections: PointAnalysisSectionDefinition[];
  overview: {
    question: string;
    findings: TechnicalInsightCard[];
    relatedSections: string[];
    cores: number[];
    expanded: number[];
    latestDraw: number[];
    latestHitCores: number[];
    latestMissCores: number[];
    metrics: EvidenceMetric[];
    dataHealth: {
      pointsLatestDate: string | null;
      historyLatestDate: string | null;
      expertLatestDate: string | null;
      statusText: string;
      confidence: '高' | '中' | '低';
    };
  };
  distribution: {
    question: string;
    findings: TechnicalInsightCard[];
    relatedSections: string[];
    positionStats: PositionStat[];
    hotZones: ReturnType<typeof analyzeHeatZones>;
    topFrequency: PositionStat[];
    longMiss: PositionStat[];
  };
  structure: {
    question: string;
    findings: TechnicalInsightCard[];
    relatedSections: string[];
    clusters: ReturnType<typeof analyzeClusterDynamics>;
    networkStats: ReturnType<typeof analyzeGraphNetwork>;
    structureAdvanced: {
      topBridges: ReturnType<typeof analyzeGraphNetwork>;
      averageCommunityDensity: number;
      averageStructuralStability: number;
      anomaly: boolean;
    };
    cooccurrencePairs: ReturnType<typeof getCooccurrenceTop>;
    heatZones: ReturnType<typeof analyzeHeatZones>;
  };
  dynamics: {
    question: string;
    findings: TechnicalInsightCard[];
    relatedSections: string[];
    cyclicPatterns: ReturnType<typeof analyzeCyclicPatterns>;
    markov: ReturnType<typeof analyzeMarkov>;
    volatilityStats: ReturnType<typeof analyzeVolatility>;
    complexSequence: ReturnType<typeof analyzeComplexSequence>;
    sequenceAdvanced: ReturnType<typeof analyzeComplexSequence>;
  };
  regime: {
    question: string;
    findings: TechnicalInsightCard[];
    relatedSections: string[];
    regime: MarketRegime;
    entropy: ReturnType<typeof computeEntropy>;
    conflicts: ConflictSignal[];
  };
  validation: {
    question: string;
    findings: TechnicalInsightCard[];
    relatedSections: string[];
    results: RuleBacktestResult[];
    baselineResults: RuleBacktestResult[];
    enhancedComparison: EnhancedBacktestComparison;
    featureContribution: FeatureContributionBreakdown[];
    summary: ValidationSummary;
  };
  timeline: {
    question: string;
    findings: TechnicalInsightCard[];
    relatedSections: string[];
    coverageSnapshots: TimelineSnapshot[];
    recommendationReplays: RecommendationReplayRow[];
    actionStats: ActionReplayStats[];
    snapshots: TimelineSnapshot[];
  };
  decision: {
    question: string;
    findings: TechnicalInsightCard[];
    relatedSections: string[];
    scoreCards: ScoreCard[];
    unifiedDecision: UnifiedDecisionSummary;
    finalRecommendation: FinalRecommendation;
    riskWarnings: RiskWarning[];
    expertConsensus: ExpertConsensusInput;
    calibration: PointCalibrationSummary;
    structureAdvanced: {
      topBridges: ReturnType<typeof analyzeGraphNetwork>;
      anomaly: boolean;
    };
    sequenceAdvanced: ReturnType<typeof analyzeComplexSequence>;
    enhancedComparison: EnhancedBacktestComparison;
    featureContribution: FeatureContributionBreakdown[];
  };
}

export interface BuildPointAnalysisDashboardInput {
  cores: number[];
  prevCores: number[];
  draws: number[][];
  historyTimeline: Array<{ date: string; period: string; numbers: number[] }>;
  pointsTimeline: Array<{ date: string; points: number[] }>;
  expertDashboard: ExpertDashboardData | null;
  pointsLatestDate: string | null;
  historyLatestDate: string | null;
  expertLatestDate: string | null;
}

export interface TimelineSnapshot {
  date: string;
  period: string;
  label: string;
  hitCount: number;
  coverageRatio: number;
  coreHits: string[];
  state: '高覆盖' | '中覆盖' | '低覆盖';
}

export interface RecommendationReplayRow {
  date: string;
  period: string;
  label: string;
  recommendedTop5: string[];
  recommendedCore5: string[];
  recommendedBackup2: string[];
  actualNumbers: string[];
  top5Hits: string[];
  core5Hits: string[];
  backup2Hits: string[];
  top5HitCount: number;
  core5HitCount: number;
  backup2HitCount: number;
  decisionAction: '顺势' | '对冲' | '跟随' | '观察';
  decisionConfidence: '高' | '中' | '低';
  consensusHighlights: string[];
  whyHit: string;
  whyMiss: string;
  riskContext: string;
  dataReady: boolean;
  missingReason: string | null;
}

export interface ActionReplayStats {
  action: '顺势' | '对冲' | '跟随' | '观察';
  periods: number;
  hitPeriods: number;
  hitRate: number;
  averageTop5Hits: number;
}

const POINT_ANALYSIS_SECTIONS: PointAnalysisSectionDefinition[] = [
  { key: 'overview', label: '信号总览', icon: '🧭', description: '先看当前信号快照、覆盖状态与数据健康。' },
  { key: 'distribution', label: '分布与覆盖', icon: '📐', description: '看频率、覆盖率、局部密度与分布缺口。' },
  { key: 'structure', label: '结构关联', icon: '🕸️', description: '看集群、热区、共现和网络中心性。' },
  { key: 'dynamics', label: '动态演化', icon: '🌊', description: '看周期、转移、波动和序列形态。' },
  { key: 'regime', label: '状态识别', icon: '🧠', description: '看系统处于什么状态，以及状态是否稳定。' },
  { key: 'validation', label: '规则验证', icon: '🧪', description: '看规则在近期窗口里是否真的有效。' },
  { key: 'decision', label: '综合判断', icon: '🎯', description: '汇总多模型共识、风险和最终技术判断。' },
];

function confidenceFromRatio(ratio: number): '高' | '中' | '低' {
  if (ratio >= 0.7) return '高';
  if (ratio >= 0.35) return '中';
  return '低';
}

function formatNumber(value: number): string {
  return String(value).padStart(2, '0');
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function average(values: number[]): number {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function decideReplayAction(
  regimeKey: PointAnalysisDashboardModel['regime']['regime']['key'],
  entropyValue: number,
  top5Count: number,
  markovIntersection: number,
  conflicts: number
): '顺势' | '对冲' | '跟随' | '观察' {
  if (regimeKey === 'hot' && top5Count >= 3 && markovIntersection >= 3 && conflicts === 0) {
    return '顺势';
  }
  if (entropyValue >= 5.2 || conflicts >= 2) {
    return '对冲';
  }
  if (top5Count >= 2 || markovIntersection >= 2) {
    return '跟随';
  }
  return '观察';
}

function summarizeReplayHit(
  actualNumbers: number[],
  hitNumbers: number[],
  driversByNumber: Map<number, string[]>
) {
  if (!actualNumbers.length) {
    return '当期开奖数据缺失，无法判断命中原因。';
  }
  if (!hitNumbers.length) {
    return '';
  }
  return hitNumbers
    .slice(0, 3)
    .map((num) => {
      const reasons = (driversByNumber.get(num) || []).slice(0, 2);
      return reasons.length ? `${formatNumber(num)}：${reasons.join('、')}` : `${formatNumber(num)}：多证据共振`;
    })
    .join('；');
}

function summarizeReplayMiss(
  actualNumbers: number[],
  top5Hits: number[],
  conflictsByNumber: Map<number, string[]>,
  unifiedConflicts: string[],
  riskDescriptions: string[],
  action: string
) {
  if (!actualNumbers.length) {
    return '当期开奖数据缺失，无法判断是否失手。';
  }
  if (top5Hits.length > 0) {
    return '本期出现部分命中，但仍有未覆盖区域，建议结合风险提示继续收窄。';
  }
  const merged = [...[...conflictsByNumber.values()].flat(), ...unifiedConflicts, ...riskDescriptions].filter(Boolean);
  const summary = merged.slice(0, 3).join('、');
  return summary ? `${action}策略未命中，主要受到${summary}影响。` : `${action}策略未命中，当期结构与动态证据支撑不足。`;
}

function buildRecommendationReplays(
  pointsTimeline: Array<{ date: string; points: number[] }>,
  historyTimeline: Array<{ date: string; period: string; numbers: number[] }>
): { replays: RecommendationReplayRow[]; actionStats: ActionReplayStats[] } {
  const replays = pointsTimeline.slice(0, 10).map((pointEntry, index) => {
    const actualRow = historyTimeline.find((item) => item.date === pointEntry.date) || null;
    const visibleHistory = historyTimeline.filter((item) => item.date < pointEntry.date);
    const replayDraws = visibleHistory.map((item) => item.numbers);
    const cores = pointEntry.points;
    const prevCores = pointsTimeline[index + 1]?.points ?? [];
    const unopenedHighScores = getPreviousHighUnopened(prevCores, replayDraws);
    const scoreCards = computeScoreCards(cores, replayDraws, unopenedHighScores).sort((a, b) => b.totalScore - a.totalScore);
    const markovTop = analyzeMarkov(cores, replayDraws).predictions.slice(0, 8).map((item) => item.number);
    const hotZoneNumbers = new Set(
      analyzeHeatZones(cores, replayDraws)
        .filter((zone) => zone.temperature !== 'cold')
        .flatMap((zone) => zone.numbers)
    );
    const clusterNumbers = new Set(analyzeClusterDynamics(cores, replayDraws).flatMap((cluster) => cluster.numbers));
    const cooccurrencePairs = getCooccurrenceTop(cores, replayDraws);
    const pairSupportMap = new Map<number, number>();
    cooccurrencePairs.forEach((item) => {
      pairSupportMap.set(item.pair[0], (pairSupportMap.get(item.pair[0]) || 0) + item.count);
      pairSupportMap.set(item.pair[1], (pairSupportMap.get(item.pair[1]) || 0) + item.count);
    });
    const volatilityMap = new Map(analyzeVolatility(cores, replayDraws).map((item) => [item.number, item]));
    const contributionMap = new Map(
      scoreCards.map((item) => [
        item.number,
        {
          structureBoost: Number((item.graphScore * 0.06).toFixed(1)),
          sequenceBoost: Number((item.sequenceScore * 0.06).toFixed(1)),
        },
      ])
    );
    const driversByNumber = new Map<number, string[]>();
    const conflictsByNumber = new Map<number, string[]>();

    const recommendedTop5 = scoreCards
      .slice(0, 12)
      .map((card) => {
        const drivers: string[] = [];
        const conflicts: string[] = [];
        let adjusted = card.totalScore;

        if (markovTop.includes(card.number)) {
          adjusted += 8;
          drivers.push('Markov 交集支持');
        }
        if (hotZoneNumbers.has(card.number)) {
          adjusted += 6;
          drivers.push('热区支持');
        }
        if (clusterNumbers.has(card.number)) {
          adjusted += 6;
          drivers.push('集群支持');
        }

        const pairSupport = pairSupportMap.get(card.number) || 0;
        if (pairSupport >= 2) {
          adjusted += Math.min(8, pairSupport);
          drivers.push(`共现 ${pairSupport} 次`);
        }

        const recentHits = countHitsInRecent(card.number, 8, replayDraws);
        if (recentHits > 0) {
          adjusted += Math.min(6, recentHits * 2);
          drivers.push(`近8期命中 ${recentHits} 次`);
        }

        const volatility = volatilityMap.get(card.number);
        if (card.missScore >= 60) {
          adjusted -= 5;
          conflicts.push('遗漏压力偏高');
        }
        if (volatility && volatility.volatility >= 0.16) {
          adjusted -= 4;
          conflicts.push('波动偏高');
        }
        if (!markovTop.includes(card.number) && !hotZoneNumbers.has(card.number) && !clusterNumbers.has(card.number)) {
          adjusted -= 3;
          conflicts.push('缺少强结构支撑');
        }

        const contribution = contributionMap.get(card.number);
        if ((contribution?.structureBoost || 0) > 2.5) {
          drivers.push('图网络增强');
        }
        if ((contribution?.sequenceBoost || 0) > 2.5) {
          drivers.push('序列谱增强');
        }

        driversByNumber.set(card.number, drivers);
        conflictsByNumber.set(card.number, conflicts);
        return { number: card.number, adjusted };
      })
      .sort((a, b) => b.adjusted - a.adjusted)
      .slice(0, 5)
      .map((item) => item.number);

    const finalRecommendation = getFinalRecommendation(cores, replayDraws, unopenedHighScores);
    const unifiedDecision = buildUnifiedDecisionSummary(cores, replayDraws, {
      repeatedNumbers: [],
      focusNumbers: [],
      focusMatrices: [],
      historicalSupportByNumber: {},
      missingDataPenalty: 0.4,
    });
    const riskWarnings = getRiskWarnings(cores, replayDraws);
    const regime = detectMarketRegime(cores, replayDraws);
    const entropy = computeEntropy(replayDraws);
    const markovIntersection = markovTop.filter((num) => recommendedTop5.includes(num)).length;
    const action = decideReplayAction(
      regime.key,
      entropy.value,
      recommendedTop5.length,
      markovIntersection,
      unifiedDecision.conflicts.length + riskWarnings.length
    );

    const actualNumbers = actualRow?.numbers ?? [];
    const top5Hits = recommendedTop5.filter((num) => actualNumbers.includes(num));
    const core5Hits = finalRecommendation.core5.filter((num) => actualNumbers.includes(num));
    const backup2Hits = finalRecommendation.backup2.filter((num) => actualNumbers.includes(num));

    return {
      date: pointEntry.date,
      period: actualRow?.period ?? `${pointEntry.date.replace(/-/g, '')}-missing`,
      label: `${pointEntry.date} / ${actualRow?.period ?? '缺开奖'}`,
      recommendedTop5: recommendedTop5.map(formatNumber),
      recommendedCore5: finalRecommendation.core5.map(formatNumber),
      recommendedBackup2: finalRecommendation.backup2.map(formatNumber),
      actualNumbers: actualNumbers.map(formatNumber),
      top5Hits: top5Hits.map(formatNumber),
      core5Hits: core5Hits.map(formatNumber),
      backup2Hits: backup2Hits.map(formatNumber),
      top5HitCount: top5Hits.length,
      core5HitCount: core5Hits.length,
      backup2HitCount: backup2Hits.length,
      decisionAction: action,
      decisionConfidence: unifiedDecision.confidence,
      consensusHighlights: unifiedDecision.topNumbers
        .slice(0, 3)
        .map((item) => `${formatNumber(item.number)}：${item.reasons.slice(0, 2).join('、')}`),
      whyHit: summarizeReplayHit(actualNumbers, top5Hits, driversByNumber),
      whyMiss: summarizeReplayMiss(
        actualNumbers,
        top5Hits,
        conflictsByNumber,
        unifiedDecision.conflicts.map((item) => item.description),
        riskWarnings.map((item) => item.description),
        action
      ),
      riskContext: riskWarnings[0]?.description || unifiedDecision.conflicts[0]?.description || '当期未出现明显风险警报。',
      dataReady: !!actualRow,
      missingReason: actualRow ? null : '开奖数据缺失，无法完整复盘',
    } satisfies RecommendationReplayRow;
  });

  const actionTypes: Array<ActionReplayStats['action']> = ['顺势', '对冲', '跟随', '观察'];
  const actionStats = actionTypes.map((action) => {
    const matched = replays.filter((item) => item.dataReady && item.decisionAction === action);
    const hitPeriods = matched.filter((item) => item.top5HitCount > 0).length;
    return {
      action,
      periods: matched.length,
      hitPeriods,
      hitRate: matched.length ? hitPeriods / matched.length : 0,
      averageTop5Hits: matched.length ? average(matched.map((item) => item.top5HitCount)) : 0,
    };
  });

  return { replays, actionStats };
}

function summarizeExpertConsensus(dashboard: ExpertDashboardData | null): ExpertConsensusInput {
  if (!dashboard) {
    return {
      repeatedNumbers: [],
      focusNumbers: [],
      focusMatrices: [],
      historicalSupportByNumber: {},
      missingDataPenalty: 0.6,
    };
  }

  const latestView = dashboard.dailyMatrixViews?.[0];
  const repeatedCounter = new Map<number, number>();
  latestView?.sourceGroups.forEach(group => {
    group.matrices.forEach(matrix => {
      matrix.rows.flat().forEach(value => {
        if (!value) return;
        const num = Number(value);
        repeatedCounter.set(num, (repeatedCounter.get(num) || 0) + 1);
      });
    });
  });

  const repeatedNumbers = [...repeatedCounter.entries()]
    .filter(([, count]) => count >= 2)
    .map(([number]) => number)
    .sort((a, b) => a - b);

  const focusNumbers = (dashboard.insightSummary?.focusNumbers || [])
    .map(item => Number(item.number))
    .filter(num => !Number.isNaN(num));

  const focusMatrices = (dashboard.insightSummary?.focusMatrices || [])
    .map(item => `${item.sourceTitle}·${item.matrixTitle}`);

  const historicalSupportByNumber: Record<number, number> = {};
  const recentRows = (dashboard.trackingDetails || []).slice(0, 12);
  recentRows.forEach(row => {
    const weightBase = row.isPending ? 0.2 : 1;
    row.top12.forEach(num => {
      const key = Number(num);
      const hitBonus = row.top12Hits.includes(num) ? 1.2 : 0;
      historicalSupportByNumber[key] = Number(((historicalSupportByNumber[key] || 0) + weightBase + hitBonus).toFixed(2));
    });
    row.gold7.forEach(num => {
      const key = Number(num);
      const hitBonus = row.gold7Hits.includes(num) ? 1.5 : 0;
      historicalSupportByNumber[key] = Number(((historicalSupportByNumber[key] || 0) + weightBase * 0.8 + hitBonus).toFixed(2));
    });
    row.gold2.forEach(num => {
      const key = Number(num);
      const hitBonus = row.gold2Hits.includes(num) ? 1.8 : 0;
      historicalSupportByNumber[key] = Number(((historicalSupportByNumber[key] || 0) + weightBase * 0.6 + hitBonus).toFixed(2));
    });
  });

  const pendingCount = recentRows.filter(row => row.isPending || row.missingActualData).length;
  const missingDataPenalty = recentRows.length ? Number((pendingCount / recentRows.length).toFixed(2)) : 0.4;

  return {
    repeatedNumbers,
    focusNumbers,
    focusMatrices,
    historicalSupportByNumber,
    missingDataPenalty,
  };
}

export function buildPointAnalysisDashboardModel(
  input: BuildPointAnalysisDashboardInput
): PointAnalysisDashboardModel {
  const {
    cores,
    prevCores,
    draws,
    historyTimeline,
    pointsTimeline,
    expertDashboard,
    pointsLatestDate,
    historyLatestDate,
    expertLatestDate,
  } = input;

  const expanded = expandPositions(cores);
  const expertConsensus = summarizeExpertConsensus(expertDashboard);
  const latestDraw = draws[0] ?? [];
  const latestHitCores = cores.filter((num) => latestDraw.includes(num));
  const latestMissCores = cores.filter((num) => !latestDraw.includes(num));
  const positionStats = getPositionStats(cores, expanded, draws);
  const hotZones = analyzeHeatZones(cores, draws);
  const clusters = analyzeClusterDynamics(cores, draws);
  const cyclicPatterns = analyzeCyclicPatterns(cores, draws);
  const markov = analyzeMarkov(cores, draws);
  const networkStats = analyzeGraphNetwork(cores, draws);
  const volatilityStats = analyzeVolatility(cores, draws);
  const cooccurrencePairs = getCooccurrenceTop(cores, draws);
  const complexSequence = analyzeComplexSequence(cores, draws);
  const entropy = computeEntropy(draws);
  const regime = detectMarketRegime(cores, draws);
  const baselineValidationResults = backtestRuleSet(cores, draws, { includeEnhanced: false });
  const validationResults = backtestRuleSet(cores, draws, { includeEnhanced: true });
  const enhancedComparison = compareEnhancedBacktest(baselineValidationResults, validationResults);
  const unopenedHighScores = getPreviousHighUnopened(prevCores, draws);
  const scoreCards = computeScoreCards(cores, draws, unopenedHighScores).sort((a, b) => b.totalScore - a.totalScore);
  const featureContribution = scoreCards
    .map(item => {
      const structureBoost = Number((item.graphScore * 0.06).toFixed(1));
      const sequenceBoost = Number((item.sequenceScore * 0.06).toFixed(1));
      return {
        number: item.number,
        structureBoost,
        sequenceBoost,
        totalBoost: Number((structureBoost + sequenceBoost).toFixed(1)),
      };
    })
    .sort((a, b) => b.totalBoost - a.totalBoost)
    .slice(0, 10);
  const finalRecommendation = getFinalRecommendation(cores, draws, unopenedHighScores);
  const riskWarnings = getRiskWarnings(cores, draws);
  const unifiedDecision = buildUnifiedDecisionSummary(cores, draws, expertConsensus);
  const replayBundle = buildRecommendationReplays(pointsTimeline, historyTimeline);
  const timelineSnapshots = historyTimeline.slice(0, 10).map((item, index) => {
    const coreHits = cores.filter((num) => item.numbers.includes(num)).map(formatNumber);
    const coverageRatio = cores.length ? coreHits.length / cores.length : 0;
    return {
      date: item.date,
      period: item.period,
      label: `${index + 1}. ${item.date.slice(5)} · ${item.period}`,
      hitCount: coreHits.length,
      coverageRatio,
      coreHits,
      state: coverageRatio >= 0.7 ? '高覆盖' : coverageRatio >= 0.35 ? '中覆盖' : '低覆盖',
    } as TimelineSnapshot;
  });

  const topFrequency = [...positionStats].sort((a, b) => b.hits10 - a.hits10).slice(0, 8);
  const longMiss = [...positionStats].sort((a, b) => b.misses - a.misses).slice(0, 8);
  const hottestZone = [...hotZones].sort((a, b) => b.energy - a.energy)[0];
  const bestCluster = [...clusters].sort((a, b) => b.clusterScore - a.clusterScore)[0];
  const topCentralNode = networkStats[0];
  const topCyclic = [...cyclicPatterns].sort((a, b) => b.resonanceScore - a.resonanceScore)[0];
  const topMarkov = markov.predictions[0];
  const mostVolatile = volatilityStats[0];
  const bestRule = [...validationResults].sort((a, b) => b.windows.w30 - a.windows.w30)[0];
  const weakestRule = [...validationResults].sort((a, b) => a.windows.w30 - b.windows.w30)[0];
  const coverageRatio = cores.length ? latestHitCores.length / cores.length : 0;
  const averageCommunityDensity = networkStats.length
    ? networkStats.reduce((sum, item) => sum + item.communityDensity, 0) / networkStats.length
    : 0;
  const averageStructuralStability = networkStats.length
    ? networkStats.reduce((sum, item) => sum + item.structuralStability, 0) / networkStats.length
    : 0;
  const structureAnomaly =
    networkStats.filter(item => item.bridgeScore >= 0.45 && item.structuralStability < 0.35).length >= 2 ||
    averageCommunityDensity < 0.28;
  const averageTimelineCoverage = timelineSnapshots.length
    ? timelineSnapshots.reduce((sum, item) => sum + item.coverageRatio, 0) / timelineSnapshots.length
    : 0;
  const dataHealthAligned =
    !!pointsLatestDate &&
    !!historyLatestDate &&
    !!expertLatestDate &&
    pointsLatestDate === expertLatestDate &&
    historyLatestDate >= pointsLatestDate;

  return {
    sections: POINT_ANALYSIS_SECTIONS,
    overview: {
      question: '当前系统里有哪些核心信号、当前覆盖表现如何、数据是否处于可分析状态？',
      findings: [
        {
          title: '最新覆盖状态',
          summary: `最新一期覆盖 ${latestHitCores.length}/${cores.length} 个核心信号，覆盖率 ${formatPercent(coverageRatio)}。`,
          confidence: confidenceFromRatio(coverageRatio),
        },
        {
          title: '扩展邻域规模',
          summary: `核心 ${cores.length} 个，扩展邻域 ${expanded.length} 个，当前适合先看扩展覆盖再看局部结构。`,
          confidence: expanded.length >= cores.length * 2 ? '高' : '中',
        },
        {
          title: '数据健康状态',
          summary: dataHealthAligned
            ? '点位、历史与专家数据日期对齐，可直接进入后续分析。'
            : '存在日期错位或缺失，后续判断应降低置信度。',
          confidence: dataHealthAligned ? '高' : '低',
        },
      ],
      relatedSections: ['分布与覆盖', '状态识别', '综合判断'],
      cores,
      expanded,
      latestDraw,
      latestHitCores,
      latestMissCores,
      metrics: [
        { label: '核心信号数', value: `${cores.length}`, detail: '当前主信号集合规模' },
        { label: '扩展邻域数', value: `${expanded.length}`, detail: '按邻域展开后的总覆盖规模' },
        { label: '最新命中数', value: `${latestHitCores.length}`, detail: '最新一期落入核心集合的数量' },
        { label: '最新未命中数', value: `${latestMissCores.length}`, detail: '最新一期未被核心集合覆盖的数量' },
      ],
      dataHealth: {
        pointsLatestDate,
        historyLatestDate,
        expertLatestDate,
        statusText: dataHealthAligned ? '数据对齐，分析置信度较高。' : '数据存在错位，最新判断需谨慎。',
        confidence: dataHealthAligned ? '高' : '低',
      },
    },
    distribution: {
      question: '这些信号在近期窗口里分布是否均匀，哪些区域过热、哪些区域稀疏？',
      findings: [
        {
          title: '高频层',
          summary: topFrequency.length
            ? `近期频率最高的是 ${topFrequency.slice(0, 3).map((item) => formatNumber(item.num)).join('、')}。`
            : '暂无足够数据建立高频层。',
          confidence: topFrequency.length ? '高' : '低',
        },
        {
          title: '稀疏层',
          summary: longMiss.length
            ? `近期遗漏最长的是 ${longMiss.slice(0, 3).map((item) => formatNumber(item.num)).join('、')}。`
            : '暂无足够数据识别稀疏层。',
          confidence: longMiss.length ? '中' : '低',
        },
        {
          title: '区域覆盖',
          summary: hottestZone
            ? `${hottestZone.zone} 当前能量最高，说明分布并不均匀，存在明显局部聚集。`
            : '区域能量尚未形成明显差异。',
          confidence: hottestZone?.numbers.length ? '高' : '低',
        },
      ],
      relatedSections: ['结构关联', '动态演化'],
      positionStats,
      hotZones,
      topFrequency,
      longMiss,
    },
    structure: {
      question: '这些信号之间有哪些局部团簇、共现关系和网络中心节点？',
      findings: [
        {
          title: '最强集群',
          summary: bestCluster
            ? `当前最强集群是 ${bestCluster.numbers.map(formatNumber).join('、')}，集群分数 ${bestCluster.clusterScore}。`
            : '当前没有形成显著集群结构。',
          confidence: bestCluster ? '高' : '低',
        },
        {
          title: '热区中心',
          summary: hottestZone
            ? `${hottestZone.zone} 为当前热区中心，说明结构热点集中在 ${hottestZone.range}。`
            : '当前没有形成明确热区中心。',
          confidence: hottestZone ? '中' : '低',
        },
        {
          title: '桥接与稳定',
          summary: topCentralNode
            ? `${formatNumber(topCentralNode.number)} 桥接度最高，结构稳定度均值 ${(averageStructuralStability * 100).toFixed(0)}%。`
            : '暂无足够数据识别桥接节点。',
          confidence: topCentralNode && !structureAnomaly ? '高' : '中',
        },
      ],
      relatedSections: ['分布与覆盖', '动态演化', '综合判断'],
      clusters,
      networkStats,
      structureAdvanced: {
        topBridges: networkStats.slice(0, 5),
        averageCommunityDensity: Number(averageCommunityDensity.toFixed(3)),
        averageStructuralStability: Number(averageStructuralStability.toFixed(3)),
        anomaly: structureAnomaly,
      },
      cooccurrencePairs,
      heatZones: hotZones,
    },
    dynamics: {
      question: '这些信号在时间维度上是延续、回摆、切换，还是处于突变状态？',
      findings: [
        {
          title: '周期焦点',
          summary: topCyclic
            ? `${formatNumber(topCyclic.number)} 的周期共振分最高，当前处于 ${topCyclic.phase}。`
            : '暂无明显周期焦点。',
          confidence: topCyclic ? '中' : '低',
        },
        {
          title: '状态转移',
          summary: topMarkov
            ? `${formatNumber(topMarkov.number)} 的转移概率最高，下一步更可能保持 ${topMarkov.nextPrediction}。`
            : '暂无明显状态转移优势。',
          confidence: topMarkov ? '高' : '低',
        },
        {
          title: '波动簇',
          summary: mostVolatile
            ? `${formatNumber(mostVolatile.number)} 波动最强，属于 ${mostVolatile.cluster}。`
            : '暂无明显波动差异。',
          confidence: mostVolatile ? '中' : '低',
        },
        {
          title: '序列频谱状态',
          summary: `主频峰 ${complexSequence.spectralPeak}，不稳定度 ${complexSequence.sequenceInstability}，当前为 ${complexSequence.stateLabel}。`,
          confidence: complexSequence.stateLabel === '局部突变' || complexSequence.stateLabel === '高噪失稳' ? '中' : '高',
        },
      ],
      relatedSections: ['状态识别', '规则验证'],
      cyclicPatterns,
      markov,
      volatilityStats,
      complexSequence,
      sequenceAdvanced: complexSequence,
    },
    regime: {
      question: '系统当前属于什么状态，这种状态是否支持已有结构规律继续有效？',
      findings: [
        {
          title: '当前状态标签',
          summary: `${regime.label}：${regime.description}`,
          confidence: '高',
        },
        {
          title: '系统熵状态',
          summary: `当前熵值 ${entropy.value}，属于 ${entropy.level}，说明系统整体 ${entropy.description}。`,
          confidence: entropy.level === '高均衡' ? '中' : '高',
        },
        {
          title: '冲突信号',
          summary: unifiedDecision.conflicts.length
            ? `当前检测到 ${unifiedDecision.conflicts.length} 个结构与动态之间的冲突信号。`
            : '当前未检测到明显冲突，结构与动态判断基本一致。',
          confidence: unifiedDecision.conflicts.length ? '中' : '高',
        },
      ],
      relatedSections: ['动态演化', '规则验证', '综合判断'],
      regime,
      entropy,
      conflicts: unifiedDecision.conflicts,
    },
    validation: {
      question: '这些规则在近期窗口里到底有没有用，是否出现失效或阶段性退化？',
      findings: [
        {
          title: '近期最强规则',
          summary: bestRule
            ? `${bestRule.label} 在 30 期窗口表现最好，近期可信度 ${bestRule.confidence}。`
            : '暂无规则验证结果。',
          confidence: bestRule?.confidence ?? '低',
        },
        {
          title: '近期最弱规则',
          summary: weakestRule
            ? `${weakestRule.label} 当前窗口最弱，需要谨慎使用。`
            : '暂无规则验证结果。',
          confidence: weakestRule ? '中' : '低',
        },
        {
          title: '整体稳定性',
          summary: validationResults.length
            ? `规则平均 30 期命中率为 ${formatPercent(
                validationResults.reduce((sum, item) => sum + item.windows.w30, 0) / validationResults.length
              )}。`
            : '暂无足够样本计算规则稳定性。',
          confidence: validationResults.length ? '中' : '低',
        },
        {
          title: '增强增益',
          summary: `增强对照：30期 ${enhancedComparison.w30.lift >= 0 ? '+' : ''}${enhancedComparison.w30.lift}%，60期 ${enhancedComparison.w60.lift >= 0 ? '+' : ''}${enhancedComparison.w60.lift}%，120期 ${enhancedComparison.w120.lift >= 0 ? '+' : ''}${enhancedComparison.w120.lift}%。`,
          confidence: enhancedComparison.passed ? '高' : '中',
        },
      ],
      relatedSections: ['状态识别', '综合判断'],
      results: validationResults,
      baselineResults: baselineValidationResults,
      enhancedComparison,
      featureContribution,
      summary: {
        bestRule: bestRule?.label ?? '无',
        weakestRule: weakestRule?.label ?? '无',
        average30Window: validationResults.length
          ? validationResults.reduce((sum, item) => sum + item.windows.w30, 0) / validationResults.length
        : 0,
        average60Window: validationResults.length
          ? validationResults.reduce((sum, item) => sum + item.windows.w60, 0) / validationResults.length
          : 0,
        average120Window: validationResults.length
          ? validationResults.reduce((sum, item) => sum + item.windows.w120, 0) / validationResults.length
          : 0,
        enhancedLift30: enhancedComparison.w30.lift,
        enhancedLift60: enhancedComparison.w60.lift,
        enhancedLift120: enhancedComparison.w120.lift,
        enhancedPassed: enhancedComparison.passed,
      },
    },
    timeline: {
      question: '最近 10 期里，当前核心信号的覆盖带是怎样变化的？',
      findings: [
        {
          title: '时间轴覆盖',
          summary: timelineSnapshots.length
            ? `最近 10 期平均覆盖率 ${formatPercent(averageTimelineCoverage)}，可用于观察覆盖带的稳定性。`
            : '暂无足够时间轴样本。',
          confidence: timelineSnapshots.length ? '中' : '低',
        },
        {
          title: '最强覆盖期',
          summary: timelineSnapshots[0]
            ? `${timelineSnapshots[0].label} 的覆盖最强，命中 ${timelineSnapshots[0].hitCount} 个核心信号。`
            : '暂无最强覆盖期。',
          confidence: timelineSnapshots[0] ? '中' : '低',
        },
        {
          title: '最弱覆盖期',
          summary: timelineSnapshots.length
            ? `${timelineSnapshots[timelineSnapshots.length - 1].label} 的覆盖最弱，命中 ${timelineSnapshots[timelineSnapshots.length - 1].hitCount} 个核心信号。`
            : '暂无最弱覆盖期。',
          confidence: timelineSnapshots.length ? '中' : '低',
        },
      ],
      relatedSections: ['动态演化', '状态识别', '规则验证'],
      coverageSnapshots: timelineSnapshots,
      recommendationReplays: replayBundle.replays,
      actionStats: replayBundle.actionStats,
      snapshots: timelineSnapshots,
    },
    decision: {
      question: '在前面的分布、结构、动态和验证都看完后，最终应该如何形成综合技术判断？',
      findings: [
        {
          title: '共识强度',
          summary: `当前共识置信度为 ${unifiedDecision.confidence}，最强共识信号数 ${unifiedDecision.topNumbers.filter((item) => item.level === '强共识').length}。`,
          confidence: unifiedDecision.confidence,
        },
        {
          title: '综合建议',
          summary: `核心判断聚焦于 ${finalRecommendation.core5.map(formatNumber).join('、')}，并以 ${finalRecommendation.backup2.map(formatNumber).join('、')} 作为补充观察。`,
          confidence: '高',
        },
        {
          title: '主要风险',
          summary: riskWarnings.length
            ? `${riskWarnings[0].type}：${riskWarnings[0].description}。`
            : '当前未发现显著结构性风险。',
          confidence: riskWarnings.length ? '中' : '高',
        },
        {
          title: '增强门槛',
          summary: enhancedComparison.passed
            ? '图网络 + 序列谱增强通过回测门槛，已纳入主决策权重。'
            : '增强尚未通过回测门槛，当前仅作为证据参考，不提升主权重。',
          confidence: enhancedComparison.passed ? '高' : '中',
        },
      ],
      relatedSections: ['结构关联', '动态演化', '规则验证'],
      scoreCards,
      unifiedDecision,
      finalRecommendation,
      riskWarnings,
      expertConsensus,
      calibration: {
        bins: unifiedDecision.calibration.bins.map(bin => ({
          scoreRange: bin.scoreRange,
          sampleSize: bin.sampleSize,
          observedHitRate: bin.observedHitRate,
          predictedHitRate: bin.predictedHitRate,
          calibratedConfidence: bin.calibratedConfidence,
          reliable: bin.reliable,
        })),
        overallReliable: unifiedDecision.calibration.overallReliable,
      },
      structureAdvanced: {
        topBridges: networkStats.slice(0, 5),
        anomaly: structureAnomaly,
      },
      sequenceAdvanced: complexSequence,
      enhancedComparison,
      featureContribution,
    },
  };
}
