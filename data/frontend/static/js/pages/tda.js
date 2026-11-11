/**
 * K8 page module: tda
 * 拓扑数据分析 TDA 推演战区 (第14战区)
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') return;

  window.K8Pages.register(function (vueApi, ctx) {
    const { isRunning, openTab, addLog, startLogPolling, terminalLogs, fetchTDAData } = ctx;

    const triggerTDARun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🍩 正在启动【拓扑数据分析 TDA】持续同调推演任务...', 'info');
        const res = await fetch('/api/pipeline/run-tda', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            await fetchTDAData(true);
            addLog('✨ TDA 拓扑持续同调推演与大研报已实时刷新完毕！', 'success');
          });
        } else {
          isRunning.value = false;
          addLog('❌ 启动 TDA 拓扑任务失败: ' + (res.statusText || '服务异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动 TDA 拓扑推演失败: ' + err.message, 'danger');
      }
    };

    return { triggerTDARun };
  });
})();
