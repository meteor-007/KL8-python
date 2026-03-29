// ========== 动态分析引擎 - 快乐8点位分析核心逻辑 ==========
export const FIBONACCI_NUMS = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89];

// ========== 辅助统计函数 ==========
export function countHitsInRecent(num: number, periods: number, draws: number[][]): number {
  if (!draws || draws.length === 0) return 0;
  let count = 0;
  for (let i = 0; i < Math.min(periods, draws.length); i++) {
    if (draws[i] && draws[i].includes(num)) count++;
  }
  return count;
}

export function countConsecutiveMisses(num: number, draws: number[][]): number {
  if (!draws || draws.length === 0) return 0;
  for (let i = 0; i < draws.length; i++) {
    if (draws[i] && draws[i].includes(num)) return i;
  }
  return draws.length;
}

// ========== 扩展规则 ==========
export function expandPositions(cores: number[]): number[] {
  const set = new Set<number>();
  cores.forEach(p => {
    const prev = p === 1 ? 80 : p - 1;
    const next = p === 80 ? 1 : p + 1;
    set.add(prev);
    set.add(p);
    set.add(next);
  });
  return Array.from(set).sort((a, b) => a - b);
}

// ========== 拓展点位统计 ==========
export interface PositionStat {
  num: number;
  isCore: boolean;
  hits10: number;
  hits3: number;
  misses: number;
}

export interface RuleBacktestResult {
  ruleKey: string;
  label: string;
  windows: {
    w30: number;
    w60: number;
    w120: number;
  };
  stability: '高' | '中' | '低';
  lastFailureGap: number;
  confidence: '高' | '中' | '低';
}

export interface MarketRegime {
  key: 'hot' | 'cold' | 'balanced' | 'breakout';
  label: string;
  description: string;
  recommendedBias: string;
}

export interface ConsensusScore {
  number: number;
  score: number;
  level: '强共识' | '中共识' | '仅观察';
  reasons: string[];
}

export interface ExpertConsensusInput {
  repeatedNumbers: number[];
  focusNumbers: number[];
  focusMatrices: string[];
  historicalSupportByNumber: Record<number, number>;
  missingDataPenalty: number;
}

export interface ConsensusScoreBreakdown {
  pointBase: number;
  structureBoost: number;
  expertStructureBoost: number;
  historicalAdjustment: number;
  penalty: number;
  totalBeforeCalibration: number;
}

export interface CalibrationBin {
  scoreRange: string;
  min: number;
  max: number;
  sampleSize: number;
  observedHitRate: number;
  predictedHitRate: number;
  calibratedConfidence: '高' | '中' | '低';
  reliable: boolean;
}

export interface CalibrationSummary {
  bins: CalibrationBin[];
  method: 'empirical-bins';
  overallReliable: boolean;
}

export interface RiskTriggerEvidence {
  label: string;
  value: string;
}

export interface RiskRule {
  type: string;
  level: 'high' | 'medium' | 'low';
  severity: 'high' | 'medium' | 'low';
  source?: 'graph' | 'sequence' | 'hybrid' | 'consensus' | 'data';
  description: string;
  suggestion: string;
  triggerValue: string;
  triggerThreshold: string;
  response: string;
  evidenceRefs: string[];
}

export interface ConflictSignal {
  type: string;
  severity: '高' | '中' | '低';
  source?: 'graph' | 'sequence' | 'hybrid';
  description: string;
}

export interface AdvancedNetworkMetrics {
  number: number;
  degree: number;
  centrality: number;
  betweenness: number;
  bridgeScore: number;
  communityDensity: number;
  structuralStability: number;
}

export interface SequenceSpectrumMetrics {
  spectralPeak: number;
  bandEnergyRatio: {
    low: number;
    mid: number;
    high: number;
  };
  phaseDrift: number;
  sequenceInstability: number;
  instabilityTrend: number;
  regimeShiftScore: number;
  stateLabel: '平稳延续' | '缓慢迁移' | '局部突变' | '高噪失稳';
  thresholdHint: string;
}

export interface EnhancedBacktestComparison {
  w30: { baseline: number; enhanced: number; lift: number };
  w60: { baseline: number; enhanced: number; lift: number };
  w120: { baseline: number; enhanced: number; lift: number };
  stabilityDelta: number;
  failureGapDelta: number;
  passed: boolean;
}

export interface FeatureContributionBreakdown {
  number: number;
  structureBoost: number;
  sequenceBoost: number;
  totalBoost: number;
}

export interface UnifiedDecisionRow {
  number: number;
  consensusScore: number;
  level: '强共识' | '中共识' | '仅观察';
  reasons: string[];
  scoreBreakdown: ConsensusScoreBreakdown;
  calibratedHitRate: number;
  calibratedConfidence: '高' | '中' | '低';
  sampleSize: number;
  reliable: boolean;
}

export interface UnifiedDecisionSummary {
  topNumbers: UnifiedDecisionRow[];
  topMatrixLabels: string[];
  confidence: '高' | '中' | '低';
  conflicts: ConflictSignal[];
  calibration: CalibrationSummary;
}

export function getPositionStats(cores: number[], expanded: number[], draws: number[][]): PositionStat[] {
  return expanded.map(num => ({
    num,
    isCore: cores.includes(num),
    hits10: countHitsInRecent(num, 10, draws),
    hits3: countHitsInRecent(num, 3, draws),
    misses: countConsecutiveMisses(num, draws),
  }));
}

// ========== 连号集群分析 ==========
export interface ClusterGroup {
  numbers: number[];
  clusterScore: number;
  trend: string;
}

export function analyzeClusterDynamics(cores: number[], draws: number[][]): ClusterGroup[] {
  const clusters: ClusterGroup[] = [];
  if (cores.length === 0) return [];
  const sorted = [...cores].sort((a, b) => a - b);
  let group: number[] = [sorted[0]];

  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] - sorted[i - 1] <= 3) {
      group.push(sorted[i]);
    } else {
      if (group.length >= 2) {
        const h3sum = group.reduce((s, n) => s + countHitsInRecent(n, 3, draws), 0);
        clusters.push({
          numbers: [...group],
          clusterScore: Math.round((group.length * 1.5 + h3sum) * 10) / 10,
          trend: h3sum > group.length ? '↑升温' : '→平稳'
        });
      }
      group = [sorted[i]];
    }
  }
  if (group.length >= 2) {
    const h3sum = group.reduce((s, n) => s + countHitsInRecent(n, 3, draws), 0);
    clusters.push({
      numbers: [...group],
      clusterScore: Math.round((group.length * 1.5 + h3sum) * 10) / 10,
      trend: h3sum > group.length ? '↑升温' : '→平稳'
    });
  }
  return clusters;
}

