/**
 * K8 page module: unified_brain
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (unified_brain)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

    // ══════════════════════════════════════════════════════════
    // 全栈统一决策主脑 (无加权 · 纯物理概率场)
    // ══════════════════════════════════════════════════════════
    const unifiedBrainData = ref(null);
    const unifiedBrainLoading = ref(false);

    const fetchUnifiedBrain = async () => {
      unifiedBrainLoading.value = true;
      try {
        let loaded = false;
        try {
          const res = await fetch('/api/quant/unified-brain');
          if (res.ok) {
            const d = await res.json();
            if (d && (d.data || d.target_period)) {
              unifiedBrainData.value = d.data || d;
              addLog('🧠 全栈统一决策主脑最新解算数据已加载', 'success');
              loaded = true;
            }
          }
        } catch (apiErr) {
          console.warn('API /api/quant/unified-brain 读取异常，尝试静态降级通道:', apiErr);
        }

        // 双通道高可靠降级: 若 API 异常，平滑读取静态持久化资产
        if (!loaded) {
          const staticRes = await fetch('/static/unified_decision_latest.json');
          if (staticRes.ok) {
            const staticData = await staticRes.json();
            // G5: 静态快照可能过期, 标记来源而非冒充实时解算
            unifiedBrainData.value = { ...staticData, __stale_fallback: true,
              __stale_note: '接口不可用，当前展示的是静态决策快照，可能已过期' };
            addLog('🧠 统一决策主脑通过静态通道载入（⚠️ 快照可能过期）', 'info');
          }
        }
      } catch (err) {
        console.error('获取统一决策主脑失败:', err);
      } finally {
        unifiedBrainLoading.value = false;
      }
    };

    const triggerUnifiedBrainRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🧠 正在启动【全栈统一决策主脑】全局物理概率解算...', 'info');
        const res = await fetch('/api/pipeline/run-unified-brain', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            await fetchUnifiedBrain();
            await fetchPrediction();
            addLog('✨ 全栈统一决策主脑推演解算完成并刷新！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog(`❌ 启动统一决策主脑失败: ${err.message}`, 'danger');
      }
    };

    return {
      unifiedBrainData,
      unifiedBrainLoading,
      fetchUnifiedBrain,
      triggerUnifiedBrainRun
    };
  });
})();
