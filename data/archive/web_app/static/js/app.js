/**
 * K8-QUANT Web Multi-Level Cyber Navigation & Tab Management System
 * 多级菜单树、动态 Tab 标签页管理、6 大系统主题自由切换与 ECharts 响应式换肤
 */

const { createApp, ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } = Vue;

const App = {
  setup() {
    // 侧边栏折叠状态
    const isSidebarCollapsed = ref(false);

    // ──────────────── 0. 6 大系统主题状态与切换 ────────────────
    const themes = [
      { id: 'theme-cyber', name: '深邃赛博', icon: '🌌', desc: '极客蓝霓虹 (默认)', dotColor: '#00f0ff', badge: 'CYBER' },
      { id: 'theme-gold', name: '黑金尊享', icon: '👑', desc: '曜石黑金操盘手', dotColor: '#f59e0b', badge: 'GOLD' },
      { id: 'theme-aurora', name: '极光星河', icon: '✨', desc: '极光幻彩魅紫', dotColor: '#c084fc', badge: 'AURORA' },
      { id: 'theme-emerald', name: '量子翡翠', icon: '🌲', desc: '矩阵代码荧光绿', dotColor: '#10b981', badge: 'MATRIX' },
      { id: 'theme-midnight', name: '深空暗夜', icon: '🌑', desc: '纯粹极简纯黑', dotColor: '#ffffff', badge: 'OLED' },
      { id: 'theme-light', name: '皓月雅白', icon: '☀️', desc: '典雅明亮日间', dotColor: '#0284c7', badge: 'LIGHT' }
    ];

    const currentTheme = ref(localStorage.getItem('k8_quant_theme') || 'theme-cyber');
    const showThemeDropdown = ref(false);

    const currentThemeObj = computed(() => {
      return themes.find(t => t.id === currentTheme.value) || themes[0];
    });

    const setTheme = (themeId) => {
      currentTheme.value = themeId;
      localStorage.setItem('k8_quant_theme', themeId);
      document.documentElement.className = themeId;
      document.body.className = themeId;
      showThemeDropdown.value = false;
      const themeObj = themes.find(t => t.id === themeId);
      addLog(`🎨 系统界面主题已无缝切换至【${themeObj ? themeObj.name : themeId}】`, 'info');
      // 重新调整图表配色
      nextTick(() => {
        updateAllCharts();
      });
    };

    // 多级菜单配置
    const menuGroups = ref([
      {
        id: 'trading',
        name: '核心操盘研判',
        icon: '🎯',
        opened: true,
        children: [
          { key: 'live_cockpit', title: '实时量化驾驶舱', icon: '⚡', badge: 'HOT' },
          { key: 'gold_pairs', title: '今日金胆与黄金搭档', icon: '👑', badge: '' },
          { key: 'hidden_energy', title: '首席特供 Hidden Energy', icon: '🌟', badge: '' }
        ]
      },
      {
        id: 'matrix',
        name: '走势与数据态势',
        icon: '🔮',
        opened: true,
        children: [
          { key: 'draw_trend_chart', title: '开奖号码走势图', icon: '📈', badge: '100期' },
          { key: 'matrix_80', title: '80码全景热力矩阵', icon: '🌐', badge: '80' },
          { key: 'tail_entropy', title: '尾数分布与香农熵', icon: '📊', badge: '' },
          { key: 'history_table', title: '历史开奖总库检索', icon: '📋', badge: '' }
        ]
      },
      {
        id: 'algorithm',
        name: '算法模型实验室',
        icon: '🧬',
        opened: true,
        children: [
          { key: 'model_tuning', title: '三维权重动态调优', icon: '⚙️', badge: '' },
          { key: 'radar_view', title: 'EF/RW/FO 动能雷达', icon: '🧭', badge: '' },
          { key: 'pure_pool', title: '纯净池与LR定胆分析', icon: '🧪', badge: '' }
        ]
      },
      {
        id: 'jingle',
        name: '顺口溜口诀决策',
        icon: '📜',
        opened: true,
        children: [
          { key: 'jingle_cockpit', title: '顺口溜组合带出研判', icon: '📜', badge: 'NEW' },
          { key: 'jingle_rules_lib', title: '90条精英口诀规则库', icon: '📖', badge: '90' }
        ]
      },
      {
        id: 'spatial_points',
        name: '空间重点点位分析',
        icon: '🔮',
        opened: true,
        children: [
          { key: 'points_cockpit', title: '重点点位决策大屏', icon: '🎯', badge: 'HOT' },
          { key: 'points_matrix', title: '80点位全景精排矩阵', icon: '🌐', badge: '80' },
          { key: 'points_review', title: '样本外滚动复盘审计', icon: '📊', badge: 'WF' }
        ]
      },
      {
        id: 'follow',
        name: '跟随分析研判',
        icon: '🔗',
        opened: true,
        children: [
          { key: 'follow_cockpit', title: '跟随分析决策舱', icon: '⚡', badge: 'HOT' },
          { key: 'follow_conditions', title: '条件跟随多窗明细', icon: '🔗', badge: '5对' }
        ]
      },
      {
        id: 'point_suppression',
        name: '点位期数反弹追踪',
        icon: '🪞',
        opened: true,
        children: [
          { key: 'suppression_cockpit', title: '未开点位反弹驾驶舱', icon: '🎯', badge: 'NEW' },
          { key: 'suppression_patterns', title: '影子替身与能量外溢', icon: '🪞', badge: '伴生' },
          { key: 'suppression_review', title: '样本外滚动复盘审计', icon: '📊', badge: 'WF' }
        ]
      },
      {
        id: 'killseeker',
        name: 'KillSeeker 杀号决策',
        icon: '⚔️',
        opened: true,
        children: [
          { key: 'kill_cockpit', title: '核心杀号决策大屏', icon: '⚔️', badge: 'HOT' },
          { key: 'kill_review', title: '杀号对账复盘审计', icon: '📊', badge: '75%+' },
          { key: 'kill_logs', title: '杀号控制研报中心', icon: '📑', badge: '' }
        ]
      },
      {
        id: 'gold_pick2',
        name: '定金选2决策',
        icon: '💎',
        opened: true,
        children: [
          { key: 'gold_pick2_cockpit', title: '定金选2决策驾驶舱', icon: '💎', badge: 'HOT' },
          { key: 'gold_pick2_review', title: '选2样本外滚动复盘', icon: '📊', badge: 'WF' },
          { key: 'gold_pick2_logs', title: '定金选2研报中心', icon: '📑', badge: '' }
        ]
      },
      {
        id: 'gemini',
        name: 'Gemini 选2预测',
        icon: '🔮',
        opened: true,
        children: [
          { key: 'gemini_cockpit', title: '选2多算子驾驶舱', icon: '🔮', badge: '' },
          { key: 'gemini_review', title: '样本外复盘审计', icon: '📊', badge: 'WF' },
          { key: 'gemini_history', title: '每日预测研报总库', icon: '📑', badge: '' }
        ]
      },
      {
        id: 'aggregation',
        name: '终审数据汇总复盘',
        icon: '🧬',
        opened: true,
        children: [
          { key: 'agg_cockpit', title: '7路共识终审决策大屏', icon: '⚡', badge: 'HOT' },
          { key: 'agg_reports', title: '每日终审战报总库', icon: '📑', badge: '' }
        ]
      },
      {
        id: 'audit',
        name: '复盘与回测审计',
        icon: '📈',
        opened: true,
        children: [
          { key: 'hit_rate_trends', title: '历史 25 期命中率走势', icon: '📉', badge: '' },
          { key: 'reports_browser', title: '每日研判报告总库', icon: '📑', badge: '' }
        ]
      },
      {
        id: 'ops',
        name: '自动化调度中心',
        icon: '⚡',
        opened: true,
        children: [
          { key: 'live_terminal', title: '流水线黑客日志终端', icon: '💻', badge: 'LIVE' }
        ]
      }
    ]);

    // 动态 Tab 标签页管理
    const tabs = ref([
      { key: 'live_cockpit', title: '实时量化驾驶舱', icon: '⚡', closable: false }
    ]);
    const activeTab = ref('live_cockpit');

    const toggleGroup = (group) => {
      group.opened = !group.opened;
    };

    const openTab = (key, title, icon = '📄') => {
      const existing = tabs.value.find(t => t.key === key);
      if (!existing) {
        tabs.value.push({ key, title, icon, closable: key !== 'live_cockpit' });
      }
      activeTab.value = key;
      if (key === 'agg_cockpit') {
        fetchAggCockpit();
      } else if (key === 'agg_reports') {
        fetchAggHistory();
      }
      // 切换标签后重新调整图表尺寸与主题
      nextTick(() => {
        handleResize();
      });
    };

    const closeTab = (key) => {
      const idx = tabs.value.findIndex(t => t.key === key);
      if (idx === -1) return;
      tabs.value.splice(idx, 1);
      if (activeTab.value === key) {
        activeTab.value = tabs.value[Math.max(0, idx - 1)].key;
      }
      nextTick(() => { handleResize(); });
    };

    const closeOtherTabs = () => {
      tabs.value = tabs.value.filter(t => t.key === activeTab.value || !t.closable);
    };

    const closeAllTabs = () => {
      tabs.value = tabs.value.filter(t => !t.closable);
      activeTab.value = 'live_cockpit';
    };

    // ──────────────── 业务数据状态 ────────────────
    const systemStatus = ref({
      latest_draw_period: '---',
      latest_draw_date: '---',
      target_period: '---',
      latest_draw_numbers: [],
      beacon_status: 'NORMAL',
      status: 'ONLINE',
      system_name: 'K8-Quant 智能量化系统',
      version: 'V5.0 Enterprise'
    });

    const prediction = ref({
      period: '---',
      date: '---',
      golden_pair: [0, 0],
      golden_pair_reason: '加载中...',
      top5_gold: [],
      top12_pool: [],
      golden_core: [],
      hidden_energy_5: [],
      sub_pairs: [],
      weights: { EF: 0.4, RW: 0.3, FO: 0.3 },
      weights_plain: '加载中...',
      pure_pool: [],
      shannon_entropy: 0.0,
      risk_status: 'NORMAL'
    });

    const matrixData = ref([]);
    const tailStats = ref([]);
    const zoneStats = ref([]);
    const trendStats = ref(null);
    const activeFilter = ref('all');

    // 80码开奖走势图状态 (默认100期、日期升序)
    const trendLimit = ref(100);
    const trendCustomInput = ref(100);
    const trendData = ref({ draws: [], ball_stats: [], summary: {} });
    const trendLoading = ref(false);
    const trendShowOmission = ref(true);
    const trendZoneFilter = ref('all');
    const trendViewMode = ref('wide');
    const highlightedBall = ref(null);
    const trendSearchBall = ref('');
    const customPicks = ref([]);

    // 历史表格分页
    const historyTable = reactive({
      page: 1,
      page_size: 15,
      total: 0,
      total_pages: 1,
      q: '',
      items: []
    });

    // 研判报告
    const reportList = ref([]);
    const currentReport = ref({ title: '', content: '', date: '', period: '' });

    // 弹窗与详情
    const selectedBall = ref(null);
    const showBallModal = ref(false);

    // 参数微调
    const modelParams = reactive({
      EF: 0.40,
      RW: 0.30,
      FO: 0.30
    });
    const paramSaveMsg = ref('');

    // 控制台与日志
    const terminalLogs = ref([
      `[${new Date().toLocaleTimeString()}] 🚀 K8-Quant 企业级多主题量化决策终端已就绪`,
      `[${new Date().toLocaleTimeString()}] 🎨 当前界面主题: ${themes.find(t => t.id === currentTheme.value)?.name || '深邃赛博'}`
    ]);
    const isRunning = ref(false);
    const currentTaskId = ref(null);
    const autoScroll = ref(true);
    let logPollTimer = null;

    // ECharts 实例引用 (支持驾驶舱与独立 Tab 双向挂载)
    let radarChart = null;
    let radarChartTab = null;
    let trendChart = null;
    let trendChartTab = null;
    let tailChart = null;
    let tailChartTab = null;
    let zoneChart = null;
    let zoneChartTab = null;
    let trendDistChart = null;
    let trendSumOddChart = null;

    // ──────────────── API 请求方法 ────────────────

    const fetchSystemStatus = async () => {
      try {
        const res = await fetch('/api/system/status');
        if (res.ok) {
          systemStatus.value = await res.json();
        }
      } catch (err) {
        console.error('获取系统状态失败:', err);
      }
    };

    const fetchPrediction = async () => {
      try {
        const res = await fetch('/api/quant/latest-prediction');
        if (res.ok) {
          prediction.value = await res.json();
          modelParams.EF = prediction.value.weights?.EF || 0.40;
          modelParams.RW = prediction.value.weights?.RW || 0.30;
          modelParams.FO = prediction.value.weights?.FO || 0.30;
          updateRadarChart();
        }
      } catch (err) {
        console.error('获取最新预测失败:', err);
      }
    };

    const fetchMatrixData = async () => {
      try {
        const res = await fetch('/api/quant/matrix-80');
        if (res.ok) {
          const data = await res.json();
          matrixData.value = data.matrix || [];
          tailStats.value = data.tail_stats || [];
          zoneStats.value = data.zone_stats || [];
          updateTailChart(data.tail_stats || []);
          updateZoneChart(data.zone_stats || []);
        }
      } catch (err) {
        console.error('获取80码矩阵失败:', err);
      }
    };

    const fetchHistoryTrends = async (limit = 25) => {
      try {
        const res = await fetch(`/api/quant/history-trends?limit=${limit}`);
        if (res.ok) {
          const data = await res.json();
          trendStats.value = data;
          updateTrendChart(data);
        }
      } catch (err) {
        console.error('获取历史走势失败:', err);
      }
    };

    const fetchLotteryTrends = async (limit = 100) => {
      try {
        trendLoading.value = true;
        trendLimit.value = limit;
        trendCustomInput.value = limit;
        const res = await fetch(`/api/quant/lottery-trends?limit=${limit}`);
        if (res.ok) {
          trendData.value = await res.json();
          nextTick(() => {
            updateTrendDistChart();
            updateTrendSumOddChart();
          });
        }
      } catch (err) {
        console.error('获取开奖号码走势图失败:', err);
      } finally {
        trendLoading.value = false;
      }
    };

    const handleCustomLimitSubmit = () => {
      let n = parseInt(trendCustomInput.value);
      if (isNaN(n) || n < 5) n = 100;
      if (n > 1000) n = 1000;
      fetchLotteryTrends(n);
    };

    const toggleHighlightBall = (num) => {
      if (highlightedBall.value === num) {
        highlightedBall.value = null;
      } else {
        highlightedBall.value = num;
      }
    };

    const handleSearchBallHighlight = () => {
      let n = parseInt(trendSearchBall.value);
      if (!isNaN(n) && n >= 1 && n <= 80) {
        highlightedBall.value = n;
      } else {
        highlightedBall.value = null;
      }
    };

    const toggleCustomPick = (num) => {
      const idx = customPicks.value.indexOf(num);
      if (idx > -1) {
        customPicks.value.splice(idx, 1);
      } else {
        customPicks.value.push(num);
        customPicks.value.sort((a, b) => a - b);
      }
    };

    const loadTop5ToCustomPicks = () => {
      if (prediction.value?.top5_gold?.length) {
        customPicks.value = [...prediction.value.top5_gold];
      }
    };

    const loadHiddenEnergyToCustomPicks = () => {
      if (prediction.value?.hidden_energy_5?.length) {
        customPicks.value = [...prediction.value.hidden_energy_5];
      }
    };

    const clearCustomPicks = () => {
      customPicks.value = [];
    };

    const filteredBallColumns = computed(() => {
      if (trendZoneFilter.value === '1') {
        return Array.from({ length: 20 }, (_, i) => i + 1);
      } else if (trendZoneFilter.value === '2') {
        return Array.from({ length: 20 }, (_, i) => i + 21);
      } else if (trendZoneFilter.value === '3') {
        return Array.from({ length: 20 }, (_, i) => i + 41);
      } else if (trendZoneFilter.value === '4') {
        return Array.from({ length: 20 }, (_, i) => i + 61);
      }
      return Array.from({ length: 80 }, (_, i) => i + 1);
    });

    const getBallStat = (num) => {
      if (!trendData.value || !trendData.value.ball_stats) return {};
      return trendData.value.ball_stats[num - 1] || {};
    };

    const fetchHistoryTable = async (page = 1) => {
      historyTable.page = page;
      try {
        const url = `/api/quant/history-table?page=${historyTable.page}&page_size=${historyTable.page_size}&q=${encodeURIComponent(historyTable.q)}`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          historyTable.items = data.items || [];
          historyTable.total = data.total || 0;
          historyTable.total_pages = data.total_pages || 1;
        }
      } catch (err) {
        console.error('获取历史表格失败:', err);
      }
    };

    const fetchReportList = async () => {
      try {
        const res = await fetch('/api/reports/list');
        if (res.ok) {
          reportList.value = await res.json();
          if (reportList.value.length > 0 && !currentReport.value.content) {
            openReportContent(reportList.value[0]);
          }
        }
      } catch (err) {
        console.error('获取报告列表失败:', err);
      }
    };

    const openReportContent = async (item) => {
      try {
        const res = await fetch(`/api/reports/detail/${item.raw_date || item.date}`);
        if (res.ok) {
          const data = await res.json();
          currentReport.value = {
            date: data.date,
            period: data.period,
            title: `第 ${data.period} 期量化研判与复盘审计报告 (${data.date})`,
            content: data.content
          };
        }
      } catch (err) {
        console.error('读取报告全文失败:', err);
      }
    };

    const openBallDetail = async (ball) => {
      try {
        const res = await fetch(`/api/quant/number/${ball.number}`);
        if (res.ok) {
          selectedBall.value = await res.json();
          showBallModal.value = true;
        }
      } catch (err) {
        console.error('获取球号详情失败:', err);
      }
    };

    // ──────────────── 任务与流水线触发 ────────────────

    const runPipeline = async () => {
      if (isRunning.value) return;
      try {
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        isRunning.value = true;
        addLog('⚡ 正在发起【全流程量化预测流水线】任务请求...');
        const res = await fetch('/api/pipeline/run', { method: 'POST' });
        const data = await res.json();
        if (data.task_id) {
          currentTaskId.value = data.task_id;
          addLog(`✅ 任务已创建 (ID: ${data.task_id})，正在流式获取计算日志...`, 'success');
          startLogPolling(data.task_id);
        } else {
          addLog(`⚠️ 任务提示: ${data.message || '已有任务在运行'}`, 'warn');
          isRunning.value = false;
        }
      } catch (err) {
        addLog(`❌ 发起任务失败: ${err}`, 'error');
        isRunning.value = false;
      }
    };

    const syncData = async () => {
      if (isRunning.value) return;
      try {
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        isRunning.value = true;
        addLog('🔄 正在拉取并同步历史开奖数据...');
        const res = await fetch('/api/pipeline/sync-data', { method: 'POST' });
        const data = await res.json();
        if (data.task_id) {
          currentTaskId.value = data.task_id;
          addLog(`✅ 数据同步任务已就绪 (ID: ${data.task_id})`, 'success');
          startLogPolling(data.task_id);
        } else {
          addLog(`⚠️ 同步提示: ${data.message || '任务冲突'}`, 'warn');
          isRunning.value = false;
        }
      } catch (err) {
        addLog(`❌ 同步失败: ${err}`, 'error');
        isRunning.value = false;
      }
    };

    const startLogPolling = (taskId, callback = null) => {
      if (logPollTimer) clearInterval(logPollTimer);
      logPollTimer = setInterval(async () => {
        try {
          const res = await fetch(`/api/pipeline/logs/${taskId}`);
          if (res.ok) {
            const data = await res.json();
            if (data.logs && data.logs.length > 0) {
              terminalLogs.value = data.logs;
              if (autoScroll.value) {
                nextTick(() => {
                  const elem = document.getElementById('terminal-logs-window');
                  if (elem) elem.scrollTop = elem.scrollHeight;
                });
              }
            }
            if (data.status === 'SUCCESS' || data.status === 'FAILED' || data.status === 'ERROR') {
              clearInterval(logPollTimer);
              isRunning.value = false;
              addLog(`🏁 任务【${data.title || taskId}】已结束，状态: ${data.status}`, data.status === 'SUCCESS' ? 'success' : 'error');
              fetchSystemStatus();
              fetchPrediction();
              fetchMatrixData();
              fetchHistoryTrends();
              fetchHistoryTable(1);
              fetchJingleSummary();
              fetchSpatialPointsSummary();
              fetchSpatialPointsMatrix();
              fetchSpatialPointsReview(pointsReviewPeriods.value);
              fetchJingleSummary();
              fetchJingleReview();
              if (typeof callback === 'function') {
                try {
                  await callback();
                } catch (cbErr) {
                  console.error('任务完成回调异常:', cbErr);
                }
              }
            }
          }
        } catch (e) {
          console.error('轮询日志失败:', e);
        }
      }, 1500);
    };

    const pollTaskLogs = startLogPolling;

    const addLog = (msg, type = 'info') => {
      const timeStr = new Date().toLocaleTimeString();
      terminalLogs.value.push(`[${timeStr}] ${msg}`);
      if (autoScroll.value) {
        nextTick(() => {
          const elem = document.getElementById('terminal-logs-window');
          if (elem) elem.scrollTop = elem.scrollHeight;
        });
      }
    };

    const clearLogs = () => {
      terminalLogs.value = [];
    };

    // ──────────────── 参数调优 ────────────────

    const normalizeWeights = () => {
      const total = modelParams.EF + modelParams.RW + modelParams.FO;
      if (total > 0) {
        modelParams.EF = parseFloat((modelParams.EF / total).toFixed(2));
        modelParams.RW = parseFloat((modelParams.RW / total).toFixed(2));
        modelParams.FO = parseFloat((1.0 - modelParams.EF - modelParams.RW).toFixed(2));
      }
      updateRadarChart();
    };

    const saveParams = async () => {
      try {
        const res = await fetch('/api/config/params', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            EF: modelParams.EF,
            RW: modelParams.RW,
            FO: modelParams.FO
          })
        });
        const data = await res.json();
        if (res.ok) {
          paramSaveMsg.value = '✅ 权重参数更新成功！';
          addLog(`⚙️ 操盘手已更新权重参数: EF(蹭热度)=${modelParams.EF}, RW(抓冷门)=${modelParams.RW}, FO(找周期)=${modelParams.FO}`, 'success');
          setTimeout(() => { paramSaveMsg.value = ''; }, 3000);
        } else {
          paramSaveMsg.value = `❌ 错误: ${data.detail || '保存失败'}`;
        }
      } catch (err) {
        paramSaveMsg.value = `❌ 请求异常: ${err}`;
      }
    };

    // ──────────────── ECharts 多主题配色引擎 ────────────────

    const getThemeColors = () => {
      const isLight = currentTheme.value === 'theme-light';
      switch (currentTheme.value) {
        case 'theme-gold':
          return {
            textColor: '#d1c7b7',
            axisColor: 'rgba(245, 158, 11, 0.25)',
            splitColor: 'rgba(245, 158, 11, 0.08)',
            primary: '#f59e0b',
            secondary: '#fbbf24',
            accent: '#d97706',
            tooltipBg: 'rgba(18, 20, 26, 0.95)'
          };
        case 'theme-aurora':
          return {
            textColor: '#d8b4fe',
            axisColor: 'rgba(192, 132, 252, 0.25)',
            splitColor: 'rgba(192, 132, 252, 0.08)',
            primary: '#c084fc',
            secondary: '#f472b6',
            accent: '#2dd4bf',
            tooltipBg: 'rgba(20, 14, 42, 0.95)'
          };
        case 'theme-emerald':
          return {
            textColor: '#a7f3d0',
            axisColor: 'rgba(16, 185, 129, 0.25)',
            splitColor: 'rgba(16, 185, 129, 0.08)',
            primary: '#10b981',
            secondary: '#34d399',
            accent: '#a3e635',
            tooltipBg: 'rgba(8, 28, 18, 0.95)'
          };
        case 'theme-midnight':
          return {
            textColor: '#cbd5e1',
            axisColor: 'rgba(255, 255, 255, 0.2)',
            splitColor: 'rgba(255, 255, 255, 0.06)',
            primary: '#38bdf8',
            secondary: '#ffffff',
            accent: '#818cf8',
            tooltipBg: 'rgba(20, 20, 20, 0.95)'
          };
        case 'theme-light':
          return {
            textColor: '#334155',
            axisColor: 'rgba(15, 23, 42, 0.15)',
            splitColor: 'rgba(15, 23, 42, 0.06)',
            primary: '#0284c7',
            secondary: '#d97706',
            accent: '#7c3aed',
            tooltipBg: 'rgba(255, 255, 255, 0.95)'
          };
        case 'theme-cyber':
        default:
          return {
            textColor: '#94a3b8',
            axisColor: 'rgba(6, 182, 212, 0.25)',
            splitColor: 'rgba(6, 182, 212, 0.06)',
            primary: '#00f0ff',
            secondary: '#f59e0b',
            accent: '#a855f7',
            tooltipBg: 'rgba(14, 20, 36, 0.95)'
          };
      }
    };

    const initCharts = () => {
      const radarElem = document.getElementById('radar-chart');
      if (radarElem) radarChart = echarts.init(radarElem);
      const radarTabElem = document.getElementById('radar-chart-tab');
      if (radarTabElem) radarChartTab = echarts.init(radarTabElem);

      const trendElem = document.getElementById('trend-chart');
      if (trendElem) trendChart = echarts.init(trendElem);
      const trendTabElem = document.getElementById('trend-chart-tab');
      if (trendTabElem) trendChartTab = echarts.init(trendTabElem);

      const tailElem = document.getElementById('tail-chart');
      if (tailElem) tailChart = echarts.init(tailElem);
      const tailTabElem = document.getElementById('tail-chart-tab');
      if (tailTabElem) tailChartTab = echarts.init(tailTabElem);

      const zoneElem = document.getElementById('zone-chart');
      if (zoneElem) zoneChart = echarts.init(zoneElem);
      const zoneTabElem = document.getElementById('zone-chart-tab');
      if (zoneTabElem) zoneChartTab = echarts.init(zoneTabElem);

      const trendDistElem = document.getElementById('lottery-trend-dist-chart');
      if (trendDistElem) trendDistChart = echarts.init(trendDistElem);
      const trendSumOddElem = document.getElementById('lottery-trend-sum-odd-chart');
      if (trendSumOddElem) trendSumOddChart = echarts.init(trendSumOddElem);

      window.addEventListener('resize', handleResize);
    };

    const updateAllCharts = () => {
      updateRadarChart();
      if (trendStats.value) updateTrendChart(trendStats.value);
      if (tailStats.value) updateTailChart(tailStats.value);
      if (zoneStats.value) updateZoneChart(zoneStats.value);
      if (trendData.value && trendData.value.ball_stats && trendData.value.ball_stats.length > 0) {
        updateTrendDistChart();
        updateTrendSumOddChart();
      }
    };

    const handleResize = () => {
      if (radarChart) radarChart.resize();
      if (radarChartTab) radarChartTab.resize();
      if (trendChart) trendChart.resize();
      if (trendChartTab) trendChartTab.resize();
      if (tailChart) tailChart.resize();
      if (tailChartTab) tailChartTab.resize();
      if (zoneChart) zoneChart.resize();
      if (zoneChartTab) zoneChartTab.resize();
      if (trendDistChart) trendDistChart.resize();
      if (trendSumOddChart) trendSumOddChart.resize();
    };

    const updateRadarChart = () => {
      const tc = getThemeColors();
      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        radar: {
          indicator: [
            { name: 'EF 蹭热度 (能量场)', max: 100 },
            { name: 'RW 抓冷门 (遗漏回补)', max: 100 },
            { name: 'FO 找周期 (谐波)', max: 100 },
            { name: 'MK 找跟班 (关联度)', max: 100 },
            { name: '香农熵补偿 (扎堆/分散)', max: 100 }
          ],
          shape: 'polygon',
          splitNumber: 4,
          axisName: { color: tc.primary, fontSize: 12, fontWeight: 600 },
          splitLine: { lineStyle: { color: tc.splitColor } },
          splitArea: {
            show: true,
            areaStyle: {
              color: [tc.splitColor, tc.splitColor, tc.splitColor, tc.splitColor]
            }
          },
          axisLine: { lineStyle: { color: tc.axisColor } }
        },
        series: [{
          name: '三维融合量化动能',
          type: 'radar',
          data: [{
            value: [
              Math.round(modelParams.EF * 200),
              Math.round(modelParams.RW * 200),
              Math.round(modelParams.FO * 200),
              75,
              80
            ],
            name: '当前模型赋能',
            symbol: 'circle',
            symbolSize: 6,
            itemStyle: { color: tc.primary },
            areaStyle: {
              color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
                { offset: 0, color: tc.primary + '99' },
                { offset: 1, color: tc.secondary + '26' }
              ])
            },
            lineStyle: { width: 2.5, color: tc.primary }
          }]
        }]
      };

      const elem1 = document.getElementById('radar-chart');
      if (elem1) {
        if (!radarChart || radarChart.isDisposed()) radarChart = echarts.init(elem1);
        radarChart.setOption(option, true);
      }
      const elem2 = document.getElementById('radar-chart-tab');
      if (elem2) {
        if (!radarChartTab || radarChartTab.isDisposed()) radarChartTab = echarts.init(elem2);
        radarChartTab.setOption(option, true);
      }
    };

    const updateTrendChart = (data) => {
      if (!data || !data.periods) return;
      const tc = getThemeColors();
      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        legend: {
          data: ['Top 5 命中数', 'Top 12 命中数', '基准均线 (Top5: 2码)'],
          textStyle: { color: tc.textColor },
          top: 0
        },
        grid: { left: '3%', right: '4%', bottom: '8%', top: '18%', containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: data.periods.map(p => p.slice(-3) + '期'),
          axisLine: { lineStyle: { color: tc.axisColor } },
          axisLabel: { color: tc.textColor, fontSize: 11 }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 8,
          splitLine: { lineStyle: { color: tc.splitColor } },
          axisLabel: { color: tc.textColor }
        },
        series: [
          {
            name: 'Top 5 命中数',
            type: 'line',
            smooth: true,
            data: data.top5_hits,
            itemStyle: { color: tc.secondary },
            lineStyle: { width: 3, shadowColor: tc.secondary + '80', shadowBlur: 10 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: tc.secondary + '55' },
                { offset: 1, color: tc.secondary + '00' }
              ])
            }
          },
          {
            name: 'Top 12 命中数',
            type: 'line',
            smooth: true,
            data: data.top12_hits,
            itemStyle: { color: tc.primary },
            lineStyle: { width: 2, shadowColor: tc.primary + '80', shadowBlur: 8 }
          },
          {
            name: '基准均线 (Top5: 2码)',
            type: 'line',
            data: data.periods.map(() => 2),
            lineStyle: { type: 'dashed', color: tc.accent, width: 1.5 },
            symbol: 'none'
          }
        ]
      };

      const elem1 = document.getElementById('trend-chart');
      if (elem1) {
        if (!trendChart || trendChart.isDisposed()) trendChart = echarts.init(elem1);
        trendChart.setOption(option, true);
      }
      const elem2 = document.getElementById('trend-chart-tab');
      if (elem2) {
        if (!trendChartTab || trendChartTab.isDisposed()) trendChartTab = echarts.init(elem2);
        trendChartTab.setOption(option, true);
      }
    };

    const updateTailChart = (tails) => {
      if (!tails || tails.length === 0) return;
      const tc = getThemeColors();
      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        grid: { left: '3%', right: '3%', bottom: '5%', top: '15%', containLabel: true },
        xAxis: {
          type: 'category',
          data: tails.map(t => '尾' + t.tail),
          axisLine: { lineStyle: { color: tc.axisColor } },
          axisLabel: { color: tc.textColor }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 6,
          splitLine: { lineStyle: { color: tc.splitColor } },
          axisLabel: { color: tc.textColor }
        },
        series: [{
          name: '最新期出现次数',
          type: 'bar',
          data: tails.map(t => {
            let color = tc.primary;
            if (t.count === 0) color = '#ef4444';
            else if (t.count >= 4) color = tc.secondary;
            return {
              value: t.count,
              itemStyle: { color: color, borderRadius: [4, 4, 0, 0] }
            };
          }),
          barWidth: '55%'
        }]
      };

      const elem1 = document.getElementById('tail-chart');
      if (elem1) {
        if (!tailChart || tailChart.isDisposed()) tailChart = echarts.init(elem1);
        tailChart.setOption(option, true);
      }
      const elem2 = document.getElementById('tail-chart-tab');
      if (elem2) {
        if (!tailChartTab || tailChartTab.isDisposed()) tailChartTab = echarts.init(elem2);
        tailChartTab.setOption(option, true);
      }
    };

    const updateZoneChart = (zones) => {
      if (!zones || zones.length === 0) return;
      const tc = getThemeColors();
      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        series: [{
          name: '区间出号分布',
          type: 'pie',
          radius: ['45%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 6, borderColor: 'transparent', borderWidth: 2 },
          label: {
            show: true,
            color: tc.textColor,
            fontSize: 11,
            formatter: '{b}: {c}个'
          },
          data: zones.map((z, idx) => {
            const colors = [tc.primary, tc.secondary, tc.accent, '#10b981'];
            return {
              value: z.count,
              name: z.zone.split(' ')[0],
              itemStyle: { color: colors[idx % colors.length] }
            };
          })
        }]
      };

      const elem1 = document.getElementById('zone-chart');
      if (elem1) {
        if (!zoneChart || zoneChart.isDisposed()) zoneChart = echarts.init(elem1);
        zoneChart.setOption(option, true);
      }
      const elem2 = document.getElementById('zone-chart-tab');
      if (elem2) {
        if (!zoneChartTab || zoneChartTab.isDisposed()) zoneChartTab = echarts.init(elem2);
        zoneChartTab.setOption(option, true);
      }
    };

    const updateTrendDistChart = () => {
      if (!trendData.value || !trendData.value.ball_stats || trendData.value.ball_stats.length === 0) return;
      const tc = getThemeColors();
      const stats = trendData.value.ball_stats;
      const totalP = trendData.value.summary?.total_periods || trendLimit.value;
      const expectedAvg = (totalP * 0.25).toFixed(1);

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor },
          formatter: (params) => {
            const p = params[0];
            const ball = stats[p.dataIndex];
            if (!ball) return '';
            const zoneNames = ['', '一区(01-20)', '二区(21-40)', '三区(41-60)', '四区(61-80)'];
            return `<div style="font-weight:bold;color:${tc.primary};margin-bottom:4px;">号码 ${ball.display} · ${zoneNames[ball.zone]}</div>
                    <div style="font-size:12px;line-height:1.6;">
                      <div>📊 出号频次: <b style="color:${tc.secondary};">${ball.frequency}</b> 次 (占比 ${ball.frequency_rate}%)</div>
                      <div>🎯 理论均值: <b>${expectedAvg}</b> 次</div>
                      <div>❄️ 最大遗漏: <b>${ball.max_omission}</b> 期</div>
                      <div>📉 平均遗漏: <b>${ball.avg_omission}</b> 期</div>
                      <div>🔥 最大连出: <b>${ball.max_consecutive}</b> 期</div>
                      <div>⏳ 当前遗漏: <b>${ball.current_omission}</b> 期</div>
                    </div>`;
          }
        },
        grid: { left: '3%', right: '3%', bottom: '8%', top: '16%', containLabel: true },
        xAxis: {
          type: 'category',
          data: stats.map(b => b.display),
          axisLine: { lineStyle: { color: tc.axisColor } },
          axisLabel: { color: tc.textColor, interval: 1, fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          name: '出现次数',
          nameTextStyle: { color: tc.textColor, fontSize: 11 },
          splitLine: { lineStyle: { color: tc.splitColor } },
          axisLabel: { color: tc.textColor }
        },
        series: [{
          name: '出现次数',
          type: 'bar',
          data: stats.map(b => {
            let color = tc.primary;
            if (b.zone === 1) color = '#06b6d4';
            else if (b.zone === 2) color = '#f59e0b';
            else if (b.zone === 3) color = '#a855f7';
            else if (b.zone === 4) color = '#10b981';
            return {
              value: b.frequency,
              itemStyle: { color: color, borderRadius: [2, 2, 0, 0] }
            };
          }),
          barWidth: '60%',
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
            data: [{ yAxis: parseFloat(expectedAvg), name: '理论平均线' }],
            label: { color: '#ef4444', formatter: `理论均线: ${expectedAvg}次`, position: 'insideEndTop' }
          }
        }]
      };

      const elem = document.getElementById('lottery-trend-dist-chart');
      if (elem) {
        if (!trendDistChart || trendDistChart.isDisposed()) trendDistChart = echarts.init(elem);
        trendDistChart.setOption(option, true);
      }
    };

    const updateTrendSumOddChart = () => {
      if (!trendData.value || !trendData.value.draws || trendData.value.draws.length === 0) return;
      const tc = getThemeColors();
      const draws = trendData.value.draws;

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        legend: {
          data: ['和值走势 (左轴)', '单数(奇数)个数 (右轴)'],
          textStyle: { color: tc.textColor },
          top: 0
        },
        grid: { left: '3%', right: '4%', bottom: '8%', top: '16%', containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: draws.map(d => d.period.slice(-3) + '期'),
          axisLine: { lineStyle: { color: tc.axisColor } },
          axisLabel: { color: tc.textColor, fontSize: 10 }
        },
        yAxis: [
          {
            type: 'value',
            name: '和值',
            nameTextStyle: { color: tc.textColor, fontSize: 11 },
            min: 500,
            max: 1150,
            splitLine: { lineStyle: { color: tc.splitColor } },
            axisLabel: { color: tc.textColor }
          },
          {
            type: 'value',
            name: '奇数个数',
            nameTextStyle: { color: tc.textColor, fontSize: 11 },
            min: 0,
            max: 20,
            splitLine: { show: false },
            axisLabel: { color: tc.textColor }
          }
        ],
        series: [
          {
            name: '和值走势 (左轴)',
            type: 'line',
            smooth: true,
            yAxisIndex: 0,
            data: draws.map(d => d.sum),
            itemStyle: { color: tc.secondary },
            lineStyle: { width: 2.5, color: tc.secondary },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: tc.secondary + '33' },
                { offset: 1, color: tc.secondary + '00' }
              ])
            }
          },
          {
            name: '单数(奇数)个数 (右轴)',
            type: 'line',
            smooth: true,
            yAxisIndex: 1,
            data: draws.map(d => d.odd_count),
            itemStyle: { color: tc.primary },
            lineStyle: { width: 2, color: tc.primary }
          }
        ]
      };

      const elem = document.getElementById('lottery-trend-sum-odd-chart');
      if (elem) {
        if (!trendSumOddChart || trendSumOddChart.isDisposed()) trendSumOddChart = echarts.init(elem);
        trendSumOddChart.setOption(option, true);
      }
    };

    // ──────────────── 辅助计算与衍生视图 ────────────────

    const filteredMatrix = computed(() => {
      if (activeFilter.value === 'all') return matrixData.value;
      if (activeFilter.value === 'top5') return matrixData.value.filter(b => b.is_top5);
      if (activeFilter.value === 'top12') return matrixData.value.filter(b => b.is_top12);
      if (activeFilter.value === 'cold') return matrixData.value.filter(b => b.omission >= 6);
      if (activeFilter.value === 'hot') return matrixData.value.filter(b => b.freq_30 >= 8);
      return matrixData.value;
    });

    const purePoolDetailed = computed(() => {
      const pool = prediction.value?.pure_pool || [];
      return pool.map(num => {
        const found = matrixData.value.find(b => b.number === num);
        if (found) {
          return {
            ...found,
            display: String(num).padStart(2, '0')
          };
        }
        return {
          number: num,
          display: String(num).padStart(2, '0'),
          tag: '纯净金胆',
          omission: '-',
          freq_30: '-',
          energy: '-'
        };
      });
    });

    const top12Detailed = computed(() => {
      const pool = prediction.value?.top12_pool || [];
      const top5 = prediction.value?.top5_gold || [];
      const he5 = prediction.value?.hidden_energy_5 || [];
      return pool.map((num, idx) => {
        const found = matrixData.value.find(b => b.number === num) || {};
        return {
          rank: idx + 1,
          number: num,
          display: String(num).padStart(2, '0'),
          energy: found.energy || '-',
          zone: found.zone || Math.floor((num - 1) / 20) + 1,
          tail: found.tail !== undefined ? found.tail : (num % 10),
          omission: found.omission !== undefined ? found.omission : '-',
          freq_30: found.freq_30 !== undefined ? found.freq_30 : '-',
          is_gold: top5.includes(num),
          is_he5: he5.includes(num),
          ...found
        };
      });
    });

    const trendDetailedList = computed(() => {
      if (!trendStats.value || !trendStats.value.periods) return [];
      const list = [];
      const p = trendStats.value.periods;
      for (let i = 0; i < p.length; i++) {
        list.push({
          period: p[i],
          date: trendStats.value.dates ? trendStats.value.dates[i] : '---',
          top5_hit: trendStats.value.top5_hits ? trendStats.value.top5_hits[i] : 0,
          top12_hit: trendStats.value.top12_hits ? trendStats.value.top12_hits[i] : 0,
          sum: trendStats.value.draw_sums ? trendStats.value.draw_sums[i] : '---',
          odd_ratio: trendStats.value.odd_ratios ? ((trendStats.value.odd_ratios[i] * 100).toFixed(0) + '%') : '---'
        });
      }
      return list.reverse();
    });

    const tailsWithBalls = computed(() => {
      const result = [];
      const latestDraw = systemStatus.value?.latest_draw_numbers || [];
      const top5 = prediction.value?.top5_gold || [];
      const top12 = prediction.value?.top12_pool || [];

      for (let t = 0; t <= 9; t++) {
        const tailStat = tailStats.value.find(s => s.tail === t) || { count: 0, status: '平稳' };
        const balls = [];
        for (let i = 1; i <= 80; i++) {
          if (i % 10 === t) {
            const found = matrixData.value.find(b => b.number === i) || {};
            balls.push({
              number: i,
              display: String(i).padStart(2, '0'),
              omission: found.omission !== undefined ? found.omission : (latestDraw.includes(i) ? 0 : '-'),
              is_hit_latest: latestDraw.includes(i) || found.omission === 0,
              is_top5: top5.includes(i) || found.is_top5,
              is_top12: top12.includes(i) || found.is_top12,
              ...found
            });
          }
        }
        result.push({
          tail: t,
          count: tailStat.count,
          status: tailStat.status,
          balls: balls
        });
      }
      return result;
    });

    // ──────────────── 顺口溜口诀规则与对账状态 ────────────────
    const jingleSummary = ref(null);
    const jingleReview = ref(null);
    const jingleRules = ref([]);
    const jingleRulesMeta = ref({});
    const jingleRuleKindFilter = ref('all');
    const jingleRuleSearchKeyword = ref('');
    const jingleLoading = ref(false);

    const fetchJingleSummary = async () => {
      try {
        const res = await fetch('/api/jingle/summary');
        if (res.ok) {
          jingleSummary.value = await res.json();
        }
      } catch (err) {
        console.error('Failed to fetch jingle summary:', err);
      }
    };

    const fetchJingleReview = async (n = 30) => {
      try {
        jingleLoading.value = true;
        const res = await fetch(`/api/jingle/review?n=${n}`);
        if (res.ok) {
          jingleReview.value = await res.json();
        }
      } catch (err) {
        console.error('Failed to fetch jingle review:', err);
      } finally {
        jingleLoading.value = false;
      }
    };

    const fetchJingleRules = async () => {
      try {
        const res = await fetch('/api/jingle/rules');
        if (res.ok) {
          const data = await res.json();
          if (data && data.status === 'ok') {
            jingleRules.value = data.rules || [];
            jingleRulesMeta.value = data.meta || {};
          }
        }
      } catch (err) {
        console.error('Failed to fetch jingle rules:', err);
      }
    };

    const triggerJingleRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        terminalLogs.value = [];
        addLog('🚀 顺口溜口诀全流程推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-jingle', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchJingleSummary();
            await fetchJingleReview();
            addLog('✨ 顺口溜口诀数据与预测已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动顺口溜任务失败: ' + err.message, 'danger');
      }
    };

    const filteredJingleRules = computed(() => {
      let list = jingleRules.value || [];
      if (jingleRuleKindFilter.value !== 'all') {
        list = list.filter(r => r.kind === jingleRuleKindFilter.value);
      }
      if (jingleRuleSearchKeyword.value && jingleRuleSearchKeyword.value.trim()) {
        const kw = jingleRuleSearchKeyword.value.trim();
        list = list.filter(r => {
          const trgStr = (r.trigger || []).map(x => String(x).padStart(2, '0')).join(' ');
          const predStr = (r.predict || []).map(x => String(x).padStart(2, '0')).join(' ');
          return trgStr.includes(kw) || predStr.includes(kw) || String(r.rule_id).includes(kw);
        });
      }
      return list;
    });

    // ──────────────── 空间重点点位分析状态 ────────────────
    const spatialPointsSummary = ref(null);
    const spatialPointsMatrix = ref([]);
    const spatialPointsReview = ref(null);
    const spatialPointsLoading = ref(false);
    const pointsMatrixFilter = ref('all');
    const pointsReviewPeriods = ref(30);

    const filteredPointsMatrix = computed(() => {
      let list = spatialPointsMatrix.value || [];
      if (pointsMatrixFilter.value === 'core5') {
        list = list.filter(b => b.tier === 'Core5');
      } else if (pointsMatrixFilter.value === 'top10') {
        list = list.filter(b => b.tier === 'Core5' || b.tier === 'Top10');
      } else if (pointsMatrixFilter.value === 'ext15') {
        list = list.filter(b => b.tier === 'Core5' || b.tier === 'Top10' || b.tier === 'Ext15');
      } else if (pointsMatrixFilter.value === 'sig') {
        list = list.filter(b => b.is_significant);
      }
      return list;
    });

    const fetchSpatialPointsSummary = async () => {
      try {
        const res = await fetch('/api/spatial-points/summary');
        if (res.ok) {
          spatialPointsSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取空间重点点位摘要失败:', err);
      }
    };

    const fetchSpatialPointsMatrix = async () => {
      try {
        const res = await fetch('/api/spatial-points/matrix');
        if (res.ok) {
          const data = await res.json();
          spatialPointsMatrix.value = data.matrix || [];
        }
      } catch (err) {
        console.error('获取空间重点点位矩阵失败:', err);
      }
    };

    const fetchSpatialPointsReview = async (n = 30) => {
      try {
        spatialPointsLoading.value = true;
        pointsReviewPeriods.value = n;
        const res = await fetch(`/api/spatial-points/review?n=${n}`);
        if (res.ok) {
          spatialPointsReview.value = await res.json();
        }
      } catch (err) {
        console.error('获取空间重点点位复盘失败:', err);
      } finally {
        spatialPointsLoading.value = false;
      }
    };

    const triggerSpatialPointsRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        terminalLogs.value = [];
        addLog('🚀 空间重点点位全量推演流水线任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-spatial-points', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchSpatialPointsSummary();
            await fetchSpatialPointsMatrix();
            await fetchSpatialPointsReview(pointsReviewPeriods.value);
            addLog('✨ 空间重点点位推演与精排已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动空间重点点位推演失败: ' + err.message, 'danger');
      }
    };

    // ──────────────── 跟随分析 (重复号追踪与多窗条件跟随) 状态 ────────────────
    const followSummary = ref(null);
    const followReview = ref(null);
    const followConditions = ref(null);
    const followLoading = ref(false);
    const followReviewPeriods = ref(30);

    const fetchFollowSummary = async () => {
      try {
        const res = await fetch('/api/follow/summary');
        if (res.ok) {
          followSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取跟随分析摘要失败:', err);
      }
    };

    const fetchFollowReview = async (n = 30) => {
      try {
        followLoading.value = true;
        followReviewPeriods.value = n;
        const res = await fetch(`/api/follow/review?n=${n}`);
        if (res.ok) {
          followReview.value = await res.json();
        }
      } catch (err) {
        console.error('获取跟随分析复盘失败:', err);
      } finally {
        followLoading.value = false;
      }
    };

    const fetchFollowConditions = async () => {
      try {
        const res = await fetch('/api/follow/conditions');
        if (res.ok) {
          followConditions.value = await res.json();
        }
      } catch (err) {
        console.error('获取跟随分析条件明细失败:', err);
      }
    };

    const triggerFollowRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        terminalLogs.value = [];
        addLog('🚀 跟随分析(重复号追踪与多窗条件跟随)推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-follow', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchFollowSummary();
            await fetchFollowReview(followReviewPeriods.value);
            await fetchFollowConditions();
            addLog('✨ 跟随分析推演与复盘流水已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动跟随分析推演失败: ' + err.message, 'danger');
      }
    };

    // ──────────────── 未开点位反弹追踪 (Point Suppression Engine) 状态 ────────────────
    const suppressionSummary = ref(null);
    const suppressionReview = ref(null);
    const suppressionPatterns = ref(null);
    const suppressionLoading = ref(false);
    const suppressionReviewPeriods = ref(30);

    const fetchSuppressionSummary = async () => {
      try {
        const res = await fetch('/api/suppression/summary');
        if (res.ok) {
          suppressionSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取未开点位反弹摘要失败:', err);
      }
    };

    const fetchSuppressionReview = async (n = 30) => {
      try {
        suppressionLoading.value = true;
        suppressionReviewPeriods.value = n;
        const res = await fetch(`/api/suppression/review?n=${n}`);
        if (res.ok) {
          suppressionReview.value = await res.json();
        }
      } catch (err) {
        console.error('获取未开点位反弹复盘流水失败:', err);
      } finally {
        suppressionLoading.value = false;
      }
    };

    const fetchSuppressionPatterns = async () => {
      try {
        const res = await fetch('/api/suppression/patterns');
        if (res.ok) {
          suppressionPatterns.value = await res.json();
        }
      } catch (err) {
        console.error('获取影子替身与能量外溢模式失败:', err);
      }
    };

    const triggerSuppressionRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        terminalLogs.value = [];
        addLog('🚀 未开点位高压反弹与空间关联推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-suppression', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchSuppressionSummary();
            await fetchSuppressionReview(suppressionReviewPeriods.value);
            await fetchSuppressionPatterns();
            addLog('✨ 未开点位反弹追踪与影子替身数据已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动未开点位反弹推演失败: ' + err.message, 'danger');
      }
    };

    // ──────────────── 13. KillSeeker 杀号决策核心状态与方法 ────────────────
    const killSummary = ref(null);
    const killReview = ref(null);
    const killLogs = ref([]);
    const selectedKillLog = ref(null);
    const killLogDetail = ref('');
    const killLoading = ref(false);
    const killReviewPeriods = ref(30);

    const fetchKillSummary = async () => {
      try {
        const res = await fetch('/api/kill/summary');
        if (res.ok) {
          killSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取KillSeeker杀号摘要失败:', err);
      }
    };

    const fetchKillReview = async (n = 30) => {
      try {
        killLoading.value = true;
        killReviewPeriods.value = n;
        const res = await fetch(`/api/kill/review?n=${n}`);
        if (res.ok) {
          killReview.value = await res.json();
        }
      } catch (err) {
        console.error('获取KillSeeker杀号复盘失败:', err);
      } finally {
        killLoading.value = false;
      }
    };

    const fetchKillLogs = async () => {
      try {
        const res = await fetch('/api/kill/logs');
        if (res.ok) {
          killLogs.value = await res.json();
          if (killLogs.value && killLogs.value.length > 0 && !selectedKillLog.value) {
            selectKillLog(killLogs.value[0]);
          }
        }
      } catch (err) {
        console.error('获取KillSeeker日志列表失败:', err);
      }
    };

    const selectKillLog = async (item) => {
      selectedKillLog.value = item;
      try {
        const res = await fetch(`/api/kill/log-detail/${item.filename}`);
        if (res.ok) {
          const data = await res.json();
          if (window.marked) {
            killLogDetail.value = marked.parse(data.content || '');
          } else {
            killLogDetail.value = data.content || '';
          }
        }
      } catch (err) {
        console.error('获取KillSeeker日志详情失败:', err);
        killLogDetail.value = '加载日志失败: ' + err.message;
      }
    };

    const triggerKillRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        terminalLogs.value = [];
        addLog('⚔️ KillSeeker 杀号全流程推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-kill', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchKillSummary();
            await fetchKillReview(killReviewPeriods.value);
            await fetchKillLogs();
            addLog('✨ KillSeeker 杀号推演数据已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动KillSeeker杀号推演失败: ' + err.message, 'danger');
      }
    };

    // ──────────────── 14. Gemini 选2预测核心状态与方法 ────────────────
    const geminiSummary = ref(null);
    const geminiReview = ref(null);
    const geminiHistory = ref([]);
    const selectedGeminiReport = ref(null);
    const geminiReportDetail = ref('');
    const geminiLoading = ref(false);
    const geminiReviewPeriods = ref(30);

    const fetchGeminiSummary = async () => {
      try {
        const res = await fetch('/api/gemini/summary');
        if (res.ok) {
          geminiSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取Gemini选2摘要失败:', err);
      }
    };

    const fetchGeminiReview = async (n = 30) => {
      try {
        geminiLoading.value = true;
        geminiReviewPeriods.value = n;
        const res = await fetch(`/api/gemini/review?n=${n}`);
        if (res.ok) {
          geminiReview.value = await res.json();
        }
      } catch (err) {
        console.error('获取Gemini选2复盘失败:', err);
      } finally {
        geminiLoading.value = false;
      }
    };

    const fetchGeminiHistory = async () => {
      try {
        const res = await fetch('/api/gemini/history');
        if (res.ok) {
          geminiHistory.value = await res.json();
          if (geminiHistory.value && geminiHistory.value.length > 0 && !selectedGeminiReport.value) {
            selectGeminiReport(geminiHistory.value[0]);
          }
        }
      } catch (err) {
        console.error('获取Gemini选2历史研报失败:', err);
      }
    };

    const selectGeminiReport = async (item) => {
      selectedGeminiReport.value = item;
      try {
        const res = await fetch(`/api/gemini/history-detail/${item.filename}`);
        if (res.ok) {
          const data = await res.json();
          geminiReportDetail.value = data.content || '';
        }
      } catch (err) {
        console.error('获取Gemini研报详情失败:', err);
        geminiReportDetail.value = '加载研报失败: ' + err.message;
      }
    };

    const triggerGeminiRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        terminalLogs.value = [];
        addLog('💎 Gemini 选2全流程量化推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-gemini', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchGeminiSummary();
            await fetchGeminiReview(geminiReviewPeriods.value);
            await fetchGeminiHistory();
            addLog('✨ Gemini 选2预测数据已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动Gemini选2推演失败: ' + err.message, 'danger');
      }
    };

    // ──────────────── 15. 定金选2决策 核心状态与方法 ────────────────
    const goldPick2Summary = ref(null);
    const goldPick2Review = ref(null);
    const goldPick2Matrix = ref(null);
    const goldPick2Logs = ref([]);
    const selectedGoldPick2Log = ref(null);
    const goldPick2LogDetail = ref('');
    const goldPick2Loading = ref(false);
    const goldPick2ReviewPeriods = ref(30);

    const fetchGoldPick2Summary = async () => {
      try {
        const res = await fetch('/api/gold-pick2/summary');
        if (res.ok) {
          goldPick2Summary.value = await res.json();
        }
      } catch (err) {
        console.error('获取定金选2摘要失败:', err);
      }
    };

    const fetchGoldPick2Review = async (n = 30) => {
      try {
        goldPick2Loading.value = true;
        goldPick2ReviewPeriods.value = n;
        const res = await fetch(`/api/gold-pick2/review?n=${n}`);
        if (res.ok) {
          goldPick2Review.value = await res.json();
        }
      } catch (err) {
        console.error('获取定金选2复盘失败:', err);
      } finally {
        goldPick2Loading.value = false;
      }
    };

    const fetchGoldPick2Matrix = async () => {
      try {
        const res = await fetch('/api/gold-pick2/matrix');
        if (res.ok) {
          goldPick2Matrix.value = await res.json();
        }
      } catch (err) {
        console.error('获取定金选2矩阵失败:', err);
      }
    };

    const fetchGoldPick2Logs = async () => {
      try {
        const res = await fetch('/api/gold-pick2/logs');
        if (res.ok) {
          goldPick2Logs.value = await res.json();
          if (goldPick2Logs.value && goldPick2Logs.value.length > 0 && !selectedGoldPick2Log.value) {
            selectGoldPick2Log(goldPick2Logs.value[0]);
          }
        }
      } catch (err) {
        console.error('获取定金选2研报清单失败:', err);
      }
    };

    const selectGoldPick2Log = async (item) => {
      selectedGoldPick2Log.value = item;
      try {
        const res = await fetch(`/api/gold-pick2/log-detail/${item.filename}`);
        if (res.ok) {
          const data = await res.json();
          goldPick2LogDetail.value = data.content || '';
        }
      } catch (err) {
        console.error('获取定金选2研报详情失败:', err);
        goldPick2LogDetail.value = '加载研报失败: ' + err.message;
      }
    };

    const triggerGoldPick2Run = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        terminalLogs.value = [];
        addLog('💎 定金选2全流程决策推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-gold-pick2', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchGoldPick2Summary();
            await fetchGoldPick2Review(goldPick2ReviewPeriods.value);
            await fetchGoldPick2Matrix();
            await fetchGoldPick2Logs();
            addLog('✨ 定金选2预测数据已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动定金选2推演失败: ' + err.message, 'danger');
      }
    };

    // ──────────────── 终审数据汇总复盘 ────────────────
    const aggCockpit = ref({});
    const aggHistory = ref([]);
    const selectedAggReport = ref(null);
    const aggReportDetail = ref('');
    const aggLoading = ref(false);

    const fetchAggCockpit = async () => {
      aggLoading.value = true;
      try {
        const res = await fetch('/api/aggregation/cockpit');
        if (res.ok) {
          aggCockpit.value = await res.json();
        }
      } catch (err) {
        console.error('获取终审数据汇总驾驶舱失败:', err);
      } finally {
        aggLoading.value = false;
      }
    };

    const fetchAggHistory = async () => {
      try {
        const res = await fetch('/api/aggregation/history');
        if (res.ok) {
          const list = await res.json();
          aggHistory.value = list;
          if (list && list.length > 0 && !selectedAggReport.value) {
            selectAggReport(list[0]);
          }
        }
      } catch (err) {
        console.error('获取汇总复盘历史失败:', err);
      }
    };

    const selectAggReport = async (item) => {
      selectedAggReport.value = item;
      try {
        const res = await fetch(`/api/aggregation/history/${item.filename}`);
        if (res.ok) {
          const data = await res.json();
          aggReportDetail.value = data.content || '';
        }
      } catch (err) {
        aggReportDetail.value = '读取战报详情失败: ' + err.message;
      }
    };

    const triggerAggRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal', '流水线黑客日志终端', '💻');
        terminalLogs.value = [];
        addLog('🧬 终审数据汇总复盘 (7路多维共振 + 8区空间平衡) 任务已提交后台...', 'info');
        const res = await fetch('/api/aggregation/run?force=true', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchAggCockpit();
            await fetchAggHistory();
            addLog('✨ 终审数据汇总复盘计算完毕并已自动刷新！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动终审数据汇总失败: ' + err.message, 'danger');
      }
    };

    onMounted(async () => {
      // 初始化当前主题
      document.documentElement.className = currentTheme.value;
      document.body.className = currentTheme.value;

      initCharts();
      await fetchSystemStatus();
      await fetchPrediction();
      await fetchMatrixData();
      await fetchHistoryTrends();
      await fetchLotteryTrends(100);
      await fetchHistoryTable(1);
      await fetchReportList();
      await fetchAggCockpit();
      await fetchAggHistory();
      await fetchJingleSummary();
      await fetchJingleReview(30);
      await fetchJingleRules();
      await fetchSpatialPointsSummary();
      await fetchSpatialPointsMatrix();
      await fetchSpatialPointsReview(30);
      await fetchFollowSummary();
      await fetchFollowReview(30);
      await fetchFollowConditions();
      await fetchSuppressionSummary();
      await fetchSuppressionReview(30);
      await fetchSuppressionPatterns();
      await fetchKillSummary();
      await fetchKillReview(30);
      await fetchKillLogs();
      await fetchGoldPick2Summary();
      await fetchGoldPick2Review(30);
      await fetchGoldPick2Matrix();
      await fetchGoldPick2Logs();
      await fetchGeminiSummary();
      await fetchGeminiReview(30);
      await fetchGeminiHistory();
    });

    onBeforeUnmount(() => {
      if (logPollTimer) clearInterval(logPollTimer);
      window.removeEventListener('resize', handleResize);
    });

    return {
      isSidebarCollapsed,
      themes,
      currentTheme,
      currentThemeObj,
      showThemeDropdown,
      setTheme,
      menuGroups,
      tabs,
      activeTab,
      toggleGroup,
      openTab,
      closeTab,
      closeOtherTabs,
      closeAllTabs,
      systemStatus,
      prediction,
      matrixData,
      tailStats,
      zoneStats,
      trendStats,
      activeFilter,
      // 衍生与视图计算属性
      filteredMatrix,
      purePoolDetailed,
      top12Detailed,
      trendDetailedList,
      tailsWithBalls,
      // 走势图状态与方法
      trendLimit,
      trendCustomInput,
      trendData,
      trendLoading,
      trendShowOmission,
      trendZoneFilter,
      trendViewMode,
      highlightedBall,
      trendSearchBall,
      customPicks,
      toggleCustomPick,
      loadTop5ToCustomPicks,
      loadHiddenEnergyToCustomPicks,
      clearCustomPicks,
      filteredBallColumns,
      getBallStat,
      fetchLotteryTrends,
      fetchHistoryTrends,
      handleCustomLimitSubmit,
      toggleHighlightBall,
      handleSearchBallHighlight,
      // 历史表格与研报
      historyTable,
      reportList,
      currentReport,
      selectedBall,
      showBallModal,
      modelParams,
      paramSaveMsg,
      terminalLogs,
      isRunning,
      autoScroll,
      openBallDetail,
      openReportContent,
      fetchHistoryTable,
      runPipeline,
      syncData,
      clearLogs,
      normalizeWeights,
      saveParams,
      // 顺口溜口诀
      jingleSummary,
      jingleReview,
      jingleRules,
      jingleRulesMeta,
      jingleRuleKindFilter,
      jingleRuleSearchKeyword,
      jingleLoading,
      filteredJingleRules,
      fetchJingleSummary,
      fetchJingleReview,
      fetchJingleRules,
      triggerJingleRun,
      // 空间重点点位分析
      spatialPointsSummary,
      spatialPointsMatrix,
      spatialPointsReview,
      spatialPointsLoading,
      pointsMatrixFilter,
      pointsReviewPeriods,
      filteredPointsMatrix,
      fetchSpatialPointsSummary,
      fetchSpatialPointsMatrix,
      fetchSpatialPointsReview,
      triggerSpatialPointsRun,
      // 跟随分析
      followSummary,
      followReview,
      followConditions,
      followLoading,
      followReviewPeriods,
      fetchFollowSummary,
      fetchFollowReview,
      fetchFollowConditions,
      triggerFollowRun,
      // 未开点位反弹追踪
      suppressionSummary,
      suppressionReview,
      suppressionPatterns,
      suppressionLoading,
      suppressionReviewPeriods,
      fetchSuppressionSummary,
      fetchSuppressionReview,
      fetchSuppressionPatterns,
      triggerSuppressionRun,
      // KillSeeker 杀号决策
      killSummary,
      killReview,
      killLogs,
      selectedKillLog,
      killLogDetail,
      killLoading,
      killReviewPeriods,
      fetchKillSummary,
      fetchKillReview,
      fetchKillLogs,
      selectKillLog,
      triggerKillRun,
      // 定金选2决策
      goldPick2Summary,
      goldPick2Review,
      goldPick2Matrix,
      goldPick2Logs,
      selectedGoldPick2Log,
      goldPick2LogDetail,
      goldPick2Loading,
      goldPick2ReviewPeriods,
      fetchGoldPick2Summary,
      fetchGoldPick2Review,
      fetchGoldPick2Matrix,
      fetchGoldPick2Logs,
      selectGoldPick2Log,
      triggerGoldPick2Run,
      // Gemini 选2预测
      geminiSummary,
      geminiReview,
      geminiHistory,
      selectedGeminiReport,
      geminiReportDetail,
      geminiLoading,
      geminiReviewPeriods,
      fetchGeminiSummary,
      fetchGeminiReview,
      fetchGeminiHistory,
      selectGeminiReport,
      triggerGeminiRun,
      // 终审数据汇总复盘
      aggCockpit,
      aggHistory,
      selectedAggReport,
      aggReportDetail,
      aggLoading,
      fetchAggCockpit,
      fetchAggHistory,
      selectAggReport,
      triggerAggRun
    };
  }
};

createApp(App).mount('#app');


