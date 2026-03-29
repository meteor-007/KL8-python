import { useEffect, useMemo, useState } from 'react';
import {
  convertHistoryToDraws,
  getLatestPoints,
  loadDataFromAPI,
  loadExpertDashboard,
  loadFollowerHistory,
  type ExpertTabKey,
  type FollowerHistoryItem,
} from './data/dataLoader';
import { buildPointAnalysisDashboardModel } from './data/pointAnalysisViewModel';
import { buildPointDecisionBrief, type ReportSectionKey } from './data/pointDecisionBrief';
import { ExpertDashboardScreen } from './components/ExpertDashboardScreen';
import { PointDecisionBriefScreen } from './components/PointDecisionBriefScreen';

function DataLoadingStatus({
  loading,
  error,
  pointsCount,
  historyCount,
  latestDate,
}: {
  loading: boolean;
  error: string | null;
  pointsCount: number;
  historyCount: number;
  latestDate: string | null;
}) {
  if (loading) {
    return (
      <div className="mb-6 rounded-2xl border border-cyan-500/30 bg-cyan-500/10 p-4">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 animate-spin rounded-full border-b-2 border-cyan-300" />
          <div>
            <div className="text-sm font-semibold text-cyan-300">正在加载数据...</div>
            <div className="text-xs text-gray-400 mt-1">正在读取点位、历史开奖和专家看板文件</div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-4">
        <div className="text-sm font-semibold text-red-300">数据加载失败</div>
        <div className="text-xs text-red-200 mt-2">{error}</div>
      </div>
    );
  }

  return (
    <div className="mb-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
      <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
        <div>
          <div className="text-xs text-gray-400">最新点位日期</div>
          <div className="font-semibold text-emerald-200 mt-1">{latestDate || '未知'}</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">点位数据天数</div>
          <div className="font-semibold text-emerald-200 mt-1">{pointsCount}</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">历史开奖期数</div>
          <div className="font-semibold text-emerald-200 mt-1">{historyCount}</div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [activeMenu, setActiveMenu] = useState<'points' | 'follower'>('points');
  const [activePointsSection, setActivePointsSection] = useState<ReportSectionKey>('overview');
  const [activeExpertTab, setActiveExpertTab] = useState<ExpertTabKey>('daily');

  const [cores, setCores] = useState<number[]>([]);
  const [prevCores, setPrevCores] = useState<number[]>([]);
  const [pointsTimeline, setPointsTimeline] = useState<Array<{ date: string; points: number[] }>>([]);
  const [draws, setDraws] = useState<number[][]>([]);
  const [historyTimeline, setHistoryTimeline] = useState<Array<{ date: string; period: string; numbers: number[] }>>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dataStats, setDataStats] = useState({
    pointsCount: 0,
    historyCount: 0,
    latestDate: null as string | null,
  });

  const [followerHistory, setFollowerHistory] = useState<FollowerHistoryItem[]>([]);
  const [expertLoading, setExpertLoading] = useState(true);
  const [expertError, setExpertError] = useState<string | null>(null);
  const [expertDashboard, setExpertDashboard] = useState<any>(null);

  useEffect(() => {
    const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/src/data';

    const loadMainData = async () => {
      try {
        setLoading(true);
        setLoadError(null);

        const { pointsData, historyData, status } = await loadDataFromAPI(
          `${API_BASE}/daily_points.txt`,
          `${API_BASE}/kl8_history_final.txt`
        );

        if (!status.success) {
          setLoadError(status.message || '数据加载失败');
          return;
        }

        const latestPoints = getLatestPoints(pointsData);
        setCores(latestPoints);
        setPrevCores(pointsData[1]?.points ?? []);
        setPointsTimeline(pointsData);
        setDraws(convertHistoryToDraws(historyData));
        setHistoryTimeline(historyData);
        setDataStats({
          pointsCount: pointsData.length,
          historyCount: historyData.length,
          latestDate: pointsData[0]?.date ?? null,
        });
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : '数据加载失败');
      } finally {
        setLoading(false);
      }
    };

    const loadFollowerData = async () => {
      const rows = await loadFollowerHistory(`${API_BASE}/recommendation_history.csv`);
      setFollowerHistory(rows);
    };

    const loadExpertData = async () => {
      try {
        setExpertLoading(true);
        setExpertError(null);
        const dashboard = await loadExpertDashboard(`${API_BASE}/expert_dashboard.json`);
        if (!dashboard) {
          setExpertError('未找到 expert_dashboard.json，请先运行 start_service.py 生成专家看板数据。');
          return;
        }
        setExpertDashboard(dashboard);
      } catch (error) {
        setExpertError(error instanceof Error ? error.message : '专家看板加载失败');
      } finally {
        setExpertLoading(false);
      }
    };

    loadMainData();
    loadFollowerData();
    loadExpertData();
  }, []);

  const pointsDashboardModel = useMemo(
    () =>
      buildPointAnalysisDashboardModel({
        cores,
        prevCores,
        draws,
        historyTimeline,
        pointsTimeline,
        expertDashboard,
        pointsLatestDate: dataStats.latestDate,
        historyLatestDate: expertDashboard?.meta?.historyLatestDate ?? null,
        expertLatestDate: expertDashboard?.meta?.latestDate ?? null,
      }),
    [cores, prevCores, draws, historyTimeline, pointsTimeline, dataStats.latestDate, expertDashboard]
  );

  const pointBriefModel = useMemo(() => buildPointDecisionBrief(pointsDashboardModel), [pointsDashboardModel]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.12),_transparent_30%),linear-gradient(180deg,_#0b1120_0%,_#111827_45%,_#0f172a_100%)] text-gray-100">
      <header className="sticky top-0 z-50 border-b border-gray-800/80 bg-gray-950/85 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="bg-gradient-to-r from-cyan-300 via-sky-300 to-emerald-300 bg-clip-text text-3xl font-bold text-transparent">
              数据分析系统
            </h1>
            <p className="mt-1 text-sm text-gray-400">按技术工作流组织的信号分析与数据追踪看板</p>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500">当前模块</div>
            <div className="mt-1 text-sm font-semibold text-cyan-300">
              {activeMenu === 'points' ? '点位分析简报' : '专家关注号分析'}
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        <aside className="fixed left-0 top-[81px] h-[calc(100vh-81px)] w-72 overflow-y-auto border-r border-gray-800/80 bg-gray-950/70 p-4 backdrop-blur-xl">
          <nav className="space-y-6">
            <div>
              <div className="px-4 py-2 text-xs font-bold uppercase tracking-[0.24em] text-gray-500">点位决策简报</div>
              <div className="mt-2 space-y-1">
                {pointBriefModel.sections.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => {
                      setActiveMenu('points');
                      setActivePointsSection(item.key);
                    }}
                    className={`w-full rounded-2xl border px-4 py-3 text-left transition-all ${
                      activeMenu === 'points' && activePointsSection === item.key
                        ? 'border-cyan-400/40 bg-cyan-500/15 text-cyan-200'
                        : 'border-transparent bg-gray-900/40 text-gray-400 hover:border-gray-700 hover:bg-gray-800/60 hover:text-gray-200'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{item.icon}</span>
                      <div>
                        <div className="font-semibold">{item.label}</div>
                        <div className="mt-1 text-xs text-gray-500">{item.description}</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-gray-800/70 pt-4">
              <div className="px-4 py-2 text-xs font-bold uppercase tracking-[0.24em] text-gray-500">数据追踪汇总</div>
              <button
                type="button"
                onClick={() => setActiveMenu('follower')}
                className={`mt-2 w-full rounded-2xl border px-4 py-3 text-left transition-all ${
                  activeMenu === 'follower'
                    ? 'border-purple-400/40 bg-purple-500/15 text-purple-200'
                    : 'border-transparent bg-gray-900/40 text-gray-400 hover:border-gray-700 hover:bg-gray-800/60 hover:text-gray-200'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-lg">📊</span>
                  <div>
                    <div className="font-semibold">专家关注号分析</div>
                    <div className="mt-1 text-xs text-gray-500">保留现有专家矩阵、历史复盘和重点结论视图</div>
                  </div>
                </div>
              </button>
            </div>
          </nav>
        </aside>

        <main className="ml-72 flex-1 px-8 py-8">
          <div className="mx-auto max-w-7xl">
            <DataLoadingStatus
              loading={loading}
              error={loadError}
              pointsCount={dataStats.pointsCount}
              historyCount={dataStats.historyCount}
              latestDate={dataStats.latestDate}
            />

            {activeMenu === 'points' ? (
              <PointDecisionBriefScreen
                model={pointsDashboardModel}
                brief={pointBriefModel}
                activeSection={activePointsSection}
              />
            ) : (
              <ExpertDashboardScreen
                dashboard={expertDashboard}
                loading={expertLoading}
                error={expertError}
                activeTab={activeExpertTab}
                onTabChange={setActiveExpertTab}
                fallbackHistory={followerHistory}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
