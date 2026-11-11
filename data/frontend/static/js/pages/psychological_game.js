/**
 * K8 page module: psychological_game
 * Pipeline triggers; refs + fetch* stay in app.js (early shared business state).
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (psychological_game)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const {
      isRunning, openTab, addLog, startLogPolling, terminalLogs,
      fetchPsychologicalGameData, fetchPsychologicalGameBacktest, fetchPrimeCompositeData
    } = ctx;

    const triggerPsychologicalGameRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🧠 正在启动【心理博弈论与逆向均值回归】全流程量化推演任务...', 'info');
        const res = await fetch('/api/pipeline/run-psychological-game', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchPsychologicalGameData(true);
            await fetchPsychologicalGameBacktest(true);
            addLog('✨ 心理博弈论与逆向均值回归推演与战报已实时刷新完毕！', 'success');
          });
        } else {
          isRunning.value = false;
          addLog('❌ 启动心理博弈推演任务失败: ' + (res.statusText || '服务器响应异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动心理博弈推演失败: ' + err.message, 'danger');
      }
    };

    const triggerPsychologicalGameBacktestRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('📊 正在启动【心理博弈论与逆向均值回归】严格样本外滚动回测审计...', 'info');
        const res = await fetch('/api/pipeline/run-psychological-game-backtest', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchPsychologicalGameBacktest(true);
            addLog('✨ 心理博弈严格样本外滚动回测账本与流水已实时刷新完毕！', 'success');
          });
        } else {
          isRunning.value = false;
          addLog('❌ 启动心理博弈回测审计失败: ' + (res.statusText || '服务器响应异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动心理博弈回测审计失败: ' + err.message, 'danger');
      }
    };

    const triggerPrimeCompositeRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🧬 正在启动【质数合数与尾数香农熵】全流程量化推演任务...', 'info');
        const res = await fetch('/api/pipeline/run-prime-composite', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchPrimeCompositeData(true);
            addLog('✨ 质合数与尾数香农熵推演计算已实时刷新完毕！', 'success');
          });
        } else {
          isRunning.value = false;
          addLog('❌ 启动质合数推演任务失败: ' + (res.statusText || '服务器响应异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动质合数推演失败: ' + err.message, 'danger');
      }
    };

    return {
      triggerPsychologicalGameRun,
      triggerPsychologicalGameBacktestRun,
      triggerPrimeCompositeRun
    };
  });
})();
