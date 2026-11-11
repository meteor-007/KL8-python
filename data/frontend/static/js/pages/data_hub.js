/**
 * K8 page module: data_hub
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (data_hub)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

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
        spatialPointsLoading.value = true;
        const res = await fetch('/api/spatial-points/matrix');
        if (res.ok) {
          const data = await res.json();
          spatialPointsMatrix.value = data.matrix || [];
        }
      } catch (err) {
        console.error('获取空间重点点位矩阵失败:', err);
      } finally {
        spatialPointsLoading.value = false;
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
        openTab('live_terminal');
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

    return {
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
      triggerSpatialPointsRun
    };
  });
})();
