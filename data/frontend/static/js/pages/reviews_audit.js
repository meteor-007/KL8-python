/**
 * K8 page module: reviews_audit
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (reviews_audit)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

    const fetchMetaGoldSummary = (...args) => ctx.fetchMetaGoldSummary(...args);
    const fetchFunnelSummary = (...args) => ctx.fetchFunnelSummary(...args);

    // ══════════════════════════════════════════════════════════
    // 每日自学习自动复盘总账本 & 10大模块预测全景大盘
    // ══════════════════════════════════════════════════════════
    const reviewsLedgerData = ref(null);
    const reviewsLedgerLimit = ref(50);
    const reviewsLedgerLoading = ref(false);
    const selectedReviewDetail = ref(null);
    const showReviewDetailModal = ref(false);

    const fetchReviewsLedger = async (limit = 50) => {
      reviewsLedgerLoading.value = true;
      reviewsLedgerLimit.value = limit;
      try {
        const res = await fetch(`/api/reviews/ledger?limit=${limit}`);
        if (res.ok) {
          reviewsLedgerData.value = await res.json();
          addLog(`📋 每日自学习自动复盘总账本 (近${limit}期) 加载完成`, 'success');
        }
      } catch (err) {
        addLog(`❌ 获取复盘总账本失败: ${err.message}`, 'error');
      } finally {
        reviewsLedgerLoading.value = false;
      }
    };

    const openReviewDetailModal = async (period) => {
      try {
        const res = await fetch(`/api/reviews/detail/${period}`);
        if (res.ok) {
          selectedReviewDetail.value = await res.json();
          showReviewDetailModal.value = true;
        }
      } catch (err) {
        addLog(`❌ 读取第${period}期复盘详情失败: ${err.message}`, 'error');
      }
    };

    const closeReviewDetailModal = () => {
      showReviewDetailModal.value = false;
      selectedReviewDetail.value = null;
    };

    const modulesOverviewData = ref(null);
    const modulesOverviewLoading = ref(false);

    const fetchAllModulesOverview = async () => {
      modulesOverviewLoading.value = true;
      try {
        const [res] = await Promise.all([
          fetch('/api/quant/modules-overview'),
          fetchMetaGoldSummary(),
          fetchFunnelSummary()
        ]);
        if (res && res.ok) {
          modulesOverviewData.value = await res.json();
          addLog('🌐 13大子模块今日预测全景大盘加载完成', 'success');
        }
      } catch (err) {
        addLog(`❌ 获取全模块预测总览失败: ${err.message}`, 'error');
      } finally {
        modulesOverviewLoading.value = false;
      }
    };

        // ══════════════════════════════════════════════════════════
    // 22:00 夜间全自动定时调度器 & 自动进化模型
    // ══════════════════════════════════════════════════════════
    const schedulerStatus = ref({
      enabled: true,
      target_time: '22:00',
      countdown_human: '--',
      countdown_seconds: 0,
      is_running: false,
      last_status: 'IDLE',
      last_message: '调度器待命中',
      next_run_time: '--',
      last_finished_at: '--'
    });
    const schedulerLoading = ref(false);

    const fetchSchedulerStatus = async () => {
      try {
        const res = await fetch('/api/scheduler/status');
        if (res.ok) {
          schedulerStatus.value = await res.json();
        }
      } catch (err) {
        console.error('获取调度器状态失败:', err);
      }
    };

    const triggerNightlyRun = async () => {
      if (isRunning.value || schedulerStatus.value.is_running) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🌙 正在触发【22:00 夜间全自动闭环推演与自学习进化流水线】...', 'info');
        const res = await fetch('/api/pipeline/run-nightly', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchSchedulerStatus();
            await fetchMasterReview(30);
            await fetchEvolutionStatus();
            await fetchPrediction();
            await fetchSystemStatus();
            await fetchAllModulesOverview();
            addLog('✨ 22:00 夜间全自动闭环推演与自学习进化已圆满完成并刷新！', 'success');
          });
        } else {
          isRunning.value = false;
          addLog(`❌ 触发夜间流水线失败 [HTTP ${res.status}]`, 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog(`❌ 触发夜间流水线异常: ${err.message}`, 'danger');
      }
    };

    // ══════════════════════════════════════════════════════════
    // 全模块实战命中复盘总决算
    // ══════════════════════════════════════════════════════════
    const masterReviewData = ref(null);
    const masterReviewLoading = ref(false);
    const masterReviewPeriods = ref(30);

    const fetchMasterReview = async (n = 30) => {
      masterReviewLoading.value = true;
      masterReviewPeriods.value = n;
      try {
        const res = await fetch(`/api/reviews/master-summary?n=${n}`);
        if (res.ok) {
          masterReviewData.value = await res.json();
          addLog(`🏆 15大全模块实战命中复盘 (近${n}期) 已刷新`, 'success');
        }
      } catch (err) {
        console.error('获取全模块复盘失败:', err);
      } finally {
        masterReviewLoading.value = false;
      }
    };

    const triggerMasterReviewRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🏆 正在启动全模块实战命中复盘对账任务...', 'info');
        const res = await fetch(`/api/pipeline/run-master-review?n=${masterReviewPeriods.value}`, { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            await fetchMasterReview(masterReviewPeriods.value);
            addLog('✨ 全模块命中复盘对账完成！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog(`❌ 启动全模块复盘失败: ${err.message}`, 'danger');
      }
    };

    // ══════════════════════════════════════════════════════════
    // 跨模块元学习自动进化模型
    // ══════════════════════════════════════════════════════════
    const evolutionData = ref(null);
    const evolutionHistory = ref([]);
    // G5: 标记进化历史是否来自静态快照降级(数组无法挂属性, 故单独用标志位)
    const evolutionHistoryStale = ref(false);
    const evolutionLoading = ref(false);
    const selectedEvolutionItem = ref(null);
    const showEvolutionModal = ref(false);

    const openEvolutionDetail = (item) => {
      selectedEvolutionItem.value = item;
      showEvolutionModal.value = true;
    };

    const closeEvolutionDetail = () => {
      showEvolutionModal.value = false;
      selectedEvolutionItem.value = null;
    };

    const fetchEvolutionStatus = async () => {
      evolutionLoading.value = true;
      try {
        // 通道 1: 实时获取最新进化状态
        try {
          const res1 = await fetch('/api/evolution/status');
          if (res1.ok) {
            const d1 = await res1.json();
            evolutionData.value = d1.data || d1;
          }
        } catch (e1) {
          console.warn('获取进化状态API异常:', e1);
        }

        // 通道 2: 获取全量每日历史执行记录 (API 优先 + 静态文件回退)
        try {
          const res2 = await fetch('/api/evolution/history');
          if (res2.ok) {
            const list = await res2.json();
            if (Array.isArray(list) && list.length > 0) {
              evolutionHistory.value = list;
            } else {
              throw new Error('API 返回空历史');
            }
          } else {
            throw new Error(`API HTTP ${res2.status}`);
          }
        } catch (e2) {
          console.warn('获取进化历史API失败，平滑降级至静态通道:', e2);
          const staticRes = await fetch('/static/evolution_history.json');
          if (staticRes.ok) {
            evolutionHistory.value = await staticRes.json();
            // G5: 降级数据可能过期, 必须标注来源
            evolutionHistoryStale.value = true;
          }
        }
      } catch (err) {
        console.error('获取自动进化状态失败:', err);
      } finally {
        evolutionLoading.value = false;
      }
    };

    const triggerEvolutionRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🧬 正在触发跨模块元学习自动进化模型迭代...', 'info');
        const res = await fetch('/api/pipeline/run-evolution?n=30', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            await fetchEvolutionStatus();
            await fetchPrediction();
            await fetchMasterReview(30);
            addLog('✨ 元学习模型进化迭代完成，最新参数已自动热加载！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog(`❌ 启动进化迭代失败: ${err.message}`, 'danger');
      }
    };

    return {
      reviewsLedgerData,
      reviewsLedgerLimit,
      reviewsLedgerLoading,
      selectedReviewDetail,
      showReviewDetailModal,
      fetchReviewsLedger,
      openReviewDetailModal,
      closeReviewDetailModal,
      modulesOverviewData,
      modulesOverviewLoading,
      fetchAllModulesOverview,
      schedulerStatus,
      schedulerLoading,
      fetchSchedulerStatus,
      triggerNightlyRun,
      masterReviewData,
      masterReviewLoading,
      masterReviewPeriods,
      fetchMasterReview,
      triggerMasterReviewRun,
      evolutionData,
      evolutionHistory,
      evolutionHistoryStale,
      evolutionLoading,
      fetchEvolutionStatus,
      triggerEvolutionRun,
      selectedEvolutionItem,
      showEvolutionModal,
      openEvolutionDetail,
      closeEvolutionDetail
    };
  });
})();
