// 数据加载服务 - 自动读取本地数据文件

/**
 * 从 daily_points.txt 加载最新点位数据
 * 文件格式：date:YYYY-MM-DD,points:XX XX XX...
 */
export function loadDailyPoints(content: string): Array<{ date: string; points: number[] }> {
  const lines = content.split(/\r?\n/).filter(line => line.trim());
  const results: Array<{ date: string; points: number[] }> = [];

  for (const line of lines) {
    const match = line.match(/date:(\d{4}-\d{2}-\d{2}),points:(.+)/);
    if (match) {
      const date = match[1];
      const points = match[2]
        .trim()
        .split(/\s+/)
        .map(s => parseInt(s.trim(), 10))
        .filter(n => !isNaN(n) && n >= 1 && n <= 80);
      
      if (points.length > 0) {
        results.push({ date, points: [...new Set(points)].sort((a, b) => a - b) });
      }
    }
  }

  // 按日期降序排列，最新的在前
  return results.sort((a, b) => b.date.localeCompare(a.date));
}

/**
 * 从 kl8_history_final.txt 加载历史开奖数据
 * 文件格式：date:YYYY-MM-DD,period:XXXXXXXX,numbers:XX-XX-...-XX
 */
export function loadHistoryData(content: string): Array<{ date: string; period: string; numbers: number[] }> {
  const lines = content.split(/\r?\n/).filter(line => line.trim());
  const results: Array<{ date: string; period: string; numbers: number[] }> = [];

  for (const line of lines) {
    // 支持两种格式
    // 格式 1: date:YYYY-MM-DD,period:XXXXXXXX,numbers:XX-XX-...-XX
    // 格式 2: 开奖日期：YYYY-MM-DD，开奖期数:XXXXXXXX，开奖号码:XX-XX-...-XX
    const match1 = line.match(/date:(\d{4}-\d{2}-\d{2}),period:(\d+),numbers:(.+)/);
    const match2 = line.match (/开奖日期：(\d{4}-\d{2}-\d{2}),开奖期数:(\d+),开奖号码:(.+)/);
    
    const match = match1 || match2;
    if (match) {
      const date = match[1];
      const period = match[2];
      const numbers = match[3]
        .split(/[-\s,]+/)
        .map(s => parseInt(s.trim(), 10))
        .filter(n => !isNaN(n) && n >= 1 && n <= 80);
      
      if (numbers.length >= 10) {
        results.push({ 
          date, 
          period, 
          numbers: [...new Set(numbers)].sort((a, b) => a - b) 
        });
      }
    }
  }

  // 按日期降序排列，最新的在前
  return results.sort((a, b) => b.date.localeCompare(a.date));
}

/**
 * 获取最新日期的点位数据
 */
export function getLatestPoints(pointsData: Array<{ date: string; points: number[] }>): number[] {
  if (pointsData.length === 0) {
    return [];
  }
  return pointsData[0].points;
}

/**
 * 将历史数据转换为分析引擎需要的格式 (number[][])
 */
export function convertHistoryToDraws(
  historyData: Array<{ date: string; period: string; numbers: number[] }>
): number[][] {
  return historyData.map(item => item.numbers);
}

/**
 * 加载状态接口
 */
export interface LoadStatus {
  success: boolean;
  message: string;
  pointsCount?: number;
  historyCount?: number;
  error?: Error;
}

/**
 * 模拟从本地文件加载数据 (实际使用时需要通过后端 API 或 Electron)
 * 由于浏览器安全限制，这里提供一个模拟接口
 */
export async function loadDataFromLocalFiles(): Promise<LoadStatus> {
  try {
    // 注意：由于浏览器安全限制，前端不能直接读取本地文件
    // 需要通过以下方式之一实现:
    // 1. 使用 Electron 等框架提供文件系统访问
    // 2. 通过后端 API 提供文件内容
    // 3. 使用 Vite 的 import.meta.url 导入 (仅适用于构建时已知的文件)
    
    // 这里我们先返回一个提示信息
    return {
      success: false,
      message: '需要通过后端 API 或 Electron 访问本地文件，请参考 README 中的部署说明',
      pointsCount: 0,
      historyCount: 0
    };
  } catch (error) {
    return {
      success: false,
      message: '数据加载失败',
      error: error instanceof Error ? error : new Error('未知错误')
    };
  }
}

/**
 * 从 API 加载数据 (推荐方式)
 */
