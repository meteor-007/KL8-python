/**
 * K8 page module: jingle
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (jingle)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

    // ──────────────── 顺口溜口诀规则与对账状态 ────────────────
    const jingleSummary = ref(null);
    const jingleReview = ref(null);
    const jingleRules = ref([]);
    const jingleRulesMeta = ref({});
    const jingleRuleKindFilter = ref('all');
    const jingleRuleSearchKeyword = ref('');
    const jingleLoading = ref(false);

    const fetchJingleSummary = async () => {
      try {
        const res = await fetch('/api/jingle/summary');
        if (res.ok) {
          jingleSummary.value = await res.json();
        }
      } catch (err) {
        console.error('Failed to fetch jingle summary:', err);
      }
    };

    const fetchJingleReview = async (n = 30) => {
      try {
        jingleLoading.value = true;
        const res = await fetch(`/api/jingle/review?n=${n}`);
        if (res.ok) {
          jingleReview.value = await res.json();
        }
      } catch (err) {
        console.error('Failed to fetch jingle review:', err);
      } finally {
        jingleLoading.value = false;
      }
    };

    const fetchJingleRules = async () => {
      try {
        const res = await fetch('/api/jingle/rules');
        if (res.ok) {
          const data = await res.json();
          if (data && data.status === 'ok') {
            jingleRules.value = data.rules || [];
            jingleRulesMeta.value = data.meta || {};
          }
        }
      } catch (err) {
        console.error('Failed to fetch jingle rules:', err);
      }
    };

    const triggerJingleRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🚀 顺口溜口诀全流程推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-jingle', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchJingleSummary();
            await fetchJingleReview();
            addLog('✨ 顺口溜口诀数据与预测已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动顺口溜任务失败: ' + err.message, 'danger');
      }
    };

    const filteredJingleRules = computed(() => {
      let list = jingleRules.value || [];
      if (jingleRuleKindFilter.value !== 'all') {
        list = list.filter(r => r.kind === jingleRuleKindFilter.value);
      }
      if (jingleRuleSearchKeyword.value && jingleRuleSearchKeyword.value.trim()) {
        const kw = jingleRuleSearchKeyword.value.trim();
        list = list.filter(r => {
          const trgStr = (r.trigger || []).map(x => String(x).padStart(2, '0')).join(' ');
          const predStr = (r.predict || []).map(x => String(x).padStart(2, '0')).join(' ');
          return trgStr.includes(kw) || predStr.includes(kw) || String(r.rule_id).includes(kw);
        });
      }
      return list;
    });


    // ══════════════════════════════════════════════════════════
    // 顺口溜 & 跟随 样本外复盘增强
    // ══════════════════════════════════════════════════════════
    const jingleReviewPeriods = ref(30);

    const fetchJingleReviewEnhanced = async (n = 30) => {
      jingleLoading.value = true;
      jingleReviewPeriods.value = n;
      try {
        const res = await fetch(`/api/jingle/review?n=${n}`);
        if (res.ok) {
          jingleReview.value = await res.json();
          addLog(`📜 顺口溜口诀样本外近${n}期复盘对账完成`, 'success');
        }
      } catch (err) {
        addLog(`❌ 获取口诀复盘失败: ${err.message}`, 'error');
      } finally {
        jingleLoading.value = false;
      }
    };

    return {
      jingleSummary,
      jingleReview,
      jingleRules,
      jingleRulesMeta,
      jingleRuleKindFilter,
      jingleRuleSearchKeyword,
      jingleLoading,
      filteredJingleRules,
      fetchJingleSummary,
      fetchJingleReview,
      fetchJingleRules,
      triggerJingleRun,
      jingleReviewPeriods,
      fetchJingleReviewEnhanced
    };
  });
})();
