/**
 * K8 page module: suppression
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (suppression)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

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
        openTab('live_terminal');
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

    return {
      suppressionSummary,
      suppressionReview,
      suppressionPatterns,
      suppressionLoading,
      suppressionReviewPeriods,
      fetchSuppressionSummary,
      fetchSuppressionReview,
      fetchSuppressionPatterns,
      triggerSuppressionRun
    };
  });
})();