// ========== 周期性分析 ==========
export interface CyclicPattern {
  number: number;
  period: number;
  phase: string;
  resonanceScore: number;
}

export function analyzeCyclicPatterns(cores: number[], draws: number[][]): CyclicPattern[] {
  return cores.map(num => {
    const appearances: number[] = [];
    draws.forEach((draw, i) => {
      if (draw && draw.includes(num)) appearances.push(i);
    });

    let avgGap = 0;
    if (appearances.length > 1) {
      const gaps = [];
      for (let i = 1; i < appearances.length; i++) gaps.push(appearances[i] - appearances[i - 1]);
      avgGap = gaps.reduce((s, g) => s + g, 0) / gaps.length;
    }

    const misses = countConsecutiveMisses(num, draws);
    const phase = misses === 0 ? '活跃期' : misses >= 3 ? '蓄能期' : '过渡期';
    const resonance = (10 - Math.min(10, misses)) * 0.8 + countHitsInRecent(num, 5, draws) * 1.2;

    return {
      number: num,
      period: Math.round((avgGap || 3) * 10) / 10,
      phase,
      resonanceScore: Math.round(resonance * 10) / 10
    };
  });
}

// ========== 热力场域 ==========
export interface HeatZone {
  zone: string;
  name: string;
  range: string;
  numbers: number[];
  energy: number;
  level: 'high' | 'medium' | 'low';
  temperature: 'hot' | 'warm' | 'cold';
}

export function analyzeHeatZones(cores: number[], draws: number[][]): HeatZone[] {
  const zones: [string, [number, number]][] = [
    ['A区(01-10)', [1, 10]],
    ['B区(11-20)', [11, 20]],
    ['C区(21-30)', [21, 30]],
    ['D区(31-40)', [31, 40]],
    ['E区(41-50)', [41, 50]],
    ['F区(51-60)', [51, 60]],
    ['G区(61-70)', [61, 70]],
    ['H区(71-80)', [71, 80]],
  ];

  return zones.map(([zone, [lo, hi]]) => {
    const nums = cores.filter(n => n >= lo && n <= hi);
    const energy = nums.reduce((s, n) => s + countHitsInRecent(n, 5, draws) * 2 + Math.max(0, 5 - countConsecutiveMisses(n, draws)), 0);
    const level = energy >= 12 ? 'high' : energy >= 6 ? 'medium' : 'low';
    return {
      zone,
      name: zone,
      range: `${lo}-${hi}`,
      numbers: nums,
      energy,
      level: level as 'high' | 'medium' | 'low',
      temperature: level === 'high' ? 'hot' : level === 'medium' ? 'warm' : 'cold'
    };
  });
}

function clamp(value: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, value));
}

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function computeWindowHitRate(targets: number[], draws: number[][], window: number): number {
  const selected = draws.slice(0, Math.min(window, draws.length));
  if (!selected.length || !targets.length) return 0;
  const hitCount = selected.reduce((sum, draw) => sum + targets.filter(num => draw.includes(num)).length, 0);
  return hitCount / (selected.length * targets.length);
}

function pickGraphCandidates(cores: number[], draws: number[][]): number[] {
  return analyzeGraphNetwork(cores, draws)
    .slice(0, Math.min(8, cores.length))
    .map(item => item.number);
}

function pickSequenceCandidates(cores: number[], draws: number[][]): number[] {
  const spectrum = analyzeComplexSequence(cores, draws);
  if (!cores.length) return [];
  const anchor = Math.max(0, Math.min(9, Math.round(spectrum.spectralPeak * 9)));
  const buckets = new Map<number, number>();
  cores.forEach(num => {
    const key = num % 10;
    buckets.set(key, (buckets.get(key) || 0) + countHitsInRecent(num, 8, draws));
  });
  const sortedBuckets = [...buckets.entries()].sort((a, b) => b[1] - a[1]).map(item => item[0]);
  const preferred = [anchor, (anchor + 1) % 10, (anchor + 9) % 10, ...sortedBuckets];
  const seen = new Set<number>();
  const targets: number[] = [];
  preferred.forEach(bucket => {
    cores
      .filter(num => num % 10 === bucket)
      .sort((a, b) => countConsecutiveMisses(a, draws) - countConsecutiveMisses(b, draws))
      .forEach(num => {
        if (!seen.has(num) && targets.length < 8) {
          seen.add(num);
          targets.push(num);
        }
      });
  });
  return targets.length ? targets : cores.slice(0, Math.min(8, cores.length));
}

function stabilityToScore(stability: RuleBacktestResult['stability']): number {
  if (stability === '高') return 2;
  if (stability === '中') return 1;
  return 0;
}

export function backtestRuleSet(
  cores: number[],
  draws: number[][],
  options: { includeEnhanced?: boolean } = {}
): RuleBacktestResult[] {
  const includeEnhanced = options.includeEnhanced ?? true;
  const clusters = analyzeClusterDynamics(cores, draws);
  const cyclic = analyzeCyclicPatterns(cores, draws);
  const heat = analyzeHeatZones(cores, draws);
  const markov = analyzeMarkov(cores, draws);
  const scoreCards = computeScoreCards(cores, draws);

  const clusterNums = [...new Set(clusters.flatMap(cluster => cluster.numbers))];
  const cyclicNums = cyclic.filter(item => item.resonanceScore >= 5).map(item => item.number);
  const heatNums = heat.filter(zone => zone.temperature === 'hot').flatMap(zone => zone.numbers);
  const markovNums = markov.predictions.slice(0, Math.min(8, markov.predictions.length)).map(item => item.number);
  const scoreNums = scoreCards.slice().sort((a, b) => b.totalScore - a.totalScore).slice(0, Math.min(8, scoreCards.length)).map(item => item.number);
  const graphNums = pickGraphCandidates(cores, draws);
  const sequenceNums = pickSequenceCandidates(cores, draws);

  const buildResult = (ruleKey: string, label: string, targets: number[]): RuleBacktestResult => {
    const w30 = computeWindowHitRate(targets, draws, 30);
    const w60 = computeWindowHitRate(targets, draws, 60);
    const w120 = computeWindowHitRate(targets, draws, 120);
    const delta = Math.max(w30, w60, w120) - Math.min(w30, w60, w120);
    const stability: RuleBacktestResult['stability'] = delta < 0.05 ? '高' : delta < 0.1 ? '中' : '低';
    const lastFailureGap = (() => {
      for (let i = 0; i < Math.min(20, draws.length); i++) {
        const hit = targets.some(num => draws[i]?.includes(num));
        if (hit) return i;
      }
      return Math.min(20, draws.length);
    })();
    const confidence: RuleBacktestResult['confidence'] = w30 >= 0.32 ? '高' : w30 >= 0.2 ? '中' : '低';
    return {
      ruleKey,
      label,
      windows: {
        w30: Math.round(w30 * 100),
        w60: Math.round(w60 * 100),
        w120: Math.round(w120 * 100),
      },
      stability,
      lastFailureGap,
      confidence,
    };
  };

  const baseline = [
    buildResult('cluster', '集群联动', clusterNums),
    buildResult('cyclic', '周期共振', cyclicNums),
    buildResult('heat', '热区趋势', heatNums),
    buildResult('markov', '转移预测', markovNums),
    buildResult('score', '综合评分', scoreNums),
  ];

  if (!includeEnhanced) {
    return baseline;
  }

  return [
    ...baseline,
    buildResult('graph', '图网络桥接', graphNums),
    buildResult('sequence', '序列频谱', sequenceNums),
  ];
}

