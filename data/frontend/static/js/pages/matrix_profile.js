/**
 * K8 page module: matrix_profile
 * 矩阵轮廓 Matrix Profile 极速查重战区 (第13战区)
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') return;

  window.K8Pages.register(function (vueApi, ctx) {
    const { isRunning, openTab, addLog, startLogPolling, terminalLogs, fetchMatrixProfileData, isModuleRetired } = ctx;

    const triggerMatrixProfileRun = async () => {
      if (await isModuleRetired('matrix_profile')) { addLog('⏹ 矩阵轮廓模块已退役，不发起推演请求；复启需修改 module_gate.MODULE_SEED 判决', 'warn'); return; }
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('⚡ 正在启动【矩阵轮廓 Matrix Profile】极速查重推演任务...', 'info');
        const res = await fetch('/api/pipeline/run-matrix-profile', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            await fetchMatrixProfileData(true);
            addLog('✨ 矩阵轮廓查重推演与大研报已实时刷新完毕！', 'success');
          });
        } else {
          isRunning.value = false;
          addLog('❌ 启动矩阵轮廓任务失败: ' + (res.statusText || '服务异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动矩阵轮廓失败: ' + err.message, 'danger');
      }
    };

    return { triggerMatrixProfileRun };
  });
})();
