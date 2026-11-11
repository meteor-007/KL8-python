/**
 * K8 page module: cockpit_live
 * Registered via K8Pages; merged into Vue setup() bindings.
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (cockpit_live)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, computed, nextTick } = vueApi;
    const {
      isRunning, openTab, addLog, startLogPolling, getThemeColors,
    terminalLogs, chartHandles, fetchPrediction
    } = ctx;

    // ══════════════════════════════════════════════════════════
    // 5 大新增量化决策与风控资产 (Meta-Gold / 三级漏斗 / 宏观环境 / FDR审计 / 模拟盘)
    // ══════════════════════════════════════════════════════════
    const metaGoldSummary = ref(null);
    const metaGoldReview = ref(null);
    const metaGoldReviewPeriods = ref(30);
    const metaGoldLoading = ref(false);

    const funnelSummary = ref(null);
    const funnelReview = ref(null);
    const funnelReviewPeriods = ref(30);
    const funnelLoading = ref(false);

    const envRegimeSummary = ref(null);
    const fdrAuditSummary = ref(null);
    const fdrAuditLoading = ref(false);
    const paperTradingSummary = ref(null);
    const fdrAuditPeriods = ref(100);
    const paperTradingRolling = ref(30);

    const fetchMetaGoldSummary = async () => {
      try {
        const res = await fetch('/api/quant/meta-gold');
        if (res.ok) {
          metaGoldSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取Meta-Gold失败:', err);
      }
    };

    const fetchMetaGoldReview = async (n = 30) => {
      metaGoldLoading.value = true;
      metaGoldReviewPeriods.value = n;
      try {
        const res = await fetch(`/api/quant/meta-gold/review?n=${n}`);
        if (res.ok) {
          metaGoldReview.value = await res.json();
        }
      } catch (err) {
        console.error('获取Meta-Gold复盘失败:', err);
      } finally {
        metaGoldLoading.value = false;
      }
    };

    const fetchFunnelSummary = async () => {
      try {
        const res = await fetch('/api/quant/funnel-pipeline');
        if (res.ok) {
          funnelSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取三级漏斗失败:', err);
      }
    };

    const fetchFunnelReview = async (n = 30) => {
      funnelLoading.value = true;
      funnelReviewPeriods.value = n;
      try {
        const res = await fetch(`/api/quant/funnel-pipeline/review?n=${n}`);
        if (res.ok) {
          funnelReview.value = await res.json();
        }
      } catch (err) {
        console.error('获取三级漏斗复盘失败:', err);
      } finally {
        funnelLoading.value = false;
      }
    };

    const fetchEnvRegimeSummary = async () => {
      try {
        const res = await fetch('/api/quant/environment-regime');
        if (res.ok) {
          envRegimeSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取宏观环境失败:', err);
      }
    };

    const fetchFdrAuditSummary = async (n = 100) => {
      fdrAuditPeriods.value = n;
      fdrAuditLoading.value = true;
      try {
        const res = await fetch(`/api/quant/fdr-audit?n=${n}`);
        if (res.ok) {
          fdrAuditSummary.value = await res.json();
        } else {
          // 接口失败时清空, 保留上一份旧数据会让页面"装新鲜" (E5 同类问题)
          fdrAuditSummary.value = null;
        }
      } catch (err) {
        console.error('获取FDR审计失败:', err);
        fdrAuditSummary.value = null;
      } finally {
        fdrAuditLoading.value = false;
      }
    };

    // C3: FDR 页展示辅助 —— 后端真实字段是 total_picks/pooled_rate/ci_lo/bh_q/winner,
    // 页面过去读的是 n_trials/hit_rate/ci_lower (字段名全错, 一直在显示空值)。
    const moduleCount = computed(() => {
      const m = fdrAuditSummary.value?.modules;
      return m ? Object.keys(m).length : null;
    });
    const winningCount = computed(() => {
      const w = fdrAuditSummary.value?.winning;
      return Array.isArray(w) ? w.length : null;
    });
    const baselineRate = computed(() => fdrAuditSummary.value?.baseline_rate ?? 0.25);
    const baselinePct = computed(() => (baselineRate.value * 100).toFixed(1));
    const pct = (v) => (v === null || v === undefined ? '-' : (v * 100).toFixed(1) + '%');
    const qClass = (info) => {
      if (info?.insufficient) return 'text-slate-400';
      const q = info?.bh_q;
      if (q === null || q === undefined) return 'text-slate-400';
      return q < 0.05 ? 'text-emerald-300 font-bold' : 'text-slate-400';
    };

    // 2026-10-21 统计诚信修复 (Bug#7 前端侧)：
    // 页面过去用 `significant` 判「✅ 过 BH-FDR」，但该字段是**单模块未校正**判据
    // (n≥min_n 且 CI下界>1 且 p≤α)；跨几十个模块校正后的结论在 bh_q / bh_significant / winner 上。
    // 实测 trinity_top5 原始 p=0.019 会被标成"过 BH-FDR"，而 BH-q=0.713 并未通过。
    // 统一改走本函数：以 BH 校正位为准，q 兜底。
    const bhPassed = (info) => {
      if (!info) return false;
      if (info.winner === true) return true;
      if (typeof info.bh_significant === 'boolean') return info.bh_significant;
      const q = info.bh_q;
      return typeof q === 'number' && q < 0.05;
    };

    // ══════════════════════════════════════════════════════════
    // E5: 数据新鲜度 —— 停更数据从此在界面上现形, 不许再装新鲜
    // ══════════════════════════════════════════════════════════
    const freshness = ref(null);
    const freshnessExpanded = ref(false);
    const freshnessLoading = ref(false);

    const fetchFreshness = async () => {
      freshnessLoading.value = true;
      try {
        const res = await fetch('/api/health/freshness');
        // 接口失败就清空: 留着上一份旧数据, 页面会继续"装新鲜"
        freshness.value = res.ok ? await res.json() : null;
      } catch (err) {
        console.error('获取数据新鲜度失败:', err);
        freshness.value = null;
      } finally {
        freshnessLoading.value = false;
      }
    };

    const freshnessBadCount = computed(() => freshness.value?.bad_count ?? 0);
    const freshnessMark = (state) =>
      ({ fresh: '✅', stale: '⚠️', anomaly: '❗', missing: '❌' }[state] || '·');
    const freshnessStateText = (state) =>
      ({ fresh: '新鲜', stale: '停更', anomaly: '期号超前', missing: '缺产出' }[state] || state);
    const freshnessLagText = (it) => {
      if (!it || it.lag === null || it.lag === undefined) return '未标期号';
      if (it.lag === -1) return '已备下一期';
      if (it.lag <= 0) return '本期已落稿';
      return `落后 ${it.lag} 期`;
    };

    // ══════════════════════════════════════════════════════════
    // B包: 模块投票注册表 —— 全站唯一的"谁有票权"权威源。
    // 各个模块卡片不再各自吹各自的, 状态一律从这张表读。
    // ══════════════════════════════════════════════════════════
    const moduleRegistry = ref(null);
    const moduleRegistryLoading = ref(false);
    const weeklyAdvice = ref(null);
    const weeklyAdviceLoading = ref(false);

    const fetchModuleRegistry = async () => {
      moduleRegistryLoading.value = true;
      try {
        const res = await fetch('/api/modules/registry');
        const d = res.ok ? await res.json() : null;
        moduleRegistry.value = d?.status === 'ok' ? d : null;
      } catch (err) {
        console.error('获取模块注册表失败:', err);
        moduleRegistry.value = null;
      } finally {
        moduleRegistryLoading.value = false;
      }
    };

    const fetchWeeklyAdvice = async () => {
      weeklyAdviceLoading.value = true;
      try {
        const res = await fetch('/api/advisor/weekly');
        weeklyAdvice.value = res.ok ? await res.json() : null;
      } catch (err) {
        console.error('获取周度建议单失败:', err);
        weeklyAdvice.value = null;
      } finally {
        weeklyAdviceLoading.value = false;
      }
    };

    // 按模块 id 拿注册表条目 (拿不到就返回空对象, 调用方自己决定降级显示)
    const moduleStatusOf = (id) => moduleRegistry.value?.registry?.modules?.[id] || null;

    // 给卡片渲染状态徽章: 三态 + 票权 + 一句话理由
    const moduleDisposition = (id) => {
      const m = moduleStatusOf(id);
      if (!m) return { known: false, label: '', cls: '', weight: null, note: '' };
      const status = m.status || 'observation';
      const w = m.vote_weight || 0;
      const style = {
        votable:     { label: '✅ 有票权',   cls: 'background: rgba(16,185,129,0.15); color:#6ee7b7; border:1px solid rgba(16,185,129,0.4);' },
        observation: { label: '👁 观察仓',   cls: 'background: rgba(245,158,11,0.15); color:#fcd34d; border:1px solid rgba(245,158,11,0.4);' },
        retired:     { label: '⏹ 已退役',   cls: 'background: rgba(244,63,94,0.15);  color:#fda4af; border:1px solid rgba(244,63,94,0.4);' },
      }[status] || { label: status, cls: 'background: rgba(100,116,139,0.2); color:#cbd5e1;' };
      return {
        known: true,
        status,
        label: style.label,
        cls: style.cls,
        weight: w,
        votable: status === 'votable' && w > 0,
        name: m.name || id,
        // 状态牌的悬浮说明: 优先用裁决理由, 否则用自动备注
        note: (m.decree && m.decree.reason) || m.auto_note || m.watermark || '',
        watermark: m.watermark || '',
        preregistered: !!m.preregistered || !!m.preregistered_hypothesis,
      };
    };

    // 两个观察仓模块的状态牌 (B3): 模板里别重复调函数, 用 computed 收口
    const primeCompositeGate = computed(() => moduleDisposition('prime_composite'));
    const psychGameGate = computed(() => moduleDisposition('psychological_game'));

    // C5: 模拟盘页的分模块前瞻账 —— dict 转数组, 已开奖的排前面, 待对账的沉底
    const byModuleRows = computed(() => {
      const bm = paperTradingSummary.value?.by_module;
      if (!bm || typeof bm !== 'object') return [];
      return Object.entries(bm)
        .map(([id, info]) => ({
          id,
          name: info?.name || id,
          disp: moduleDisposition(id),
          n_periods: info?.n_periods ?? 0,
          pending: info?.pending ?? 0,
          recorded: info?.recorded ?? 0,
          pooled_rate: info?.pooled_rate ?? null,
          lift: info?.lift ?? null,
          lift_ci_lo: info?.lift_ci_lo ?? null,
          bh_q: info?.bh_q ?? null,
          // 未校正位与 BH 校正位都带上，模板统一用 bhPassed() 判定
          significant: !!info?.significant,
          raw_significant: !!info?.raw_significant,
          bh_significant: !!info?.bh_significant,
          winner: !!info?.winner,
          insufficient: info?.insufficient !== false,
          gate_progress: info?.gate_progress || '-',
        }))
        .sort((a, b) => {
          if (a.lift === null && b.lift === null) return b.recorded - a.recorded;
          if (a.lift === null) return 1;
          if (b.lift === null) return -1;
          return b.lift - a.lift;
        });
    });

    // B包: 注册表表格 —— 按票权从大到小排, 没有票权的沉底。顺带算"影响力占比",
    // 让用户一眼看出共识结论到底是谁说了算 (过去这件事是黑箱)。
    const voteWeightSum = computed(() => {
      const mods = moduleRegistry.value?.registry?.modules;
      if (!mods) return 0;
      return Object.values(mods)
        .filter((m) => m.status === 'votable')
        .reduce((s, m) => s + (m.vote_weight || 0), 0);
    });

    const registryRows = computed(() => {
      const mods = moduleRegistry.value?.registry?.modules;
      if (!mods) return [];
      const total = voteWeightSum.value;
      const order = { votable: 0, observation: 1, retired: 2 };
      return Object.entries(mods)
        .map(([id, m]) => {
          const w = m.vote_weight || 0;
          const votable = m.status === 'votable' && w > 0;
          return {
            id,
            name: m.name || id,
            status: m.status,
            label: { votable: '✅ 有票权', observation: '👁 观察仓', retired: '⏹ 已退役' }[m.status] || m.status,
            weight: w,
            share: votable && total > 0 ? w / total : null,
            lift: m.evidence?.lift ?? null,
            lift_shrunk: m.evidence?.lift_shrunk ?? null,
            n: m.evidence?.n_periods ?? null,
            reason: (m.decree && m.decree.reason) || m.auto_note || m.watermark || '',
            note: m.watermark || m.auto_note || '',
            preregistered: !!m.preregistered,
            prospective: m.prospective_periods ?? null,
          };
        })
        .sort((a, b) =>
          (order[a.status] ?? 9) - (order[b.status] ?? 9) || b.weight - a.weight);
    });

    const fetchPaperTradingSummary = async (rolling = 30) => {
      paperTradingRolling.value = rolling;
      try {
        const res = await fetch(`/api/quant/paper-trading?rolling=${rolling}`);
        if (res.ok) {
          paperTradingSummary.value = await res.json();
        }
      } catch (err) {
        console.error('获取模拟盘台账失败:', err);
      }
    };

    return {
      metaGoldSummary,
      metaGoldReview,
      metaGoldReviewPeriods,
      metaGoldLoading,
      fetchMetaGoldSummary,
      fetchMetaGoldReview,
      funnelSummary,
      funnelReview,
      funnelReviewPeriods,
      funnelLoading,
      fetchFunnelSummary,
      fetchFunnelReview,
      envRegimeSummary,
      fdrAuditSummary,
      fdrAuditLoading,
      moduleCount,
      winningCount,
      baselineRate,
      baselinePct,
      pct,
      qClass,
      bhPassed,
      freshness,
      freshnessExpanded,
      freshnessLoading,
      freshnessBadCount,
      freshnessMark,
      freshnessStateText,
      freshnessLagText,
      fetchFreshness,
      moduleRegistry,
      moduleRegistryLoading,
      weeklyAdvice,
      weeklyAdviceLoading,
      fetchModuleRegistry,
      fetchWeeklyAdvice,
      moduleStatusOf,
      moduleDisposition,
      primeCompositeGate,
      psychGameGate,
      byModuleRows,
      voteWeightSum,
      registryRows,
      paperTradingSummary,
      fdrAuditPeriods,
      paperTradingRolling,
      fetchEnvRegimeSummary,
      fetchFdrAuditSummary,
      fetchPaperTradingSummary
    };
  });
})();