function averageWindow(rows: RuleBacktestResult[], key: 'w30' | 'w60' | 'w120'): number {
  if (!rows.length) return 0;
  return rows.reduce((sum, row) => sum + row.windows[key], 0) / rows.length;
}

export function compareEnhancedBacktest(
  baseline: RuleBacktestResult[],
  enhanced: RuleBacktestResult[]
): EnhancedBacktestComparison {
  const baselineW30 = averageWindow(baseline, 'w30');
  const baselineW60 = averageWindow(baseline, 'w60');
  const baselineW120 = averageWindow(baseline, 'w120');
  const enhancedW30 = averageWindow(enhanced, 'w30');
  const enhancedW60 = averageWindow(enhanced, 'w60');
  const enhancedW120 = averageWindow(enhanced, 'w120');

  const baselineStability = average(baseline.map(row => stabilityToScore(row.stability)));
  const enhancedStability = average(enhanced.map(row => stabilityToScore(row.stability)));
  const baselineFailureGap = average(baseline.map(row => row.lastFailureGap));
  const enhancedFailureGap = average(enhanced.map(row => row.lastFailureGap));

  const w30Lift = Number((enhancedW30 - baselineW30).toFixed(2));
  const w60Lift = Number((enhancedW60 - baselineW60).toFixed(2));
  const w120Lift = Number((enhancedW120 - baselineW120).toFixed(2));
  const stabilityDelta = Number((enhancedStability - baselineStability).toFixed(2));
  const failureGapDelta = Number((baselineFailureGap - enhancedFailureGap).toFixed(2));

  return {
    w30: { baseline: Number(baselineW30.toFixed(2)), enhanced: Number(enhancedW30.toFixed(2)), lift: w30Lift },
    w60: { baseline: Number(baselineW60.toFixed(2)), enhanced: Number(enhancedW60.toFixed(2)), lift: w60Lift },
    w120: { baseline: Number(baselineW120.toFixed(2)), enhanced: Number(enhancedW120.toFixed(2)), lift: w120Lift },
    stabilityDelta,
    failureGapDelta,
    passed: w30Lift >= 2 && w60Lift >= 0 && w120Lift >= 0 && stabilityDelta >= 0,
  };
}

export function detectMarketRegime(cores: number[], draws: number[][]): MarketRegime {
  const heatZones = analyzeHeatZones(cores, draws);
  const hotZoneCount = heatZones.filter(zone => zone.temperature === 'hot' && zone.numbers.length > 0).length;
  const avgMiss = average(cores.map(num => countConsecutiveMisses(num, draws)));
  const avgHits3 = average(cores.map(num => countHitsInRecent(num, 3, draws)));

  if (hotZoneCount >= 3 && avgHits3 >= 1.2) {
    return {
      key: 'hot',
      label: '热号延续期',
      description: '近期热区较多，核心号码连续活跃。',
      recommendedBias: '优先保留近期高频和共振号码。',
    };
  }
  if (avgMiss >= 4.5) {
    return {
      key: 'cold',
      label: '冷号回补期',
      description: '当前平均遗漏较高，系统更容易出现补冷行为。',
      recommendedBias: '适度加入近期长遗漏号码。',
    };
  }
  if (hotZoneCount <= 1 && avgHits3 < 0.8) {
    return {
      key: 'balanced',
      label: '分散震荡期',
      description: '热区不集中，号码表现偏分散。',
      recommendedBias: '以分散覆盖和风险控制为主。',
    };
  }
  return {
    key: 'breakout',
    label: '集中爆发期',
    description: '部分区域开始聚焦，存在结构性突破迹象。',
    recommendedBias: '优先观察高分矩阵与高分核心号的叠加区域。',
  };
}

// ========== 马尔可夫 ==========
export interface MarkovState {
  number: number;
  currentState: string;
  transitionProb: number;
  nextPrediction: string;
  probability: number;
}

export interface MarkovAnalysis {
  transitionMatrix: { from: number; to: number; probability: number }[];
  predictions: MarkovState[];
}

export function analyzeMarkov(cores: number[], draws: number[][]): MarkovAnalysis {
  const preds: MarkovState[] = cores.map(num => {
    const h3 = countHitsInRecent(num, 3, draws);
    const h10 = countHitsInRecent(num, 10, draws);
    const miss = countConsecutiveMisses(num, draws);
    const hitRate = h10 / Math.max(1, draws.length);
    const recentBias = h3 / 3;
    const missDecay = Math.max(0, 1 - miss * 0.15);
    const transProb = Math.min(0.95, Math.max(0.05, hitRate * 0.3 + recentBias * 0.4 + missDecay * 0.3));

    return {
      number: num,
      currentState: h3 >= 2 ? '热态' : miss >= 3 ? '冷态' : '温态',
      transitionProb: Math.round(transProb * 100) / 100,
      nextPrediction: transProb > 0.5 ? '大概率' : transProb > 0.35 ? '中等' : '低',
      probability: transProb
    };
  }).sort((a, b) => b.probability - a.probability);

  const transitionMatrix = preds.slice(0, 10).map((p, i) => ({
    from: p.number,
    to: preds[(i + 1) % preds.length]?.number || p.number,
    probability: p.probability
  }));

  return { transitionMatrix, predictions: preds };
}

