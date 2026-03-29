import type {
  ActionReplayStats,
  PointAnalysisDashboardModel,
  RecommendationReplayRow,
  TimelineSnapshot,
} from './pointAnalysisViewModel';

export type ReportSectionKey = 'overview' | 'evidence' | 'review';

export interface ReportSectionDefinition {
  key: ReportSectionKey;
  label: string;
  icon: string;
  description: string;
}

export interface Top5Insight {
  number: number;
  rankScore: number;
  drivers: string[];
  conflicts: string[];
  confidence: '高' | '中' | '低';
  riskAdjustedVerdict: string;
  action: string;
  uncertainty: string;
  evidenceChain: string[];
  evidenceRefs: string[];
  enhancedContribution: {
    structureBoost: number;
    sequenceBoost: number;
    totalBoost: number;
    gate: '生效' | '仅参考';
  };
  calibratedHitRate: number;
  calibrationSampleSize: number;
  calibrationReliable: boolean;
  linkedStructureNumbers: number[];
  consensusBreakdown: Array<{
    label: string;
    value: number;
  }>;
  scoreBreakdown: Array<{
    label: string;
    value: number;
  }>;
}

export interface MacroTrendSummary {
  dominantCycle: string;
  fieldBias: string;
  entropyAnomaly: string;
  volatilityState: string;
}

export interface RiskBrief {
  headline: string;
  primaryRisk: string;
  response: string;
  entropyCorrection: string;
  triggerCondition: string;
  boundary: string;
  riskScore: number;
  riskScoreBreakdown: Array<{
    label: string;
    value: number;
  }>;
  evidenceRefs: string[];
  topRiskRules: Array<{
    type: string;
    triggerValue: string;
    triggerThreshold: string;
    response: string;
  }>;
}

export interface DecisionTreeNode {
  condition: string;
  action: string;
  confidence: '高' | '中' | '低';
  fallback: string;
  triggerValue: string;
  triggerThreshold: string;
  evidenceRef: string;
}

export interface EvidenceMarkovRow {
  number: number;
  label: string;
  supportScore: number;
  support: string;
  isExact: boolean;
}

export interface EvidenceTripletRow {
  numbers: number[];
  label: string;
  supportScore: number;
  support: string;
  missPressure: string;
}

export interface EvidenceCooccurrenceRow {
  pair: [number, number];
  label: string;
  count: number;
  support: string;
}

export interface EvidenceDetails {
  markovIntersection: EvidenceMarkovRow[];
  tripletClusters: EvidenceTripletRow[];
  entropyCorrection: string;
  cooccurrenceSupport: EvidenceCooccurrenceRow[];
  networkStructure: Array<{
    number: number;
    bridgeScore: number;
    communityDensity: number;
    structuralStability: number;
    support: string;
  }>;
  sequenceSpectrum: {
    spectralPeak: number;
    phaseDrift: number;
    sequenceInstability: number;
    instabilityTrend: number;
    regimeShiftScore: number;
    stateLabel: string;
    thresholdHint: string;
  };
}

export interface ReviewStats {
  bestRule: string;
  weakestRule: string;
  average30Window: number;
  average60Window: number;
  average120Window: number;
  recentCoverage: number;
  latestHitCount: number;
  dataHealth: string;
  recentTrend: string;
  enhancedLift30: number;
  enhancedLift60: number;
  enhancedLift120: number;
  enhancedPassed: boolean;
  stabilityDelta: number;
  failureGapDelta: number;
  calibrationReliability: string;
  recommendedTop5AvgHit: number;
  recommendedCore5AvgHit: number;
  recommendedTop5HitRate: number;
  recommendedCore5HitRate: number;
  bestReplayPeriod: string;
  worstReplayPeriod: string;
  actionWinRate: ActionReplayStats[];
}

export interface RecommendationReview {
  rows: RecommendationReplayRow[];
}

export interface CoverageReview {
  snapshots: TimelineSnapshot[];
}

export interface ReviewSummary {
  dataHealth: string;
  calibrationReliability: string;
}

export interface PointDecisionBriefModel {
  sections: ReportSectionDefinition[];
  executiveSummary: {
    verdict: string;
    confidence: '高' | '中' | '低';
    recommendedAction: string;
    keyMessages: string[];
  };
  top5Insights: Top5Insight[];
  macroTrend: MacroTrendSummary;
  riskBrief: RiskBrief;
  decisionTree: DecisionTreeNode[];
  evidenceDetails: EvidenceDetails;
  reviewStats: ReviewStats;
  recommendationReview: RecommendationReview;
  coverageReview: CoverageReview;
  reviewSummary: ReviewSummary;
}

