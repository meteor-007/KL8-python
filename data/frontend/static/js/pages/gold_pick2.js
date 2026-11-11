/**
 * K8 page module: gold_pick2
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (gold_pick2)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

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
        openTab('live_terminal');
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

    return {
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
      triggerGoldPick2Run
    };
  });
})();
