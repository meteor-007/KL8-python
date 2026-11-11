/**
 * K8 page module: point_omission
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (point_omission)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

    // ──────────────── 🎯 点位+遗漏号深度分析 (Point & Omission System) 状态与方法 ────────────────
    const pointOmissionSummary = ref(null);
    const pointOmissionReport = ref('');
    const pointOmissionReportHtml = ref('');
    const pointOmissionBacktest = ref(null);
    const pointOmissionHitLedger = ref(null);
    const pointOmissionLoading = ref(false);
    const pointOmissionLedgerLoading = ref(false);
    const pointOmissionSubTab = ref('overview');

    const methodChineseNames = {
      cluster: '连号集群行为',
      cyclic: '周期性波段节奏',
      heatmap: '数字场域能量图',
      markov: '马尔可夫转移矩阵',
      fibonacci: '斐波那契黄金分割',
      linalg_svd: 'SVD协方差共现',
      complex_fft: '复变/Hilbert/FFT',
      graph_net: '图网络关系挖掘',
      volatility: '波动率二项过度离散',
      remainder: '余数空间映射',
      entropy: '号码熵与均衡监控',
      contrarian: '反向心理博弈',
      adversarial: '对抗逐号反证'
    };

    const getMethodChineseName = (key) => methodChineseNames[key] || key;

    const fetchPointOmissionSummary = async (force = false) => {
      try {
        pointOmissionLoading.value = true;
        const res = await axios.get(`/api/point-omission/summary?refresh=${force}`);
        if (res.data && res.data.status === 'ok') {
          pointOmissionSummary.value = res.data.data;
        }
      } catch (err) {
        console.error('获取点位+遗漏概要失败:', err);
      } finally {
        pointOmissionLoading.value = false;
      }
    };

    const fetchPointOmissionReport = async () => {
      try {
        const res = await axios.get('/api/point-omission/report');
        if (res.data && res.data.status === 'ok') {
          pointOmissionReport.value = res.data.content || '';
          if (window.marked && pointOmissionReport.value) {
            pointOmissionReportHtml.value = marked.parse(pointOmissionReport.value);
          } else {
            pointOmissionReportHtml.value = '<pre class="whitespace-pre-wrap font-mono">' + pointOmissionReport.value + '</pre>';
          }
        }
      } catch (err) {
        console.error('获取点位+遗漏研报失败:', err);
      }
    };

    const fetchPointOmissionBacktest = async () => {
      try {
        const res = await axios.get('/api/point-omission/backtest');
        if (res.data && res.data.status === 'ok') {
          pointOmissionBacktest.value = res.data.backtest;
        }
      } catch (err) {
        console.error('获取点位+遗漏回测数据失败:', err);
      }
    };

    const fetchPointOmissionHitLedger = async (n = 40) => {
      try {
        pointOmissionLedgerLoading.value = true;
        const res = await axios.get(`/api/point-omission/hit-ledger?n=${n}`);
        if (res.data && res.data.status === 'ok') {
          pointOmissionHitLedger.value = res.data;
        }
      } catch (err) {
        console.error('获取逐期命中台账失败:', err);
      } finally {
        pointOmissionLedgerLoading.value = false;
      }
    };

    const seedPointOmissionHitLedger = async (n = 40) => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        pointOmissionLedgerLoading.value = true;
        addLog(`📒 开始近 ${n} 期回测灌入逐期命中台账…`, 'info');
        const res = await axios.post(`/api/point-omission/hit-ledger/seed?n=${n}`);
        if (res.data && res.data.status === 'ok') {
          addLog(`✅ 台账灌入完成：写入 ${res.data.written} 期，补全球号 ${res.data.patched}`, 'success');
          await fetchPointOmissionHitLedger(n);
        } else {
          addLog('❌ 台账灌入失败: ' + (res.data?.message || 'unknown'), 'danger');
        }
      } catch (err) {
        addLog('❌ 台账灌入失败: ' + (err.message || err), 'danger');
      } finally {
        isRunning.value = false;
        pointOmissionLedgerLoading.value = false;
      }
    };

    const triggerPointOmissionRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        pointOmissionLoading.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🚀 点位+遗漏号深度推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-point-omission', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchPointOmissionSummary(true);
            await fetchPointOmissionReport();
            await fetchPointOmissionBacktest();
            await fetchPointOmissionHitLedger();
            addLog('✨ 点位+遗漏号深度推演与 5+2 决策数据已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        pointOmissionLoading.value = false;
        addLog('❌ 启动点位+遗漏深度推演失败: ' + err.message, 'danger');
      }
    };

    const setPointOmissionSubTab = (tab) => {
      pointOmissionSubTab.value = tab;
      if (tab === 'report' && !pointOmissionReport.value) {
        fetchPointOmissionReport();
      }
      if (tab === 'backtest' && !pointOmissionBacktest.value) {
        fetchPointOmissionBacktest();
      }
      if (tab === 'ledger' && !pointOmissionHitLedger.value) {
        fetchPointOmissionHitLedger();
      }
    };

    const isPointOmissionCore = (num) => {
      if (!pointOmissionSummary.value || !pointOmissionSummary.value.core_points) return false;
      return pointOmissionSummary.value.core_points.includes(num);
    };

    const isPointOmissionExpanded = (num) => {
      if (!pointOmissionSummary.value || !pointOmissionSummary.value.expanded_points) return false;
      return pointOmissionSummary.value.expanded_points.includes(num);
    };

    const isPointOmissionTop5 = (num) => {
      if (!pointOmissionSummary.value || !pointOmissionSummary.value.top5) return false;
      return pointOmissionSummary.value.top5.some(it => it.number === num);
    };

    const isPointOmissionDefensive = (num) => {
      if (!pointOmissionSummary.value || !pointOmissionSummary.value.defensive_picks) return false;
      return pointOmissionSummary.value.defensive_picks.includes(num);
    };

    const getPointOmissionNumScore = (num) => {
      if (!pointOmissionSummary.value || !pointOmissionSummary.value.dimension_scores_80) return 0;
      const item = pointOmissionSummary.value.dimension_scores_80[String(num)];
      return item ? item.score : 0;
    };

    const getPointOmissionNumMiss = (num) => {
      if (!pointOmissionSummary.value || !pointOmissionSummary.value.dimension_scores_80) return 0;
      const item = pointOmissionSummary.value.dimension_scores_80[String(num)];
      return item ? item.streak_miss : 0;
    };

    const getPointOmissionMatrixClass = (num) => {
      if (isPointOmissionTop5(num)) {
        return 'border-amber-400 bg-gradient-to-b from-amber-500/30 to-amber-900/20 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.5)] font-bold';
      }
      if (isPointOmissionDefensive(num)) {
        return 'border-purple-400 bg-gradient-to-b from-purple-600/30 to-purple-950/30 text-purple-300 shadow-[0_0_12px_rgba(168,85,247,0.5)] font-bold';
      }
      if (isPointOmissionCore(num)) {
        return 'border-cyan-500/70 bg-cyan-950/30 text-cyan-300 shadow-[0_0_8px_rgba(6,182,212,0.3)] font-bold';
      }
      if (isPointOmissionExpanded(num)) {
        return 'border-slate-700 bg-slate-900/40 text-slate-200 hover:border-slate-500';
      }
      return 'border-slate-800 bg-slate-950/20 text-slate-600 hover:border-slate-700';
    };

    return {
      pointOmissionSummary,
      pointOmissionReport,
      pointOmissionReportHtml,
      pointOmissionBacktest,
      pointOmissionHitLedger,
      pointOmissionLoading,
      pointOmissionLedgerLoading,
      pointOmissionSubTab,
      getMethodChineseName,
      fetchPointOmissionSummary,
      fetchPointOmissionReport,
      fetchPointOmissionBacktest,
      fetchPointOmissionHitLedger,
      seedPointOmissionHitLedger,
      triggerPointOmissionRun,
      setPointOmissionSubTab,
      isPointOmissionCore,
      isPointOmissionExpanded,
      isPointOmissionTop5,
      isPointOmissionDefensive,
      getPointOmissionNumScore,
      getPointOmissionNumMiss,
      getPointOmissionMatrixClass
    };
  });
})();