function formatNumber(value: number) {
  return String(value).padStart(2, '0');
}

function average(values: number[]) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function unique(values: number[]) {
  return [...new Set(values)].sort((a, b) => a - b);
}

function confidenceFromScore(score: number, driverCount: number, conflictCount: number): '高' | '中' | '低' {
  if (score >= 90 && driverCount >= 3 && conflictCount === 0) return '高';
  if (score >= 70 && driverCount >= 2) return '中';
  return '低';
}

function decidePrimaryAction(
  regimeKey: PointAnalysisDashboardModel['regime']['regime']['key'],
  entropyValue: number,
  top5: Top5Insight[],
  intersectionCount: number,
  conflicts: number
) {
  const strongTop = top5.filter((item) => item.confidence === '高').length;
  const strongIntersection = intersectionCount;

  if (regimeKey === 'hot' && strongTop >= 3 && strongIntersection >= 3 && conflicts === 0) {
    return '顺势';
  }

  if (entropyValue >= 5.2 || conflicts >= 2) {
    return '对冲';
  }

  if (strongIntersection >= 2 || strongTop >= 2) {
    return '跟随';
  }

  return '观察';
}

function buildPairSupportMap(pairs: PointAnalysisDashboardModel['structure']['cooccurrencePairs']) {
  const map = new Map<number, number>();
  pairs.forEach((item) => {
    const [a, b] = item.pair;
    map.set(a, (map.get(a) || 0) + item.count);
    map.set(b, (map.get(b) || 0) + item.count);
  });
  return map;
}

