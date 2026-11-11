/**
 * K8 page module: retired
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (retired)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

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
        openTab('live_terminal');
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
        openTab('live_terminal');
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

    // ══════════════════════════════════════════════════════════
    // 双层LSTM 深度学习时序模块 State & Methods
    // ══════════════════════════════════════════════════════════
    const lstmSummary = ref(null);
    const lstmReview = ref(null);
    const lstmReviewPeriods = ref(15);
    const lstmReports = ref([]);
    const selectedLstmReport = ref(null);
    const lstmReportDetail = ref(null);
    const lstmLoading = ref(false);

    const fetchLstmSummary = async () => {
      lstmLoading.value = true;
      try {
        const res = await fetch('/api/lstm/summary');
        if (res.ok) {
          lstmSummary.value = await res.json();
          addLog('🧠 双层LSTM最新推演数据加载完成', 'success');
        } else {
          addLog('⚠️ 双层LSTM数据获取异常', 'warn');
        }
      } catch (err) {
        addLog(`❌ 获取双层LSTM数据失败: ${err.message}`, 'error');
      } finally {
        lstmLoading.value = false;
      }
    };

    const fetchLstmReview = async (n = 15) => {
      lstmLoading.value = true;
      lstmReviewPeriods.value = n;
      try {
        const res = await fetch(`/api/lstm/review?n=${n}`);
        if (res.ok) {
          lstmReview.value = await res.json();
          addLog(`📊 双层LSTM样本外近${n}期复盘数据加载完成`, 'success');
        }
      } catch (err) {
        addLog(`❌ 获取双层LSTM复盘失败: ${err.message}`, 'error');
      } finally {
        lstmLoading.value = false;
      }
    };

    const fetchLstmReports = async () => {
      lstmLoading.value = true;
      try {
        const res = await fetch('/api/lstm/reports');
        if (res.ok) {
          lstmReports.value = await res.json();
          if (lstmReports.value.length > 0 && !selectedLstmReport.value) {
            selectLstmReport(lstmReports.value[0]);
          }
        }
      } catch (err) {
        addLog(`❌ 获取LSTM研报列表失败: ${err.message}`, 'error');
      } finally {
        lstmLoading.value = false;
      }
    };

    const selectLstmReport = async (rep) => {
      selectedLstmReport.value = rep;
      lstmLoading.value = true;
      try {
        const res = await fetch(`/api/lstm/report-detail/${encodeURIComponent(rep.filename)}`);
        if (res.ok) {
          lstmReportDetail.value = await res.json();
        }
      } catch (err) {
        addLog(`❌ 加载LSTM研报内容失败: ${err.message}`, 'error');
      } finally {
        lstmLoading.value = false;
      }
    };

    const triggerLstmRun = async () => {
      try {
        const res = await fetch('/api/pipeline/run-lstm', { method: 'POST' });
        const data = await res.json();
        addLog(`🚀 ${data.message}`, 'info');
        openTab('live_terminal');
      } catch (err) {
        addLog(`❌ 触发LSTM推演任务失败: ${err.message}`, 'error');
      }
    };

    return {
      followSummary,
      followReview,
      followConditions,
      followLoading,
      followReviewPeriods,
      fetchFollowSummary,
      fetchFollowReview,
      fetchFollowConditions,
      triggerFollowRun,
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
      lstmSummary,
      lstmReview,
      lstmReviewPeriods,
      lstmReports,
      selectedLstmReport,
      lstmReportDetail,
      lstmLoading,
      fetchLstmSummary,
      fetchLstmReview,
      fetchLstmReports,
      selectLstmReport,
      triggerLstmRun
    };
  });
})();