// ========== 动能：上期高分解锁 ==========
export function getPreviousHighUnopened(prevCores: number[] | undefined, draws: number[][]): number[] {
  if (!prevCores || !prevCores.length || draws.length < 2) return [];
  
  // draws[0] = 最新一期开奖, draws[1] = 上一期开奖
  // 要验证上一期推荐(prevCores)的结果，对应的是 draws[1] (上一期的真实开奖结果)
  // 如果当前是跑这周二的预测，cores 是周二，draws[0] 可能是未出的周二(如果占位的话)或者周一; 
  // 这取决于 dataLoader 中 draws和cores的对其情况。
  // 按照 KL8 的逻辑，draws[0] 是已知的最近开奖。如果 cores 对于 draws[0] 也是同步的...
  // 简单处理：判断 prevCores 中的高分号码(用历史数据 draws.slice(2) 来打分) 是不是被包含在 draws[1] 中
  const prevDraw = draws[1];
  const historyForPrev = draws.slice(2);
  
  const prevScores = computeScoreCards(prevCores, historyForPrev); // 不传第三个参数，防止递归
  
  // 如果大于等于 60 分，且未开出，就留作势能补偿
  const unopenedHighScores = prevScores
    .filter(s => s.totalScore >= 60)
    .filter(s => !prevDraw.includes(s.number))
    .map(s => s.number);
    
  return unopenedHighScores;
}

// ========== 智能评分卡 ==========
export interface ScoreCard {
  number: number;
  totalScore: number;
  freqScore: number;
  missScore: number;
  neighborScore: number;
  clusterScore: number;
  cycleScore: number;
  macroScore: number;
  mathScore: number;
  deathScore: number;
  momentumScore: number;
  graphScore: number;
  sequenceScore: number;
}

export function computeScoreCards(cores: number[], draws: number[][], unopenedHighScores: number[] = []): ScoreCard[] {
  const expanded = expandPositions(cores);
  const stats = getPositionStats(cores, expanded, draws);
  const cycles = analyzeCyclicPatterns(cores, draws);
  const clusters = analyzeClusterDynamics(cores, draws);
  const networkMetrics = analyzeGraphNetwork(cores, draws);
  const networkMap = new Map(networkMetrics.map(item => [item.number, item]));
  const sequenceMetrics = analyzeComplexSequence(cores, draws);
  const spectralAnchor = Math.max(0, Math.min(9, Math.round(sequenceMetrics.spectralPeak * 9)));
  
  // 1. 宏观能量守恒 (和值)
  let sumBias = 0;
  if (draws.length >= 3) {
    const avgSum = draws.slice(0, 3).reduce((acc, d) => acc + (d ? d.reduce((a,b)=>a+b,0) : 0), 0) / 3;
    if (avgSum > 850) sumBias = -1;
    else if (avgSum < 770) sumBias = 1;
  }
  
  // 2. 012路 (模数轨迹) & 3. 质数极变
  const primesSet = new Set([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79]);
  const modCounts = [0, 0, 0];
  let primeHits = 0;
  const recent5 = draws.slice(0, 5);
  recent5.forEach(d => {
    if (d) {
      d.forEach(n => {
        modCounts[n % 3]++;
        if (primesSet.has(n)) primeHits++;
      });
    }
  });
  let coldMod = 0;
  if (modCounts[1] < modCounts[0] && modCounts[1] < modCounts[2]) coldMod = 1;
  if (modCounts[2] < modCounts[0] && modCounts[2] < modCounts[1]) coldMod = 2;
  const needsColdMod = modCounts[coldMod] < 28;
  const needsPrimeBurst = primeHits < 22;

  // 4. 等差数组同构
  const arithmeticBoosts: Record<number, number> = {};
  const sortedCores = [...cores].sort((a,b)=>a-b);
  for(let i=0; i<sortedCores.length-2; i++) {
    for(let j=i+1; j<sortedCores.length-1; j++) {
      const diff = sortedCores[j] - sortedCores[i];
      const nextVal = sortedCores[j] + diff;
      if (sortedCores.includes(nextVal)) {
        arithmeticBoosts[sortedCores[i]] = (arithmeticBoosts[sortedCores[i]] || 0) + 30;
        arithmeticBoosts[sortedCores[j]] = (arithmeticBoosts[sortedCores[j]] || 0) + 30;
        arithmeticBoosts[nextVal] = (arithmeticBoosts[nextVal] || 0) + 30;
      }
    }
  }

  return cores.map(num => {
    const stat = stats.find(s => s.num === num);
    const cyc = cycles.find(c => c.number === num);
    if (!stat || !cyc) return null;

    const inCluster = clusters.some(c => c.numbers.includes(num));
    // 即使不是核心也能拿到邻居分，但在这里它本身就是核心点位之一
    const isNeighbor = expanded.includes(num);

    const freqScore = Math.min(100, stat.hits3 * 30 + stat.hits10 * 5);
    const missScore = Math.min(100, stat.misses * 15);
    const neighborScore = isNeighbor ? 80 : 20;
    const clusterScore = inCluster ? 90 : 30;
    const cycleScore = Math.min(100, cyc.resonanceScore * 10);

    // 计算5大新增维度打分
    let macroScore = 0;
    if (sumBias === 1 && num > 40) macroScore += 40;
    else if (sumBias === -1 && num <= 40) macroScore += 40;
    if (needsColdMod && (num % 3 === coldMod)) macroScore += 30;
    if (needsPrimeBurst && primesSet.has(num)) macroScore += 40;

    const mathScore = Math.min(100, arithmeticBoosts[num] || 0);
    // 绝对杀号过滤网：遗漏极大且缺乏集群支撑的点位直接重罚
    const deathScore = (stat.misses > 22 && !inCluster) ? -150 : 0;
    
    // 上期高分未开，获得动能补偿加分
    const momentumScore = unopenedHighScores.includes(num) ? 60 : 0;
    const network = networkMap.get(num);
    const graphScore = network
      ? Math.round(
          clamp(
            network.centrality * 45 +
              network.bridgeScore * 35 +
              network.structuralStability * 20,
            0,
            100
          )
        )
      : 20;
    const spectralDistance = Math.min(Math.abs((num % 10) - spectralAnchor), 10 - Math.abs((num % 10) - spectralAnchor));
    const sequenceBase = 68 - spectralDistance * 7;
    const sequenceStateBoost =
      sequenceMetrics.stateLabel === '平稳'
        ? 14
        : sequenceMetrics.stateLabel === '渐变'
          ? 8
          : 3;
    const sequencePenalty = sequenceMetrics.sequenceInstability * 22 + Math.abs(sequenceMetrics.phaseDrift) * 10;
    const sequenceScore = Math.round(clamp(sequenceBase + sequenceStateBoost - sequencePenalty, 0, 100));

    // 综合各项进行新一轮的占比调和
    const total = 
        freqScore * 0.13 
        + missScore * 0.13 
        + neighborScore * 0.08 
        + clusterScore * 0.13 
        + cycleScore * 0.13 
        + Math.min(100, macroScore) * 0.14 
        + mathScore * 0.05 
        + momentumScore * 0.09
        + graphScore * 0.06
        + sequenceScore * 0.06
        + deathScore;

    return {
      number: num,
      totalScore: Math.round(total),
      freqScore: Math.round(freqScore),
      missScore: Math.round(missScore),
      neighborScore: Math.round(neighborScore),
      clusterScore: Math.round(clusterScore),
      cycleScore: Math.round(cycleScore),
      macroScore: Math.round(Math.min(100, macroScore)),
      mathScore: Math.round(mathScore),
      deathScore: Math.round(deathScore),
      momentumScore: Math.round(momentumScore),
      graphScore: Math.round(graphScore),
      sequenceScore: Math.round(sequenceScore),
    };
  }).filter(Boolean) as ScoreCard[];
}