function buildTop5Insights(model: PointAnalysisDashboardModel) {
  const scoreCards = [...model.decision.scoreCards].sort((a, b) => b.totalScore - a.totalScore);
  const markovTop = model.dynamics.markov.predictions.slice(0, 8).map((item) => item.number);
  const hotZoneNumbers = new Set(
    model.distribution.hotZones
      .filter((zone) => zone.temperature !== 'cold')
      .flatMap((zone) => zone.numbers)
  );
  const clusterNumbers = new Set(model.structure.clusters.flatMap((cluster) => cluster.numbers));
  const pairSupportMap = buildPairSupportMap(model.structure.cooccurrencePairs);
  const timelineHitMap = new Map<number, number>();
  model.timeline.snapshots.forEach((snapshot) => {
    snapshot.coreHits.forEach((hit) => {
      const num = Number(hit);
      timelineHitMap.set(num, (timelineHitMap.get(num) || 0) + 1);
    });
  });
  const volatilityMap = new Map(model.dynamics.volatilityStats.map((item) => [item.number, item]));
  const markovRankMap = new Map(model.dynamics.markov.predictions.map((item, index) => [item.number, index + 1]));
  const zoneMap = new Map<number, string>();
  model.distribution.hotZones.forEach((zone) => {
    zone.numbers.forEach((num) => zoneMap.set(num, zone.zone));
  });
  const clusterMap = new Map<number, string>();
  model.structure.clusters.forEach((cluster) => {
    cluster.numbers.forEach((num) => clusterMap.set(num, cluster.numbers.join('-')));
  });
  const networkMap = new Map(model.structure.networkStats.map((item) => [item.number, item]));
  const sequence = model.dynamics.sequenceAdvanced;
  const enhancedPassed = model.validation.enhancedComparison.passed;
  const contributionMap = new Map(model.validation.featureContribution.map((item) => [item.number, item]));
  const recentPeriods = model.timeline.snapshots.slice(0, 3).map((item) => item.period).filter(Boolean);
  const validationSummary = model.validation.summary;
  const consensusMap = new Map(model.decision.unifiedDecision.topNumbers.map((item) => [item.number, item]));

  return scoreCards
    .slice(0, 12)
    .map((card) => {
      const drivers: string[] = [];
      const conflicts: string[] = [];
      let adjusted = card.totalScore;
      const scoreBreakdown: Top5Insight['scoreBreakdown'] = [
        { label: '基础评分', value: card.totalScore },
      ];

      if (markovTop.includes(card.number)) {
        adjusted += 8;
        drivers.push('进入 Markov 筛选交集');
        scoreBreakdown.push({ label: 'Markov 加分', value: 8 });
      }
      if (hotZoneNumbers.has(card.number)) {
        adjusted += 6;
        drivers.push('处于热区支撑带');
        scoreBreakdown.push({ label: '热区支撑', value: 6 });
      }
      if (clusterNumbers.has(card.number)) {
        adjusted += 6;
        drivers.push('连号集群支撑');
        scoreBreakdown.push({ label: '集群支撑', value: 6 });
      }
      const pairSupport = pairSupportMap.get(card.number) || 0;
      if (pairSupport >= 2) {
        const pairBonus = Math.min(8, pairSupport);
        adjusted += pairBonus;
        drivers.push(`共现支撑 ${pairSupport}`);
        scoreBreakdown.push({ label: '共现加分', value: pairBonus });
      }
      const timelineHits = timelineHitMap.get(card.number) || 0;
      if (timelineHits > 0) {
        const timelineBonus = Math.min(6, timelineHits * 2);
        adjusted += timelineBonus;
        drivers.push(`时间轴命中 ${timelineHits} 期`);
        scoreBreakdown.push({ label: '时间轴加分', value: timelineBonus });
      }

      const volatility = volatilityMap.get(card.number);
      if (card.missScore >= 60) {
        adjusted -= 5;
        conflicts.push('近期遗漏压力偏高');
        scoreBreakdown.push({ label: '遗漏扣分', value: -5 });
      }
      if (volatility && volatility.volatility >= 0.16) {
        adjusted -= 4;
        conflicts.push('波动偏高');
        scoreBreakdown.push({ label: '波动扣分', value: -4 });
      }
      if (!markovTop.includes(card.number) && !hotZoneNumbers.has(card.number) && !clusterNumbers.has(card.number)) {
        conflicts.push('缺少强结构支撑');
        scoreBreakdown.push({ label: '结构缺失扣分', value: -3 });
        adjusted -= 3;
      }
      const contribution = contributionMap.get(card.number);
      const structureBoost = contribution?.structureBoost || 0;
      const sequenceBoost = contribution?.sequenceBoost || 0;
      const totalBoost = contribution?.totalBoost || 0;
      if (structureBoost > 2.5) {
        drivers.push('图网络桥接增强');
        scoreBreakdown.push({ label: '图网络贡献', value: Math.round(structureBoost) });
      }
      if (sequenceBoost > 2.5) {
        drivers.push('序列频谱增强');
        scoreBreakdown.push({ label: '序列谱贡献', value: Math.round(sequenceBoost) });
      }
      if (sequence.stateLabel === '局部突变' || sequence.stateLabel === '高噪失稳') {
        conflicts.push('序列处于突变态');
      }

      const confidence = confidenceFromScore(adjusted, drivers.length, conflicts.length);
      const verdict =
        confidence === '高'
          ? '优先关注'
          : confidence === '中'
            ? '中性跟随'
            : '谨慎观察';
      const action =
        confidence === '高'
          ? '主跟随'
          : confidence === '中'
            ? '小仓跟随'
            : '仅观察';
      const uncertainty =
        conflicts.length === 0
          ? '当前冲突信号较少，主要不确定性来自短期波动。'
          : `存在 ${conflicts.length} 个冲突因子，建议按风险阈值动态调整。`;
      const evidenceChain = [
        markovTop.includes(card.number) ? '动态证据：Markov 转移支撑' : '动态证据：Markov 支撑弱',
        hotZoneNumbers.has(card.number) || clusterNumbers.has(card.number) || (networkMap.get(card.number)?.bridgeScore || 0) >= 0.3
          ? '结构证据：热区/集群/桥接至少一项成立'
          : '结构证据：缺少热区、集群与桥接共振',
        `序列证据：${sequence.stateLabel}态，不稳定度 ${sequence.sequenceInstability}`,
        timelineHits > 0 ? `回测证据：近窗命中 ${timelineHits} 期` : '回测证据：近窗命中支撑一般',
      ];
      const evidenceRefs: string[] = [];
      const markovRank = markovRankMap.get(card.number);
      if (markovRank) {
        evidenceRefs.push(`动态引用：Markov 排位第 ${markovRank}（来源：dynamics.markov.predictions）`);
      }
      const zone = zoneMap.get(card.number);
      if (zone) {
        evidenceRefs.push(`结构引用：热区 ${zone}（来源：distribution.hotZones）`);
      }
      const cluster = clusterMap.get(card.number);
      if (cluster) {
        evidenceRefs.push(`结构引用：连号集群 ${cluster}（来源：structure.clusters）`);
      }
      const network = networkMap.get(card.number);
      if (network) {
        evidenceRefs.push(
          `结构引用：桥接 ${network.bridgeScore.toFixed(2)} / 稳定 ${network.structuralStability.toFixed(2)}（来源：structure.networkStats）`
        );
      }
      evidenceRefs.push(
        `动态引用：主频峰 ${sequence.spectralPeak}，相位漂移 ${sequence.phaseDrift}（来源：dynamics.sequenceAdvanced）`
      );
      if (recentPeriods.length > 0) {
        evidenceRefs.push(`期次引用：最近窗口 ${recentPeriods.join(' / ')}（来源：timeline.snapshots）`);
      }
      evidenceRefs.push(
        `回测引用：最佳规则 ${validationSummary.bestRule}，30期均值 ${(validationSummary.average30Window || 0).toFixed(1)}%（来源：validation.results）`
      );
      const consensus = consensusMap.get(card.number);
      const consensusBreakdown = consensus
        ? [
            { label: '点位基础', value: Math.round(consensus.scoreBreakdown.pointBase) },
            { label: '结构增强', value: Math.round(consensus.scoreBreakdown.structureBoost) },
            { label: '专家结构', value: Math.round(consensus.scoreBreakdown.expertStructureBoost) },
            { label: '历史修正', value: Math.round(consensus.scoreBreakdown.historicalAdjustment) },
            { label: '罚分', value: -Math.round(consensus.scoreBreakdown.penalty) },
          ]
        : [];

      return {
        number: card.number,
        rankScore: Math.max(0, Math.round(adjusted)),
        drivers,
        conflicts,
        confidence,
        riskAdjustedVerdict: verdict,
        action,
        uncertainty,
        evidenceChain,
        evidenceRefs,
        enhancedContribution: {
          structureBoost: Number(structureBoost.toFixed(1)),
          sequenceBoost: Number(sequenceBoost.toFixed(1)),
          totalBoost: Number(totalBoost.toFixed(1)),
          gate: enhancedPassed ? '生效' : '仅参考',
        },
        calibratedHitRate: consensus?.calibratedHitRate ?? 0,
        calibrationSampleSize: consensus?.sampleSize ?? 0,
        calibrationReliable: consensus?.reliable ?? false,
        linkedStructureNumbers: Array.from(
          new Set(
            [
              card.number,
              ...(pairSupportMap.get(card.number) ? [card.number] : []),
              ...model.structure.cooccurrencePairs
                .filter(pair => pair.pair[0] === card.number || pair.pair[1] === card.number)
                .flatMap(pair => [pair.pair[0], pair.pair[1]]),
              ...model.structure.clusters
                .filter(cluster => cluster.numbers.includes(card.number))
                .flatMap(cluster => cluster.numbers),
            ].filter((value): value is number => typeof value === 'number' && !Number.isNaN(value))
          )
        ).sort((a, b) => a - b),
        consensusBreakdown,
        scoreBreakdown,
      };
    })
    .sort((a, b) => b.rankScore - a.rankScore)
    .slice(0, 5);
}

