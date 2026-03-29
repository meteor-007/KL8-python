import { useState, type ReactNode } from 'react';
import type { PointAnalysisDashboardModel } from '../data/pointAnalysisViewModel';
import type {
  PointDecisionBriefModel,
  ReportSectionKey,
  Top5Insight,
} from '../data/pointDecisionBrief';

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-gray-700/50 bg-gray-900/60 p-6 shadow-[0_24px_80px_rgba(0,0,0,0.22)]">
      <div className="mb-4">
        <h2 className="text-2xl font-bold text-white">{title}</h2>
        {subtitle ? <p className="mt-1 text-sm leading-relaxed text-gray-400">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function ConfidenceBadge({ value }: { value: '高' | '中' | '低' }) {
  const cls =
    value === '高'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
      : value === '中'
        ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-200'
        : 'border-rose-500/30 bg-rose-500/10 text-rose-200';
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${cls}`}>可信度 {value}</span>;
}

function NumberPill({ value, tone = 'cyan' }: { value: number | string; tone?: 'cyan' | 'emerald' | 'amber' | 'rose' }) {
  const cls = {
    cyan: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
    emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
    amber: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
    rose: 'border-rose-500/30 bg-rose-500/10 text-rose-200',
  }[tone];
  return <span className={`inline-flex min-w-10 justify-center rounded-full border px-3 py-1 text-xs font-bold ${cls}`}>{value}</span>;
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-2 text-lg font-bold text-white">{value}</div>
      {detail ? <div className="mt-2 text-xs leading-relaxed text-gray-400">{detail}</div> : null}
    </div>
  );
}

function InsightCard({
  item,
  selectedNetworkNumber,
  selectedTopNumber,
  onSelectTopNumber,
}: {
  item: Top5Insight;
  selectedNetworkNumber: number | null;
  selectedTopNumber: number | null;
  onSelectTopNumber: (value: number | null) => void;
}) {
  const linkedToSelected =
    selectedNetworkNumber == null || item.linkedStructureNumbers.includes(selectedNetworkNumber);
  const selectedByTop = selectedTopNumber === item.number;
  return (
    <button
      type="button"
      onClick={() => onSelectTopNumber(selectedByTop ? null : item.number)}
      className={`rounded-2xl border bg-gray-950/50 p-4 transition ${
        selectedByTop
          ? 'border-violet-400/50 shadow-[0_0_0_1px_rgba(167,139,250,0.25)]'
          : selectedNetworkNumber == null
          ? 'border-gray-700/50'
          : linkedToSelected
            ? 'border-cyan-400/40 shadow-[0_0_0_1px_rgba(34,211,238,0.2)]'
            : 'border-gray-800/50 opacity-60'
      } text-left`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <NumberPill value={item.number} tone={item.confidence === '高' ? 'emerald' : item.confidence === '中' ? 'amber' : 'rose'} />
          <div>
            <div className="text-sm font-semibold text-white">综合共识分 {item.rankScore}</div>
            <div className="mt-1 text-xs text-gray-500">{item.riskAdjustedVerdict}</div>
          </div>
        </div>
        <ConfidenceBadge value={item.confidence} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
          建议动作：{item.action}
        </span>
        {selectedNetworkNumber != null ? (
          <span
            className={`rounded-full border px-3 py-1 text-xs ${
              linkedToSelected
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                : 'border-gray-700 bg-gray-900/60 text-gray-400'
            }`}
          >
            {linkedToSelected ? `受节点 ${selectedNetworkNumber} 支撑` : `与节点 ${selectedNetworkNumber} 弱相关`}
          </span>
        ) : null}
        <span
          className={`rounded-full border px-3 py-1 text-xs ${
            selectedByTop
              ? 'border-violet-400/40 bg-violet-500/15 text-violet-100'
              : 'border-gray-700 bg-gray-900/60 text-gray-300'
          }`}
        >
          {selectedByTop ? '已锁定该候选，证据区反向高亮' : '点击可反查结构证据'}
        </span>
        <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs text-violet-100">
          增强贡献 {item.enhancedContribution.totalBoost}（{item.enhancedContribution.gate}）
        </span>
        <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-100">
          校准后命中率 {Math.round(item.calibratedHitRate * 100)}%
        </span>
        <span className="rounded-full border border-gray-700 bg-gray-900/60 px-3 py-1 text-xs text-gray-300">
          样本 {item.calibrationSampleSize} · {item.calibrationReliable ? '可靠' : '低样本'}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {item.drivers.map((text) => (
          <span key={text} className="rounded-full border border-emerald-500/20 bg-emerald-500/8 px-3 py-1 text-xs text-emerald-100">
            {text}
          </span>
        ))}
        {item.conflicts.map((text) => (
          <span key={text} className="rounded-full border border-rose-500/20 bg-rose-500/8 px-3 py-1 text-xs text-rose-100">
            {text}
          </span>
        ))}
      </div>
      <div className="mt-4 rounded-xl border border-gray-700/50 bg-gray-900/60 p-3">
        <div className="text-xs text-gray-400">证据链</div>
        <div className="mt-2 space-y-1 text-xs text-gray-200">
          {item.evidenceChain.map((row) => (
            <div key={row}>- {row}</div>
          ))}
        </div>
      </div>
      <div className="mt-3 rounded-xl border border-gray-700/50 bg-gray-900/60 p-3">
        <div className="text-xs text-gray-400">权重拆解</div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
          {item.scoreBreakdown.map((row) => (
            <div key={`${item.number}-${row.label}`} className="flex items-center justify-between rounded-lg border border-gray-700/50 px-2 py-1 text-gray-200">
              <span>{row.label}</span>
              <span className={row.value >= 0 ? 'text-emerald-200' : 'text-rose-200'}>
                {row.value >= 0 ? `+${row.value}` : row.value}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 rounded-xl border border-gray-700/50 bg-gray-900/60 p-3">
        <div className="text-xs text-gray-400">跨系统共识拆解</div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
          {item.consensusBreakdown.map((row) => (
            <div key={`${item.number}-consensus-${row.label}`} className="flex items-center justify-between rounded-lg border border-gray-700/50 px-2 py-1 text-gray-200">
              <span>{row.label}</span>
              <span className={row.value >= 0 ? 'text-emerald-200' : 'text-rose-200'}>
                {row.value >= 0 ? `+${row.value}` : row.value}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 text-xs leading-relaxed text-gray-400">不确定性：{item.uncertainty}</div>
      {selectedNetworkNumber != null || selectedByTop ? (
        <div className="mt-2 text-xs leading-relaxed text-gray-400">
          结构关联链：{item.linkedStructureNumbers.join('、')}
        </div>
      ) : null}
      <div className="mt-2 text-xs leading-relaxed text-gray-400">
        图网络 +{item.enhancedContribution.structureBoost} · 序列谱 +{item.enhancedContribution.sequenceBoost}
      </div>
      <div className="mt-3 rounded-xl border border-gray-700/50 bg-gray-900/60 p-3">
        <div className="text-xs text-gray-400">可追溯引用</div>
        <div className="mt-2 space-y-1 text-xs text-gray-300">
          {item.evidenceRefs.map((ref) => (
            <div key={`${item.number}-${ref}`}>- {ref}</div>
          ))}
        </div>
      </div>
    </button>
  );
}

function FoldSection({
  title,
  summary,
  children,
  open = false,
}: {
  title: string;
  summary: string;
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details className="group rounded-3xl border border-gray-700/50 bg-gray-900/60 p-5" open={open}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-white">{title}</div>
          <div className="mt-1 text-sm text-gray-400">{summary}</div>
        </div>
        <span className="text-sm text-gray-500 transition-transform duration-200 group-open:rotate-180">⌄</span>
      </summary>
      <div className="mt-5">{children}</div>
    </details>
  );
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function renderOverview(
  model: PointAnalysisDashboardModel,
  brief: PointDecisionBriefModel,
  selectedNetworkNumber: number | null,
  selectedTopNumber: number | null,
  onSelectTopNumber: (value: number | null) => void
) {
  const selectedTop = brief.top5Insights.find((item) => item.number === selectedTopNumber) ?? null;
  const linkedTopCount =
    selectedNetworkNumber == null
      ? brief.top5Insights.length
      : brief.top5Insights.filter(item => item.linkedStructureNumbers.includes(selectedNetworkNumber)).length;
  return (
    <div className="space-y-6">
      <Panel title="本期怎么看" subtitle="首屏只看结论、Top 5、宏观趋势和风险应对，细节留到证据层。">
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)] gap-4">
          <div className="rounded-3xl border border-cyan-500/15 bg-cyan-500/5 p-5">
            <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">最终结论</div>
            <div className="mt-3 text-3xl font-black text-white">{brief.executiveSummary.verdict}</div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <ConfidenceBadge value={brief.executiveSummary.confidence} />
              <span className="rounded-full border border-gray-700 bg-gray-900/60 px-3 py-1 text-xs text-gray-300">
                建议动作：{brief.executiveSummary.recommendedAction}
              </span>
            </div>
            <ul className="mt-4 space-y-2 text-sm leading-relaxed text-gray-200">
              {brief.executiveSummary.keyMessages.map((message) => (
                <li key={message} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 px-4 py-3">
                  {message}
                </li>
              ))}
              {selectedNetworkNumber != null ? (
                <li className="rounded-2xl border border-cyan-500/20 bg-cyan-500/8 px-4 py-3">
                  当前已锁定结构节点 {selectedNetworkNumber}，Top 5 中受其支撑的候选有 {linkedTopCount} 个。
                </li>
              ) : null}
              {selectedTop ? (
                <li className="rounded-2xl border border-violet-500/20 bg-violet-500/8 px-4 py-3">
                  当前已锁定候选 {selectedTop.number}，证据层会反向高亮它关联的结构节点、共现对和热区。
                </li>
              ) : null}
            </ul>
          </div>

          <div className="rounded-3xl border border-gray-700/50 bg-gray-950/50 p-5">
            <div className="text-sm font-semibold text-white">宏观趋势</div>
            <div className="mt-4 space-y-3">
              <MetricCard label="主导周期" value={brief.macroTrend.dominantCycle} />
              <MetricCard label="场域偏向" value={brief.macroTrend.fieldBias} />
              <MetricCard label="熵值异常" value={brief.macroTrend.entropyAnomaly} />
              <MetricCard label="波动状态" value={brief.macroTrend.volatilityState} />
            </div>
          </div>
        </div>
      </Panel>

      <Panel title="Top 5 深度解析" subtitle="按风险调整后的综合共识分排序，而不是只看单一高分。">
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {brief.top5Insights.map((item) => (
            <InsightCard
              key={item.number}
              item={item}
              selectedNetworkNumber={selectedNetworkNumber}
              selectedTopNumber={selectedTopNumber}
              onSelectTopNumber={onSelectTopNumber}
            />
          ))}
        </div>
      </Panel>

      <Panel title="风险预警与应对" subtitle="先看最怕什么，再看怎么降风险。">
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)] gap-4">
          <div className="rounded-3xl border border-rose-500/15 bg-rose-500/5 p-5">
            <div className="text-xs uppercase tracking-[0.2em] text-rose-200">主要风险</div>
            <div className="mt-3 text-lg font-semibold text-white">{brief.riskBrief.headline}</div>
            <p className="mt-3 text-sm leading-relaxed text-gray-200">{brief.riskBrief.primaryRisk}</p>
            <div className="mt-4 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-3">
              <div className="text-xs text-rose-100">综合风险分</div>
              <div className="mt-1 text-2xl font-black text-white">{brief.riskBrief.riskScore}</div>
            </div>
          </div>
          <div className="rounded-3xl border border-gray-700/50 bg-gray-950/50 p-5">
            <div className="text-sm font-semibold text-white">应对建议</div>
            <div className="mt-3 space-y-3 text-sm leading-relaxed text-gray-200">
              <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 px-4 py-3">{brief.riskBrief.response}</div>
              <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 px-4 py-3">{brief.riskBrief.entropyCorrection}</div>
              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/8 px-4 py-3">
                <div className="text-xs text-amber-100">触发条件</div>
                <div className="mt-1 text-sm text-gray-100">{brief.riskBrief.triggerCondition}</div>
              </div>
              <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/8 px-4 py-3">
                <div className="text-xs text-cyan-100">执行边界</div>
                <div className="mt-1 text-sm text-gray-100">{brief.riskBrief.boundary}</div>
              </div>
              <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 px-4 py-3">
                <div className="text-xs text-gray-300">风险评分拆解</div>
                <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {brief.riskBrief.riskScoreBreakdown.map((item) => (
                    <div key={item.label} className="flex items-center justify-between rounded-lg border border-gray-700/50 px-2 py-1 text-xs">
                      <span className="text-gray-200">{item.label}</span>
                      <span className={item.value >= 0 ? 'text-rose-200' : 'text-emerald-200'}>
                        {item.value >= 0 ? `+${item.value}` : item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 px-4 py-3">
                <div className="text-xs text-gray-300">可追溯引用</div>
                <div className="mt-2 space-y-1 text-xs text-gray-300">
                  {brief.riskBrief.evidenceRefs.map((ref) => (
                    <div key={ref}>- {ref}</div>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 px-4 py-3">
                <div className="text-xs text-gray-300">前三风险规则</div>
                <div className="mt-2 space-y-2 text-xs text-gray-300">
                  {brief.riskBrief.topRiskRules.map((rule) => (
                    <div key={rule.type} className="rounded-lg border border-gray-700/50 px-3 py-2">
                      <div className="font-semibold text-gray-100">{rule.type}</div>
                      <div className="mt-1">触发值：{rule.triggerValue}</div>
                      <div>阈值：{rule.triggerThreshold}</div>
                      <div>应对：{rule.response}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Panel>

      <Panel title="趋势简报决策树" subtitle="主建议只给一个，避免多个结论并列打架。">
        <div className="space-y-3">
          {brief.decisionTree.map((node, index) => (
            <div key={`${index}-${node.action}`} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm font-semibold text-white">
                  {index + 1}. {node.condition}
                </div>
                <ConfidenceBadge value={node.confidence} />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
                  动作：{node.action}
                </span>
                <span className="rounded-full border border-gray-700 bg-gray-900/60 px-3 py-1 text-xs text-gray-300">
                  兜底：{node.fallback}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/8 px-3 py-2">
                  <div className="text-[11px] text-amber-100">触发值</div>
                  <div className="mt-1 text-xs text-gray-100">{node.triggerValue}</div>
                </div>
                <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/8 px-3 py-2">
                  <div className="text-[11px] text-cyan-100">阈值规则</div>
                  <div className="mt-1 text-xs text-gray-100">{node.triggerThreshold}</div>
                </div>
              </div>
              <div className="mt-2 text-xs text-gray-400">可追溯引用：{node.evidenceRef}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function renderEvidence(
  model: PointAnalysisDashboardModel,
  brief: PointDecisionBriefModel,
  selectedNetworkNumber: number | null,
  selectedTopNumber: number | null,
  onSelectNetworkNumber: (value: number | null) => void
) {
  const selectedTop = brief.top5Insights.find((item) => item.number === selectedTopNumber) ?? null;
  const selectedStructureNumbers = selectedTop?.linkedStructureNumbers ?? [];
  const filteredPairs =
    brief.evidenceDetails.cooccurrenceSupport.filter((item) => {
      const byNode =
        selectedNetworkNumber == null ||
        item.pair[0] === selectedNetworkNumber ||
        item.pair[1] === selectedNetworkNumber;
      const byTop =
        selectedTop == null ||
        selectedStructureNumbers.includes(item.pair[0]) ||
        selectedStructureNumbers.includes(item.pair[1]);
      return byNode && byTop;
    });

  const filteredZones =
    model.distribution.hotZones.filter((zone) => {
      if (zone.numbers.length === 0) return false;
      const byNode = selectedNetworkNumber == null || zone.numbers.includes(selectedNetworkNumber);
      const byTop =
        selectedTop == null || zone.numbers.some((num) => selectedStructureNumbers.includes(num));
      return byNode && byTop;
    });

  return (
    <div className="space-y-6">
      <Panel title="证据层" subtitle="默认折叠，只在需要时展开。">
        <div className="space-y-4">
          <FoldSection
            title="Markov 筛选交集"
            summary={`优先展示与 Top 5 同时成立的候选，共 ${brief.evidenceDetails.markovIntersection.length} 个。`}
          >
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {brief.evidenceDetails.markovIntersection.map((item) => (
                <div key={item.number} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <NumberPill value={item.label} tone="cyan" />
                      <div className="text-sm font-semibold text-white">支撑分 {item.supportScore}</div>
                    </div>
                  </div>
                  <div className="mt-3 text-sm text-gray-300">{item.support}</div>
                </div>
              ))}
            </div>
          </FoldSection>

          <FoldSection
            title="连号集群三元组（点位场 + 遗漏）"
            summary={`从集群、热区和遗漏压力里提取最值得看的一组三元结构，共 ${brief.evidenceDetails.tripletClusters.length} 个。`}
          >
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {brief.evidenceDetails.tripletClusters.map((item) => (
                <div key={item.label} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {item.numbers.map((number) => (
                      <NumberPill key={number} value={number} tone="emerald" />
                    ))}
                    <span className="text-sm font-semibold text-white">支撑分 {item.supportScore}</span>
                  </div>
                  <div className="mt-3 text-sm text-gray-300">{item.support}</div>
                  <div className="mt-2 text-xs text-gray-500">{item.missPressure}</div>
                </div>
              ))}
            </div>
          </FoldSection>

          <FoldSection title="对抗与熵值校正" summary="解释为什么现在是顺势、对冲、跟随还是观察。">
            <div className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4 text-sm leading-relaxed text-gray-200">
              {brief.evidenceDetails.entropyCorrection}
            </div>
          </FoldSection>

          <FoldSection
            title="共现支撑"
            summary={
              selectedNetworkNumber == null && selectedTop == null
                ? `展示最近最稳定的共现对，共 ${brief.evidenceDetails.cooccurrenceSupport.length} 组。`
                : `当前已按${selectedNetworkNumber != null ? `节点 ${selectedNetworkNumber}` : ''}${selectedNetworkNumber != null && selectedTop != null ? ' + ' : ''}${selectedTop != null ? `候选 ${selectedTop.number}` : ''}过滤，共现对剩余 ${filteredPairs.length} 组。`
            }
          >
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {filteredPairs.map((item) => (
                <div key={item.label} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
                  <div className="flex items-center gap-3">
                    <NumberPill value={item.pair[0]} tone="amber" />
                    <span className="text-gray-500">+</span>
                    <NumberPill value={item.pair[1]} tone="amber" />
                    <span className="text-sm font-semibold text-white">共现 {item.count} 次</span>
                  </div>
                  <div className="mt-3 text-sm text-gray-300">{item.support}</div>
                </div>
              ))}
            </div>
          </FoldSection>

          <FoldSection
            title="图网络结构证据"
            summary={
              selectedNetworkNumber == null && selectedTop == null
                ? `桥接节点与结构稳定性证据，共 ${brief.evidenceDetails.networkStructure.length} 条。点击节点可反向联动筛选共现对和热区。`
                : `当前结构筛选已生效${selectedNetworkNumber != null ? `：节点 ${selectedNetworkNumber}` : ''}${selectedNetworkNumber != null && selectedTop != null ? '，' : ''}${selectedTop != null ? `候选 ${selectedTop.number}` : ''}。`
            }
          >
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => onSelectNetworkNumber(null)}
                className={`rounded-full border px-3 py-1 text-xs transition ${
                  selectedNetworkNumber == null
                    ? 'border-cyan-400/40 bg-cyan-500/15 text-cyan-200'
                    : 'border-gray-700 bg-gray-900/60 text-gray-300 hover:border-gray-600'
                }`}
              >
                查看全部
              </button>
              {selectedNetworkNumber != null ? (
                <div className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs text-violet-100">
                  当前节点 {selectedNetworkNumber}
                </div>
              ) : null}
              {selectedTop != null ? (
                <div className="rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-3 py-1 text-xs text-fuchsia-100">
                  当前候选 {selectedTop.number}
                </div>
              ) : null}
            </div>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {brief.evidenceDetails.networkStructure.map((item) => (
                <button
                  type="button"
                  key={`network-${item.number}`}
                  onClick={() => onSelectNetworkNumber(selectedNetworkNumber === item.number ? null : item.number)}
                  className={`rounded-2xl border bg-gray-950/50 p-4 text-left transition ${
                    selectedNetworkNumber === item.number
                      ? 'border-cyan-400/50 shadow-[0_0_0_1px_rgba(34,211,238,0.25)]'
                      : selectedTop != null && selectedStructureNumbers.includes(item.number)
                        ? 'border-fuchsia-400/40 shadow-[0_0_0_1px_rgba(217,70,239,0.18)]'
                        : 'border-gray-700/50 hover:border-gray-500/60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <NumberPill value={item.number} tone="emerald" />
                    <div className="text-sm font-semibold text-white">{item.support}</div>
                  </div>
                  {selectedTop != null && selectedStructureNumbers.includes(item.number) ? (
                    <div className="mt-2 text-xs text-fuchsia-200">该节点被当前候选直接引用</div>
                  ) : null}
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-gray-300">
                    <div className="rounded-lg border border-gray-700/50 px-2 py-1">桥接 {item.bridgeScore.toFixed(2)}</div>
                    <div className="rounded-lg border border-gray-700/50 px-2 py-1">社团密度 {item.communityDensity.toFixed(2)}</div>
                    <div className="rounded-lg border border-gray-700/50 px-2 py-1">稳定 {item.structuralStability.toFixed(2)}</div>
                  </div>
                </button>
              ))}
            </div>
          </FoldSection>

          <FoldSection
            title="热区反向筛选"
            summary={
              selectedNetworkNumber == null && selectedTop == null
                ? `展示当前有结构信号的热区，共 ${filteredZones.length} 个。`
                : `当前已按${selectedNetworkNumber != null ? `节点 ${selectedNetworkNumber}` : ''}${selectedNetworkNumber != null && selectedTop != null ? ' + ' : ''}${selectedTop != null ? `候选 ${selectedTop.number}` : ''}反查热区，共命中 ${filteredZones.length} 个区域。`
            }
          >
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {filteredZones.map((zone) => (
                <div key={zone.zone} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-white">{zone.zone}</div>
                    <div className="text-xs text-gray-400">能量 {zone.energy}</div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {zone.numbers.map((num) => (
                      <NumberPill
                        key={`${zone.zone}-${num}`}
                        value={num}
                        tone={
                          selectedNetworkNumber === num
                            ? 'emerald'
                            : selectedTop != null && selectedStructureNumbers.includes(num)
                              ? 'amber'
                              : 'cyan'
                        }
                      />
                    ))}
                  </div>
                </div>
              ))}
              {filteredZones.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-gray-700/60 bg-gray-950/30 p-4 text-sm text-gray-400">
                  当前节点没有落入已识别热区，说明它更像跨区桥接点而不是热区核心。
                </div>
              ) : null}
            </div>
          </FoldSection>

          <FoldSection title="序列频谱证据" summary="主频峰、相位漂移与不稳定度共同决定当前序列状态。">
            <div className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
                  状态：{brief.evidenceDetails.sequenceSpectrum.stateLabel}
                </span>
                <span className="rounded-full border border-gray-700 bg-gray-900/60 px-3 py-1 text-xs text-gray-300">
                  主频峰：{brief.evidenceDetails.sequenceSpectrum.spectralPeak}
                </span>
                <span className="rounded-full border border-gray-700 bg-gray-900/60 px-3 py-1 text-xs text-gray-300">
                  相位漂移：{brief.evidenceDetails.sequenceSpectrum.phaseDrift}
                </span>
                <span className="rounded-full border border-gray-700 bg-gray-900/60 px-3 py-1 text-xs text-gray-300">
                  趋势：{brief.evidenceDetails.sequenceSpectrum.instabilityTrend}
                </span>
                <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-100">
                  状态切换：{brief.evidenceDetails.sequenceSpectrum.regimeShiftScore}
                </span>
                <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-3 py-1 text-xs text-rose-100">
                  不稳定度：{brief.evidenceDetails.sequenceSpectrum.sequenceInstability}
                </span>
              </div>
              <div className="mt-3 text-sm text-gray-300">{brief.evidenceDetails.sequenceSpectrum.thresholdHint}</div>
            </div>
          </FoldSection>
        </div>
      </Panel>
    </div>
  );
}