// ========== 熵值分析 ==========
export function computeEntropy(draws: number[][]): { value: number; level: string; description: string } {
  if (!draws || draws.length === 0) return { value: 0, level: '无数据', description: '等待数据...' };
  const freq: Record<number, number> = {};
  const total = draws.length * 20;
  draws.flat().forEach(n => { freq[n] = (freq[n] || 0) + 1; });
  let entropy = 0;
  Object.values(freq).forEach(f => {
    const p = f / total;
    if (p > 0) entropy -= p * Math.log2(p);
  });
  const maxE = Math.log2(80);
  const ratio = entropy / maxE;
  return {
    value: Math.round(entropy * 100) / 100,
    level: ratio > 0.92 ? '高均衡' : '偏集中',
    description: ratio > 0.92 ? '分布均匀' : '集中分布'
  };
}


// ========== 风险预警 ==========
export interface RiskWarning extends RiskRule {}

export function getRiskWarnings(cores: number[], draws: number[][]): RiskWarning[] {
  const warnings: RiskWarning[] = [];
  const zones = analyzeHeatZones(cores, draws);
  const densest = zones.reduce((max, z) => z.numbers.length > max.numbers.length ? z : max, zones[0]);
  const spectrum = analyzeComplexSequence(cores, draws);
  const network = analyzeGraphNetwork(cores, draws);
  const weakBridgeCount = network.filter(item => item.bridgeScore >= 0.45 && item.structuralStability < 0.35).length;
  const collapseCount = network.filter(item => item.communityDensity < 0.18).length;
  const driftCount = network.filter(item => item.betweenness >= 0.7 && item.structuralStability < 0.3).length;
  const noisyState = spectrum.sequenceInstability >= 0.75;
  if (densest.numbers.length >= 4) {
    warnings.push({
      type: '拥挤风险',
      level: 'high',
      severity: 'high',
      source: 'hybrid',
      description: `${densest.zone}聚集过多核心点位`,
      suggestion: '建议分散投资',
      triggerValue: `最拥挤区域 ${densest.zone}，聚集 ${densest.numbers.length} 个核心点`,
      triggerThreshold: '阈值：单一区域核心数 >= 4',
      response: '降低单一区域集中度，优先拆分到相邻热区。',
      evidenceRefs: [
        `热区引用：${densest.zone}，能量 ${densest.energy}（来源：distribution.hotZones）`,
      ],
    });
  }
  if (spectrum.sequenceInstability >= 0.62) {
    warnings.push({
      type: '序列突变风险',
      level: 'high',
      severity: 'high',
      source: 'sequence',
      description: `序列不稳定度 ${spectrum.sequenceInstability.toFixed(2)}，当前处于${spectrum.stateLabel}态。`,
      suggestion: '建议降低激进动作优先级，并提高对冲覆盖。',
      triggerValue: `不稳定度 ${spectrum.sequenceInstability.toFixed(2)}，状态 ${spectrum.stateLabel}`,
      triggerThreshold: '阈值：sequenceInstability >= 0.62',
      response: '把顺势动作降一级，同时提高观察和对冲权重。',
      evidenceRefs: [
        `序列引用：主频峰 ${spectrum.spectralPeak}（来源：dynamics.sequenceAdvanced）`,
        `序列引用：相位漂移 ${spectrum.phaseDrift}（来源：dynamics.sequenceAdvanced）`,
      ],
    });
  }
  if (weakBridgeCount >= 2) {
    warnings.push({
      type: '桥接断裂',
      level: 'medium',
      severity: 'medium',
      source: 'graph',
      description: `检测到 ${weakBridgeCount} 个桥接节点稳定度偏低，结构连接存在断裂迹象。`,
      suggestion: '优先保留结构稳定节点，减少边缘节点权重。',
      triggerValue: `低稳定桥接节点 ${weakBridgeCount} 个`,
      triggerThreshold: '阈值：bridgeScore >= 0.45 且 structuralStability < 0.35 的节点 >= 2',
      response: '降低边缘节点的跟随级别，优先看桥接强且稳定的节点。',
      evidenceRefs: [
        '结构引用：来源于 structure.networkStats 的桥接与稳定度联合检测',
      ],
    });
  }
  if (collapseCount >= 3) {
    warnings.push({
      type: '社团塌缩',
      level: 'medium',
      severity: 'medium',
      source: 'graph',
      description: `有 ${collapseCount} 个节点所在社团密度过低，局部团簇支撑不足。`,
      suggestion: '减少对局部团簇的过度解读，优先看跨区结构证据。',
      triggerValue: `低社团密度节点 ${collapseCount} 个`,
      triggerThreshold: '阈值：communityDensity < 0.18 的节点 >= 3',
      response: '集群证据降权，改看共现与桥接证据。',
      evidenceRefs: [
        '结构引用：communityDensity 低于阈值的节点统计（来源：structure.networkStats）',
      ],
    });
  }
  if (driftCount >= 2) {
    warnings.push({
      type: '结构漂移',
      level: 'medium',
      severity: 'medium',
      source: 'graph',
      description: `检测到 ${driftCount} 个高介数但低稳定节点，结构正在迁移。`,
      suggestion: '降低对历史结构惯性的依赖，改看最新窗口证据。',
      triggerValue: `高介数低稳定节点 ${driftCount} 个`,
      triggerThreshold: '阈值：betweenness >= 0.7 且 structuralStability < 0.3 的节点 >= 2',
      response: '提高近期窗口权重，降低长期固定结构权重。',
      evidenceRefs: [
        '结构引用：betweenness 与 structuralStability 联合检测（来源：structure.networkStats）',
      ],
    });
  }
  if (noisyState) {
    warnings.push({
      type: '高噪失稳',
      level: 'high',
      severity: 'high',
      source: 'sequence',
      description: `高频噪声占比抬升，不稳定度达到 ${spectrum.sequenceInstability.toFixed(2)}。`,
      suggestion: '避免用单一规则重仓决策，优先校准后可信度。',
      triggerValue: `高噪比例 ${spectrum.bandEnergyRatio.high.toFixed(2)}`,
      triggerThreshold: '阈值：sequenceInstability >= 0.75',
      response: '只保留多证据共识候选，其余降为观察。',
      evidenceRefs: [
        `序列引用：高频能量占比 ${spectrum.bandEnergyRatio.high.toFixed(2)}（来源：dynamics.sequenceAdvanced）`,
      ],
    });
  }
  return warnings.sort((a, b) => {
    const severityScore = { high: 3, medium: 2, low: 1 };
    return severityScore[b.severity] - severityScore[a.severity];
  });
}