function buildMacroTrend(model: PointAnalysisDashboardModel): MacroTrendSummary {
  const topCyclic = [...model.dynamics.cyclicPatterns].sort((a, b) => b.resonanceScore - a.resonanceScore)[0];
  const lowHalf = model.overview.cores.filter((num) => num <= 40).length;
  const highHalf = model.overview.cores.length - lowHalf;
  const topVolatility = [...model.dynamics.volatilityStats].sort((a, b) => b.volatility - a.volatility)[0];

  let fieldBias = '上下区均衡';
  if (highHalf - lowHalf >= 3) {
    fieldBias = '上半区偏强';
  } else if (lowHalf - highHalf >= 3) {
    fieldBias = '下半区偏强';
  }

  const entropyValue = model.regime.entropy.value;
  let entropyAnomaly = '熵值处于中性区间';
  if (entropyValue >= 5.2) {
    entropyAnomaly = '熵值偏高，系统更分散';
  } else if (entropyValue <= 4.6) {
    entropyAnomaly = '熵值偏低，系统更集中';
  }

  const volatilityState = topVolatility
    ? `${topVolatility.number} 号属于 ${topVolatility.cluster}，整体波动以 ${topVolatility.volatility} 为代表`
    : '暂无明显波动信号';

  return {
    dominantCycle: topCyclic
      ? `${topCyclic.phase}为主，平均周期约 ${topCyclic.period} 期`
      : '暂无稳定的主导周期',
    fieldBias,
    entropyAnomaly,
    volatilityState,
  };
}

