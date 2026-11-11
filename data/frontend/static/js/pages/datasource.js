/**
 * K8 page module: datasource
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (datasource)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction, fetchAllModulesOverview
    } = ctx;

    // ══════════════════════════════════════════════════════════
    // 数据源1×数据源2 深层关联推演与样本外滚动复盘
    // ══════════════════════════════════════════════════════════
    const datasourceSummary = ref(null);
    const datasourceReview = ref(null);
    const datasourceLogs = ref([]);
    const selectedDatasourceLog = ref(null);
    const datasourceLogDetail = ref('');
    const datasourceLoading = ref(false);
    const datasourceReviewPeriods = ref(30);

    const fetchDatasourceSummary = async () => {
      try {
        const res = await fetch('/api/datasource/summary');
        if (res.ok) {
          const data = await res.json();
          datasourceSummary.value = data.data || data;
        }
      } catch (err) {
        console.error('获取数据源1×2深层关联摘要失败:', err);
      }
    };

    const fetchDatasourceReview = async (n = 30) => {
      datasourceLoading.value = true;
      datasourceReviewPeriods.value = n;
      try {
        const res = await fetch(`/api/datasource/review?n=${n}`);
        if (res.ok) {
          const data = await res.json();
          datasourceReview.value = data.data || data;
        }
      } catch (err) {
        console.error('获取数据源1×2复盘对账失败:', err);
      } finally {
        datasourceLoading.value = false;
      }
    };

    const fetchDatasourceLogs = async () => {
      try {
        const res = await fetch('/api/datasource/history');
        if (res.ok) {
          datasourceLogs.value = await res.json();
          if (datasourceLogs.value && datasourceLogs.value.length > 0 && !selectedDatasourceLog.value) {
            selectDatasourceLog(datasourceLogs.value[0]);
          }
        }
      } catch (err) {
        console.error('获取数据源1×2历史清单失败:', err);
      }
    };

    const selectDatasourceLog = async (item) => {
      selectedDatasourceLog.value = item;
      try {
        const res = await fetch(`/api/reports/detail/${encodeURIComponent(item.filename)}`);
        if (res.ok) {
          const data = await res.json();
          datasourceLogDetail.value = data.content || '';
        }
      } catch (err) {
        datasourceLogDetail.value = '加载预测单失败: ' + err.message;
      }
    };

    const triggerDatasourceRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🧬 数据源1×2深层关联推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-datasource', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchDatasourceSummary();
            await fetchDatasourceReview(datasourceReviewPeriods.value);
            await fetchDatasourceLogs();
            await fetchAllModulesOverview();
            addLog('✨ 数据源1×2深层关联推演已完成并刷新！', 'success');
          });
        } else {
          isRunning.value = false;
          const errText = await res.text();
          addLog(`❌ 启动数据源1×2推演失败 [HTTP ${res.status}]: ${errText}`, 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动数据源1×2推演失败: ' + err.message, 'danger');
      }
    };

    // ──────────────── 数据源1与数据源2 原始阵列全景数据服务 ────────────────
    const datasourceMatrixData = ref(null);
    const datasourceMatrixLoading = ref(false);
    const datasourceMatrixSelectedPeriod = ref('');
    const currentMatrixHighlightMode = ref('all');
    const matrixHighlightModes = [
      { id: 'all', label: '全部', icon: '🌐' },
      { id: 'win', label: '仅中奖', icon: '🟣' },
      { id: 'point', label: '仅点位', icon: '🌸' },
      { id: 'star', label: '仅热码', icon: '⭐' },
      { id: 'cross', label: '仅双源交集', icon: '👑' }
    ];

    const canPrevDatasourcePeriod = computed(() => {
      if (!datasourceMatrixData.value || !datasourceMatrixData.value.available_periods) return false;
      const list = datasourceMatrixData.value.available_periods;
      const curIdx = list.indexOf(datasourceMatrixSelectedPeriod.value);
      return curIdx !== -1 && curIdx < list.length - 1;
    });

    const canNextDatasourcePeriod = computed(() => {
      if (!datasourceMatrixData.value || !datasourceMatrixData.value.available_periods) return false;
      const list = datasourceMatrixData.value.available_periods;
      const curIdx = list.indexOf(datasourceMatrixSelectedPeriod.value);
      return curIdx > 0;
    });

    const fetchDatasourceMatrix = async (period = null) => {
      datasourceMatrixLoading.value = true;
      try {
        const url = period ? `/api/datasource/matrix?period=${encodeURIComponent(period)}` : '/api/datasource/matrix';
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          datasourceMatrixData.value = data;
          datasourceMatrixSelectedPeriod.value = data.period;
        }
      } catch (err) {
        console.error('获取数据源1×2原始阵列失败:', err);
      } finally {
        datasourceMatrixLoading.value = false;
      }
    };

    const prevDatasourcePeriod = () => {
      if (!canPrevDatasourcePeriod.value) return;
      const list = datasourceMatrixData.value.available_periods;
      const curIdx = list.indexOf(datasourceMatrixSelectedPeriod.value);
      if (curIdx !== -1 && curIdx < list.length - 1) {
        fetchDatasourceMatrix(list[curIdx + 1]);
      }
    };

    const nextDatasourcePeriod = () => {
      if (!canNextDatasourcePeriod.value) return;
      const list = datasourceMatrixData.value.available_periods;
      const curIdx = list.indexOf(datasourceMatrixSelectedPeriod.value);
      if (curIdx > 0) {
        fetchDatasourceMatrix(list[curIdx - 1]);
      }
    };

    const isCrossIntersection = (num) => {
      if (!datasourceMatrixData.value || !datasourceMatrixData.value.cross_stats) return false;
      return (datasourceMatrixData.value.cross_stats.intersection || []).includes(num);
    };

    /** 阵列当前选中期在 Walk-Forward 流水中的对账行（严格无未来） */
    const datasourceMatrixReviewRow = computed(() => {
      const rows = (datasourceReview.value && datasourceReview.value.rows) || [];
      const p = String(datasourceMatrixSelectedPeriod.value || '');
      if (!p) return null;
      return rows.find((r) => String(r.target_period || r.period) === p) || null;
    });

    const jumpMatrixToReviewPeriod = (period) => {
      if (period == null || period === '') return;
      fetchDatasourceMatrix(String(period));
      nextTick(() => {
        setTimeout(() => {
          const el = document.getElementById('module-review-datasource-matrix');
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 60);
      });
    };

    const scrollToDatasourceMatrixReview = () => {
      const el = document.getElementById('module-review-datasource-matrix');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (!datasourceReview.value || !datasourceReview.value.rows || !datasourceReview.value.rows.length) {
        fetchDatasourceReview(datasourceReviewPeriods.value || 30);
      }
    };

    const getMatrixCellClass = (cell) => {
      if (!cell) return '';
      const classes = [];
      if (cell.is_point) classes.push('cell-point');
      if (cell.is_win) classes.push('cell-win');
      if (cell.is_star) classes.push('cell-star');

      // 快捷过滤高亮模式
      const mode = currentMatrixHighlightMode.value;
      if (mode === 'win' && !cell.is_win) classes.push('cell-dimmed');
      else if (mode === 'point' && !cell.is_point) classes.push('cell-dimmed');
      else if (mode === 'star' && !cell.is_star) classes.push('cell-dimmed');
      else if (mode === 'cross' && !isCrossIntersection(cell.num)) classes.push('cell-dimmed');

      return classes.join(' ');
    };

    return {
      datasourceSummary,
      datasourceReview,
      datasourceLogs,
      selectedDatasourceLog,
      datasourceLogDetail,
      datasourceLoading,
      datasourceReviewPeriods,
      fetchDatasourceSummary,
      fetchDatasourceReview,
      fetchDatasourceLogs,
      selectDatasourceLog,
      triggerDatasourceRun,
      datasourceMatrixData,
      datasourceMatrixLoading,
      datasourceMatrixSelectedPeriod,
      currentMatrixHighlightMode,
      matrixHighlightModes,
      canPrevDatasourcePeriod,
      canNextDatasourcePeriod,
      fetchDatasourceMatrix,
      prevDatasourcePeriod,
      nextDatasourcePeriod,
      isCrossIntersection,
      datasourceMatrixReviewRow,
      jumpMatrixToReviewPeriod,
      scrollToDatasourceMatrixReview,
      getMatrixCellClass
    };
  });
})();