export async function loadDataFromAPI(
  pointsUrl: string,
  historyUrl: string
): Promise<{
  pointsData: Array<{ date: string; points: number[] }>;
  historyData: Array<{ date: string; period: string; numbers: number[] }>;
  status: LoadStatus;
}> {
  try {
    const [pointsResponse, historyResponse] = await Promise.all([
      fetch(pointsUrl),
      fetch(historyUrl)
    ]);

    if (!pointsResponse.ok || !historyResponse.ok) {
      throw new Error('数据文件获取失败');
    }

    const pointsText = await pointsResponse.text();
    const historyText = await historyResponse.text();

    const pointsData = loadDailyPoints(pointsText);
    const historyData = loadHistoryData(historyText);

    return {
      pointsData,
      historyData,
      status: {
        success: true,
        message: '数据加载成功',
        pointsCount: pointsData.length,
        historyCount: historyData.length
      }
    };
  } catch (error) {
    return {
      pointsData: [],
      historyData: [],
      status: {
        success: false,
        message: '数据加载失败',
        error: error instanceof Error ? error : new Error('未知错误')
      }
    };
  }
}

/**
 * 加载专家比对矩阵数据
 */
export async function loadExpertMatrix(url: string): Promise<any> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.warn("专家比对矩阵加载失败:", e);
    return null;
  }
}

export type ExpertTabKey = 'daily' | 'insight' | 'global' | 'energy' | 'tracking' | 'beginner';

export interface ExpertTabItem {
  key: ExpertTabKey;
  label: string;
}

export interface MatrixBlock {
  date: string;
  displayDate: string;
  actualNumbers: string[];
  actualPeriod: string;
  actualStatus: 'matched' | 'missing';
  missingActualData: boolean;
  matrixDiagnostics?: {
    data1MatrixCount: number;
    data2MatrixCount: number;
  };
  dailyBrief?: {
    verdict: string;
    summary: string;
    uncertainty: '高' | '中' | '低' | string;
    confidence?: '高' | '中' | '低' | string;
    score?: number;
    focusNumbers?: string[];
    focusMatrices?: string[];
    triggerThreshold?: {
      primaryHitRate?: number;
      strongHitRate?: number;
      minimumSamples?: number;
      [key: string]: number | undefined;
    };
    evidenceRefs?: string[];
  };
  sourceGroups: Array<{
    key: string;
    title: string;
    matrices: Array<{
      title: string;
      rows: string[][];
      hitNumbers: string[];
    }>;
  }>;
}

// 兼容旧版组件定义，避免历史实现编译报错。
export interface BeginnerSnapshot {
  date: string;
  title?: string;
  matrixLabels?: {
    source1Left: string;
    source1Right: string;
    source2Left: string;
    source2Right: string;
  };
  matrixRows?: Array<{
    rowLabel: string;
    source1: { left: string[]; right: string[] };
    source2: { left: string[]; right: string[] };
  }>;
  reportTitle?: string;
  entropySummary?: string;
  reportEntries?: Array<{ label: string; numbers: string[]; reason: string }>;
  summaryTitle?: string;
  summaryText?: string;
  backtests?: Array<{ title: string; items: Array<{ period: string; state: string; recommended: string[]; hits: string[] }> }>;
}

export interface GlobalMetricRow {
  name: string;
  days: number;
  totalHits: number;
  lastHits: string[];
  fillCount: number;
  matrixId?: string;
  energy?: string;
  stability?: string;
  stabilityValue?: number | null;
  entropy?: string;
  centroid?: string;
  coupling?: string;
  couplingValue?: number | null;
}

export interface EnergyMonitorRow {
  name: string;
  repeatedCount: number;
  hitCount: number;
  numbers: string[];
  matrixId?: string;
  energyStatus?: string;
  trend?: string;
}

export interface TrackingAuditRow {
  date: string;
  displayDate: string;
  gold2: string[];
  gold7: string[];
  top12: string[];
  actualNumbers: string[];
  actualPeriod: string;
  isPending: boolean;
  missingActualData: boolean;
  pendingReason: string;
  gold2Hits: string[];
  gold7Hits: string[];
  top12Hits: string[];
  gold2HitCount: number;
  gold7HitCount: number;
  top12HitCount: number;
  verdict?: string;
  missReason?: string;
  actual?: string[];
  actualRaw?: string;
  hitGold2?: number;
  hitGold7?: number;
  hitTop12?: number;
  hitNumbersGold2?: string[];
  hitNumbersGold7?: string[];
  hitNumbersTop12?: string[];
  evaluation?: string;
  status?: 'pending' | 'great' | 'stable' | 'watch' | 'cooldown';
  confidence?: '高' | '中' | '低' | string;
  uncertainty?: '高' | '中' | '低' | string;
  riskScore?: number;
  triggerThreshold?: {
    gold2Hit?: number;
    gold7Hit?: number;
    top12Hit?: number;
    strongTop12Hit?: number;
    [key: string]: number | undefined;
  };
  evidenceRefs?: string[];
}

