/**
 * K8 page module: sixteen
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (sixteen)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

    // ──────────────── 16期中热频次动态推演与组合决策 ────────────────
    const sixteenSummary = ref(null);
    const sixteenReview = ref(null);
    const sixteenReviewPeriods = ref(30);
    const sixteenHistory = ref([]);
    const selectedSixteenReport = ref(null);
    const sixteenReportDetail = ref('');
    const sixteenLoading = ref(false);
    const sixteenMatrixFilter = ref('ALL');
    // chart instance lives on ctx.chartHandles.sixteenDistChart

    const filteredSixteenMatrix = computed(() => {
      if (!sixteenSummary.value || !sixteenSummary.value.matrix_80) return [];
      const list = sixteenSummary.value.matrix_80;
      const f = sixteenMatrixFilter.value;
      if (f === 'ALL') return list;
      if (f === 'PROMO') return list.filter(c => !c.is_outgoing);
      if (f === 'DEMO') return list.filter(c => c.is_outgoing);
      if (f === 'ICE_BREAK') return list.filter(c => !c.is_outgoing && (c.freq_16 === 0 || c.freq_16 === 1));
      if (f === 'WARM_WAKE') return list.filter(c => !c.is_outgoing && c.freq_16 === 2);
      if (f === 'GOLD_RUSH') return list.filter(c => !c.is_outgoing && c.freq_16 === 3);
      if (f === 'HOT_MOMENTUM') return list.filter(c => !c.is_outgoing && (c.freq_16 === 4 || c.freq_16 === 5));
      if (f === 'OUTGOING_COOL') return list.filter(c => c.is_outgoing && c.freq_16 >= 6);
      if (f === 'GOLD_CORE') {
        const goldPicks = [
          sixteenSummary.value.gold_dan,
          sixteenSummary.value.silver_dan,
          sixteenSummary.value.bronze_dan,
          ...(sixteenSummary.value.medium_top5 || []),
          ...((sixteenSummary.value.freq_bucket_picks || {}).all_picks || [])
        ];
        return list.filter(c => goldPicks.includes(c.number));
      }
      if (f === 'BUCKET_PICKS') {
        const picks = ((sixteenSummary.value.freq_bucket_picks || {}).all_picks || []);
        return list.filter(c => picks.includes(c.number));
      }
      return list;
    });

    const sixteenBucketLookback = ref(null);
    const sixteenBucketAdvanced = ref(false);
    const sixteenBucketSortCompare = ref(null);

    const fetchSixteenBucketLookback = async (offset = 1) => {
      try {
        sixteenLoading.value = true;
        const res = await fetch(`/api/sixteen/bucket-lookback?offset=${offset}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        sixteenBucketLookback.value = await res.json();
        addLog(`📊 已加载第 ${sixteenBucketLookback.value.target_period} 期频次桶精选回看（命中高亮）`, 'success');
      } catch (err) {
        addLog('❌ 回看精选命中失败: ' + err.message, 'danger');
      } finally {
        sixteenLoading.value = false;
      }
    };

    const clearSixteenBucketLookback = () => {
      sixteenBucketLookback.value = null;
    };

    const copySixteenWechatBrief = async () => {
      const text = (sixteenSummary.value && sixteenSummary.value.daily_ops_brief
        && sixteenSummary.value.daily_ops_brief.wechat_text) || '';
      if (!text) return;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const ta = document.createElement('textarea');
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        }
        addLog('📋 已复制16期分桶原文到剪贴板', 'success');
      } catch (e) {
        addLog('❌ 复制失败: ' + (e && e.message ? e.message : e), 'danger');
      }
    };

    const fetchSixteenBucketSortCompare = async (n = 20) => {
      try {
        sixteenLoading.value = true;
        addLog(`📊 对比近 ${n} 期各桶内排序的精选命中…`, 'info');
        const res = await fetch(`/api/sixteen/bucket-sort-compare?n=${n}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        sixteenBucketSortCompare.value = await res.json();
        const best = sixteenBucketSortCompare.value.best_sort_by;
        const cur = sixteenBucketSortCompare.value.current_sort_by;
        if (best && best !== cur) {
          addLog(`✨ 样本最优排序: ${best}（当前 ${cur}，可一键切换）`, 'success');
        } else {
          addLog(`✨ 当前默认 ${cur} 已是近 ${sixteenBucketSortCompare.value.n_periods} 期样本最优`, 'success');
        }
      } catch (err) {
        addLog('❌ 排序对比失败: ' + err.message, 'danger');
      } finally {
        sixteenLoading.value = false;
      }
    };

    const applyBestBucketSort = async () => {
      const best = sixteenBucketSortCompare.value && sixteenBucketSortCompare.value.best_sort_by;
      if (!best) return;
      await applySixteenBucketConfig({ sort_by: best });
    };

    const setSixteenMatrixFilter = (filterKey) => {
      sixteenMatrixFilter.value = filterKey;
    };

    const scrollToSixteenMatrixReview = () => {
      const el = document.getElementById('module-review-sixteen-matrix');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (!sixteenReview.value || !sixteenReview.value.rows || !sixteenReview.value.rows.length) {
        fetchSixteenReview(sixteenReviewPeriods.value || 30);
      }
    };

    const isSixteenBucketHit = (hitList, n) => {
      if (!hitList || !hitList.length) return false;
      return hitList.indexOf(n) >= 0 || hitList.indexOf(Number(n)) >= 0;
    };

    const applySixteenBucketConfig = async (patch) => {
      if (sixteenLoading.value || isRunning.value) return;
      try {
        sixteenLoading.value = true;
        addLog(`📊 更新频次桶精选规则: ${JSON.stringify(patch)}`, 'info');
        const res = await fetch('/api/sixteen/bucket-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch || {})
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        if (data.summary) {
          sixteenSummary.value = data.summary;
          nextTick(() => updateSixteenDistChart());
        } else {
          await fetchSixteenSummary();
        }
        addLog('✨ 频次桶精选/剩余已按新规则重算', 'success');
      } catch (err) {
        addLog('❌ 更新桶精选配置失败: ' + err.message, 'danger');
      } finally {
        sixteenLoading.value = false;
      }
    };

    const fetchSixteenSummary = async (force = false) => {
      try {
        const res = await fetch(`/api/sixteen/summary${force ? '?force=true' : ''}`);
        if (res.ok) {
          sixteenSummary.value = await res.json();
          nextTick(() => {
            updateSixteenDistChart();
          });
        }
      } catch (err) {
        console.error('获取16期中热推演摘要失败:', err);
      }
    };

    const formatSixteenKillHits = (arr) => {
      const list = Array.isArray(arr) ? arr : [];
      if (!list.length) return '无';
      return list.map((x) => String(x).padStart(2, '0')).join(' ');
    };

    const sixteenOpsPointsSet = computed(() => {
      const pts = (((sixteenSummary.value || {}).daily_ops_brief || {}).points || {}).points || [];
      return new Set(pts.map((x) => Number(x)));
    });
    const sixteenOpsTipSet = computed(() => {
      const tip = ((sixteenSummary.value || {}).daily_ops_brief || {}).tip3 || [];
      return new Set(tip.map((x) => Number(x)));
    });

    const sixteenBallChipClass = (n, baseHit) => {
      const num = Number(n);
      if (baseHit) return 'bg-fuchsia-500/25 border-2 border-fuchsia-300 text-fuchsia-100';
      if (sixteenOpsTipSet.value.has(num)) return 'bg-emerald-500/25 border-2 border-emerald-300 text-emerald-100';
      if (sixteenOpsPointsSet.value.has(num)) return 'bg-cyan-500/15 border border-cyan-400/55 text-cyan-200';
      return null;
    };

    const sixteenDisplayTop5 = computed(() => {
      const s = sixteenSummary.value || {};
      const brief = s.daily_ops_brief || {};
      const tip = brief.tip3 || s.ops_tip3 || s.top3_gold || (s.medium_top5 || []).slice(0, 3);
      return tip.slice(0, 3);
    });
    const sixteenDisplayTop12 = computed(() => sixteenDisplayTop5.value);
    const sixteenTip3Text = computed(() => {
      const tip = sixteenDisplayTop5.value;
      if (!tip.length) return '--';
      return tip.map((n) => String(n).padStart(2, '0')).join(' ');
    });
    const sixteenDisplayRebound = computed(() => {
      const s = sixteenSummary.value || {};
      const rb = (s.daily_ops_brief && s.daily_ops_brief.rebound) || {};
      return {
        gold: rb.gold != null ? rb.gold : (s.gold_dan != null ? s.gold_dan : null),
        silver: rb.silver != null ? rb.silver : (s.silver_dan != null ? s.silver_dan : null),
        bronze: rb.bronze != null ? rb.bronze : (s.bronze_dan != null ? s.bronze_dan : null),
      };
    });
    const sixteenDisplayPairs = computed(() => {
      const s = sixteenSummary.value || {};
      const ops = (s.daily_ops_brief && s.daily_ops_brief.pairs) || [];
      return ops.length ? ops : (s.top5_pairs || []);
    });

    const fetchSixteenReview = async (n = 30) => {
      try {
        sixteenLoading.value = true;
        sixteenReviewPeriods.value = n;
        const res = await fetch(`/api/sixteen/review?n=${n}`);
        if (res.ok) {
          sixteenReview.value = await res.json();
        }
      } catch (err) {
        console.error('获取16期中热推演复盘失败:', err);
      } finally {
        sixteenLoading.value = false;
      }
    };

    const fetchSixteenHistory = async () => {
      try {
        const res = await fetch('/api/sixteen/history');
        if (res.ok) {
          sixteenHistory.value = await res.json();
          if (sixteenHistory.value && sixteenHistory.value.length > 0 && !selectedSixteenReport.value) {
            selectSixteenReport(sixteenHistory.value[0]);
          }
        }
      } catch (err) {
        console.error('获取16期中热研报列表失败:', err);
      }
    };

    const selectSixteenReport = async (item) => {
      selectedSixteenReport.value = item;
      try {
        const res = await fetch(`/api/sixteen/history-detail/${item.filename}`);
        if (res.ok) {
          const data = await res.json();
          sixteenReportDetail.value = data.content || '';
        }
      } catch (err) {
        console.error('获取16期中热研报详情失败:', err);
        sixteenReportDetail.value = '加载研报失败: ' + err.message;
      }
    };

    const triggerSixteenRun = async () => {
      if (isRunning.value) return;
      try {
        isRunning.value = true;
        openTab('live_terminal');
        terminalLogs.value = [];
        addLog('🔥 16期中热频次动态推演与组合决策任务已提交后台...', 'info');
        const res = await fetch('/api/pipeline/run-sixteen', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          const taskId = data.task_id;
          startLogPolling(taskId, async () => {
            await fetchSixteenSummary(true);
            await fetchSixteenReview(sixteenReviewPeriods.value);
            await fetchSixteenHistory();
            addLog('✨ 16期中热频次推演已实时刷新完毕！', 'success');
          });
        }
      } catch (err) {
        isRunning.value = false;
        addLog('❌ 启动16期中热推演失败: ' + err.message, 'danger');
      }
    };

    const updateSixteenDistChart = () => {
      const dom = document.getElementById('sixteenDistChart');
      if (!dom || !sixteenSummary.value) return;
      if (!chartHandles.sixteenDistChart || chartHandles.sixteenDistChart.isDisposed()) {
        chartHandles.sixteenDistChart = echarts.init(dom);
      }
      const tc = getThemeColors();
      const dist = sixteenSummary.value.distribution_counts || {};
      const categories = ['0次\n(遗漏冷)', '1次\n(低频)', '2次\n(温冷)', '3次\n(中温)', '4次\n(黄金)', '5次\n(活跃)', '6次\n(强热)', '7次\n(高热)', '8+次\n(极热)'];
      const values = [
        dist['0'] || 0,
        dist['1'] || 0,
        dist['2'] || 0,
        dist['3'] || 0,
        dist['4'] || 0,
        dist['5'] || 0,
        dist['6'] || 0,
        dist['7'] || 0,
        dist['8+'] || 0
      ];
      const colors = ['#64748b', '#38bdf8', '#0ea5e9', '#facc15', '#10b981', '#34d399', '#fb923c', '#f87171', '#f43f5e'];

      const opt = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor },
          formatter: (params) => {
            const p = params[0];
            const cleanName = (p.name || '').replace('\n', ' ');
            const val = p.value || 0;
            const pct = ((val / 80) * 100).toFixed(1);
            return `<div style="font-weight:bold;color:${tc.primary};margin-bottom:4px;">${cleanName}</div>
                    <div style="font-size:12px;line-height:1.6;">
                      <div>📊 号码个数: <b style="color:${tc.secondary};">${val}</b> 码</div>
                      <div>🎯 大盘占比: <b>${pct}%</b> (共80码)</div>
                    </div>`;
          }
        },
        grid: { top: '16%', left: '3%', right: '3%', bottom: '12%', containLabel: true },
        xAxis: {
          type: 'category',
          data: categories,
          axisLabel: {
            color: tc.textColor,
            fontSize: 12,
            interval: 0,
            lineHeight: 16
          },
          axisLine: { lineStyle: { color: tc.axisColor } }
        },
        yAxis: {
          type: 'value',
          name: '号码个数 (码)',
          nameTextStyle: { color: tc.textColor, fontSize: 12 },
          axisLabel: { color: tc.textColor },
          splitLine: { lineStyle: { color: tc.splitColor } }
        },
        series: [{
          name: '号码个数',
          type: 'bar',
          barMaxWidth: 52,
          barCategoryGap: '28%',
          data: values.map((val, idx) => ({
            value: val,
            itemStyle: {
              color: colors[idx],
              borderRadius: [6, 6, 0, 0]
            }
          })),
          label: {
            show: true,
            position: 'top',
            color: tc.textColor,
            fontWeight: 'bold',
            fontSize: 13,
            formatter: '{c} 码'
          }
        }]
      };
      chartHandles.sixteenDistChart.setOption(opt, true);
      chartHandles.sixteenDistChart.resize();
    };

    return {
      sixteenSummary,
      sixteenReview,
      sixteenReviewPeriods,
      sixteenHistory,
      selectedSixteenReport,
      sixteenReportDetail,
      sixteenLoading,
      sixteenMatrixFilter,
      filteredSixteenMatrix,
      setSixteenMatrixFilter,
      scrollToSixteenMatrixReview,
      fetchSixteenSummary,
      sixteenDisplayTop5,
      sixteenDisplayTop12,
      sixteenTip3Text,
      sixteenDisplayRebound,
      sixteenDisplayPairs,
      sixteenBallChipClass,
      sixteenOpsPointsSet,
      formatSixteenKillHits,
      fetchSixteenReview,
      fetchSixteenHistory,
      selectSixteenReport,
      triggerSixteenRun,
      updateSixteenDistChart,
      applySixteenBucketConfig,
      isSixteenBucketHit,
      sixteenBucketLookback,
      fetchSixteenBucketLookback,
      clearSixteenBucketLookback,
      copySixteenWechatBrief,
      sixteenBucketAdvanced,
      sixteenBucketSortCompare,
      fetchSixteenBucketSortCompare,
      applyBestBucketSort
    };
  });
})();