// ========== 终极推荐 ==========
export interface FinalRecommendation {
  core5: number[];
  backup2: number[];
  recommendedCore: number[];
  reasoning: string[];
  bettingStrategy: string;
  coreStrategy: string;
  riskNote: string;
}

export function getFinalRecommendation(cores: number[], draws: number[][], unopenedHighScores: number[] = []): FinalRecommendation {
  const scores = computeScoreCards(cores, draws, unopenedHighScores);
  const top = [...scores].sort((a, b) => b.totalScore - a.totalScore);
  const core5 = top.slice(0, 5).map(s => s.number);
  return {
    core5,
    backup2: top.slice(5, 7).map(s => s.number),
    recommendedCore: core5,
    reasoning: ['核心评分领先', '数据趋势看好', '符合历史规律'],
    bettingStrategy: '建议采用定胆复式策略',
    coreStrategy: '关注高分核心位，避开短期热度极值',
    riskNote: '彩市有风险，分析仅供参考'
  };
}

// ========== 其他逻辑 ==========
export function getGoldenPositions(): number[] {
  return [1, 13, 21, 33, 50, 67, 80];
}

export function getModularMapping(cores: number[]): { mod3: number[]; mod5: number[]; mod8: number[] } {
  const m3 = [0,0,0], m5 = [0,0,0,0,0], m8 = [0,0,0,0,0,0,0,0];
  cores.forEach(n => { m3[n%3]++; m5[n%5]++; m8[n%8]++; });
  return { mod3: m3, mod5: m5, mod8: m8 };
}

export function analyzeComplexSequence(cores: number[], draws: number[][]): SequenceSpectrumMetrics {
  const timeSeries = draws.slice(0, 120).map(draw => draw.filter(num => cores.includes(num)).length);
  if (!cores.length || timeSeries.length < 6) {
    return {
      spectralPeak: 0,
      bandEnergyRatio: { low: 0.34, mid: 0.33, high: 0.33 },
      phaseDrift: 0,
      sequenceInstability: 0.5,
      instabilityTrend: 0,
      regimeShiftScore: 0.4,
      stateLabel: '缓慢迁移',
      thresholdHint: '样本不足，采用安全默认值。',
    };
  }

  const centered = timeSeries.map(value => value - average(timeSeries));
  const N = centered.length;
  const spectrum: Array<{ k: number; amp: number }> = [];
  for (let k = 1; k <= Math.floor(N / 2); k++) {
    let re = 0;
    let im = 0;
    for (let n = 0; n < N; n++) {
      const angle = (2 * Math.PI * k * n) / N;
      re += centered[n] * Math.cos(angle);
      im -= centered[n] * Math.sin(angle);
    }
    const amp = Math.sqrt(re * re + im * im) / N;
    spectrum.push({ k, amp });
  }

  const totalEnergy = spectrum.reduce((sum, item) => sum + item.amp, 0) || 1;
  const peak = spectrum.slice().sort((a, b) => b.amp - a.amp)[0] || { k: 1, amp: 0 };
  const spectralPeak = Number((peak.k / Math.max(1, Math.floor(N / 2))).toFixed(3));

  const lowEnergy = spectrum.filter(item => item.k <= N * 0.1).reduce((sum, item) => sum + item.amp, 0);
  const midEnergy = spectrum
    .filter(item => item.k > N * 0.1 && item.k <= N * 0.25)
    .reduce((sum, item) => sum + item.amp, 0);
  const highEnergy = Math.max(0, totalEnergy - lowEnergy - midEnergy);

  const low = Number((lowEnergy / totalEnergy).toFixed(3));
  const mid = Number((midEnergy / totalEnergy).toFixed(3));
  const high = Number((highEnergy / totalEnergy).toFixed(3));
  const phaseDrift = Number(((average(timeSeries.slice(0, 8)) - average(timeSeries.slice(8, 16))) / Math.max(1, average(timeSeries))).toFixed(3));
  const sequenceInstability = Number(clamp(high * 0.9 + Math.abs(phaseDrift) * 0.6, 0, 1).toFixed(3));
  const recent20 = timeSeries.slice(0, 20);
  const recent60 = timeSeries.slice(0, 60);
  const all120 = timeSeries.slice(0, 120);
  const instability20 = Number(clamp((Math.max(...recent20) - Math.min(...recent20)) / Math.max(1, average(recent20)), 0, 1).toFixed(3));
  const instability60 = Number(clamp((Math.max(...recent60) - Math.min(...recent60)) / Math.max(1, average(recent60)), 0, 1).toFixed(3));
  const instability120 = Number(clamp((Math.max(...all120) - Math.min(...all120)) / Math.max(1, average(all120)), 0, 1).toFixed(3));
  const instabilityTrend = Number((instability20 - instability60).toFixed(3));
  const regimeShiftScore = Number(clamp(Math.abs(instability20 - instability120) * 1.3 + Math.abs(phaseDrift) * 0.4, 0, 1).toFixed(3));
  const stateLabel: SequenceSpectrumMetrics['stateLabel'] =
    sequenceInstability < 0.32
      ? '平稳延续'
      : sequenceInstability < 0.55
        ? '缓慢迁移'
        : sequenceInstability < 0.78
          ? '局部突变'
          : '高噪失稳';
  const thresholdHint =
    stateLabel === '平稳延续'
      ? '序列延续性较强，适合顺势。'
      : stateLabel === '缓慢迁移'
        ? '序列正在迁移，建议均衡跟随。'
        : stateLabel === '局部突变'
          ? '局部突变风险升高，建议提高对冲比例。'
          : '高噪失稳，优先多证据校准后再决策。';

  return {
    spectralPeak,
    bandEnergyRatio: { low, mid, high },
    phaseDrift,
    sequenceInstability,
    instabilityTrend,
    regimeShiftScore,
    stateLabel,
    thresholdHint,
  };
}

