/**
 * K8 page module: random_forest
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (random_forest)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const {
      isRunning, isRandomForestRunning, openTab, addLog, startLogPolling, terminalLogs,
      fetchRandomForestData
    } = ctx;

    const triggerRandomForestRun = async () => {
      if (isRunning.value || (isRandomForestRunning && isRandomForestRunning.value)) return;
      try {
        if (isRandomForestRunning) isRandomForestRunning.value = true;
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🌲 正在启动【随机森林号码预测】训练与推演...', 'info');
        const res = await fetch('/api/pipeline/run-random-forest', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchRandomForestData(false);
            if (isRandomForestRunning) isRandomForestRunning.value = false;
            addLog('✨ 随机森林号码预测与复盘缓存已刷新！', 'success');
          });
        } else {
          isRunning.value = false;
          if (isRandomForestRunning) isRandomForestRunning.value = false;
          addLog('❌ 启动随机森林任务失败: ' + (res.statusText || '异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        if (isRandomForestRunning) isRandomForestRunning.value = false;
        addLog('❌ 启动随机森林失败: ' + err.message, 'danger');
      }
    };

    return { triggerRandomForestRun };
  });
})();
