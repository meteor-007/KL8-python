/**
 * K8 page module: linear_algebra
 * 线性代数空间投影量化推演战区 (第10战区) 页面交互与触发器
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (linear_algebra)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const {
      isRunning, isLinearAlgebraRunning, openTab, addLog, startLogPolling, terminalLogs,
      fetchLinearAlgebraData
    } = ctx;

    const triggerLinearAlgebraRun = async () => {
      if (isRunning.value || (isLinearAlgebraRunning && isLinearAlgebraRunning.value)) return;
      try {
        if (isLinearAlgebraRunning) isLinearAlgebraRunning.value = true;
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('📐 正在启动【线性代数空间投影量化推演】全流程矩阵解算任务...', 'info');
        const res = await fetch('/api/pipeline/run-linear-algebra', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchLinearAlgebraData(false);
            if (isLinearAlgebraRunning) isLinearAlgebraRunning.value = false;
            addLog('✨ 线性代数空间投影多维矩阵推演与大研报已实时刷新完毕！', 'success');
          });
        } else {
          isRunning.value = false;
          if (isLinearAlgebraRunning) isLinearAlgebraRunning.value = false;
          addLog('❌ 启动线性代数推演任务失败: ' + (res.statusText || '服务器响应异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        if (isLinearAlgebraRunning) isLinearAlgebraRunning.value = false;
        addLog('❌ 启动线性代数推演失败: ' + err.message, 'danger');
      }
    };

    return {
      triggerLinearAlgebraRun
    };
  });
})();