export function analyzeGraphNetwork(cores: number[], draws: number[][]): AdvancedNetworkMetrics[] {
  const recent = draws.slice(0, 80);
  const adjacency = new Map<number, Map<number, number>>();
  cores.forEach(num => adjacency.set(num, new Map<number, number>()));

  recent.forEach(draw => {
    const focused = draw.filter(num => cores.includes(num));
    for (let i = 0; i < focused.length; i++) {
      for (let j = i + 1; j < focused.length; j++) {
        const a = focused[i];
        const b = focused[j];
        adjacency.get(a)?.set(b, (adjacency.get(a)?.get(b) || 0) + 1);
        adjacency.get(b)?.set(a, (adjacency.get(b)?.get(a) || 0) + 1);
      }
    }
  });

  const maxCo = Math.max(
    1,
    ...cores.flatMap(a => cores.filter(b => b !== a).map(b => adjacency.get(a)?.get(b) || 0))
  );

  return cores
    .map(num => {
      const neighbors = [...(adjacency.get(num)?.keys() || [])];
      const degree = neighbors.length;
      const centrality = cores.length > 1 ? degree / (cores.length - 1) : 0;

      let connectedPairs = 0;
      const totalPairs = (neighbors.length * (neighbors.length - 1)) / 2;
      for (let i = 0; i < neighbors.length; i++) {
        for (let j = i + 1; j < neighbors.length; j++) {
          if ((adjacency.get(neighbors[i])?.get(neighbors[j]) || 0) > 0) connectedPairs += 1;
        }
      }
      const communityDensity = totalPairs > 0 ? connectedPairs / totalPairs : 0;
      const betweenness = totalPairs > 0 ? (totalPairs - connectedPairs) / totalPairs : 0;
      const avgWeight = neighbors.length
        ? average(neighbors.map(other => (adjacency.get(num)?.get(other) || 0) / maxCo))
        : 0;
      const structuralStability = Number(clamp(avgWeight, 0, 1).toFixed(3));
      const bridgeScore = Number(clamp(centrality * (1 - communityDensity), 0, 1).toFixed(3));

      return {
        number: num,
        degree,
        centrality: Number(centrality.toFixed(3)),
        betweenness: Number(betweenness.toFixed(3)),
        bridgeScore,
        communityDensity: Number(communityDensity.toFixed(3)),
        structuralStability,
      };
    })
    .sort((a, b) => b.bridgeScore - a.bridgeScore || b.centrality - a.centrality);
}

export function analyzeVolatility(cores: number[], draws: number[][]): { number: number; volatility: number; cluster: string }[] {
  return cores.map(number => {
    const windows = [5, 10, 20].map(window => countHitsInRecent(number, window, draws) / Math.max(1, window));
    const mean = average(windows);
    const variance = average(windows.map(value => (value - mean) ** 2));
    const volatility = Math.sqrt(variance);
    return {
      number,
      volatility: Math.round(volatility * 1000) / 1000,
      cluster: volatility < 0.08 ? '稳定热号' : volatility < 0.16 ? '平衡波动' : '冲高回落',
    };
  }).sort((a, b) => b.volatility - a.volatility);
}

export function getCooccurrenceTop(cores: number[], draws: number[][]): { pair: [number, number]; count: number }[] {
  const pairCount = new Map<string, number>();
  draws.slice(0, 80).forEach(draw => {
    const focused = draw.filter(num => cores.includes(num)).sort((a, b) => a - b);
    for (let i = 0; i < focused.length; i++) {
      for (let j = i + 1; j < focused.length; j++) {
        const key = `${focused[i]}-${focused[j]}`;
        pairCount.set(key, (pairCount.get(key) || 0) + 1);
      }
    }
  });
  return [...pairCount.entries()]
    .map(([key, count]) => {
      const [a, b] = key.split('-').map(Number);
      return { pair: [a, b] as [number, number], count };
    })
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);
}

function confidenceFromHitRate(hitRate: number): '高' | '中' | '低' {
  if (hitRate >= 0.28) return '高';
  if (hitRate >= 0.18) return '中';
  return '低';
}

function buildCalibrationSummary(rows: Array<{ number: number; rawScore: number }>, draws: number[][]): CalibrationSummary {
  const windows = [
    { min: 0, max: 39, scoreRange: '0-39' },
    { min: 40, max: 54, scoreRange: '40-54' },
    { min: 55, max: 69, scoreRange: '55-69' },
    { min: 70, max: 84, scoreRange: '70-84' },
    { min: 85, max: 999, scoreRange: '85+' },
  ];
  const bins = windows.map(window => {
    const bucket = rows.filter(row => row.rawScore >= window.min && row.rawScore <= window.max);
    const sampleSize = bucket.length;
    const observedHitRate = sampleSize
      ? average(bucket.map(row => countHitsInRecent(row.number, 30, draws) / Math.max(1, Math.min(30, draws.length))))
      : 0;
    const predictedHitRate = sampleSize ? average(bucket.map(row => clamp(row.rawScore / 100, 0, 1))) : 0;
    return {
      scoreRange: window.scoreRange,
      min: window.min,
      max: window.max,
      sampleSize,
      observedHitRate: Number(observedHitRate.toFixed(3)),
      predictedHitRate: Number(predictedHitRate.toFixed(3)),
      calibratedConfidence: confidenceFromHitRate(observedHitRate),
      reliable: sampleSize >= 3,
    } satisfies CalibrationBin;
  });

  return {
    bins,
    method: 'empirical-bins',
    overallReliable: bins.filter(bin => bin.reliable).length >= 2,
  };
}

function matchCalibration(rawScore: number, calibration: CalibrationSummary): CalibrationBin | null {
  return calibration.bins.find(bin => rawScore >= bin.min && rawScore <= bin.max) ?? null;
}