function buildRiskBrief(model: PointAnalysisDashboardModel, top5: Top5Insight[]) {
  const primaryRisk = model.decision.riskWarnings[0];
  const conflict = model.regime.conflicts[0];
  const sequence = model.dynamics.sequenceAdvanced;
  const bridgeWeakCount = model.structure.networkStats.filter(
    item => item.bridgeScore >= 0.45 && item.structuralStability < 0.35
  ).length;
  const highConfidenceCount = top5.filter(item => item.confidence === '高').length;
  const conflictCount = model.regime.conflicts.length;
  const warningCount = model.decision.riskWarnings.length;
  const entropy = model.regime.entropy.value;

  const riskScoreBreakdown: RiskBrief['riskScoreBreakdown'] = [
    { label: '熵值风险', value: entropy >= 5.2 ? 35 : entropy <= 4.6 ? 20 : 28 },
    { label: '冲突信号', value: conflictCount * 12 },
    { label: '系统预警', value: warningCount * 10 },
    { label: '序列不稳定', value: Math.round(sequence.sequenceInstability * 20) },
    { label: '桥接断裂', value: bridgeWeakCount * 6 },
    { label: '高可信候选缓冲', value: -highConfidenceCount * 8 },
  ];
  const riskScore = Math.max(
    0,
    Math.min(100, Math.round(riskScoreBreakdown.reduce((sum, item) => sum + item.value, 0)))
  );
  const headline =
    primaryRisk?.type ||
    conflict?.type ||
    (top5.some((item) => item.confidence === '低') ? '当前仍需控制单边集中' : '当前结构总体可读');

  const response =
    model.regime.regime.key === 'hot'
      ? '优先顺势，但保留对冲位，避免单边追高。'
      : model.regime.regime.key === 'cold'
        ? '优先回补冷区，避免过度集中在高热区。'
        : model.regime.regime.key === 'breakout'
          ? '优先跟随结构突破，同时保留观察仓。'
          : '优先对冲与分散，等待结构进一步收敛。';

  const entropyCorrection =
    model.regime.entropy.value >= 5.2
      ? '对抗与熵值校正：当前熵值偏高，建议扩大覆盖、降低单边集中度。'
      : model.regime.entropy.value <= 4.6
        ? '对抗与熵值校正：当前熵值偏低，建议保留顺势，但避免过度缩窄。'
        : '对抗与熵值校正：当前熵值中性，维持均衡观察即可。';
  const triggerCondition =
    model.regime.entropy.value >= 5.2
      ? '触发条件：熵值 >= 5.2 或冲突信号 >= 2。'
      : `触发条件：序列不稳定度 >= 0.62 或桥接断裂节点 >= 2（当前 ${sequence.sequenceInstability} / ${bridgeWeakCount}）。`;
  const boundary =
    highConfidenceCount >= 3
      ? '边界条件：高可信候选不少于 3 个，可继续执行主策略。'
      : '边界条件：高可信候选不足 3 个，建议降级执行。';
  const evidenceRefs = [
    `风险引用：熵值 ${entropy.toFixed(2)}（来源：regime.entropy）`,
    `风险引用：冲突信号 ${conflictCount} 个（来源：regime.conflicts）`,
    `风险引用：系统预警 ${warningCount} 条（来源：decision.riskWarnings）`,
    `结构引用：桥接断裂节点 ${bridgeWeakCount} 个（来源：structure.networkStats）`,
    `动态引用：序列状态 ${sequence.stateLabel}，不稳定度 ${sequence.sequenceInstability}（来源：dynamics.sequenceAdvanced）`,
    `风险引用：高可信候选 ${highConfidenceCount} 个（来源：top5Insights）`,
    `风险引用：数据健康 ${model.overview.dataHealth.statusText}（来源：overview.dataHealth）`,
  ];

  return {
    headline,
    primaryRisk: primaryRisk?.description || conflict?.description || '当前未见强烈结构性风险。',
    response,
    entropyCorrection,
    triggerCondition,
    boundary,
    riskScore,
    riskScoreBreakdown,
    evidenceRefs,
    topRiskRules: model.decision.riskWarnings.slice(0, 3).map(item => ({
      type: item.type,
      triggerValue: item.triggerValue,
      triggerThreshold: item.triggerThreshold,
      response: item.response,
    })),
  };
}