export interface ExpertDashboardData {
  meta: {
    generatedAt: string;
    latestDate: string;
    historyLatestDate: string;
    dataHealth?: {
      pointsLatestDate: string;
      historyLatestDate: string;
      expertLatestDate: string;
      isMisaligned: boolean;
      message: string;
    };
  };
  overviewTabs: ExpertTabItem[];
  dailyMatrixViews: MatrixBlock[];
  insightSummary: {
    title: string;
    overview: string;
    focusNumbers: Array<{ number: string; weight: number }>;
    focusMatrices: Array<{
      sourceTitle: string;
      matrixTitle: string;
      count: number;
      repeatCount: number;
      hitCount: number;
    }>;
    riskReminder: string;
    keyFindings: string[];
  };
  globalHighlights: {
    title: string;
    intro: string;
    highlightCards: Array<{
      title: string;
      summary: string;
      lastHits: string[];
    }>;
    reasons: string[];
    evidenceRows: GlobalMetricRow[];
    persistenceRows?: Array<{
      name: string;
      days: number;
      totalHits: number;
      persistenceScore: number;
    }>;
  };
  energyHighlights: {
    title: string;
    focusRepeats: Array<{ number: string; count: number }>;
    hotMatrices: Array<{
      name: string;
      repeatedCount: number;
      hitCount: number;
      numbers: string[];
    }>;
    observations: string[];
    evidenceRows: EnergyMonitorRow[];
    crossSourceConsensus?: Array<{ number: string; count: number }>;
    cellHeatMap?: Array<{ cell: string; hitRate: number; samples: number }>;
  };
  trackingDetails: TrackingAuditRow[];
  beginnerSheet?: {
    title: string;
    reportTitle: string;
    snapshots: BeginnerSnapshot[];
  };
  globalSheet?: {
    title: string;
    metricsTitle: string;
    metrics: GlobalMetricRow[];
    balanceTitle: string;
    balances: Array<{ blockId: string; leftEnergy: string; rightEnergy: string; preference: string }>;
    reasoningTitle: string;
    reasoning: string[];
  };
  energySheet?: {
    title: string;
    monitorTitle: string;
    monitors: EnergyMonitorRow[];
    repeatTitle: string;
    repeatEntries: Array<{ label: string; value: string; numbers: string[] }>;
    notes: string[];
  };
  trackingSheet?: {
    title: string;
    rows: TrackingAuditRow[];
  };
}

export async function loadExpertDashboard(url: string): Promise<ExpertDashboardData | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.error("加载专家看板失败:", e);
    return null;
  }
}

/**
 * 历史推演记录条目接口
 */
export interface FollowerHistoryItem {
  date: string;
  gold2: string[];
  gold7: string[];
  top12: string[];
  actual: string[];
  isPending: boolean;
}

/**
 * 加载跟随号历史推演记录 (从 CSV 加载)
 */
export async function loadFollowerHistory(url: string): Promise<FollowerHistoryItem[]> {
  try {
    const res = await fetch(url);
    if (!res.ok) return [];
    
    const text = await res.text();
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    if (lines.length <= 1) return []; // 只有表头或为空

    // 智能解析 CSV (处理引号和逗号)
    const results: FollowerHistoryItem[] = [];
    
    // 跳过表头
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i];
      const parts: string[] = [];
      let inQuotes = false;
      let currentPart = '';
      
      for (let char of line) {
        if (char === '"') inQuotes = !inQuotes;
        else if (char === ',' && !inQuotes) {
          parts.push(currentPart.trim());
          currentPart = '';
        } else {
          currentPart += char;
        }
      }
      parts.push(currentPart.trim());

      if (parts.length < 5) continue;
      
      results.push({
        date: parts[0],
        gold2: parts[1] ? parts[1].split(/[,，]/) : [],
        gold7: parts[2] ? parts[2].split(/[,，]/) : [],
        top12: parts[3] ? parts[3].split(/[,，]/) : [],
        actual: parts[4] !== 'PENDING' ? parts[4].split('-') : [],
        isPending: parts[4].includes('PENDING')
      });
    }
    
    return results;
  } catch (e) {
    console.error("加载跟随号历史失败:", e);
    return [];
  }
}