export function buildUnifiedDecisionSummary(
  cores: number[],
  draws: number[][],
  expertInput: ExpertConsensusInput,
): UnifiedDecisionSummary {
  const scores = computeScoreCards(cores, draws);
  const topScores = new Map(scores.map(item => [item.number, item.totalScore]));
  const network = analyzeGraphNetwork(cores, draws);
  const sequence = analyzeComplexSequence(cores, draws);
  const historicalSupportMap = new Map<number, number>(
    Object.entries(expertInput.historicalSupportByNumber || {}).map(([key, value]) => [Number(key), value as number])
  );
  const heatSupport = new Set(analyzeHeatZones(cores, draws).filter(zone => zone.temperature !== 'cold').flatMap(zone => zone.numbers));
  const cooccurrenceSupport = new Set(getCooccurrenceTop(cores, draws).flatMap(item => item.pair));
  const graphSupport = new Set(
    network
      .filter(item => item.bridgeScore >= 0.3 || item.structuralStability >= 0.45)
      .map(item => item.number)
  );
  const expertRepeatedSet = new Set(expertInput.repeatedNumbers);
  const expertFocusSet = new Set(expertInput.focusNumbers);

  const rawRows = cores.map(number => {
    const score = topScores.get(number) || 0;
    const networkMetric = network.find(item => item.number === number);
    const pointBase = Number((score * 0.48).toFixed(2));
    const structureBoost = Number(
      (
        (heatSupport.has(number) ? 8 : 0) +
        (cooccurrenceSupport.has(number) ? 6 : 0) +
        (graphSupport.has(number) ? 10 : 0) +
        Math.max(0, ((networkMetric?.betweenness || 0) - 0.3) * 12)
      ).toFixed(2)
    );
    const expertStructureBoost = Number(
      (
        (expertRepeatedSet.has(number) ? 18 : 0) +
        (expertFocusSet.has(number) ? 12 : 0)
      ).toFixed(2)
    );
    const historicalSupport = historicalSupportMap.get(number) || 0;
    const historicalAdjustment = Number(((historicalSupport - 1.2) * 8).toFixed(2));
    const penalty = Number(
      (
        expertInput.missingDataPenalty * 12 +
        (sequence.stateLabel === '高噪失稳' ? 6 : 0) +
        ((networkMetric?.bridgeScore || 0) >= 0.45 && (networkMetric?.structuralStability || 0) < 0.35 ? 4 : 0)
      ).toFixed(2)
    );
    const total = pointBase + structureBoost + expertStructureBoost + historicalAdjustment - penalty;
    const reasons: string[] = [];
    if (expertRepeatedSet.has(number)) {
      reasons.push('专家两套矩阵重复出现');
    }
    if (heatSupport.has(number)) {
      reasons.push('近期热区支持');
    }
    if (cooccurrenceSupport.has(number)) {
      reasons.push('历史共现关系较强');
    }
    if (graphSupport.has(number)) {
      reasons.push('图网络桥接/稳定性支持');
    }
    if (expertFocusSet.has(number)) {
      reasons.push('专家重点结论同步支持');
    }
    if (historicalSupport >= 1.8) {
      reasons.push('历史复盘表现较强');
    } else if (historicalSupport > 0 && historicalSupport < 0.8) {
      reasons.push('历史复盘偏弱，已下调');
    }
    if (score >= 70) reasons.push('点位综合评分较高');
    const level: UnifiedDecisionRow['level'] = total >= 70 ? '强共识' : total >= 45 ? '中共识' : '仅观察';
    return {
      number,
      rawScore: Math.round(total),
      level,
      reasons,
      scoreBreakdown: {
        pointBase,
        structureBoost,
        expertStructureBoost,
        historicalAdjustment,
        penalty,
        totalBeforeCalibration: Number(total.toFixed(2)),
      },
    };
  });

  const calibration = buildCalibrationSummary(
    rawRows.map(row => ({ number: row.number, rawScore: row.rawScore })),
    draws
  );

  const rows: UnifiedDecisionRow[] = rawRows.map(row => {
    const matched = matchCalibration(row.rawScore, calibration);
    return {
      number: row.number,
      consensusScore: row.rawScore,
      level: row.level,
      reasons: row.reasons,
      scoreBreakdown: row.scoreBreakdown,
      calibratedHitRate: matched?.observedHitRate ?? 0,
      calibratedConfidence: matched?.calibratedConfidence ?? '低',
      sampleSize: matched?.sampleSize ?? 0,
      reliable: matched?.reliable ?? false,
    };
  }).sort((a, b) => b.consensusScore - a.consensusScore);

  const regime = detectMarketRegime(cores, draws);
  const conflicts: ConflictSignal[] = [];
  if (regime.key === 'balanced' && expertInput.focusMatrices.length <= 1) {
    conflicts.push({
      type: '结构分散',
      severity: '中',
      source: 'graph',
      description: '点位系统判断当前偏分散，专家矩阵也没有形成明显集中共识。',
    });
  }
  if (regime.key === 'hot' && !rows.some(row => row.level === '强共识' && expertRepeatedSet.has(row.number))) {
    conflicts.push({
      type: '热号缺共识',
      severity: '高',
      source: 'hybrid',
      description: '点位系统提示热号延续，但专家矩阵没有同步给出强支撑。',
    });
  }
  if (
    expertInput.focusMatrices.length >= 2 &&
    rows.slice(0, 5).filter(row => (historicalSupportMap.get(row.number) || 0) < 0.8).length >= 2
  ) {
    conflicts.push({
      type: '结构强但历史弱',
      severity: '中',
      source: 'consensus',
      description: '专家结构集中，但历史复盘对前排候选的支持偏弱，存在虚高共识风险。',
    });
  }
  if (expertInput.missingDataPenalty > 0.35) {
    conflicts.push({
      type: '数据未同步',
      severity: '高',
      source: 'data',
      description: '专家历史数据存在明显缺口，共识分已被降权处理。',
    });
  }
  const weakBridgeCount = network.filter(item => item.bridgeScore >= 0.45 && item.structuralStability < 0.35).length;
  if (weakBridgeCount >= 2) {
    conflicts.push({
      type: '桥接断裂',
      severity: '中',
      source: 'graph',
      description: `检测到 ${weakBridgeCount} 个桥接节点稳定度偏低，结构连接可靠性下降。`,
    });
  }
  if (sequence.sequenceInstability >= 0.62) {
    conflicts.push({
      type: '序列突变',
      severity: '高',
      source: 'sequence',
      description: `序列不稳定度 ${sequence.sequenceInstability.toFixed(2)}，当前处于${sequence.stateLabel}态。`,
    });
  }

  const confidence: UnifiedDecisionSummary['confidence'] =
    rows.slice(0, 5).filter(row => row.level === '强共识').length >= 3 && conflicts.length === 0
      ? '高'
      : conflicts.length <= 1
        ? '中'
        : '低';

  return {
    topNumbers: rows.slice(0, 5),
    topMatrixLabels: expertInput.focusMatrices.slice(0, 3),
    confidence,
    conflicts,
    calibration,
  };
}

export function parsePositionFile(content: string): number[] {
  return content.split(/[,\s\n]+/).map(Number).filter(n => n >= 1 && n <= 80);
}

export function parseDrawsFile(content: string): number[][] {
  return content.split('\n').map(l => l.split(/[,\s]+/).map(Number).filter(n => n >= 1 && n <= 80)).filter(d => d.length >= 10);
}

export const DEFAULT_CORES = [1, 7, 12, 14, 17, 20, 30, 32, 34, 39, 40, 44, 47, 49, 55, 59, 64, 71, 79, 80];
export const DEFAULT_DRAWS = [[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]];