function buildDecisionTree(model: PointAnalysisDashboardModel, top5: Top5Insight[], intersections: EvidenceMarkovRow[]) {
  const conflictCount = model.regime.conflicts.length + model.decision.riskWarnings.length;
  const strongTop = top5.filter((item) => item.confidence === '高').length;
  const strongIntersection = intersections.filter((item) => item.isExact).length;
  const entropy = model.regime.entropy.value;
  const clusterSupportCount = model.structure.clusters.filter(cluster =>
    cluster.numbers.some(num => top5.some(item => item.number === num))
  ).length;

  const nodes: DecisionTreeNode[] = [
    {
      condition: '如果 Markov 交集够强，并且热区/集群同时支持',
      action: '顺势',
      confidence: strongIntersection >= 3 && strongTop >= 2 ? '高' : '中',
      fallback: '如果交集开始收窄，降为跟随。',
      triggerValue: `交集 ${strongIntersection}，高可信 ${strongTop}`,
      triggerThreshold: '阈值：交集 >= 3 且高可信 >= 2',
      evidenceRef: '来源：evidence.markovIntersection + top5Insights',
    },
    {
      condition: '如果熵值偏高，或者出现明显风险信号',
      action: '对冲',
      confidence: entropy >= 5.2 || conflictCount >= 2 ? '高' : '中',
      fallback: '如果熵值回到中性区，转为观察。',
      triggerValue: `熵值 ${entropy.toFixed(2)}，风险信号 ${conflictCount}`,
      triggerThreshold: '阈值：熵值 >= 5.2 或 风险信号 >= 2',
      evidenceRef: '来源：regime.entropy + regime.conflicts + decision.riskWarnings',
    },
    {
      condition: '如果 Top 5 中有多个候选同时落入连号集群三元组',
      action: '跟随',
      confidence: top5.some((item) => item.confidence === '高') ? '中' : '低',
      fallback: '如果三元组支撑减弱，退回对冲。',
      triggerValue: `集群支撑 ${clusterSupportCount}，高可信 ${strongTop}`,
      triggerThreshold: '阈值：集群支撑 >= 2 或 高可信 >= 1',
      evidenceRef: '来源：structure.clusters + top5Insights',
    },
    {
      condition: '如果以上条件都未满足',
      action: '观察',
      confidence: '高',
      fallback: '等待下一轮数据再确认。',
      triggerValue: '未命中前述触发条件',
      triggerThreshold: '阈值：顺势/对冲/跟随均不成立',
      evidenceRef: '来源：decisionTree 分支汇总判定',
    },
  ];

  return nodes;
}

function buildMarkovIntersection(model: PointAnalysisDashboardModel, top5: Top5Insight[]) {
  const markovTop = model.dynamics.markov.predictions.slice(0, 10);
  const topNumbers = new Set(top5.map((item) => item.number));
  const exact = markovTop.filter((item) => topNumbers.has(item.number));
  const fallback = markovTop.filter((item) => !topNumbers.has(item.number)).slice(0, 5 - exact.length);
  const joined = [...exact, ...fallback].slice(0, 5);
  const scoreMap = new Map(model.decision.scoreCards.map((item) => [item.number, item.totalScore]));

  return joined.map((item) => ({
    number: item.number,
    label: formatNumber(item.number),
    supportScore: Math.round((scoreMap.get(item.number) || 0) + item.probability * 30),
    support: exact.some((row) => row.number === item.number) ? '评分与 Markov 交集' : '作为近似交集候选',
    isExact: exact.some((row) => row.number === item.number),
  }));
}

