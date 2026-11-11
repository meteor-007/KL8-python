/**
 * K8 page module: transformer
 * Transformer 全局自注意力推演战区 (第12战区)
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') return;

  window.K8Pages.register(function (vueApi, ctx) {
    const { isRunning, openTab, addLog, startLogPolling, terminalLogs, fetchTransformerData } = ctx;

    const triggerTransformerRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🤖 正在启动【Transformer 全局自注意力】时序推演任务...', 'info');
        const res = await fetch('/api/pipeline/run-transformer', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            await fetchTransformerData(true);
            addLog('✨ Transformer 全局注意力推演与大研报已实时刷新完毕！', 'success');
          });
        } else {
          isRunning.value = false;
          addLog('❌ 启动 Transformer 任务失败: ' + (res.statusText || '服务异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动 Transformer 失败: ' + err.message, 'danger');
      }
    };

    return { triggerTransformerRun };
  });
})();
