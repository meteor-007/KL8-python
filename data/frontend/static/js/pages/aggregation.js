/**
 * K8 page module: aggregation
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (aggregation)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

    // ──────────────── 策略汇总复盘 ────────────────
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
        console.error('获取策略汇总驾驶舱失败:', err);
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
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🧬 策略汇总复盘 (7路多维共振 + 8区空间平衡) 任务已提交后台...', 'info');
        const res = await fetch('/api/aggregation/run?force=true', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchAggCockpit();
            await fetchAggHistory();
            addLog('✨ 策略汇总复盘计算完毕并已自动刷新！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动策略汇总失败: ' + err.message, 'danger');
      }
    };

    return {
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
  });
})();
