/**
 * K8 page module: tprd_v40 (TPRD v4.0 双螺旋矩阵与智能缩水系统驾驶舱 - P2x)
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (tprd_v40)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const {
      isRunning, openTab, addLog, startLogPolling, terminalLogs, activeTab
    } = ctx;

    const tprdV40Data = vueApi.ref(null);
    const isTprdV40Running = vueApi.ref(false);
    const selectedPool = vueApi.ref('pool_20');
    const dhmFilter = vueApi.ref('all');

    const currentPoolData = vueApi.computed(() => {
      if (!tprdV40Data.value) return null;
      return tprdV40Data.value[selectedPool.value] || tprdV40Data.value.pool_20 || null;
    });

    const filteredDhmBets = vueApi.computed(() => {
      if (!tprdV40Data.value || !Array.isArray(tprdV40Data.value.dhm_bets)) return [];
      if (dhmFilter.value === 'all') return tprdV40Data.value.dhm_bets;
      return tprdV40Data.value.dhm_bets.filter(b => b.type === dhmFilter.value);
    });

    const recentHistory = vueApi.computed(() => {
      const h = tprdV40Data.value?.backtest_summary?.history;
      if (!Array.isArray(h)) return [];
      return h.slice(-10);
    });

    const formatBall = (n) => {
      if (n === undefined || n === null) return '--';
      return String(n).padStart(2, '0');
    };

    const getZoneCount = (idx) => {
      if (!currentPoolData.value || !currentPoolData.value.zones) return 0;
      const z = currentPoolData.value.zones;
      if (Array.isArray(z.counts) && z.counts.length > idx) {
        return z.counts[idx];
      }
      const key = `zone${idx + 1}`;
      return Array.isArray(z[key]) ? z[key].length : 0;
    };

    const copyCardPair = (card) => {
      if (!card || !card.pair) return;
      const t = `${String(card.pair[0]).padStart(2, '0')} ${String(card.pair[1]).padStart(2, '0')}`;
      copyText(t);
    };

    const copyBetBalls = (bet) => {
      if (!bet || !bet.balls) return;
      const t = bet.balls.map(n => String(n).padStart(2, '0')).join(' ');
      copyText(t);
    };

    const fetchTprdV40Data = async () => {
      try {
        const res = await fetch('/api/quant/tprd-v40/latest');
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            tprdV40Data.value = resp.data;
            return;
          }
        }
        // 静态缓存回退
        const fallback = await fetch(`/static/tprd_v40_latest.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallback.ok) {
          tprdV40Data.value = await fallback.json();
        }
      } catch (err) {
        console.warn('获取TPRD v4.0数据失败，加载静态缓存:', err);
        try {
          const fallback = await fetch(`/static/tprd_v40_latest.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallback.ok) tprdV40Data.value = await fallback.json();
        } catch (e) {}
      }
    };

    const copyText = (text) => {
      if (!text) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          if (typeof addLog === 'function') addLog(`📋 已复制到剪贴板: ${text}`, 'info');
        }).catch(() => fallbackCopy(text));
      } else {
        fallbackCopy(text);
      }
    };

    const fallbackCopy = (text) => {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try {
        document.execCommand('copy');
        if (typeof addLog === 'function') addLog(`📋 已复制: ${text}`, 'info');
      } catch (e) {
        console.warn('复制失败', e);
      }
      document.body.removeChild(ta);
    };

    const copyAllDhmBets = () => {
      if (!tprdV40Data.value || !Array.isArray(tprdV40Data.value.dhm_bets)) return;
      const lines = tprdV40Data.value.dhm_bets.map(b => {
        return b.balls.map(n => String(n).padStart(2, '0')).join(' ');
      });
      const fullText = lines.join('\n');
      copyText(fullText);
      alert(`已成功复制 DHM-Pro 全部 30 注选 5 号码！`);
    };

    const copyPick2Pairs = () => {
      if (!tprdV40Data.value || !Array.isArray(tprdV40Data.value.pick2_grid)) return;
      const text = tprdV40Data.value.pick2_grid.map(c => {
        return `${c.name}: ${String(c.pair[0]).padStart(2, '0')} ${String(c.pair[1]).padStart(2, '0')}`;
      }).join('\n');
      copyText(text);
      alert(`已成功复制 4 组选 2 抽屉组合！`);
    };

    const triggerTprdV40Run = async () => {
      if (isRunning.value || isTprdV40Running.value) return;
      try {
        isTprdV40Running.value = true;
        isRunning.value = true;
        if (typeof openTab === 'function') openTab('live_terminal');
        if (terminalLogs && terminalLogs.value) terminalLogs.value = [];
        if (typeof addLog === 'function') addLog('🧬 正在启动【TPRD v4.0 双螺旋矩阵与智能缩水系统】推演计算...', 'info');

        const res = await fetch('/api/quant/tprd-v40/run', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          if (taskId && typeof startLogPolling === 'function') {
            startLogPolling(taskId, async () => {
              await fetchTprdV40Data();
              isTprdV40Running.value = false;
              if (typeof addLog === 'function') addLog('✨ TPRD v4.0 双螺旋矩阵推演完成，大屏数据已同步更新！', 'success');
            });
          } else {
            await fetchTprdV40Data();
            isTprdV40Running.value = false;
            if (typeof addLog === 'function') addLog('✨ TPRD v4.0 推演完成！', 'success');
          }
        } else {
          isTprdV40Running.value = false;
          isRunning.value = false;
          if (typeof addLog === 'function') addLog('❌ TPRD v4.0 推演启动失败', 'error');
        }
      } catch (e) {
        console.error('TPRD v4.0 执行异常:', e);
        isTprdV40Running.value = false;
        isRunning.value = false;
        if (typeof addLog === 'function') addLog(`❌ TPRD 异常: ${e.message}`, 'error');
      }
    };

    // 初始加载与激活监听
    fetchTprdV40Data();
    vueApi.watch(activeTab, (newTab) => {
      if (newTab === 'tprd_v40_cockpit' && !tprdV40Data.value) {
        fetchTprdV40Data();
      }
    });

    return {
      tprdV40Data,
      isTprdV40Running,
      selectedPool,
      dhmFilter,
      currentPoolData,
      filteredDhmBets,
      recentHistory,
      formatBall,
      getZoneCount,
      copyCardPair,
      copyBetBalls,
      fetchTprdV40Data,
      triggerTprdV40Run,
      copyText,
      copyAllDhmBets,
      copyPick2Pairs
    };
  });
})();
