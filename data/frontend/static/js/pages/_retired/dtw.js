/**
 * K8 page module: dtw
 * 动态时间规整 DTW 推演战区 (第11战区)
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') return;

  window.K8Pages.register(function (vueApi, ctx) {
    const { isRunning, openTab, addLog, startLogPolling, terminalLogs, fetchDTWData } = ctx;

    const triggerDTWRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🌊 正在启动【动态时间规整 DTW】弹性走势量化推演任务...', 'info');
        const res = await fetch('/api/pipeline/run-dtw', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            await fetchDTWData(true);
            addLog('✨ DTW 弹性走势推演与大研报已实时刷新完毕！', 'success');
          });
        } else {
          isRunning.value = false;
          addLog('❌ 启动 DTW 推演任务失败: ' + (res.statusText || '服务异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动 DTW 推演失败: ' + err.message, 'danger');
      }
    };

    return { triggerDTWRun };
  });
})();
