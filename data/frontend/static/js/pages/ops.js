/**
 * K8 page module: ops
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (ops)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction, fetchAllModulesOverview
    } = ctx;

    // ──────────────── 每日最新点位数据录入与联动 (Daily Points Input & Sync) ────────────────
    const dailyPointsInfo = ref(null);
    const dailyPointsHistory = ref([]);
    const dailyPointsInputText = ref('');
    const dailyPointsSelectedBalls = ref([]);
    const dailyPointsTargetPeriod = ref('');
    const dailyPointsTargetDate = ref('');
    const dailyPointsAutoRun = ref(true);
    const dailyPointsSubmitting = ref(false);
    const dailyPointsLoading = ref(false);
    const dailyPointsAnalysis = ref(null);

    const fetchDailyPointsInfo = async () => {
      try {
        dailyPointsLoading.value = true;
        const res = await fetch('/api/daily-points/info');
        if (res.ok) {
          const data = await res.json();
          dailyPointsInfo.value = data;
          if (data.target_info) {
            dailyPointsTargetPeriod.value = data.target_info.target_period_str || '';
            dailyPointsTargetDate.value = data.target_info.target_date || '';
            if (data.target_info.existing_points && data.target_info.existing_points.length === 20) {
              dailyPointsSelectedBalls.value = [...data.target_info.existing_points].sort((a,b)=>a-b);
              dailyPointsInputText.value = dailyPointsSelectedBalls.value.map(x => String(x).padStart(2, '0')).join(' ');
            }
          }
          if (data.analysis) {
            dailyPointsAnalysis.value = data.analysis;
          }
        }
      } catch (err) {
        console.error('获取点位库信息失败:', err);
      } finally {
        dailyPointsLoading.value = false;
      }
    };

    const fetchDailyPointsHistory = async (limit = 30) => {
      try {
        const res = await fetch(`/api/daily-points/history?limit=${limit}`);
        if (res.ok) {
          const data = await res.json();
          dailyPointsHistory.value = data.records || [];
        }
      } catch (err) {
        console.error('获取历史点位对账失败:', err);
      }
    };

    const toggleDailyPointBall = (num) => {
      const idx = dailyPointsSelectedBalls.value.indexOf(num);
      if (idx !== -1) {
        dailyPointsSelectedBalls.value.splice(idx, 1);
      } else {
        if (dailyPointsSelectedBalls.value.length >= 20) {
          addLog('⚠️ 点位最多只能选择 20 个号码，请先取消其他号码！', 'warning');
          return;
        }
        dailyPointsSelectedBalls.value.push(num);
      }
      dailyPointsSelectedBalls.value.sort((a,b)=>a-b);
      dailyPointsInputText.value = dailyPointsSelectedBalls.value.map(x => String(x).padStart(2, '0')).join(' ');
    };

    const syncDailyPointsFromText = () => {
      const cleaned = (dailyPointsInputText.value || '')
        .replace(/，/g, ' ').replace(/、/g, ' ').replace(/；/g, ' ')
        .replace(/;/g, ' ').replace(/,/g, ' ').replace(/-/g, ' ').replace(/\|/g, ' ');
      const tokens = cleaned.match(/\b\d+\b/g) || [];
      const seen = new Set();
      const nums = [];
      for (const t of tokens) {
        const v = parseInt(t, 10);
        if (v >= 1 && v <= 80 && !seen.has(v)) {
          seen.add(v);
          nums.push(v);
        }
      }
      nums.sort((a,b)=>a-b);
      dailyPointsSelectedBalls.value = nums.slice(0, 20);
    };

    const clearDailyPointsInput = () => {
      dailyPointsSelectedBalls.value = [];
      dailyPointsInputText.value = '';
      dailyPointsAnalysis.value = null;
    };

    const submitDailyPointsForm = async (autoRun = null) => {
      if (dailyPointsSubmitting.value) return;
      syncDailyPointsFromText();
      if (dailyPointsSelectedBalls.value.length !== 20) {
        addLog(`❌ 点位数量错误：当前只有 ${dailyPointsSelectedBalls.value.length} 个号码，必须恰好为 20 个！`, 'danger');
        return;
      }
      const doAutoRun = autoRun !== null ? autoRun : dailyPointsAutoRun.value;
      try {
        dailyPointsSubmitting.value = true;
        addLog(`💾 正在提交目标期 [${dailyPointsTargetPeriod.value}] 20个点位并执行安全落盘...`, 'info');
        const payload = {
          date: dailyPointsTargetDate.value,
          period: String(dailyPointsTargetPeriod.value),
          points: dailyPointsSelectedBalls.value.map(x => String(x).padStart(2, '0')).join(' '),
          overwrite: true,
          auto_run: doAutoRun
        };
        const res = await fetch('/api/daily-points/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.status === 'ok') {
          addLog(`✅ 目标期 ${dailyPointsTargetPeriod.value} 点位已成功落盘至 daily_points.txt！`, 'success');
          if (data.data && data.data.analysis) {
            dailyPointsAnalysis.value = data.data.analysis;
          }
          await fetchDailyPointsInfo();
          await fetchDailyPointsHistory();
          // 点位变更后强制刷新 16 期操盘简报（点位交叉）
          try {
            const rt = (typeof window !== 'undefined' && window.__k8PageBindings) || {};
            if (typeof rt.fetchSixteenSummary === 'function') {
              await rt.fetchSixteenSummary(true);
              addLog('🔥 16期中热操盘简报已按新点位重算', 'success');
            }
          } catch (e) { /* ignore */ }
          if (doAutoRun && data.task_id) {
            isRunning.value = true;
            openTab('live_terminal');
            startLogPolling(data.task_id, async () => {
              const rt = (typeof window !== 'undefined' && window.__k8PageBindings) || {};
              if (typeof rt.fetchSpatialPointsSummary === 'function') await rt.fetchSpatialPointsSummary();
              if (typeof rt.fetchSuppressionSummary === 'function') await rt.fetchSuppressionSummary();
              if (typeof rt.fetchDatasourceMatrix === 'function') await rt.fetchDatasourceMatrix(null);
              if (typeof rt.fetchDatasourceSummary === 'function') await rt.fetchDatasourceSummary();
              if (typeof rt.fetchSixteenSummary === 'function') await rt.fetchSixteenSummary(true);
              addLog('✨ 点位下游全模块联动推演与上色已全部完成！矩阵已刷新到跟随表最新期。', 'success');
            });
          }
        } else {
          addLog(`❌ 点位落盘失败: ${data.detail || data.message || '未知错误'}`, 'danger');
        }
      } catch (err) {
        addLog(`❌ 提交点位异常: ${err.message}`, 'danger');
      } finally {
        dailyPointsSubmitting.value = false;
      }
    };

    const triggerDailyPointsSyncAll = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🚀 正在启动点位下游全模块联动计算 (热码加权 + 格式上色 + 空间点位 + 未开反弹)...', 'info');
        const res = await fetch('/api/daily-points/sync-all', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            const rt = (typeof window !== 'undefined' && window.__k8PageBindings) || {};
            if (typeof rt.fetchSpatialPointsSummary === 'function') await rt.fetchSpatialPointsSummary();
            if (typeof rt.fetchSuppressionSummary === 'function') await rt.fetchSuppressionSummary();
            if (typeof rt.fetchDatasourceMatrix === 'function') await rt.fetchDatasourceMatrix(null);
            if (typeof rt.fetchDatasourceSummary === 'function') await rt.fetchDatasourceSummary();
            addLog('✨ 点位下游全模块联动推演与上色已全部完成！矩阵已刷新到跟随表最新期。', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 触发点位联动异常: ' + err.message, 'danger');
      }
    };

    // ──────────────── 三高特征 (重复高/边高/冷高) × 每日点位数据服务 ────────────────
    const triHighSubTab = ref('excel_view'); // 'input' | 'excel_view' | 'cockpit'
    const triHighHistoryRows = ref([]);
    const triHighSummaryData = ref(null);
    const triHighInputPeriod = ref('');
    const triHighInputDate = ref('');
    const triHighRepeatText = ref('');
    const triHighRepeatBalls = ref([]);
    const triHighEdgeLeftText = ref('');
    const triHighEdgeLeftBalls = ref([]);
    const triHighEdgeRightText = ref('');
    const triHighEdgeRightBalls = ref([]);
    const triHighColdText = ref('');
    const triHighColdBalls = ref([]);
    const triHighSaving = ref(false);

    const parseNumbersFromStr = (str) => {
      if (!str) return [];
      const matches = str.match(/\d+/g);
      if (!matches) return [];
      const nums = matches.map(x => parseInt(x, 10)).filter(n => n >= 1 && n <= 80);
      return Array.from(new Set(nums));
    };

    const parseTriHighRepeat = () => {
      triHighRepeatBalls.value = parseNumbersFromStr(triHighRepeatText.value);
    };
    const parseTriHighEdgeLeft = () => {
      triHighEdgeLeftBalls.value = parseNumbersFromStr(triHighEdgeLeftText.value).slice(0, 4);
    };
    const parseTriHighEdgeRight = () => {
      triHighEdgeRightBalls.value = parseNumbersFromStr(triHighEdgeRightText.value).slice(0, 4);
    };
    const parseTriHighCold = () => {
      triHighColdBalls.value = parseNumbersFromStr(triHighColdText.value);
    };

    const clearTriHighInputs = () => {
      triHighRepeatText.value = '';
      triHighRepeatBalls.value = [];
      triHighEdgeLeftText.value = '';
      triHighEdgeLeftBalls.value = [];
      triHighEdgeRightText.value = '';
      triHighEdgeRightBalls.value = [];
      triHighColdText.value = '';
      triHighColdBalls.value = [];
    };

    const getUnionTriHighCount = () => {
      const all = new Set([
        ...triHighRepeatBalls.value,
        ...triHighEdgeLeftBalls.value,
        ...triHighEdgeRightBalls.value,
        ...triHighColdBalls.value
      ]);
      return all.size;
    };

    const getResonanceWithDailyPoints = () => {
      const pts = dailyPointsSelectedBalls.value || [];
      const union = new Set([
        ...triHighRepeatBalls.value,
        ...triHighEdgeLeftBalls.value,
        ...triHighEdgeRightBalls.value,
        ...triHighColdBalls.value
      ]);
      return pts.filter(n => union.has(n));
    };

    const extractTriHighNums = (arr) => {
      if (!arr || !Array.isArray(arr)) return [];
      return arr.map(item => {
        if (typeof item === 'object' && item !== null && 'num' in item) {
          return Number(item.num);
        }
        return Number(item);
      }).filter(n => !isNaN(n) && n >= 1 && n <= 80);
    };

    const selectTriHighQuickPeriod = (opt) => {
      if (!opt) return;
      triHighInputPeriod.value = opt.period;
      triHighInputDate.value = opt.date;

      // 如果选中的是已录入的历史期号，自动反填已录入的历史号码，方便用户直接修改/复核
      const found = (triHighHistoryRows.value || []).find(r => String(r.period) === String(opt.period));
      if (found) {
        const rep = extractTriHighNums(found.repeat_high);
        const el = extractTriHighNums(found.edge_high_left);
        const er = extractTriHighNums(found.edge_high_right);
        const cold = extractTriHighNums(found.cold_high);

        triHighRepeatBalls.value = rep;
        triHighRepeatText.value = rep.map(n => String(n).padStart(2, '0')).join(' ');

        triHighEdgeLeftBalls.value = el;
        triHighEdgeLeftText.value = el.map(n => String(n).padStart(2, '0')).join(' ');

        triHighEdgeRightBalls.value = er;
        triHighEdgeRightText.value = er.map(n => String(n).padStart(2, '0')).join(' ');

        triHighColdBalls.value = cold;
        triHighColdText.value = cold.map(n => String(n).padStart(2, '0')).join(' ');
      } else {
        // 待录入的新期号，清空输入框等待用户直接粘贴
        clearTriHighInputs();
      }
    };

    const fetchTriHighHistory = async () => {
      try {
        const res = await fetch('/api/tri-high/history');
        if (res.ok) {
          const data = await res.json();
          triHighHistoryRows.value = data.rows || [];
          if (triHighInputPeriod.value && !triHighRepeatText.value && !triHighEdgeLeftText.value && !triHighColdText.value) {
            const found = triHighHistoryRows.value.find(r => String(r.period) === String(triHighInputPeriod.value));
            if (found) {
              selectTriHighQuickPeriod({ period: found.period, date: found.date });
            }
          }
        }
      } catch (err) {
        console.error('获取三高历史数据失败:', err);
      }
    };

    const fetchTriHighSummary = async () => {
      try {
        const res = await fetch('/api/tri-high/summary');
        if (res.ok) {
          const data = await res.json();
          triHighSummaryData.value = data.data || data;
          const info = triHighSummaryData.value?.input_target_info;
          if (info && !triHighInputPeriod.value) {
            selectTriHighQuickPeriod({
              period: info.suggested_period,
              date: info.suggested_date
            });
          }
        }
      } catch (err) {
        console.error('获取三高推演摘要失败:', err);
      }
    };

    const saveTriHighRecord = async () => {
      if (!triHighInputPeriod.value) {
        alert('请输入目标研判期号！');
        return;
      }
      triHighSaving.value = true;
      try {
        const payload = {
          period: triHighInputPeriod.value.trim(),
          date: triHighInputDate.value.trim() || new Date().toISOString().slice(0, 10),
          repeat_high: triHighRepeatBalls.value,
          edge_high_left: triHighEdgeLeftBalls.value,
          edge_high_right: triHighEdgeRightBalls.value,
          cold_high: triHighColdBalls.value
        };
        const res = await fetch('/api/tri-high/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          const data = await res.json();
          addLog(`✅ 第 ${triHighInputPeriod.value} 期三高数据已成功保存并触发量化推演！`, 'success');
          clearTriHighInputs();
          await fetchTriHighHistory();
          await fetchTriHighSummary();
          const nextInfo = triHighSummaryData.value?.input_target_info;
          if (nextInfo) {
            triHighInputPeriod.value = nextInfo.suggested_period || '';
            triHighInputDate.value = nextInfo.suggested_date || new Date().toISOString().slice(0, 10);
          }
          triHighSubTab.value = 'excel_view';
        } else {
          const errText = await res.text();
          addLog(`❌ 保存三高数据失败: ${errText}`, 'danger');
        }
      } catch (err) {
        addLog('❌ 保存三高数据异常: ' + err.message, 'danger');
      } finally {
        triHighSaving.value = false;
      }
    };

    const triggerTriHighRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🧬 三高特征×每日点位深度共振推演任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-tri-high', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchTriHighSummary();
            await fetchTriHighHistory();
            await fetchAllModulesOverview();
            addLog('✨ 三高特征×每日点位深度共振量化推演已完成并刷新！', 'success');
          });
        } else {
          isRunning.value = false;
          const errText = await res.text();
          addLog(`❌ 启动三高共振推演失败 [HTTP ${res.status}]: ${errText}`, 'danger');
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动三高共振推演失败: ' + err.message, 'danger');
      }
    };

    return {
      dailyPointsInfo,
      dailyPointsHistory,
      dailyPointsInputText,
      dailyPointsSelectedBalls,
      dailyPointsTargetPeriod,
      dailyPointsTargetDate,
      dailyPointsAutoRun,
      dailyPointsSubmitting,
      dailyPointsLoading,
      dailyPointsAnalysis,
      fetchDailyPointsInfo,
      fetchDailyPointsHistory,
      toggleDailyPointBall,
      syncDailyPointsFromText,
      clearDailyPointsInput,
      submitDailyPointsForm,
      triggerDailyPointsSyncAll,
      triHighSubTab,
      triHighHistoryRows,
      triHighSummaryData,
      triHighInputPeriod,
      triHighInputDate,
      triHighRepeatText,
      triHighRepeatBalls,
      triHighEdgeLeftText,
      triHighEdgeLeftBalls,
      triHighEdgeRightText,
      triHighEdgeRightBalls,
      triHighColdText,
      triHighColdBalls,
      triHighSaving,
      parseTriHighRepeat,
      parseTriHighEdgeLeft,
      parseTriHighEdgeRight,
      parseTriHighCold,
      clearTriHighInputs,
      getUnionTriHighCount,
      getResonanceWithDailyPoints,
      fetchTriHighHistory,
      fetchTriHighSummary,
      saveTriHighRecord,
      triggerTriHighRun,
      selectTriHighQuickPeriod
    };
  });
})();