function buildTripletClusters(model: PointAnalysisDashboardModel, top5: Top5Insight[]) {
  const scoreMap = new Map(model.decision.scoreCards.map((item) => [item.number, item.totalScore]));
  const missMap = new Map(model.distribution.positionStats.map((item) => [item.num, item.misses]));
  const hotZoneSet = new Map<number, string>();
  model.distribution.hotZones.forEach((zone) => {
    zone.numbers.forEach((num) => hotZoneSet.set(num, zone.zone));
  });

  const candidateNumbers = unique([
    ...top5.map((item) => item.number),
    ...model.dynamics.markov.predictions.slice(0, 8).map((item) => item.number),
    ...model.structure.clusters.flatMap((cluster) => cluster.numbers),
    ...model.distribution.hotZones.filter((zone) => zone.temperature !== 'cold').flatMap((zone) => zone.numbers),
  ]).slice(0, 12);

  const triples: EvidenceTripletRow[] = [];
  for (let i = 0; i < candidateNumbers.length - 2; i++) {
    for (let j = i + 1; j < candidateNumbers.length - 1; j++) {
      for (let k = j + 1; k < candidateNumbers.length; k++) {
        const numbers = [candidateNumbers[i], candidateNumbers[j], candidateNumbers[k]];
        const labels = numbers.map(formatNumber);
        const baseScore = numbers.reduce((sum, num) => sum + (scoreMap.get(num) || 0), 0) / 3;
        const pairSupport = model.structure.cooccurrencePairs.reduce((sum, pair) => {
          return numbers.includes(pair.pair[0]) && numbers.includes(pair.pair[1]) ? sum + pair.count : sum;
        }, 0);
        const sameCluster = model.structure.clusters.some((cluster) => numbers.every((num) => cluster.numbers.includes(num)));
        const sameZone = numbers.every((num) => hotZoneSet.has(num)) && new Set(numbers.map((num) => hotZoneSet.get(num))).size === 1;
        const missPressureValue = average(numbers.map((num) => missMap.get(num) || 0));
        const supportScore = Math.round(baseScore + pairSupport * 4 + (sameCluster ? 10 : 0) + (sameZone ? 6 : 0) - missPressureValue * 1.2);

        triples.push({
          numbers,
          label: labels.join('、'),
          supportScore,
          support: [
            sameCluster ? '同属连号集群' : null,
            sameZone ? '同属热区' : null,
            pairSupport > 0 ? `共现支撑 ${pairSupport}` : null,
          ]
            .filter(Boolean)
            .join(' · ') || '作为结构候选观察',
          missPressure: `遗漏压力均值 ${missPressureValue.toFixed(1)} 期`,
        });
      }
    }
  }

  return triples.sort((a, b) => b.supportScore - a.supportScore).slice(0, 5);
}

function buildCooccurrenceSupport(model: PointAnalysisDashboardModel) {
  return model.structure.cooccurrencePairs.slice(0, 5).map((pair) => ({
    pair: pair.pair,
    label: `${formatNumber(pair.pair[0])} + ${formatNumber(pair.pair[1])}`,
    count: pair.count,
    support: `近窗共现 ${pair.count} 次`,
  }));
}

function buildReviewStats(model: PointAnalysisDashboardModel) {
  const averageWindow = (key: 'w30' | 'w60' | 'w120') =>
    model.validation.results.length
      ? average(model.validation.results.map((item) => item.windows[key])) / 100
      : 0;

  const recentCoverage = model.timeline.coverageSnapshots.length
    ? average(model.timeline.coverageSnapshots.map((item) => item.coverageRatio))
    : 0;

  const latestHitCount = model.timeline.coverageSnapshots[0]?.hitCount || 0;
  const readyReplays = model.timeline.recommendationReplays.filter((item) => item.dataReady);
  const recommendedTop5AvgHit = readyReplays.length ? average(readyReplays.map((item) => item.top5HitCount)) : 0;
  const recommendedCore5AvgHit = readyReplays.length ? average(readyReplays.map((item) => item.core5HitCount)) : 0;
  const recommendedTop5HitRate = readyReplays.length ? readyReplays.filter((item) => item.top5HitCount > 0).length / readyReplays.length : 0;
  const recommendedCore5HitRate = readyReplays.length ? readyReplays.filter((item) => item.core5HitCount > 0).length / readyReplays.length : 0;
  const bestReplay = readyReplays.slice().sort((a, b) => b.top5HitCount - a.top5HitCount)[0];
  const worstReplay = readyReplays.slice().sort((a, b) => a.top5HitCount - b.top5HitCount)[0];

  return {
    bestRule: model.validation.summary.bestRule,
    weakestRule: model.validation.summary.weakestRule,
    average30Window: averageWindow('w30'),
    average60Window: averageWindow('w60'),
    average120Window: averageWindow('w120'),
    recentCoverage,
    latestHitCount,
    dataHealth: model.overview.dataHealth.statusText,
    recentTrend: model.timeline.coverageSnapshots.length
      ? `最近 ${model.timeline.coverageSnapshots.length} 期平均覆盖 ${formatPercent(recentCoverage)}，最新一期命中 ${latestHitCount} 个核心信号。`
      : '暂无足够时间轴样本。',
    enhancedLift30: model.validation.enhancedComparison.w30.lift / 100,
    enhancedLift60: model.validation.enhancedComparison.w60.lift / 100,
    enhancedLift120: model.validation.enhancedComparison.w120.lift / 100,
    enhancedPassed: model.validation.enhancedComparison.passed,
    stabilityDelta: model.validation.enhancedComparison.stabilityDelta,
    failureGapDelta: model.validation.enhancedComparison.failureGapDelta,
    calibrationReliability: model.decision.calibration.overallReliable ? '校准样本可靠' : '校准样本偏少，仅供参考',
    recommendedTop5AvgHit,
    recommendedCore5AvgHit,
    recommendedTop5HitRate,
    recommendedCore5HitRate,
    bestReplayPeriod: bestReplay?.label ?? '暂无',
    worstReplayPeriod: worstReplay?.label ?? '暂无',
    actionWinRate: model.timeline.actionStats,
  };
}

