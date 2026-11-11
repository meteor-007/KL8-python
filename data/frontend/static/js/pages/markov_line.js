/**
 * K8 page module: markov_line (马尔可夫链与特征直线校准驾驶舱)
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (markov_line)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const {
      isRunning, openTab, addLog, startLogPolling, terminalLogs
    } = ctx;

    const markovLineData = vueApi.ref(null);
    const isMarkovLineRunning = vueApi.ref(false);

    const fetchMarkovLineData = async () => {
      try {
        const res = await fetch('/api/quant/markov_line/latest');
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            markovLineData.value = resp.data;
            return;
          }
        }
        // 静态保底回退
        const fallback = await fetch(`/static/markov_line_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallback.ok) {
          markovLineData.value = await fallback.json();
        }
      } catch (err) {
        console.warn('获取马尔可夫直线数据失败，加载静态缓存:', err);
        try {
          const fallback = await fetch(`/static/markov_line_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallback.ok) markovLineData.value = await fallback.json();
        } catch (e) {}
      }
    };

    const triggerMarkovLineRun = async () => {
      if (isRunning.value || isMarkovLineRunning.value) return;
      try {
        isMarkovLineRunning.value = true;
        isRunning.value = true;
        if (typeof openTab === 'function') openTab('live_terminal');
        if (terminalLogs && terminalLogs.value) terminalLogs.value = [];
        if (typeof addLog === 'function') addLog('📐 正在启动【马尔可夫链与特征直线校准】终极推演...', 'info');

        const res = await fetch('/api/quant/markov_line/run', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          if (taskId && typeof startLogPolling === 'function') {
            startLogPolling(taskId, async () => {
              await fetchMarkovLineData();
              isMarkovLineRunning.value = false;
              if (typeof addLog === 'function') addLog('✨ 马尔可夫特征直线推演完成，看板数据已同步刷新！', 'success');
            });
          } else {
            await fetchMarkovLineData();
            isMarkovLineRunning.value = false;
            isRunning.value = false;
            if (typeof addLog === 'function') addLog('✨ 马尔可夫特征直线推演完成！', 'success');
          }
        } else {
          isRunning.value = false;
          isMarkovLineRunning.value = false;
          if (typeof addLog === 'function') addLog('❌ 启动马尔可夫推演失败: ' + (res.statusText || '异常'), 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        isMarkovLineRunning.value = false;
        if (typeof addLog === 'function') addLog('❌ 启动马尔可夫推演异常: ' + err.message, 'danger');
      }
    };

    // 初始加载一次数据
    fetchMarkovLineData();

    return {
      markovLineData,
      isMarkovLineRunning,
      fetchMarkovLineData,
      triggerMarkovLineRun
    };
  });
})();
