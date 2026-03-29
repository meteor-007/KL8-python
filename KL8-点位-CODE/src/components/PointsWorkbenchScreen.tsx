import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type {
  EvidenceMetric,
  PointAnalysisDashboardModel,
  PointAnalysisSectionDefinition,
  PointAnalysisSectionKey,
  TechnicalInsightCard,
} from '../data/pointAnalysisViewModel';

const SelectionContext = createContext<{
  selectedNumber: number | null;
  setSelectedNumber: (value: number | null) => void;
} | null>(null);

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="bg-gray-800/50 backdrop-blur-sm rounded-2xl border border-gray-700/50 p-6">
      <div className="mb-4">
        <h2 className="text-xl font-bold text-white">{title}</h2>
        {subtitle ? <p className="text-sm text-gray-400 mt-1">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function ConfidenceBadge({ value }: { value: '高' | '中' | '低' }) {
  const cls =
    value === '高'
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
      : value === '中'
        ? 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30'
        : 'bg-red-500/15 text-red-300 border-red-500/30';
  return <span className={`inline-flex px-2 py-1 rounded-full border text-xs font-semibold ${cls}`}>可信度 {value}</span>;
}

function NumberChip({
  value,
  tone = 'cyan',
  active = false,
  onClick,
  title,
}: {
  value: number | string;
  tone?: 'cyan' | 'gray' | 'amber' | 'rose' | 'emerald';
  active?: boolean;
  onClick?: () => void;
  title?: string;
}) {
  const cls = {
    cyan: 'bg-cyan-500/10 border-cyan-500/30 text-cyan-200',
    gray: 'bg-gray-700/60 border-gray-600 text-gray-200',
    amber: 'bg-amber-500/10 border-amber-500/30 text-amber-200',
    rose: 'bg-rose-500/10 border-rose-500/30 text-rose-200',
    emerald: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200',
  }[tone];
  const selection = useContext(SelectionContext);
  const numericValue = typeof value === 'number' ? value : Number(value);
  const autoActive =
    selection?.selectedNumber !== null &&
    Number.isFinite(numericValue) &&
    selection.selectedNumber === numericValue;
  const activeCls = active || autoActive ? 'ring-2 ring-white/80 scale-[1.03]' : '';
  const shared = `inline-flex min-w-9 justify-center rounded-full border px-2 py-1 text-xs font-bold transition-transform ${cls} ${activeCls} ${
    onClick ? 'cursor-pointer hover:-translate-y-[1px] hover:brightness-110' : ''
  }`;
  const resolvedClick = onClick ?? (selection && Number.isFinite(numericValue) ? () => selection.setSelectedNumber(numericValue) : undefined);

  if (resolvedClick) {
    return (
      <button type="button" onClick={resolvedClick} title={title} aria-pressed={active || autoActive} className={shared}>
        {value}
      </button>
    );
  }

  return <span title={title} className={shared}>{value}</span>;
}

function formatPairNumber(value: number) {
  return String(value).padStart(2, '0');
}

function getFocusedPairs(
  pairs: PointAnalysisDashboardModel['structure']['cooccurrencePairs'],
  selectedNumber: number | null
) {
  if (selectedNumber === null) {
    return [...pairs];
  }

  return pairs.filter((pair) => pair.pair.includes(selectedNumber));
}

function getFocusedZones(
  zones: PointAnalysisDashboardModel['structure']['heatZones'],
  selectedNumber: number | null
) {
  if (selectedNumber === null) {
    return [...zones];
  }

  return zones.filter((zone) => zone.numbers.includes(selectedNumber));
}

function InsightCard({ item }: { item: TechnicalInsightCard }) {
  return (
    <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="text-sm font-semibold text-white">{item.title}</div>
        <ConfidenceBadge value={item.confidence} />
      </div>
      <p className="mt-3 text-sm text-gray-300 leading-relaxed">{item.summary}</p>
    </div>
  );
}

function MetricGrid({ metrics }: { metrics: EvidenceMetric[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {metrics.map((metric) => (
        <div key={metric.label} className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
          <div className="text-xs text-gray-500">{metric.label}</div>
          <div className="text-2xl font-bold text-cyan-300 mt-2">{metric.value}</div>
          {metric.detail ? <div className="text-xs text-gray-400 mt-2">{metric.detail}</div> : null}
        </div>
      ))}
    </div>
  );
}

function HeatZoneSpectrum({
  zones,
}: {
  zones: PointAnalysisDashboardModel['distribution']['hotZones'];
}) {
  const selection = useContext(SelectionContext);
  const maxEnergy = Math.max(...zones.map((zone) => zone.energy), 1);
  return (
    <div className="space-y-3">
      {zones.map((zone) => {
        const selected = selection?.selectedNumber !== null && zone.numbers.includes(selection.selectedNumber);
        const width = `${Math.max(6, (zone.energy / maxEnergy) * 100)}%`;
        const tone =
          zone.temperature === 'hot'
            ? 'from-rose-500 to-orange-400'
            : zone.temperature === 'warm'
              ? 'from-amber-500 to-yellow-400'
              : 'from-cyan-500 to-sky-400';
        return (
          <div key={zone.zone} className={`rounded-xl border p-4 ${selected ? 'border-white/60 bg-white/5 ring-2 ring-white/40' : 'border-gray-700/50 bg-gray-900/60'}`}>
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold text-white">{zone.zone}</span>
              <span className="text-gray-400">能量 {zone.energy}</span>
            </div>
            <div className="mt-3 h-3 rounded-full bg-gray-800/80">
              <div className={`h-3 rounded-full bg-gradient-to-r ${tone}`} style={{ width }} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {zone.numbers.length
                ? zone.numbers.map((value) => (
                    <NumberChip key={`${zone.zone}-${value}`} value={String(value).padStart(2, '0')} tone="cyan" />
                  ))
                : <span className="text-xs text-gray-500">当前无信号</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function NetworkConstellation({
  nodes,
  pairs,
  onSelectNumber,
}: {
  nodes: PointAnalysisDashboardModel['structure']['networkStats'];
  pairs: PointAnalysisDashboardModel['structure']['cooccurrencePairs'];
  onSelectNumber: (number: number) => void;
}) {
  const selection = useContext(SelectionContext);
  const topNodes = nodes.slice(0, 8);
  const size = 340;
  const center = size / 2;
  const radius = 112;
  const positions = new Map<number, { x: number; y: number }>();

  topNodes.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(topNodes.length, 1) - Math.PI / 2;
    positions.set(node.number, {
      x: center + Math.cos(angle) * radius,
      y: center + Math.sin(angle) * radius,
    });
  });

  const visiblePairs = pairs.filter(
    (pair) => positions.has(pair.pair[0]) && positions.has(pair.pair[1])
  );

  return (
    <div className="rounded-2xl border border-gray-700/50 bg-gray-950/60 p-4">
      <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto h-[340px] w-full max-w-[340px]">
        <circle cx={center} cy={center} r={radius + 26} fill="rgba(34,211,238,0.04)" stroke="rgba(34,211,238,0.12)" />
        {visiblePairs.map((pair) => {
          const from = positions.get(pair.pair[0])!;
          const to = positions.get(pair.pair[1])!;
          const pairSelected =
            selection?.selectedNumber !== null &&
            (pair.pair[0] === selection.selectedNumber || pair.pair[1] === selection.selectedNumber);
          const opacity = Math.min(0.9, 0.18 + pair.count / 10);
          return (
            <line
              key={`line-${pair.pair[0]}-${pair.pair[1]}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke={pairSelected ? 'rgba(255,255,255,0.9)' : `rgba(34,211,238,${opacity})`}
              strokeWidth={(pairSelected ? 2.8 : 1.5) + pair.count * 0.12}
            />
          );
        })}
        {topNodes.map((node) => {
          const point = positions.get(node.number)!;
          const nodeRadius = 18 + node.centrality * 12;
          const selected = selection?.selectedNumber === node.number;
          return (
            <g
              key={`node-${node.number}`}
              role="button"
              tabIndex={0}
              className="cursor-pointer"
              onClick={() => onSelectNumber(node.number)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onSelectNumber(node.number);
                }
              }}
            >
              <circle
                cx={point.x}
                cy={point.y}
                r={nodeRadius}
                fill={selected ? 'rgba(255,255,255,0.18)' : 'rgba(34,211,238,0.12)'}
                stroke={selected ? 'rgba(255,255,255,0.95)' : 'rgba(103,232,249,0.8)'}
                strokeWidth={selected ? 3 : 1.5}
              />
              <text x={point.x} y={point.y + 4} textAnchor="middle" fontSize="12" fill="#d1fae5" fontWeight="700">
                {String(node.number).padStart(2, '0')}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function TransitionBand({
  transitions,
}: {
  transitions: PointAnalysisDashboardModel['dynamics']['markov']['transitionMatrix'];
}) {
  const selection = useContext(SelectionContext);
  const visible = transitions.slice(0, 8);
  return (
    <div className="space-y-3">
      {visible.map((item) => (
        <div
          key={`transition-${item.from}-${item.to}`}
          className={`rounded-xl border p-4 ${
            selection?.selectedNumber !== null &&
            (selection.selectedNumber === item.from || selection.selectedNumber === item.to)
              ? 'border-white/60 bg-white/5 ring-2 ring-white/40'
              : 'border-gray-700/50 bg-gray-900/60'
          }`}
        >
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-white">
              <NumberChip value={String(item.from).padStart(2, '0')} tone="cyan" />
              <span className="text-gray-500">→</span>
              <NumberChip value={String(item.to).padStart(2, '0')} tone="emerald" />
            </div>
            <span className="text-gray-400">转移 {Math.round(item.probability * 100)}%</span>
          </div>
          <div className="mt-3 h-2 rounded-full bg-gray-800/80">
            <div
              className="h-2 rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400"
              style={{ width: `${Math.max(8, item.probability * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function ScoreLadder({
  scoreCards,
}: {
  scoreCards: PointAnalysisDashboardModel['decision']['scoreCards'];
}) {
  const selection = useContext(SelectionContext);
  const visible = scoreCards.slice(0, 8);
  const maxScore = Math.max(...visible.map((item) => item.totalScore), 1);
  return (
    <div className="space-y-3">
      {visible.map((item) => (
        <div
          key={`score-${item.number}`}
          className={`rounded-xl border p-4 ${
            selection?.selectedNumber === item.number
              ? 'border-white/60 bg-white/5 ring-2 ring-white/40'
              : 'border-gray-700/50 bg-gray-900/60'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <NumberChip value={String(item.number).padStart(2, '0')} tone="cyan" />
              <span className="text-sm text-gray-300">综合评分</span>
            </div>
            <span className="text-lg font-bold text-white">{item.totalScore}</span>
          </div>
          <div className="mt-3 h-2 rounded-full bg-gray-800/80">
            <div
              className="h-2 rounded-full bg-gradient-to-r from-cyan-400 via-sky-400 to-emerald-400"
              style={{ width: `${Math.max(10, (item.totalScore / maxScore) * 100)}%` }}
            />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-400">
            <div>频率 {item.freqScore}</div>
            <div>遗漏 {item.missScore}</div>
            <div>邻域 {item.neighborScore}</div>
            <div>周期 {item.cycleScore}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TimelineBand({
  snapshots,
  selectedNumber,
  onSelectNumber,
}: {
  snapshots: PointAnalysisDashboardModel['timeline']['snapshots'];
  selectedNumber: number | null;
  onSelectNumber: (number: number) => void;
}) {
  return (
    <div className="space-y-3">
      {snapshots.length ? snapshots.map((snapshot) => {
        const selectedLabel = selectedNumber !== null && snapshot.coreHits.includes(String(selectedNumber).padStart(2, '0'));
        const stateClass =
          snapshot.state === '高覆盖'
            ? 'border-emerald-500/30 bg-emerald-500/10'
            : snapshot.state === '中覆盖'
              ? 'border-yellow-500/30 bg-yellow-500/10'
              : 'border-cyan-500/30 bg-cyan-500/10';

        return (
          <div
            key={`${snapshot.date}-${snapshot.period}`}
            className={`rounded-xl border p-4 transition-all ${stateClass} ${selectedLabel ? 'ring-2 ring-white/50' : 'border-gray-700/50 bg-gray-900/60'}`}
          >
            <div className="flex items-center justify-between gap-3 text-sm">
              <div className="font-semibold text-white">{snapshot.label}</div>
              <span className="text-gray-300">{snapshot.state} · 命中 {snapshot.hitCount}</span>
            </div>
            <div className="mt-3 h-2 rounded-full bg-gray-800/80">
              <div className="h-2 rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400" style={{ width: `${Math.max(8, snapshot.coverageRatio * 100)}%` }} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {snapshot.coreHits.length ? snapshot.coreHits.map((value) => (
                <NumberChip
                  key={`${snapshot.label}-${value}`}
                  value={value}
                  tone="cyan"
                  active={selectedNumber !== null && Number(value) === selectedNumber}
                  onClick={() => onSelectNumber(Number(value))}
                  title={`选择 ${value}`}
                />
              )) : <span className="text-xs text-gray-500">当前窗口没有命中核心信号</span>}
            </div>
          </div>
        );
      }) : (
        <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4 text-sm text-gray-400">
          暂无时间轴样本。
        </div>
      )}
    </div>
  );
}

function buildSelectionInsight(
  model: PointAnalysisDashboardModel,
  selectedNumber: number | null
): {
  title: string;
  chips: Array<{ label: string; value: string; tone?: 'cyan' | 'gray' | 'amber' | 'rose' | 'emerald' }>;
  notes: string[];
  links: string[];
} | null {
  if (selectedNumber === null) return null;
  const value = String(selectedNumber).padStart(2, '0');
  const distributionStat = model.distribution.positionStats.find((item) => item.num === selectedNumber);
  const hotZone = model.distribution.hotZones.find((zone) => zone.numbers.includes(selectedNumber));
  const cluster = model.structure.clusters.find((item) => item.numbers.includes(selectedNumber));
  const node = model.structure.networkStats.find((item) => item.number === selectedNumber);
  const cyclic = model.dynamics.cyclicPatterns.find((item) => item.number === selectedNumber);
  const markov = model.dynamics.markov.predictions.find((item) => item.number === selectedNumber);
  const volatility = model.dynamics.volatilityStats.find((item) => item.number === selectedNumber);
  const score = model.decision.scoreCards.find((item) => item.number === selectedNumber);
  const timelineHits = model.timeline.snapshots.filter((snapshot) => snapshot.coreHits.includes(value)).length;

  return {
    title: `选中信号 ${value}`,
    chips: [
      { label: '核心', value: model.overview.cores.includes(selectedNumber) ? '是' : '否', tone: model.overview.cores.includes(selectedNumber) ? 'emerald' : 'gray' },
      { label: '扩展', value: model.overview.expanded.includes(selectedNumber) ? '是' : '否', tone: model.overview.expanded.includes(selectedNumber) ? 'cyan' : 'gray' },
      { label: '最新命中', value: model.overview.latestHitCores.includes(selectedNumber) ? '是' : '否', tone: model.overview.latestHitCores.includes(selectedNumber) ? 'amber' : 'gray' },
      { label: '时间轴命中', value: `${timelineHits}`, tone: timelineHits > 0 ? 'emerald' : 'gray' },
    ],
    notes: [
      distributionStat ? `近期 10 期命中 ${distributionStat.hits10} 次，3 期命中 ${distributionStat.hits3} 次，连续遗漏 ${distributionStat.misses} 期。` : '暂无分布统计。',
      hotZone ? `所属热区：${hotZone.zone}，当前能量 ${hotZone.energy}。` : '当前未落入明显热区。',
      cluster ? `所属集群：${cluster.numbers.map((num) => String(num).padStart(2, '0')).join('、')}，集群分数 ${cluster.clusterScore}。` : '当前未落入显著集群。',
      node ? `网络中心度 ${node.centrality}，关联节点数 ${node.degree}。` : '当前未形成明显网络节点。',
      cyclic ? `周期阶段：${cyclic.phase}，共振分 ${cyclic.resonanceScore}。` : '周期特征不足。',
      markov ? `状态：${markov.currentState}，下一步偏向 ${markov.nextPrediction}（${Math.round(markov.transitionProb * 100)}%）。` : '状态转移不足。',
      volatility ? `波动类型：${volatility.cluster}，波动率 ${volatility.volatility}。` : '波动特征不足。',
      score ? `综合评分 ${score.totalScore}，位于当前评分梯度中的前列。` : '暂无评分结果。',
    ],
    links: [
      hotZone ? `热区：${hotZone.zone}` : '热区：无',
      cluster ? '结构：已关联' : '结构：未关联',
      markov ? `状态：${markov.currentState}` : '状态：无',
    ],
  };
}

function SelectionInspector({
  model,
  selectedNumber,
  onClear,
}: {
  model: PointAnalysisDashboardModel;
  selectedNumber: number | null;
  onClear: () => void;
}) {
  const insight = useMemo(() => buildSelectionInsight(model, selectedNumber), [model, selectedNumber]);
  const selectedNumberText = selectedNumber === null ? null : String(selectedNumber).padStart(2, '0');

  return (
    <Panel title="点击联动研究台" subtitle="点击任意数字即可查看它在结构、动态、评分和时间轴上的联动关系。">
      {!insight ? (
        <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4 text-sm text-gray-400">
          先点击任意数字，系统会把它在所有模块里的关系一起高亮出来。
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(260px,0.8fr)] gap-4">
          <div className="rounded-2xl border border-cyan-500/15 bg-cyan-500/5 p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-white">{insight.title}</div>
              <button
                type="button"
                onClick={onClear}
                className="rounded-full border border-gray-700 px-3 py-1 text-xs text-gray-300 hover:bg-gray-800"
              >
                清除选择
              </button>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {insight.chips.map((chip) => (
                <span key={chip.label} className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${
                  chip.tone === 'emerald'
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                    : chip.tone === 'cyan'
                      ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200'
                      : chip.tone === 'amber'
                        ? 'border-amber-500/30 bg-amber-500/10 text-amber-200'
                        : chip.tone === 'rose'
                          ? 'border-rose-500/30 bg-rose-500/10 text-rose-200'
                          : 'border-gray-700 bg-gray-800/80 text-gray-300'
                }`}>
                  {chip.label} {chip.value}
                </span>
              ))}
            </div>
            <div className="mt-4 space-y-2 text-sm text-gray-300">
              {selectedNumberText ? (
                <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-3">
                  最近时间轴命中期：{model.timeline.snapshots.filter((snapshot) => snapshot.coreHits.includes(selectedNumberText)).map((snapshot) => snapshot.label).join('；') || '无'}
                </div>
              ) : null}
              {insight.notes.map((note, index) => (
                <div key={`${index}-${note.slice(0, 6)}`} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-3">
                  {note}
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
            <div className="text-xs uppercase tracking-wider text-gray-500 mb-3">跨模块链接</div>
            <div className="space-y-2 text-sm text-gray-300">
              {insight.links.map((link) => (
                <div key={link} className="rounded-xl border border-gray-800 bg-gray-950/50 px-3 py-2">{link}</div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}

function WorkbenchHeader({
  activeSection,
  section,
  question,
  relatedSections,
}: {
  activeSection: PointAnalysisSectionKey;
  section: PointAnalysisSectionDefinition;
  question: string;
  relatedSections: string[];
}) {
  return (
    <Panel title={`${section.icon} ${section.label}`} subtitle={section.description}>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)] gap-4">
        <div className="rounded-2xl border border-cyan-500/15 bg-cyan-500/5 p-4">
          <div className="text-xs uppercase tracking-wider text-cyan-300 mb-2">本页回答的问题</div>
          <p className="text-sm text-gray-200 leading-relaxed">{question}</p>
        </div>
        <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">与其他页面的关联</div>
          <div className="flex flex-wrap gap-2">
            {relatedSections.map((item) => (
              <span key={`${activeSection}-${item}`} className="rounded-full border border-gray-700 bg-gray-800/70 px-3 py-1 text-xs text-gray-300">
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function renderOverview(model: PointAnalysisDashboardModel) {
  return (
    <div className="space-y-6">
      <Panel title="当前最重要的发现">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {model.overview.findings.map((item) => <InsightCard key={item.title} item={item} />)}
        </div>
      </Panel>

      <Panel title="支撑这些发现的技术证据">
        <MetricGrid metrics={model.overview.metrics} />
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)] gap-6 mt-6">
          <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
            <div className="text-sm font-semibold text-white mb-3">核心信号集合</div>
            <div className="flex flex-wrap gap-2">
              {model.overview.cores.map((value) => <NumberChip key={`core-${value}`} value={String(value).padStart(2, '0')} tone="cyan" />)}
            </div>
            <div className="text-sm font-semibold text-white mt-5 mb-3">扩展邻域集合</div>
            <div className="flex flex-wrap gap-2">
              {model.overview.expanded.map((value) => <NumberChip key={`expand-${value}`} value={String(value).padStart(2, '0')} tone="gray" />)}
            </div>
          </div>
          <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
            <div className="text-sm font-semibold text-white mb-3">数据健康状态</div>
            <div className="space-y-3 text-sm text-gray-300">
              <div>点位最新日期：{model.overview.dataHealth.pointsLatestDate || '未知'}</div>
              <div>历史最新日期：{model.overview.dataHealth.historyLatestDate || '未知'}</div>
              <div>专家最新日期：{model.overview.dataHealth.expertLatestDate || '未知'}</div>
              <div className="pt-2"><ConfidenceBadge value={model.overview.dataHealth.confidence} /></div>
              <p className="text-sm text-gray-400 leading-relaxed">{model.overview.dataHealth.statusText}</p>
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function renderDistribution(model: PointAnalysisDashboardModel) {
  return (
    <div className="space-y-6">
      <Panel title="当前最重要的发现">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {model.distribution.findings.map((item) => <InsightCard key={item.title} item={item} />)}
        </div>
      </Panel>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)] gap-6">
        <Panel title="高频层与稀疏层">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <div className="text-sm font-semibold text-white mb-3">近期高频层</div>
              <div className="space-y-2">
                {model.distribution.topFrequency.map((item) => (
                  <div key={`freq-${item.num}`} className="flex items-center justify-between rounded-xl border border-gray-700/50 bg-gray-900/60 px-4 py-3">
                    <NumberChip value={String(item.num).padStart(2, '0')} tone="emerald" />
                    <span className="text-sm text-gray-300">10期命中 {item.hits10} / 3期命中 {item.hits3}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-sm font-semibold text-white mb-3">长期遗漏层</div>
              <div className="space-y-2">
                {model.distribution.longMiss.map((item) => (
                  <div key={`miss-${item.num}`} className="flex items-center justify-between rounded-xl border border-gray-700/50 bg-gray-900/60 px-4 py-3">
                    <NumberChip value={String(item.num).padStart(2, '0')} tone="amber" />
                    <span className="text-sm text-gray-300">连续遗漏 {item.misses} 期</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Panel>
        <Panel title="区域覆盖证据">
          <HeatZoneSpectrum zones={model.distribution.hotZones} />
        </Panel>
      </div>
    </div>
  );
}

function renderStructure(
  model: PointAnalysisDashboardModel,
  selectedNumber: number | null,
  onSelectNumber: (number: number) => void
) {
  const selectedLabel = selectedNumber === null ? null : formatPairNumber(selectedNumber);
  const focusedPairs = getFocusedPairs(model.structure.cooccurrencePairs, selectedNumber);
  const focusedZones = getFocusedZones(model.structure.heatZones, selectedNumber);

  return (
    <div className="space-y-6">
      <Panel title="当前最重要的发现">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {model.structure.findings.map((item) => (
            <InsightCard key={item.title} item={item} />
          ))}
        </div>
      </Panel>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)] gap-6">
        <Panel title="集群、共现与热区">
          <div className="space-y-4">
            <div
              className={`rounded-xl border p-4 ${
                selectedNumber === null
                  ? 'border-gray-700/50 bg-gray-900/60 text-gray-300'
                  : 'border-cyan-500/20 bg-cyan-500/5 text-cyan-100'
              }`}
            >
              {selectedNumber === null
                ? '当前未锁定网络节点。点击任意网络节点后，这里的共现对和热区会自动缩小到相关子集。'
                : `当前已锁定节点 ${selectedLabel}，下面只展示与该节点直接相关的共现对与热区。`}
            </div>

            {model.structure.clusters.map((cluster, index) => (
              <div key={`cluster-${index}`} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">集群 {index + 1}</span>
                  <span className="text-xs text-gray-400">分数 {cluster.clusterScore} · {cluster.trend}</span>
                </div>
                <div className="flex flex-wrap gap-2 mt-3">
                  {cluster.numbers.map((value) => (
                    <NumberChip key={`cluster-${index}-${value}`} value={formatPairNumber(value)} tone="rose" />
                  ))}
                </div>
              </div>
            ))}

            <div className="rounded-xl border border-gray-700/50 bg-gray-950/40 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-white">
                  {selectedNumber === null ? '全部共现对' : `与 ${selectedLabel} 相关的共现对`}
                </div>
                <div className="text-xs text-gray-400">共 {focusedPairs.length} 组</div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
                {focusedPairs.length ? (
                  focusedPairs.map((pair) => (
                    <div key={`pair-${pair.pair[0]}-${pair.pair[1]}`} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
                      <div className="flex items-center gap-2">
                        <NumberChip value={formatPairNumber(pair.pair[0])} tone="emerald" />
                        <span className="text-gray-500">+</span>
                        <NumberChip value={formatPairNumber(pair.pair[1])} tone="emerald" />
                      </div>
                      <div className="text-sm text-gray-400 mt-3">近窗共现 {pair.count} 次</div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4 text-sm text-gray-400 lg:col-span-2">
                    当前节点暂未筛出可见共现对。
                  </div>
                )}
              </div>
            </div>
          </div>
        </Panel>

        <Panel title="网络中心度与关系图">
          <NetworkConstellation
            nodes={model.structure.networkStats}
            pairs={model.structure.cooccurrencePairs}
            onSelectNumber={onSelectNumber}
          />
          <div className="mt-4 space-y-2">
            {model.structure.networkStats.slice(0, 6).map((node) => (
              <div key={`net-${node.number}`} className="flex items-center justify-between rounded-xl border border-gray-700/50 bg-gray-900/60 px-4 py-3">
                <NumberChip value={formatPairNumber(node.number)} tone="cyan" />
                <span className="text-sm text-gray-300">中心度 {node.centrality} · 关联节点 {node.degree}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-xl border border-gray-700/50 bg-gray-950/40 p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-white">
                {selectedNumber === null ? '全部热区' : `与 ${selectedLabel} 相关的热区`}
              </div>
              <div className="text-xs text-gray-400">共 {focusedZones.length} 个</div>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3">
              {focusedZones.length ? (
                focusedZones.map((zone) => (
                  <div key={zone.zone} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold text-white">{zone.zone}</span>
                      <span className="text-gray-400">能量 {zone.energy}</span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {zone.numbers.map((value) => (
                        <NumberChip key={`${zone.zone}-${value}`} value={formatPairNumber(value)} tone="cyan" />
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4 text-sm text-gray-400">
                  当前节点暂未命中可见热区。
                </div>
              )}
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function renderDynamics(model: PointAnalysisDashboardModel) {
  return (
    <div className="space-y-6">
      <Panel title="当前最重要的发现">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {model.dynamics.findings.map((item) => <InsightCard key={item.title} item={item} />)}
        </div>
      </Panel>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)] gap-6">
        <Panel title="时序动态证据">
          <div className="space-y-4">
            <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
              <div className="text-sm font-semibold text-white mb-3">周期共振</div>
              <div className="space-y-2">
                {model.dynamics.cyclicPatterns.slice(0, 8).map((item) => (
                  <div key={`cyclic-${item.number}`} className="flex items-center justify-between">
                    <NumberChip value={String(item.number).padStart(2, '0')} tone="cyan" />
                    <span className="text-sm text-gray-300">{item.phase} · 周期 {item.period} · 共振 {item.resonanceScore}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
              <div className="text-sm font-semibold text-white mb-3">状态转移</div>
              <div className="space-y-2">
                {model.dynamics.markov.predictions.slice(0, 8).map((item) => (
                  <div key={`markov-${item.number}`} className="flex items-center justify-between">
                    <NumberChip value={String(item.number).padStart(2, '0')} tone="emerald" />
                    <span className="text-sm text-gray-300">{item.currentState} → {item.nextPrediction} · 概率 {item.transitionProb}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Panel>
        <Panel title="波动、转移带与序列特征">
          <div className="space-y-4">
            <TransitionBand transitions={model.dynamics.markov.transitionMatrix} />
            {model.dynamics.volatilityStats.slice(0, 8).map((item) => (
              <div key={`vol-${item.number}`} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
                <div className="flex items-center justify-between">
                  <NumberChip value={String(item.number).padStart(2, '0')} tone="rose" />
                  <span className="text-sm text-gray-400">{item.cluster}</span>
                </div>
                <div className="text-xs text-gray-500 mt-2">波动率 {item.volatility}</div>
              </div>
            ))}
            <div className="rounded-xl border border-cyan-500/15 bg-cyan-500/5 p-4">
              <div className="text-sm font-semibold text-white mb-3">复杂序列摘要</div>
              <div className="grid grid-cols-2 gap-3 text-sm text-gray-300">
                <div>平均模值：{model.dynamics.complexSequence.avgMod}</div>
                <div>平均相位：{model.dynamics.complexSequence.avgPhase}</div>
                <div>主导频差：{model.dynamics.complexSequence.dominantFreq}</div>
                <div>谱能量：{model.dynamics.complexSequence.spectralEnergy}</div>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function renderRegime(model: PointAnalysisDashboardModel) {
  return (
    <div className="space-y-6">
      <Panel title="当前最重要的发现">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {model.regime.findings.map((item) => <InsightCard key={item.title} item={item} />)}
        </div>
      </Panel>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)] gap-6">
        <Panel title="状态标签与建议">
          <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-5">
            <div className="text-sm font-semibold text-white">{model.regime.regime.label}</div>
            <p className="text-sm text-gray-300 mt-3 leading-relaxed">{model.regime.regime.description}</p>
            <div className="mt-4 rounded-xl border border-cyan-500/10 bg-cyan-500/5 p-4 text-sm text-cyan-200">
              建议偏向：{model.regime.regime.recommendedBias}
            </div>
            <div className="mt-4 text-sm text-gray-300">系统熵值：{model.regime.entropy.value} · {model.regime.entropy.level}</div>
          </div>
        </Panel>
        <Panel title="冲突与分歧信号">
          <div className="space-y-3">
            {model.regime.conflicts.length ? model.regime.conflicts.map((item, index) => (
              <div key={`${item.type}-${index}`} className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-red-200">{item.type}</span>
                  <span className="text-xs text-red-300">严重度 {item.severity}</span>
                </div>
                <p className="text-sm text-gray-300 mt-3">{item.description}</p>
              </div>
            )) : <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-emerald-200">当前未检测到明显冲突，结构与动态判断基本一致。</div>}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function renderValidation(model: PointAnalysisDashboardModel) {
  return (
    <div className="space-y-6">
      <Panel title="当前最重要的发现">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {model.validation.findings.map((item) => <InsightCard key={item.title} item={item} />)}
        </div>
      </Panel>
      <Panel title="规则验证明细">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400">
                <th className="px-3 py-3 text-left">规则</th>
                <th className="px-3 py-3 text-center">30期</th>
                <th className="px-3 py-3 text-center">60期</th>
                <th className="px-3 py-3 text-center">120期</th>
                <th className="px-3 py-3 text-center">稳定性</th>
                <th className="px-3 py-3 text-center">失效期</th>
                <th className="px-3 py-3 text-center">可信度</th>
              </tr>
            </thead>
            <tbody>
              {model.validation.results.map((item) => (
                <tr key={item.ruleKey} className="border-b border-gray-800 hover:bg-gray-700/10">
                  <td className="px-3 py-3 font-semibold text-white">{item.label}</td>
                  <td className="px-3 py-3 text-center text-gray-300">{Math.round(item.windows.w30 * 100)}%</td>
                  <td className="px-3 py-3 text-center text-gray-300">{Math.round(item.windows.w60 * 100)}%</td>
                  <td className="px-3 py-3 text-center text-gray-300">{Math.round(item.windows.w120 * 100)}%</td>
                  <td className="px-3 py-3 text-center text-gray-300">{item.stability}</td>
                  <td className="px-3 py-3 text-center text-gray-300">{item.lastFailureGap}</td>
                  <td className="px-3 py-3 text-center"><ConfidenceBadge value={item.confidence} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
            <div className="text-xs text-gray-500">近期最强规则</div>
            <div className="text-lg font-bold text-cyan-300 mt-2">{model.validation.summary.bestRule}</div>
          </div>
          <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
            <div className="text-xs text-gray-500">近期最弱规则</div>
            <div className="text-lg font-bold text-amber-300 mt-2">{model.validation.summary.weakestRule}</div>
          </div>
          <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
            <div className="text-xs text-gray-500">平均 30 期表现</div>
            <div className="text-lg font-bold text-white mt-2">{Math.round(model.validation.summary.average30Window * 100)}%</div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function renderDecision(model: PointAnalysisDashboardModel) {
  return (
    <div className="space-y-6">
      <Panel title="当前最重要的发现">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {model.decision.findings.map((item) => <InsightCard key={item.title} item={item} />)}
        </div>
      </Panel>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)] gap-6">
        <Panel title="统一共识与综合判断">
          <div className="space-y-4">
            {model.decision.unifiedDecision.topNumbers.slice(0, 10).map((item) => (
              <div key={`decision-${item.number}`} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
                <div className="flex items-center justify-between">
                  <NumberChip value={String(item.number).padStart(2, '0')} tone="cyan" />
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-300">共识分 {item.consensusScore}</span>
                    <span className="rounded-full border border-gray-700 px-3 py-1 text-xs text-gray-300">{item.level}</span>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.reasons.map((reason, index) => (
                    <span key={`${item.number}-${index}`} className="rounded-full border border-gray-700 bg-gray-800/70 px-3 py-1 text-xs text-gray-300">
                      {reason}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="最终技术建议、评分阶梯与风险">
          <div className="space-y-4">
            <ScoreLadder scoreCards={model.decision.scoreCards} />
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
              <div className="text-sm font-semibold text-emerald-200">核心集合</div>
              <div className="flex flex-wrap gap-2 mt-3">
                {model.decision.finalRecommendation.core5.map((value) => <NumberChip key={`core5-${value}`} value={String(value).padStart(2, '0')} tone="emerald" />)}
              </div>
            </div>
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
              <div className="text-sm font-semibold text-amber-200">补充观察</div>
              <div className="flex flex-wrap gap-2 mt-3">
                {model.decision.finalRecommendation.backup2.map((value) => <NumberChip key={`backup-${value}`} value={String(value).padStart(2, '0')} tone="amber" />)}
              </div>
            </div>
            <div className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4 text-sm text-gray-300">
              <div className="font-semibold text-white mb-3">技术说明</div>
              <div className="space-y-2">
                {model.decision.finalRecommendation.reasoning.map((item, index) => <div key={`reason-${index}`}>{item}</div>)}
              </div>
            </div>
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <div className="text-sm font-semibold text-red-200 mb-3">风险提醒</div>
              <div className="space-y-2 text-sm text-gray-300">
                {model.decision.riskWarnings.length
                  ? model.decision.riskWarnings.map((item, index) => <div key={`${item.type}-${index}`}>{item.type}：{item.description}，建议 {item.suggestion}</div>)
                  : <div>当前未发现显著结构性风险。</div>}
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

export function PointsWorkbenchScreen({
  model,
  activeSection,
}: {
  model: PointAnalysisDashboardModel;
  activeSection: PointAnalysisSectionKey;
}) {
  const [selectedNumber, setSelectedNumber] = useState<number | null>(null);
  const section = model.sections.find((item) => item.key === activeSection) ?? model.sections[0];

  const sharedProps = {
    activeSection,
    section,
    question:
      activeSection === 'overview'
        ? model.overview.question
        : activeSection === 'distribution'
          ? model.distribution.question
          : activeSection === 'structure'
            ? model.structure.question
            : activeSection === 'dynamics'
              ? model.dynamics.question
              : activeSection === 'regime'
                ? model.regime.question
                : activeSection === 'validation'
                  ? model.validation.question
                  : model.decision.question,
    relatedSections:
      activeSection === 'overview'
        ? model.overview.relatedSections
        : activeSection === 'distribution'
          ? model.distribution.relatedSections
          : activeSection === 'structure'
            ? model.structure.relatedSections
            : activeSection === 'dynamics'
              ? model.dynamics.relatedSections
              : activeSection === 'regime'
                ? model.regime.relatedSections
                : activeSection === 'validation'
                  ? model.validation.relatedSections
                  : model.decision.relatedSections,
  };

  return (
    <SelectionContext.Provider value={{ selectedNumber, setSelectedNumber }}>
      <div className="space-y-6">
        <WorkbenchHeader {...sharedProps} />
        <SelectionInspector model={model} selectedNumber={selectedNumber} onClear={() => setSelectedNumber(null)} />
        <Panel title="最近时间轴状态带" subtitle="点击任意核心数字可追踪它在最近 10 期里的覆盖变化。">
          <TimelineBand snapshots={model.timeline.snapshots} selectedNumber={selectedNumber} onSelectNumber={setSelectedNumber} />
        </Panel>
        {activeSection === 'overview' && renderOverview(model)}
        {activeSection === 'distribution' && renderDistribution(model)}
        {activeSection === 'structure' && renderStructure(model, selectedNumber, setSelectedNumber)}
        {activeSection === 'dynamics' && renderDynamics(model)}
        {activeSection === 'regime' && renderRegime(model)}
        {activeSection === 'validation' && renderValidation(model)}
        {activeSection === 'decision' && renderDecision(model)}
      </div>
    </SelectionContext.Provider>
  );
}