export function buildPointDecisionBrief(model: PointAnalysisDashboardModel): PointDecisionBriefModel {
  const top5Insights = buildTop5Insights(model);
  const intersectionRows = buildMarkovIntersection(model, top5Insights);
  const exactIntersectionCount = model.dynamics.markov.predictions
    .slice(0, 10)
    .filter((item) => top5Insights.some((top) => top.number === item.number))
    .length;
  const primaryAction = decidePrimaryAction(
    model.regime.regime.key,
    model.regime.entropy.value,
    top5Insights,
    exactIntersectionCount,
    model.regime.conflicts.length + model.decision.riskWarnings.length
  );
  const strongTopCount = top5Insights.filter((item) => item.confidence === '高').length;

  const executiveSummary = {
    verdict: `当前更适合 ${primaryAction}`,
    confidence: strongTopCount >= 3 && exactIntersectionCount >= 2 ? '高' : strongTopCount === 0 ? '低' : '中',
    recommendedAction: primaryAction,
    keyMessages: [
      `Top 5 已筛出 ${top5Insights.length} 个最值得关注的候选。`,
      `Markov 交集命中 ${intersectionRows.filter((item) => item.isExact).length} 个。`,
      `当前熵值 ${model.regime.entropy.value.toFixed(2)}，${model.regime.entropy.description}。`,
      `增强回测：30期 ${model.validation.enhancedComparison.w30.lift >= 0 ? '+' : ''}${model.validation.enhancedComparison.w30.lift}%（${model.validation.enhancedComparison.passed ? '已通过门槛' : '未通过门槛'}）。`,
    ],
  } as const;

  const riskBrief = buildRiskBrief(model, top5Insights);
  const decisionTree = buildDecisionTree(model, top5Insights, intersectionRows);
  const reviewStats = buildReviewStats(model);

  return {
    sections: [
      { key: 'overview', label: '看结论', icon: '🧭', description: '先看本期结论、Top 5、趋势与风险动作。' },
      { key: 'evidence', label: '看证据', icon: '📚', description: '再看交集、连号三元组、共现与熵值校正。' },
      { key: 'review', label: '看复盘', icon: '📈', description: '最后看规则有效性、命中轨迹与数据健康。' },
    ],
    executiveSummary,
    top5Insights,
    macroTrend: buildMacroTrend(model),
    riskBrief,
    decisionTree,
    evidenceDetails: {
      markovIntersection: intersectionRows,
      tripletClusters: buildTripletClusters(model, top5Insights),
      entropyCorrection: riskBrief.entropyCorrection,
      cooccurrenceSupport: buildCooccurrenceSupport(model),
      networkStructure: model.structure.networkStats.slice(0, 5).map(item => ({
        number: item.number,
        bridgeScore: item.bridgeScore,
        communityDensity: item.communityDensity,
        structuralStability: item.structuralStability,
        support: item.bridgeScore >= 0.35
          ? '桥接作用明显，适合做结构骨架'
          : '桥接作用一般，建议作为辅助观察',
      })),
      sequenceSpectrum: {
        spectralPeak: model.dynamics.sequenceAdvanced.spectralPeak,
        phaseDrift: model.dynamics.sequenceAdvanced.phaseDrift,
        sequenceInstability: model.dynamics.sequenceAdvanced.sequenceInstability,
        instabilityTrend: model.dynamics.sequenceAdvanced.instabilityTrend,
        regimeShiftScore: model.dynamics.sequenceAdvanced.regimeShiftScore,
        stateLabel: model.dynamics.sequenceAdvanced.stateLabel,
        thresholdHint: model.dynamics.sequenceAdvanced.thresholdHint,
      },
    },
    reviewStats,
    recommendationReview: {
      rows: model.timeline.recommendationReplays,
    },
    coverageReview: {
      snapshots: model.timeline.coverageSnapshots,
    },
    reviewSummary: {
      dataHealth: reviewStats.dataHealth,
      calibrationReliability: reviewStats.calibrationReliability,
    },
  };
}
