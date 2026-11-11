/**
 * K8 page module: error_correction (GBDT residual boosting)
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (error_correction)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const {
      isRunning, isErrorCorrectionRunning, openTab, addLog, startLogPolling, terminalLogs,
      fetchErrorCorrectionData
    } = ctx;

    const triggerErrorCorrectionRun = async () => {
      if (isRunning.value || (isErrorCorrectionRunning && isErrorCorrectionRunning.value)) return;
      try {
        if (isErrorCorrectionRunning) isErrorCorrectionRunning.value = true;
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🧬 正在启动【残差改错 GBDT】训练与推演...', 'info');
        const res = await fetch('/api/pipeline/run-error-correction', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchErrorCorrectionData(false);
            if (isErrorCorrectionRunning) isErrorCorrectionRunning.value = false;
            addLog('✨ 残差改错预测与复盘缓存已刷新！', 'success');
          });
        } else {
          isRunning.value = false;
          if (isErrorCorrectionRunning) isErrorCorrectionRunning.value = false;
          addLog('❌ 启动残差改错任务失败: ' + (res.statusText || '异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        if (isErrorCorrectionRunning) isErrorCorrectionRunning.value = false;
        addLog('❌ 启动残差改错失败: ' + err.message, 'danger');
      }
    };

    return { triggerErrorCorrectionRun };
  });
})();