function renderReview(model: PointAnalysisDashboardModel, brief: PointDecisionBriefModel) {
  const replayRows = brief.recommendationReview.rows;
  return (
    <div className="space-y-6">
      <Panel title="推荐复盘总览" subtitle="先看推荐是否真命中，再看底层点位覆盖与规则证据。">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Top 5 平均命中" value={brief.reviewStats.recommendedTop5AvgHit.toFixed(1)} />
          <MetricCard label="核心 5 平均命中" value={brief.reviewStats.recommendedCore5AvgHit.toFixed(1)} />
          <MetricCard label="Top 5 命中期占比" value={formatPercent(brief.reviewStats.recommendedTop5HitRate)} />
          <MetricCard label="核心 5 命中期占比" value={formatPercent(brief.reviewStats.recommendedCore5HitRate)} />
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="最佳复盘期" value={brief.reviewStats.bestReplayPeriod} />
          <MetricCard label="最弱复盘期" value={brief.reviewStats.worstReplayPeriod} />
          <MetricCard label="近期最强规则" value={brief.reviewStats.bestRule} />
          <MetricCard label="近期最弱规则" value={brief.reviewStats.weakestRule} />
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="增强30期增益" value={formatPercent(brief.reviewStats.enhancedLift30)} />
          <MetricCard label="增强60期增益" value={formatPercent(brief.reviewStats.enhancedLift60)} />
          <MetricCard label="增强120期增益" value={formatPercent(brief.reviewStats.enhancedLift120)} />
          <MetricCard
            label="增强门槛"
            value={brief.reviewStats.enhancedPassed ? '已通过' : '未通过'}
            detail={`稳定性变化 ${brief.reviewStats.stabilityDelta}，失效间隔变化 ${brief.reviewStats.failureGapDelta}`}
          />
        </div>
      </Panel>

      <Panel title="最近 10 期推荐明细" subtitle="每期都展示推荐号、实际号、命中详情和失手原因。">
        <div className="space-y-3">
          {replayRows.map((row) => (
            <div key={`${row.date}-${row.period}`} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm font-semibold text-white">{row.label}</div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
                    动作：{row.decisionAction}
                  </span>
                  <ConfidenceBadge value={row.decisionConfidence} />
                  <span className="rounded-full border border-gray-700 bg-gray-900/60 px-3 py-1 text-xs text-gray-300">
                    Top 5 命中 {row.top5HitCount}
                  </span>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
                <div className="rounded-2xl border border-gray-700/50 bg-gray-900/50 p-3">
                  <div className="text-xs text-gray-400">当期推荐</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.recommendedTop5.map((value) => (
                      <NumberPill key={`${row.label}-top5-${value}`} value={value} tone={row.top5Hits.includes(value) ? 'emerald' : 'cyan'} />
                    ))}
                  </div>
                  <div className="mt-3 text-xs text-gray-500">核心 5：{row.recommendedCore5.join('、')}</div>
                  <div className="mt-1 text-xs text-gray-500">备选 2：{row.recommendedBackup2.join('、')}</div>
                </div>
                <div className="rounded-2xl border border-gray-700/50 bg-gray-900/50 p-3">
                  <div className="text-xs text-gray-400">当期实际开奖号</div>
                  {row.dataReady ? (
                    <>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {row.actualNumbers.map((value) => (
                          <NumberPill key={`${row.label}-actual-${value}`} value={value} tone={row.top5Hits.includes(value) ? 'emerald' : 'amber'} />
                        ))}
                      </div>
                      <div className="mt-3 text-xs leading-relaxed text-gray-300">
                        命中详情：Top 5 命中 {row.top5Hits.length ? row.top5Hits.join('、') : '无'}；核心 5 命中 {row.core5Hits.length ? row.core5Hits.join('、') : '无'}；备选 2 命中 {row.backup2Hits.length ? row.backup2Hits.join('、') : '无'}。
                      </div>
                    </>
                  ) : (
                    <div className="mt-3 rounded-xl border border-dashed border-amber-500/30 bg-amber-500/10 px-3 py-3 text-sm text-amber-100">
                      {row.missingReason}
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
                <div className="rounded-2xl border border-gray-700/50 bg-gray-900/50 p-3">
                  <div className="text-xs text-gray-400">推荐依据</div>
                  <div className="mt-2 space-y-1 text-xs text-gray-200">
                    {row.consensusHighlights.map((item) => (
                      <div key={`${row.label}-${item}`}>- {item}</div>
                    ))}
                  </div>
                </div>
                <div className="rounded-2xl border border-gray-700/50 bg-gray-900/50 p-3">
                  <div className="text-xs text-gray-400">命中原因</div>
                  <div className="mt-2 text-xs leading-relaxed text-gray-200">{row.whyHit || '本期未出现 Top 5 命中。'}</div>
                </div>
                <div className="rounded-2xl border border-gray-700/50 bg-gray-900/50 p-3">
                  <div className="text-xs text-gray-400">失手原因 / 风险背景</div>
                  <div className="mt-2 text-xs leading-relaxed text-gray-200">{row.whyMiss}</div>
                  <div className="mt-2 text-xs text-rose-200">风险背景：{row.riskContext}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="动作复盘" subtitle="把顺势、对冲、跟随、观察拆开，看哪种动作最近更稳。">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {brief.reviewStats.actionWinRate.map((item) => (
            <div key={item.action} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
              <div className="text-sm font-semibold text-white">{item.action}</div>
              <div className="mt-3 text-xs text-gray-400">出现期数</div>
              <div className="mt-1 text-lg font-bold text-white">{item.periods}</div>
              <div className="mt-3 text-xs text-gray-400">命中期占比</div>
              <div className="mt-1 text-lg font-bold text-cyan-200">{formatPercent(item.hitRate)}</div>
              <div className="mt-3 text-xs text-gray-400">Top 5 平均命中</div>
              <div className="mt-1 text-lg font-bold text-emerald-200">{item.averageTop5Hits.toFixed(1)}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="点位覆盖复盘" subtitle="保留底层点位覆盖走势，作为推荐结果的背景证据。">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="最近覆盖均值" value={formatPercent(brief.reviewStats.recentCoverage)} detail={brief.reviewStats.recentTrend} />
          <MetricCard label="最新覆盖命中" value={`${brief.reviewStats.latestHitCount}`} />
          <MetricCard label="30期规则均值" value={formatPercent(brief.reviewStats.average30Window)} />
          <MetricCard label="60期规则均值" value={formatPercent(brief.reviewStats.average60Window)} />
        </div>
        <div className="mt-4 space-y-3">
          {brief.coverageReview.snapshots.slice(0, 10).map((snapshot) => (
            <div key={`${snapshot.date}-${snapshot.period}`} className="rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm font-semibold text-white">{snapshot.label}</div>
                <span className="rounded-full border border-gray-700 bg-gray-900/60 px-3 py-1 text-xs text-gray-300">
                  {snapshot.state} · 命中 {snapshot.hitCount}
                </span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-gray-800/80">
                <div className="h-2 rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400" style={{ width: `${Math.max(8, snapshot.coverageRatio * 100)}%` }} />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {snapshot.coreHits.slice(0, 8).map((hit) => (
                  <NumberPill key={`${snapshot.label}-${hit}`} value={hit} tone="cyan" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="概率校准" subtitle="把原始分数映射成更可验证的命中率，避免只看裸分。">
        <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <MetricCard label="校准可靠性" value={brief.reviewSummary.calibrationReliability} />
          <MetricCard label="120期规则均值" value={formatPercent(brief.reviewStats.average120Window)} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400">
                <th className="px-3 py-2 text-left">分箱</th>
                <th className="px-3 py-2 text-center">样本</th>
                <th className="px-3 py-2 text-center">真实命中率</th>
                <th className="px-3 py-2 text-center">预测命中率</th>
                <th className="px-3 py-2 text-center">可信度</th>
                <th className="px-3 py-2 text-center">可靠性</th>
              </tr>
            </thead>
            <tbody>
              {model.decision.calibration.bins.map((bin) => (
                <tr key={bin.scoreRange} className="border-b border-gray-800">
                  <td className="px-3 py-3 text-cyan-300">{bin.scoreRange}</td>
                  <td className="px-3 py-3 text-center">{bin.sampleSize}</td>
                  <td className="px-3 py-3 text-center">{Math.round(bin.observedHitRate * 100)}%</td>
                  <td className="px-3 py-3 text-center">{Math.round(bin.predictedHitRate * 100)}%</td>
                  <td className="px-3 py-3 text-center">{bin.calibratedConfidence}</td>
                  <td className="px-3 py-3 text-center">{bin.reliable ? '可靠' : '低样本'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="数据健康" subtitle="最后再确认开奖、点位和专家数据是否对齐，避免把缺数据误判成未命中。">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <MetricCard label="点位最新日期" value={model.overview.dataHealth.pointsLatestDate || '未知'} />
          <MetricCard label="历史最新日期" value={model.overview.dataHealth.historyLatestDate || '未知'} />
          <MetricCard label="专家最新日期" value={model.overview.dataHealth.expertLatestDate || '未知'} />
        </div>
        <div className="mt-4 rounded-2xl border border-gray-700/50 bg-gray-950/50 p-4 text-sm leading-relaxed text-gray-300">
          {brief.reviewSummary.dataHealth}
        </div>
      </Panel>
    </div>
  );
}

export function PointDecisionBriefScreen({
  model,
  brief,
  activeSection,
}: {
  model: PointAnalysisDashboardModel;
  brief: PointDecisionBriefModel;
  activeSection: ReportSectionKey;
}) {
  const section = brief.sections.find((item) => item.key === activeSection) ?? brief.sections[0];
  const [selectedNetworkNumber, setSelectedNetworkNumber] = useState<number | null>(null);
  const [selectedTopNumber, setSelectedTopNumber] = useState<number | null>(null);
  const selectedTop = brief.top5Insights.find((item) => item.number === selectedTopNumber) ?? null;
  const hasActiveFilter = selectedNetworkNumber != null || selectedTopNumber != null;

  const clearAllSelections = () => {
    setSelectedNetworkNumber(null);
    setSelectedTopNumber(null);
  };

  return (
    <div className="space-y-6">
      <Panel title={`${section.icon} ${section.label}`} subtitle={section.description}>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <div className="rounded-3xl border border-gray-700/50 bg-gray-950/50 p-5">
            <div className="text-xs uppercase tracking-[0.25em] text-gray-500">分析方式</div>
            <div className="mt-3 text-sm leading-relaxed text-gray-200">
              首屏先看结论、Top 5、宏观趋势和风险应对，深度证据默认折叠，复盘信息放到最后。
            </div>
          </div>
          <div className="rounded-3xl border border-cyan-500/15 bg-cyan-500/5 p-5">
            <div className="text-xs uppercase tracking-[0.25em] text-cyan-200">当前主动作</div>
            <div className="mt-3 text-2xl font-black text-white">{brief.executiveSummary.recommendedAction}</div>
            <div className="mt-2 text-sm text-gray-300">{brief.executiveSummary.verdict}</div>
          </div>
        </div>
      </Panel>

      <Panel
        title="当前联动筛选"
        subtitle="这里会汇总当前页面已锁定的候选与结构节点，避免看久了不知道页面为什么被过滤。"
      >
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`rounded-full border px-3 py-1 text-xs ${
              hasActiveFilter
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                : 'border-gray-700 bg-gray-900/60 text-gray-300'
            }`}
          >
            {hasActiveFilter ? '联动筛选已生效' : '当前未启用联动筛选'}
          </span>
          {selectedNetworkNumber != null ? (
            <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
              结构节点：{selectedNetworkNumber}
            </span>
          ) : null}
          {selectedTop != null ? (
            <span className="rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-3 py-1 text-xs text-fuchsia-100">
              候选号码：{selectedTop.number}
            </span>
          ) : null}
          <button
            type="button"
            onClick={clearAllSelections}
            disabled={!hasActiveFilter}
            className={`rounded-full border px-4 py-2 text-xs font-semibold transition ${
              hasActiveFilter
                ? 'border-gray-600 bg-gray-900/70 text-gray-100 hover:border-gray-500'
                : 'cursor-not-allowed border-gray-800 bg-gray-900/40 text-gray-500'
            }`}
          >
            一键清空全部联动
          </button>
        </div>
        <div className="mt-4 text-sm leading-relaxed text-gray-300">
          {hasActiveFilter
            ? `当前页面会同时按${selectedNetworkNumber != null ? `结构节点 ${selectedNetworkNumber}` : ''}${
                selectedNetworkNumber != null && selectedTop != null ? ' 和 ' : ''
              }${selectedTop != null ? `候选 ${selectedTop.number}` : ''}进行联动筛选。`
            : '当前页面展示的是完整视图。你可以点击 Top 5 候选，或者点击结构节点卡片，页面会自动反向高亮相关证据。'}
        </div>
      </Panel>

      {activeSection === 'overview'
        ? renderOverview(model, brief, selectedNetworkNumber, selectedTopNumber, setSelectedTopNumber)
        : null}
      {activeSection === 'evidence'
        ? renderEvidence(
            model,
            brief,
            selectedNetworkNumber,
            selectedTopNumber,
            setSelectedNetworkNumber
          )
        : null}
      {activeSection === 'review' ? renderReview(model, brief) : null}
    </div>
  );
}
