import { useMemo, type ReactNode } from 'react';
import type { ExpertDashboardData, ExpertTabKey, FollowerHistoryItem, TrackingAuditRow } from '../data/dataLoader';

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="bg-gray-800/50 backdrop-blur-sm rounded-2xl border border-gray-700/50 p-6">
      <h2 className="text-xl font-bold text-white mb-4">{title}</h2>
      {children}
    </section>
  );
}

function Pill({ children, hit, muted }: { children: ReactNode; hit?: boolean; muted?: boolean }) {
  const cls = hit
    ? 'bg-yellow-300 text-gray-900 border-yellow-100 shadow-md shadow-yellow-500/20'
    : muted
      ? 'bg-gray-800/70 text-gray-500 border-gray-700'
      : 'bg-cyan-500/10 text-cyan-200 border-cyan-500/30';
  return <span className={`inline-flex min-w-9 justify-center px-2 py-1 rounded-full border text-xs font-bold ${cls}`}>{children}</span>;
}

function MatrixCard({
  title,
  rows,
  actualSet,
}: {
  title: string;
  rows: string[][];
  actualSet: Set<string>;
}) {
  return (
    <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
      <div className="text-sm font-semibold text-white mb-3">{title}</div>
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div key={`${title}-${index}`} className="grid grid-cols-[repeat(4,minmax(0,1fr))_20px_repeat(4,minmax(0,1fr))] gap-2 items-center">
            {row.slice(0, 4).map((value, col) => (
              <div key={`${title}-${index}-l-${col}`} className="flex justify-center">
                {value ? <Pill hit={actualSet.has(value)}>{value}</Pill> : <span className="h-8 w-8 rounded-full border border-dashed border-gray-700/70" />}
              </div>
            ))}
            <div className="text-center text-gray-600">|</div>
            {row.slice(4).map((value, col) => (
              <div key={`${title}-${index}-r-${col}`} className="flex justify-center">
                {value ? <Pill hit={actualSet.has(value)}>{value}</Pill> : <span className="h-8 w-8 rounded-full border border-dashed border-gray-700/70" />}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function fallbackRows(history: FollowerHistoryItem[]): TrackingAuditRow[] {
  return history.map(row => {
    const actualNumbers = row.actual.map(item => item.padStart(2, '0'));
    const actualSet = new Set(actualNumbers);
    const gold2 = row.gold2.map(item => item.padStart(2, '0'));
    const gold7 = row.gold7.map(item => item.padStart(2, '0'));
    const top12 = row.top12.map(item => item.padStart(2, '0'));
    return {
      date: row.date,
      displayDate: `${row.date.slice(0, 4)}-${row.date.slice(4, 6)}-${row.date.slice(6, 8)}`,
      gold2,
      gold7,
      top12,
      actualNumbers,
      actualPeriod: '',
      isPending: row.isPending,
      missingActualData: row.isPending,
      pendingReason: row.isPending ? '历史开奖文件尚未同步到该日期。' : '',
      gold2Hits: gold2.filter(item => actualSet.has(item)),
      gold7Hits: gold7.filter(item => actualSet.has(item)),
      top12Hits: top12.filter(item => actualSet.has(item)),
      gold2HitCount: gold2.filter(item => actualSet.has(item)).length,
      gold7HitCount: gold7.filter(item => actualSet.has(item)).length,
      top12HitCount: top12.filter(item => actualSet.has(item)).length,
      verdict: row.isPending ? '开奖数据缺失' : '',
      missReason: row.isPending ? '历史开奖文件尚未同步到该日期。' : '',
      uncertainty: row.isPending ? '高' : '中',
      confidence: row.isPending ? '低' : '中',
      riskScore: row.isPending ? 9.5 : undefined,
      triggerThreshold: {
        gold2Hit: 1,
        gold7Hit: 2,
        top12Hit: 3,
        strongTop12Hit: 6,
      },
      evidenceRefs: [
        `黄金选2 命中 ${gold2.filter(item => actualSet.has(item)).length}/2`,
        `精选选7 命中 ${gold7.filter(item => actualSet.has(item)).length}/7`,
        `全域Top12 命中 ${top12.filter(item => actualSet.has(item)).length}/12`,
      ],
    };
  });
}

function buildDailySummary(view: ExpertDashboardData['dailyMatrixViews'][number]) {
  const allMatrices = view.sourceGroups.flatMap(group => group.matrices.map(matrix => ({ ...matrix, source: group.title })));
  const totalNumbers = allMatrices.reduce((sum, matrix) => sum + matrix.rows.flat().filter(Boolean).length, 0);
  const totalHits = allMatrices.reduce((sum, matrix) => sum + matrix.hitNumbers.length, 0);
  const topMatrix = allMatrices
    .slice()
    .sort((a, b) => b.hitNumbers.length - a.hitNumbers.length)[0];
  const hitRate = totalNumbers > 0 ? Math.round((totalHits / totalNumbers) * 100) : 0;

  return {
    totalHits,
    hitRate,
    topMatrix: topMatrix ? `${topMatrix.source}·${topMatrix.title}` : '暂无',
  };
}

function buildTrackingReason(row: TrackingAuditRow) {
  if (row.verdict || row.missReason || row.evidenceRefs?.length) {
    return {
      verdict: row.verdict || '待复核',
      missReason: row.missReason || row.pendingReason || '请结合证据区进一步复核。',
      uncertainty: row.uncertainty || '中',
      confidence: row.confidence || (row.isPending ? '低' : '中'),
      riskScore: row.riskScore,
      triggerThreshold: row.triggerThreshold,
      evidenceRefs: row.evidenceRefs || [],
    };
  }

  if (row.isPending) {
    return {
      verdict: '待开奖',
      missReason: row.pendingReason || '该日期的开奖数据尚未同步。',
      uncertainty: '高',
      confidence: '低',
      riskScore: 9.5,
      triggerThreshold: {
        gold2Hit: 1,
        gold7Hit: 2,
        top12Hit: 3,
      },
      evidenceRefs: [],
    };
  }

  if (row.top12HitCount >= 6 || row.gold7HitCount >= 4) {
    return {
      verdict: '表现强',
      missReason: `命中集中在核心组合，Top12 命中 ${row.top12HitCount} 个，精选7命中 ${row.gold7HitCount} 个。`,
      uncertainty: '低',
      confidence: '高',
      riskScore: 2.5,
      triggerThreshold: {
        gold2Hit: 1,
        gold7Hit: 2,
        top12Hit: 3,
      },
      evidenceRefs: [],
    };
  }

  if (row.top12HitCount >= 3 || row.gold7HitCount >= 2 || row.gold2HitCount >= 1) {
    return {
      verdict: '表现中',
      missReason: `有一定命中支撑，但集中度一般，Top12 命中 ${row.top12HitCount} 个。`,
      uncertainty: '中',
      confidence: '中',
      riskScore: 5.2,
      triggerThreshold: {
        gold2Hit: 1,
        gold7Hit: 2,
        top12Hit: 3,
      },
      evidenceRefs: [],
    };
  }

  const nearMissCount = row.top12.filter(num => !row.top12Hits.includes(num)).slice(0, 4).length;
  return {
    verdict: '需观察',
    missReason: `本期核心组合未形成有效命中，建议回看候选分散度与遗漏压力（近失配候选 ${nearMissCount} 个）。`,
    uncertainty: '中',
    confidence: '中',
    riskScore: 7.8,
    triggerThreshold: {
      gold2Hit: 1,
      gold7Hit: 2,
      top12Hit: 3,
    },
    evidenceRefs: [],
  };
}

export function ExpertDashboardScreen({
  dashboard,
  loading,
  error,
  activeTab,
  onTabChange,
  fallbackHistory,
}: {
  dashboard: ExpertDashboardData | null;
  loading: boolean;
  error: string | null;
  activeTab: ExpertTabKey;
  onTabChange: (tab: ExpertTabKey) => void;
  fallbackHistory: FollowerHistoryItem[];
}) {
  const tabs = dashboard?.overviewTabs ?? [
    { key: 'daily' as ExpertTabKey, label: '每日矩阵总览' },
    { key: 'insight' as ExpertTabKey, label: '重点结论与规律' },
    { key: 'global' as ExpertTabKey, label: '全域分析结论' },
    { key: 'energy' as ExpertTabKey, label: '重号与热点观察' },
    { key: 'tracking' as ExpertTabKey, label: '历史命中复盘' },
  ];
  const trackingRows = useMemo(
    () => (dashboard?.trackingDetails?.length ? dashboard.trackingDetails : fallbackRows(fallbackHistory)),
    [dashboard, fallbackHistory]
  );

  return (
    <div id="expert-all" className="space-y-6">
      <Panel title="专家关注号分析">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm text-gray-300">按每日真实矩阵、重点结论和历史命中详情展示，不再使用技术化命名。</p>
            <p className="text-xs text-gray-500 mt-2">
              最新矩阵日期：{dashboard?.meta.latestDate || '未知'} · 历史开奖最新日期：{dashboard?.meta.historyLatestDate || '未知'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {tabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => onTabChange(tab.key)}
                className={`px-4 py-2 rounded-xl border text-sm transition-all ${
                  activeTab === tab.key
                    ? 'bg-purple-500/20 text-purple-200 border-purple-400/50'
                    : 'bg-gray-800/70 text-gray-400 border-gray-700 hover:text-gray-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        {dashboard?.meta.dataHealth && (
          <div className={`mt-4 rounded-xl border p-4 text-sm ${dashboard.meta.dataHealth.isMisaligned ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-200' : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'}`}>
            数据健康：{dashboard.meta.dataHealth.message}
          </div>
        )}
      </Panel>

      {loading && <Panel title="加载中">正在读取专家看板数据...</Panel>}
      {!loading && error && !dashboard && <Panel title="专家看板不可用">{error}</Panel>}
      {!loading && dashboard && (
        <>
          {activeTab === 'daily' && <DailyTab dashboard={dashboard} />}
          {activeTab === 'insight' && <InsightTab dashboard={dashboard} />}
          {activeTab === 'global' && <GlobalTab dashboard={dashboard} />}
          {activeTab === 'energy' && <EnergyTab dashboard={dashboard} />}
          {activeTab === 'tracking' && <TrackingTab rows={trackingRows} />}
        </>
      )}
    </div>
  );
}

function DailyTab({ dashboard }: { dashboard: ExpertDashboardData }) {
  return (
    <div className="space-y-6">
      {dashboard.dailyMatrixViews.map(view => {
        const actualSet = new Set(view.actualNumbers);
        const summary = buildDailySummary(view);
        const brief = view.dailyBrief;
        return (
          <Panel key={view.date} title={`${view.displayDate} 每日矩阵总览`}>
            <div className="mb-5">
              <div className="text-sm text-gray-400">开奖号码</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {view.actualNumbers.length > 0 ? view.actualNumbers.map(value => <Pill key={`${view.date}-${value}`} hit>{value}</Pill>) : <span className="text-sm text-yellow-300">开奖数据缺失，请先同步历史开奖。</span>}
              </div>
            </div>
            {brief && (
              <div className="mb-5 rounded-2xl border border-purple-500/20 bg-purple-500/8 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-purple-100">当日结论</span>
                  <span className="rounded-full border border-purple-400/40 bg-purple-500/10 px-2 py-0.5 text-xs text-purple-200">{brief.verdict}</span>
                  <span className="rounded-full border border-gray-600 bg-gray-800/70 px-2 py-0.5 text-xs text-gray-200">不确定性 {brief.uncertainty}</span>
                  {typeof brief.score === 'number' && (
                    <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-200">命中率分 {brief.score}</span>
                  )}
                </div>
                <div className="mt-2 text-sm text-gray-100">{brief.summary}</div>
                {!!brief.focusNumbers?.length && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {brief.focusNumbers.map(item => (
                      <Pill key={`${view.date}-focus-${item}`}>{item}</Pill>
                    ))}
                  </div>
                )}
                <div className="mt-3 text-xs text-gray-300 space-y-1">
                  {brief.evidenceRefs?.map(ref => (
                    <div key={`${view.date}-${ref}`}>证据：{ref}</div>
                  ))}
                </div>
                {brief.triggerThreshold && (
                  <div className="mt-2 text-xs text-gray-400">
                    阈值：命中率≥{brief.triggerThreshold.primaryHitRate ?? '-'}%，强信号≥{brief.triggerThreshold.strongHitRate ?? '-'}%，最小样本 {brief.triggerThreshold.minimumSamples ?? '-'}
                  </div>
                )}
              </div>
            )}
            <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/8 p-3">
                <div className="text-xs text-emerald-100">当日命中总数</div>
                <div className="mt-1 text-lg font-bold text-white">{summary.totalHits}</div>
              </div>
              <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/8 p-3">
                <div className="text-xs text-cyan-100">矩阵命中率</div>
                <div className="mt-1 text-lg font-bold text-white">{summary.hitRate}%</div>
              </div>
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/8 p-3">
                <div className="text-xs text-amber-100">重点矩阵</div>
                <div className="mt-1 text-sm font-semibold text-white">{summary.topMatrix}</div>
              </div>
            </div>
            <div className="space-y-6">
              {view.sourceGroups.map(group => (
                <div key={`${view.date}-${group.key}`}>
                  <div className="text-lg font-semibold text-white mb-3">{group.title}</div>
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    {group.matrices.map(matrix => (
                      <MatrixCard key={`${group.key}-${matrix.title}`} title={matrix.title} rows={matrix.rows} actualSet={actualSet} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

function InsightTab({ dashboard }: { dashboard: ExpertDashboardData }) {
  const insight = dashboard.insightSummary;
  return (
    <div className="space-y-6">
      <Panel title={insight.title}>
        <p className="text-sm text-gray-300">{insight.overview}</p>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-5">
          <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
            <div className="text-sm font-semibold text-white mb-3">今日重点号码</div>
            <div className="flex flex-wrap gap-2">
              {insight.focusNumbers.map(item => <Pill key={item.number}>{item.number}</Pill>)}
            </div>
          </div>
          <div className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
            <div className="text-sm font-semibold text-white mb-3">今日重点矩阵</div>
            <div className="space-y-2 text-sm text-gray-300">
              {insight.focusMatrices.map(item => <div key={`${item.sourceTitle}-${item.matrixTitle}`}>{item.sourceTitle} · {item.matrixTitle}</div>)}
            </div>
          </div>
          <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-4">
            <div className="text-sm font-semibold text-red-200 mb-3">操作提醒</div>
            <p className="text-sm text-gray-300 leading-relaxed">{insight.riskReminder}</p>
          </div>
        </div>
      </Panel>
      <Panel title="分析结论">
        <div className="space-y-3">
          {insight.keyFindings.map((item, index) => (
            <div key={`${index}-${item.slice(0, 8)}`} className="rounded-xl border border-cyan-500/10 bg-cyan-500/5 p-4 text-sm text-gray-300">
              {item}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function GlobalTab({ dashboard }: { dashboard: ExpertDashboardData }) {
  const section = dashboard.globalHighlights;
  return (
    <div className="space-y-6">
      <Panel title={section.title}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {section.highlightCards.map(card => (
            <div key={card.title} className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-4">
              <div className="text-sm font-semibold text-white">{card.title}</div>
              <p className="text-sm text-gray-300 mt-3">{card.summary}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {card.lastHits.map(hit => <Pill key={`${card.title}-${hit}`} hit>{hit}</Pill>)}
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="为什么先看这些矩阵">
        <div className="space-y-3 text-sm text-gray-300">
          {section.reasons.map((item, index) => <div key={`${index}-${item.slice(0, 8)}`}>{item}</div>)}
        </div>
      </Panel>
      {!!section.persistenceRows?.length && (
        <Panel title="矩阵长期可信度">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {section.persistenceRows.map(row => (
              <div key={row.name} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
                <div className="text-sm font-semibold text-white">{row.name}</div>
                <div className="text-xs text-gray-400 mt-2">覆盖 {row.days} 天 · 累计命中 {row.totalHits}</div>
                <div className="text-2xl font-bold text-cyan-300 mt-3">{row.persistenceScore}</div>
                <div className="text-xs text-gray-500 mt-1">持久性得分</div>
              </div>
            ))}
          </div>
        </Panel>
      )}
      <Panel title="证据区">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400">
                <th className="text-left px-3 py-2">矩阵</th>
                <th className="text-center px-3 py-2">覆盖天数</th>
                <th className="text-center px-3 py-2">累计命中</th>
                <th className="text-center px-3 py-2">号码数量</th>
              </tr>
            </thead>
            <tbody>
              {section.evidenceRows.map(row => (
                <tr key={row.name} className="border-b border-gray-800">
                  <td className="px-3 py-3 text-cyan-300 font-semibold">{row.name}</td>
                  <td className="px-3 py-3 text-center">{row.days}</td>
                  <td className="px-3 py-3 text-center">{row.totalHits}</td>
                  <td className="px-3 py-3 text-center">{row.fillCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function EnergyTab({ dashboard }: { dashboard: ExpertDashboardData }) {
  const section = dashboard.energyHighlights;
  return (
    <div className="space-y-6">
      <Panel title={section.title}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <div className="text-sm font-semibold text-white mb-3">最值得先盯的重号</div>
            <div className="flex flex-wrap gap-2">
              {section.focusRepeats.map(item => <Pill key={item.number}>{item.number}</Pill>)}
            </div>
          </div>
          <div>
            <div className="text-sm font-semibold text-white mb-3">热点矩阵</div>
            <div className="space-y-2 text-sm text-gray-300">
              {section.hotMatrices.map(item => <div key={item.name}>{item.name} · 命中 {item.hitCount} · 重复 {item.repeatedCount}</div>)}
            </div>
          </div>
        </div>
      </Panel>
      <Panel title="判断依据">
        <div className="space-y-3 text-sm text-gray-300">
          {section.observations.map((item, index) => <div key={`${index}-${item.slice(0, 8)}`}>{item}</div>)}
        </div>
      </Panel>
      {!!section.crossSourceConsensus?.length && (
        <Panel title="跨源共识号码">
          <div className="flex flex-wrap gap-2">
            {section.crossSourceConsensus.map(item => (
              <div key={item.number} className="rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-sm text-purple-200">
                {item.number} · 重复 {item.count}
              </div>
            ))}
          </div>
        </Panel>
      )}
      {!!section.cellHeatMap?.length && (
        <Panel title="矩阵坑位热度">
          <div className="space-y-3">
            {section.cellHeatMap.map(cell => (
              <div key={cell.cell} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4 flex items-center justify-between gap-4">
                <div className="text-sm text-white">{cell.cell}</div>
                <div className="flex items-center gap-3 min-w-[180px]">
                  <div className="flex-1 h-2 rounded-full bg-gray-700/50 overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-cyan-500 to-blue-500" style={{ width: `${Math.round(cell.hitRate * 100)}%` }} />
                  </div>
                  <div className="text-xs text-gray-300">{Math.round(cell.hitRate * 100)}%</div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
      <Panel title="证据区">
        <div className="space-y-3">
          {section.evidenceRows.map(row => (
            <div key={row.name} className="rounded-xl border border-gray-700/50 bg-gray-900/60 p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="font-semibold text-white">{row.name}</div>
                <div className="text-xs text-gray-400">命中 {row.hitCount} · 重复 {row.repeatedCount}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                {row.numbers.map(value => <Pill key={`${row.name}-${value}`}>{value}</Pill>)}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function TrackingTab({ rows }: { rows: TrackingAuditRow[] }) {
  return (
    <div className="space-y-6">
      <Panel title="历史命中复盘">
        <div className="space-y-4">
          {rows.map(row => (
            <div key={row.date} className="rounded-2xl border border-gray-700/50 bg-gray-900/60 p-5">
              {(() => {
                const summary = buildTrackingReason(row);
                return (
                  <>
                    <div className="mb-3 rounded-xl border border-purple-500/20 bg-purple-500/8 p-3">
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <span className="text-xs text-purple-100">复盘结论</span>
                        <span className="rounded-full border border-purple-400/40 bg-purple-500/10 px-2 py-0.5 text-xs text-purple-200">{summary.verdict}</span>
                        <span className="rounded-full border border-gray-600 bg-gray-800/70 px-2 py-0.5 text-xs text-gray-200">不确定性 {summary.uncertainty}</span>
                        <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-200">可信度 {summary.confidence}</span>
                        {typeof summary.riskScore === 'number' && (
                          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-200">风险分 {summary.riskScore}</span>
                        )}
                      </div>
                      <div className="mt-2 text-sm text-gray-200">{summary.missReason}</div>
                      {!!summary.evidenceRefs?.length && (
                        <div className="mt-2 space-y-1 text-xs text-gray-300">
                          {summary.evidenceRefs.map(ref => (
                            <div key={`${row.date}-${ref}`}>证据：{ref}</div>
                          ))}
                        </div>
                      )}
                      {summary.triggerThreshold && (
                        <div className="mt-2 text-xs text-gray-400">
                          阈值：黄金选2≥{summary.triggerThreshold.gold2Hit ?? '-'}，精选选7≥{summary.triggerThreshold.gold7Hit ?? '-'}，Top12≥{summary.triggerThreshold.top12Hit ?? '-'}（强信号 Top12≥{summary.triggerThreshold.strongTop12Hit ?? '-'}）
                        </div>
                      )}
                    </div>
                  </>
                );
              })()}
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between mb-4">
                <div>
                  <div className="text-lg font-semibold text-cyan-300">{row.displayDate}</div>
                  <div className="text-xs text-gray-500">{row.actualPeriod ? `期号 ${row.actualPeriod}` : '未同步期号'}</div>
                </div>
                <div className="text-sm text-yellow-300">{row.isPending ? row.pendingReason : `开奖号码：${row.actualNumbers.join('、')}`}</div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="rounded-xl border border-gray-700/50 bg-gray-950/50 p-4">
                  <div className="text-sm font-semibold text-white mb-3">黄金选2</div>
                  <div className="flex flex-wrap gap-2 mb-3">{row.gold2.map(value => <Pill key={`${row.date}-g2-${value}`} hit={row.gold2Hits.includes(value)}>{value}</Pill>)}</div>
                  <div className="text-xs text-gray-400">命中：{row.gold2Hits.join('、') || '无'}</div>
                </div>
                <div className="rounded-xl border border-gray-700/50 bg-gray-950/50 p-4">
                  <div className="text-sm font-semibold text-white mb-3">精选选7</div>
                  <div className="flex flex-wrap gap-2 mb-3">{row.gold7.map(value => <Pill key={`${row.date}-g7-${value}`} hit={row.gold7Hits.includes(value)}>{value}</Pill>)}</div>
                  <div className="text-xs text-gray-400">命中：{row.gold7Hits.join('、') || '无'}</div>
                </div>
                <div className="rounded-xl border border-gray-700/50 bg-gray-950/50 p-4">
                  <div className="text-sm font-semibold text-white mb-3">全域Top12</div>
                  <div className="flex flex-wrap gap-2 mb-3">{row.top12.map(value => <Pill key={`${row.date}-t12-${value}`} hit={row.top12Hits.includes(value)}>{value}</Pill>)}</div>
                  <div className="text-xs text-gray-400">命中：{row.top12Hits.join('、') || '无'}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
