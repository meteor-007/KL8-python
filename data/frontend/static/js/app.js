/**
 * K8-QUANT Web Multi-Level Cyber Navigation & Tab Management System
 * 多级菜单树、动态 Tab 标签页管理、6 大系统主题自由切换与 ECharts 响应式换肤
 */

const { createApp, ref, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } = Vue;

const App = {
  setup() {
    // ────────────── 全局双重环境感知机制 (Environment Detector) ──────────────
    const detectIsMobile = () => {
      if (typeof window === 'undefined') return false;
      const isNarrow = window.innerWidth <= 1024;
      const isTouch = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || ('ontouchstart' in window);
      return isNarrow || isTouch;
    };

    const isMobile = ref(detectIsMobile());
    const isDesktop = computed(() => !isMobile.value);

    // 侧边栏折叠状态 (桌面端生效；移动端恒置 false，杜绝菜单文字坍塌)
    const isSidebarCollapsed = ref(false);
    // 移动端侧边栏抽屉状态 (<=1024px 时生效，桌面端无副作用)
    const isMobileSidebarOpen = ref(false);

    // 同步将 is-mobile / is-desktop 样式类打在 <html> 和 <body> 上，驱动全局 CSS 自适应
    const syncEnvironmentClasses = () => {
      const mobileVal = detectIsMobile();
      isMobile.value = mobileVal;
      if (typeof document !== 'undefined') {
        const root = document.documentElement;
        const body = document.body;
        if (mobileVal) {
          root.classList.add('is-mobile');
          root.classList.remove('is-desktop');
          body.classList.add('is-mobile');
          body.classList.remove('is-desktop');
          isSidebarCollapsed.value = false;
        } else {
          root.classList.add('is-desktop');
          root.classList.remove('is-mobile');
          body.classList.add('is-desktop');
          body.classList.remove('is-mobile');
        }
      }
    };
    syncEnvironmentClasses();

    const toggleMobileSidebar = (forceState) => {
      if (typeof forceState === 'boolean') {
        isMobileSidebarOpen.value = forceState;
      } else {
        isMobileSidebarOpen.value = !isMobileSidebarOpen.value;
      }
      if (isMobileSidebarOpen.value) {
        // 移动端展开抽屉时，强制保持非折叠，完整显示所有文字
        isSidebarCollapsed.value = false;
      }
    };

    // 统一侧边栏切换动作：移动端点击“收起侧边栏”直接关闭抽屉，桌面端切换折叠/展开
    const handleSidebarToggle = () => {
      if (isMobile.value || window.innerWidth <= 1024) {
        isMobileSidebarOpen.value = false;
        isSidebarCollapsed.value = false;
      } else {
        isSidebarCollapsed.value = !isSidebarCollapsed.value;
      }
    };

    // ──────────────── 0. 6 大系统主题状态与切换 ────────────────
    const themes = [
      { id: 'theme-cyber', name: '深邃赛博', icon: '🌌', desc: '极客蓝霓虹 (默认)', dotColor: '#00f0ff', badge: 'CYBER' },
      { id: 'theme-gold', name: '黑金尊享', icon: '👑', desc: '曜石黑金操盘手', dotColor: '#f59e0b', badge: 'GOLD' },
      { id: 'theme-aurora', name: '极光星河', icon: '✨', desc: '极光幻彩魅紫', dotColor: '#c084fc', badge: 'AURORA' },
      { id: 'theme-emerald', name: '量子翡翠', icon: '🌲', desc: '矩阵代码荧光绿', dotColor: '#10b981', badge: 'MATRIX' },
      { id: 'theme-midnight', name: '深空暗夜', icon: '🌑', desc: '纯粹极简纯黑', dotColor: '#ffffff', badge: 'OLED' },
      { id: 'theme-light', name: '皓月雅白', icon: '☀️', desc: '典雅明亮日间', dotColor: '#0284c7', badge: 'LIGHT' }
    ];

    const currentTheme = ref(localStorage.getItem('k8_quant_theme') || 'theme-cyber');
    const showThemeDropdown = ref(false);

    const currentThemeObj = computed(() => {
      return themes.find(t => t.id === currentTheme.value) || themes[0];
    });

    const setTheme = (themeId) => {
      currentTheme.value = themeId;
      localStorage.setItem('k8_quant_theme', themeId);
      document.documentElement.className = themeId;
      document.body.className = themeId;
      showThemeDropdown.value = false;
      const themeObj = themes.find(t => t.id === themeId);
      addLog(`🎨 系统界面主题已无缝切换至【${themeObj ? themeObj.name : themeId}】`, 'info');
      // 重新调整图表配色
      nextTick(() => {
        updateAllCharts();
      });
    };

    // 多级菜单：真源见 menu_registry.js（K8MenuRegistry）
    const menuGroups = ref(
      (window.K8MenuRegistry && typeof window.K8MenuRegistry.buildMenuGroups === 'function')
        ? window.K8MenuRegistry.buildMenuGroups()
        : []
    );
    const MENU_OPENED_STORAGE_KEY =
      (window.K8MenuRegistry && window.K8MenuRegistry.MENU_OPENED_STORAGE_KEY) || 'k8.menu.opened.v6';

    const persistMenuOpenedState = () => {
      try {
        const state = {};
        menuGroups.value.forEach((g) => {
          state[g.id] = !!g.opened;
        });
        localStorage.setItem(MENU_OPENED_STORAGE_KEY, JSON.stringify(state));
      } catch (e) { /* ignore quota / private mode */ }
    };

    const isGroupActive = (group) => {
      if (!group || !group.children) return false;
      return group.children.some((c) => c.key === activeTab.value);
    };

    const expandMenuGroupForKey = (key) => {
      const meta = (window.K8MenuRegistry && window.K8MenuRegistry.MENU_BY_KEY[key]) || null;
      if (!meta || !meta.hub) return;
      const group = menuGroups.value.find((g) => g.id === meta.hub);
      if (group && !group.opened) {
        group.opened = true;
        persistMenuOpenedState();
      }
    };

    // 动态 Tab：默认进入遗传算法（高维区仅保留 GA + 线性代数）
    const _menuMeta = (key) => (window.K8MenuRegistry && window.K8MenuRegistry.MENU_BY_KEY[key]) || {};
    const tabs = ref([
      {
        key: 'genetic_cockpit',
        title: _menuMeta('genetic_cockpit').title || '遗传算法自进化推演战区',
        shortTitle: _menuMeta('genetic_cockpit').shortTitle || '遗传算法',
        icon: _menuMeta('genetic_cockpit').icon || '🧬',
        closable: false
      },
      {
        key: 'sixteen_cockpit',
        title: _menuMeta('sixteen_cockpit').title || '16期中热频次推演（含频次全景）',
        shortTitle: _menuMeta('sixteen_cockpit').shortTitle || '16期中热推演',
        icon: _menuMeta('sixteen_cockpit').icon || '🔥',
        closable: true
      }
    ]);
    const activeTab = ref('genetic_cockpit');
    expandMenuGroupForKey(activeTab.value);

    watch(activeTab, (newTab) => {
      if (newTab === 'modules_overview') {
        fetchAllAiMathModels();
      }
      if (newTab === 'classic_overview') {
        fetchAllClassicModels();
      }
      if (newTab === 'draw_trend_chart') {
        fetchLotteryTrends(trendLimit.value || 100);
        fetchModuleConsensus();
        setTimeout(() => {
          const el = document.getElementById('trendTableWrapper');
          if (el) el.scrollTop = el.scrollHeight;
        }, 120);
      }
      if (newTab === 'points_matrix' && (!spatialPointsMatrix.value || spatialPointsMatrix.value.length === 0)) {
        fetchSpatialPointsMatrix();
      }
      if (newTab === 'unified_brain_cockpit') {
        fetchUnifiedBrain();
      }
      if (newTab === 'nightly_scheduler') {
        fetchEvolutionStatus();
        fetchSchedulerStatus();
      }
      if (newTab === 'tri_high_input') {
        fetchTriHighHistory();
        fetchTriHighSummary();
      }
      if (newTab === 'psychological_game') {
        fetchPsychologicalGameData();
        fetchPsychologicalGameBacktest();
      }
      if (newTab === 'point_omission_cockpit') {
        fetchPointOmissionSummary();
        fetchPointOmissionBacktest();
        fetchPointOmissionHitLedger();
      }
      if (newTab === 'genetic_cockpit') {
        fetchGeneticData();
        fetchGeneticReview();
      }
      if (newTab === 'linear_algebra_cockpit') {
        fetchLinearAlgebraData();
      }
      if (newTab === 'random_forest_cockpit') {
        fetchRandomForestData();
      }
      if (newTab === 'error_correction_cockpit') {
        fetchErrorCorrectionData();
      }
      if (newTab === 'spear_shield_cockpit') {
        fetchSpearShieldData();
      }
      if (newTab === 'point_road_cockpit') {
        fetchPointRoadData();
      }
      if (newTab === 'sixteen_cockpit' || newTab === 'sixteen_dist') {
        fetchSixteenSummary(!sixteenSummary?.value?.daily_ops_brief);
      }
      if (newTab === 'dtw_cockpit') {
        fetchDTWData();
      }
      if (newTab === 'transformer_cockpit') {
        fetchTransformerData();
      }
      if (newTab === 'matrix_profile_cockpit') {
        fetchMatrixProfileData();
      }
      if (newTab === 'tda_cockpit') {
        fetchTDAData();
      }
      nextTick(() => {
        handleResize();
        if (newTab === 'sixteen_dist') {
          updateSixteenDistChart();
        }
        if (newTab === 'genetic_cockpit') {
          initGeneticConvergenceChart();
          initGeneticRadarChart();
        }
      });
    });

    const toggleGroup = (group) => {
      group.opened = !group.opened;
      persistMenuOpenedState();
    };

    const toggleAllGroups = (expandAll) => {
      const targetState = typeof expandAll === 'boolean' ? expandAll : !menuGroups.value.every(g => g.opened);
      menuGroups.value.forEach(g => {
        g.opened = targetState;
      });
      persistMenuOpenedState();
    };

    // 旧「复盘审计」独立 tab → 对应模块驾驶舱（复盘已迁入页内，不再单独开菜单）
    const REVIEW_TAB_ALIASES = {
      gold_pick2_review: 'gold_pick2_cockpit',
      sixteen_review: 'sixteen_cockpit',
      datasource_review: 'datasource_matrix',
      suppression_review: 'suppression_cockpit',
      jingle_review: 'jingle_cockpit',
      master_review_cockpit: 'genetic_cockpit',
      lstm_review: 'lstm_cockpit',
      follow_review: 'follow_cockpit',
      points_review: 'points_cockpit',
      gemini_review: 'gemini_cockpit',
      sixteen_matrix: 'sixteen_cockpit'
    };

    // 模块页内复盘锚点（openModuleHistory 滚到此处）
    const MODULE_REVIEW_ANCHORS = {
      gold_pick2_cockpit: 'module-review-gold_pick2',
      sixteen_cockpit: 'module-review-sixteen-matrix',
      sixteen_matrix: 'module-review-sixteen-matrix',
      datasource_cockpit: 'module-review-datasource-matrix',
      datasource_matrix: 'module-review-datasource-matrix',
      suppression_cockpit: 'module-review-suppression',
      jingle_cockpit: 'module-review-jingle',
      psychological_game: 'module-review-psychological_game',
      genetic_cockpit: 'module-review-genetic',
      linear_algebra_cockpit: 'module-review-linear_algebra',
      random_forest_cockpit: 'module-review-random_forest',
      error_correction_cockpit: 'module-review-error-correction'
    };

    const openTab = (key, title, icon) => {
      if (REVIEW_TAB_ALIASES[key]) {
        const target = REVIEW_TAB_ALIASES[key];
        openTab(target, title, icon);
        const anchor = MODULE_REVIEW_ANCHORS[target];
        if (anchor) {
          nextTick(() => {
            setTimeout(() => {
              const el = document.getElementById(anchor);
              if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 80);
          });
        }
        return;
      }
      const meta = (window.K8MenuRegistry && window.K8MenuRegistry.MENU_BY_KEY[key]) || {};
      const resolvedTitle = title || meta.title || key;
      const resolvedShortTitle = meta.shortTitle || resolvedTitle;
      const resolvedIcon = icon || meta.icon || '📄';
      const existing = tabs.value.find(t => t.key === key);
      if (!existing) {
        tabs.value.push({
          key,
          title: resolvedTitle,
          shortTitle: resolvedShortTitle,
          icon: resolvedIcon,
          closable: key !== 'live_cockpit'
        });
      } else {
        if (!title && meta.title && existing.title !== meta.title) {
          // 侧栏真源标题优先，纠正历史硬编码漂移
          existing.title = meta.title;
          if (meta.icon) existing.icon = meta.icon;
        }
        if (meta.shortTitle) existing.shortTitle = meta.shortTitle;
        else if (!existing.shortTitle) existing.shortTitle = existing.title;
      }
      activeTab.value = key;
      expandMenuGroupForKey(key);
      // 移动端：点击菜单后自动收起抽屉式侧边栏
      isMobileSidebarOpen.value = false;
      if (key === 'lstm_cockpit') {
        fetchLstmSummary();
      } else if (key === 'lstm_review') {
        fetchLstmReview(lstmReviewPeriods.value);
      } else if (key === 'lstm_reports') {
        fetchLstmReports();
      } else if (key === 'jingle_cockpit') {
        fetchJingleSummary();
        fetchJingleRules();
        fetchJingleReview(jingleReviewPeriods.value);
      } else if (key === 'jingle_review') {
        fetchJingleReview(jingleReviewPeriods.value);
      } else if (key === 'follow_cockpit') {
        fetchFollowSummary();
        fetchFollowConditions();
      } else if (key === 'follow_review') {
        fetchFollowReview(followReviewPeriods.value);
      } else if (key === 'points_cockpit') {
        fetchSpatialPointsSummary();
        fetchSpatialPointsMatrix();
        fetchDailyPointsInfo();
      } else if (key === 'points_matrix') {
        fetchSpatialPointsMatrix();
      } else if (key === 'points_review') {
        fetchSpatialPointsReview(pointsReviewPeriods.value);
      } else if (key === 'suppression_cockpit') {
        fetchSuppressionSummary();
        fetchSuppressionPatterns();
        fetchSuppressionReview(suppressionReviewPeriods.value);
      } else if (key === 'point_omission_cockpit') {
        fetchPointOmissionSummary();
        fetchPointOmissionBacktest();
        fetchPointOmissionHitLedger();
      } else if (key === 'suppression_review') {
        fetchSuppressionReview(suppressionReviewPeriods.value);
      } else if (key === 'gold_pick2_cockpit') {
        fetchGoldPick2Summary();
        fetchGoldPick2Matrix();
        fetchGoldPick2Logs();
        fetchGoldPick2Review(goldPick2ReviewPeriods.value);
      } else if (key === 'gold_pick2_review') {
        fetchGoldPick2Review(goldPick2ReviewPeriods.value);
      } else if (key === 'gemini_cockpit') {
        fetchGeminiSummary();
        fetchGeminiHistory();
      } else if (key === 'gemini_review') {
        fetchGeminiReview(geminiReviewPeriods.value);
      } else if (key === 'datasource_cockpit') {
        fetchDatasourceSummary();
        fetchDatasourceReview(30);
      } else if (key === 'reports_browser') {
        fetchReportList();
      } else if (key === 'daily_reviews_ledger') {
        fetchReviewsLedger(reviewsLedgerLimit.value);
      } else if (key === 'tail_entropy') {
        fetchPrimeCompositeData();
      } else if (key === 'modules_overview') {
        // 本页是六大高维数学/AI 综合大盘：只拉 AI 模型与共识，绝不触发全流程 pipeline
        fetchAllAiMathModels();
      } else if (key === 'classic_overview') {
        // 经典量化汇总大盘：并行拉七大子模块摘要，不自动跑 pipeline
        fetchAllClassicModels();
      } else if (key === 'meta_gold_cockpit') {
        fetchMetaGoldSummary();
        fetchMetaGoldReview(metaGoldReviewPeriods.value);
      } else if (key === 'funnel_cockpit') {
        fetchFunnelSummary();
        fetchFunnelReview(funnelReviewPeriods.value);
      } else if (key === 'env_regime') {
        fetchEnvRegimeSummary();
      } else if (key === 'fdr_audit') {
        fetchFdrAuditSummary(fdrAuditPeriods.value);
      } else if (key === 'paper_trading') {
        fetchPaperTradingSummary(paperTradingRolling.value);
      } else if (key === 'agg_cockpit') {
        fetchAggCockpit();
      } else if (key === 'agg_reports') {
        fetchAggHistory();
      } else if (key === 'sixteen_cockpit' || key === 'sixteen_matrix') {
        fetchSixteenSummary(!(sixteenSummary && sixteenSummary.value && sixteenSummary.value.daily_ops_brief));
        fetchSixteenReview(sixteenReviewPeriods.value);
      } else if (key === 'sixteen_dist') {
        fetchSixteenSummary(!(sixteenSummary && sixteenSummary.value && sixteenSummary.value.daily_ops_brief));
      } else if (key === 'sixteen_review') {
        fetchSixteenReview(sixteenReviewPeriods.value);
      } else if (key === 'sixteen_reports') {
        fetchSixteenHistory();
      } else if (key === 'genetic_cockpit') {
        fetchGeneticData();
        fetchGeneticReview();
      } else if (key === 'linear_algebra_cockpit') {
        fetchLinearAlgebraData();
      } else if (key === 'random_forest_cockpit') {
        fetchRandomForestData();
      } else if (key === 'error_correction_cockpit') {
        fetchErrorCorrectionData();
      } else if (key === 'spear_shield_cockpit') {
        fetchSpearShieldData();
      } else if (key === 'point_road_cockpit') {
        fetchPointRoadData();
      } else if (key === 'dtw_cockpit') {
        fetchDTWData();
      } else if (key === 'transformer_cockpit') {
        fetchTransformerData();
      } else if (key === 'matrix_profile_cockpit') {
        fetchMatrixProfileData();
      } else if (key === 'tda_cockpit') {
        fetchTDAData();
      } else if (key === 'hit_leaderboard') {
        fetchHitLeaderboard(hitRange.value);
      } else if (key === 'nightly_scheduler') {
        fetchSchedulerStatus();
        fetchEvolutionStatus();
      } else if (key === 'datasource_review') {
        fetchDatasourceReview(30);
      } else if (key === 'datasource_matrix') {
        // 始终拉跟随表最新期，避免本地粘住上一开奖期
        datasourceMatrixSelectedPeriod.value = '';
        fetchDatasourceMatrix(null);
        fetchDatasourceSummary();
        fetchDatasourceReview(datasourceReviewPeriods.value || 30);
        fetchDailyPointsInfo();
      } else if (key === 'master_review_cockpit') {
        fetchMasterReview(masterReviewPeriods.value || 30);
      } else if (key === 'unified_brain_cockpit') {
        fetchUnifiedBrain();
      } else if (key === 'draw_trend_chart') {
        fetchLotteryTrends(100);
        fetchModuleConsensus();
      } else if (key === 'matrix_80') {
        fetchMatrixData();
        // 合页另一半：预拉 012/尾数，切账本页签更快
        if (typeof fetchPrimeCompositeData === 'function') fetchPrimeCompositeData();
      } else if (key === 'history_table') {
        fetchHistoryTable(1);
      } else if (key === 'points_input') {
        fetchDailyPointsInfo();
        fetchDailyPointsHistory(30);
      } else if (key === 'tri_high_input') {
        fetchTriHighHistory();
        fetchTriHighSummary();
      } else if (key === 'psychological_game') {
        fetchPsychologicalGameData();
        fetchPsychologicalGameBacktest();
      }
      // 切换标签后重新调整图表尺寸与主题
      nextTick(() => {
        handleResize();
      });
    };

    const switchTab = (key) => {
      const t = tabs.value.find(tab => tab.key === key);
      if (t) {
        openTab(t.key, t.title, t.icon);
      } else {
        openTab(key, key);
      }
    };

    // 模块「历史复盘」：优先滚到页内锚点；无锚点时再打开遗留总库页（研报等）
    const MODULE_HISTORY = {
      live_cockpit:       { key: 'daily_reviews_ledger', title: '每日自学习自动复盘总账本', icon: '📜' },
      modules_overview:   { key: 'genetic_cockpit',      title: '遗传算法自进化推演战区',     icon: '🧬' },
      classic_overview:   { key: 'reports_browser',      title: '每日综合研判大研报总库',     icon: '📜' },
      meta_gold_cockpit:  { key: 'agg_reports',         title: '策略汇总 历史战报记录',       icon: '📜' },
      funnel_cockpit:     { key: 'daily_reviews_ledger', title: '每日自学习自动复盘总账本', icon: '📜' },
      agg_cockpit:        { key: 'agg_reports',         title: '策略汇总 历史战报记录',       icon: '📜' }
    };

    const openModuleHistory = (key) => {
      // 数据源 / 16期复盘主阵地迁到对应全景页
      const tabRedirect = {
        datasource_cockpit: 'datasource_matrix',
        sixteen_matrix: 'sixteen_cockpit'
      };
      const tabKey = tabRedirect[key] || key;
      const anchor = MODULE_REVIEW_ANCHORS[key] || MODULE_REVIEW_ANCHORS[tabKey];
      if (anchor) {
        openTab(tabKey);
        nextTick(() => {
          setTimeout(() => {
            const el = document.getElementById(anchor);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 120);
        });
        return;
      }
      const h = MODULE_HISTORY[key];
      if (h) openTab(h.key, h.title, h.icon);
    };

    // ────────────── Tab 标签页高级管理与右键快捷菜单 ──────────────
    const tabContextMenu = reactive({
      visible: false,
      x: 0,
      y: 0,
      tab: null
    });

    const openTabContextMenu = (e, tab) => {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      tabContextMenu.visible = true;
      const menuWidth = 160;
      const menuHeight = 220;
      const posX = (e ? e.clientX : 0) + menuWidth > window.innerWidth ? Math.max(10, window.innerWidth - menuWidth - 15) : (e ? e.clientX : 0);
      const posY = (e ? e.clientY : 0) + menuHeight > window.innerHeight ? Math.max(10, window.innerHeight - menuHeight - 15) : (e ? e.clientY : 0);
      tabContextMenu.x = posX;
      tabContextMenu.y = posY;
      tabContextMenu.tab = tab;
    };

    const closeTabContextMenu = () => {
      tabContextMenu.visible = false;
      tabContextMenu.tab = null;
    };

    const closeTab = (key) => {
      closeTabContextMenu();
      const idx = tabs.value.findIndex(t => t.key === key);
      if (idx === -1) return;
      tabs.value.splice(idx, 1);
      if (activeTab.value === key) {
        if (tabs.value.length > 0) {
          activeTab.value = tabs.value[Math.max(0, idx - 1)].key;
        } else {
          // 兜底：若所有标签均被移除，则恢复默认主全景
          tabs.value.push({
            key: 'genetic_cockpit',
            title: _menuMeta('genetic_cockpit').title || '遗传算法',
            icon: _menuMeta('genetic_cockpit').icon || '🧬',
            closable: false
          });
          activeTab.value = 'genetic_cockpit';
        }
      }
      nextTick(() => { handleResize(); });
    };

    const closeOtherTabs = (targetKey) => {
      closeTabContextMenu();
      const keepKey = targetKey || activeTab.value;
      tabs.value = tabs.value.filter(t => t.key === keepKey || !t.closable);
      if (!tabs.value.some(t => t.key === keepKey)) {
        if (tabs.value.length > 0) {
          activeTab.value = tabs.value[0].key;
        }
      } else {
        activeTab.value = keepKey;
      }
      nextTick(() => { handleResize(); });
    };

    const closeRightTabs = (targetKey) => {
      closeTabContextMenu();
      const keepKey = targetKey || activeTab.value;
      const idx = tabs.value.findIndex(t => t.key === keepKey);
      if (idx === -1) return;
      tabs.value = tabs.value.filter((t, i) => i <= idx || !t.closable);
      if (!tabs.value.some(t => t.key === activeTab.value)) {
        activeTab.value = keepKey;
      }
      nextTick(() => { handleResize(); });
    };

    const closeLeftTabs = (targetKey) => {
      closeTabContextMenu();
      const keepKey = targetKey || activeTab.value;
      const idx = tabs.value.findIndex(t => t.key === keepKey);
      if (idx === -1) return;
      tabs.value = tabs.value.filter((t, i) => i >= idx || !t.closable);
      if (!tabs.value.some(t => t.key === activeTab.value)) {
        activeTab.value = keepKey;
      }
      nextTick(() => { handleResize(); });
    };

    /**
     * 【一键关闭全部 Tab 标签页】
     * 规则：一键清除所有已打开的可关闭标签页，平滑恢复至系统预测全景主驾驶舱，瞬间清爽
     */
    const closeAllTabs = () => {
      closeTabContextMenu();
      tabs.value = tabs.value.filter(t => !t.closable);
      if (tabs.value.length === 0) {
        tabs.value.push({
          key: 'genetic_cockpit',
          title: _menuMeta('genetic_cockpit').title || '遗传算法',
          icon: _menuMeta('genetic_cockpit').icon || '🧬',
          closable: false
        });
      }
      activeTab.value = tabs.value[0].key;
      nextTick(() => { handleResize(); });
    };

    const refreshCurrentTab = (targetKey) => {
      closeTabContextMenu();
      const key = targetKey || activeTab.value;
      if (key) {
        switchTab(key);
      }
    };

    // ──────────────── 业务数据状态 ────────────────
    const systemStatus = ref({
      latest_draw_period: '---',
      latest_draw_date: '---',
      target_period: '---',
      latest_draw_numbers: [],
      beacon_status: 'NORMAL',
      status: 'ONLINE',
      system_name: 'K8-Quant 智能量化系统',
      version: 'V5.0 Enterprise'
    });

    const prediction = ref({
      period: '---',
      date: '---',
      golden_pair: [],
      golden_pair_reason: '加载中...',
      golden_pair_score: null,
      golden_pair_lift: null,
      golden_pair_cooc: null,
      top5_gold: [],
      top12_pool: [],
      golden_core: [],
      hidden_energy_5: [],
      sub_pairs: [],
      weights: { EF: 0.4, RW: 0.3, FO: 0.3 },
      weights_plain: '加载中...',
      pure_pool: [],
      shannon_entropy: 0.0,
      risk_status: 'NORMAL'
    });

    const matrixData = ref([]);
    const hitLeaderboard = ref(null);
    const hitLoading = ref(false);
    const hitRange = ref(10);
    const hitSortKey = ref('rate'); // 'rate' | 'count'

    // 命中榜单排序（默认按最新期命中率降序）
    const hitSortedModules = computed(() => {
      const lb = hitLeaderboard.value;
      if (!lb || !lb.modules) return [];
      const rate = (m) => (m.latest && m.latest.hit_rate != null) ? m.latest.hit_rate : 0;
      const count = (m) => (m.latest && m.latest.hit_count != null) ? m.latest.hit_count : 0;
      const arr = [...lb.modules];
      arr.sort((a, b) => {
        const ka = a.pick_type === 'kill' ? 1 : 0;
        const kb = b.pick_type === 'kill' ? 1 : 0;
        if (ka !== kb) return ka - kb; // 荐号类排前，杀号类整体排后
        return hitSortKey.value === 'count' ? count(b) - count(a) : rate(b) - rate(a);
      });
      return arr;
    });

    // 热力矩阵辅助：取模块在指定期的命中率 / 命中率配色
    const hitRateOf = (m, period) => {
      if (!m || !m.series) return null;
      const e = m.series.find(x => x.period === period);
      return e && e.hit_rate != null ? e.hit_rate : null;
    };
    const hitColor = (rate) => {
      if (rate == null) return 'rgba(15,23,42,0.55)';
      if (rate >= 75) return 'rgba(16,185,129,0.85)';
      if (rate >= 50) return 'rgba(6,182,212,0.72)';
      if (rate >= 25) return 'rgba(245,158,11,0.6)';
      return 'rgba(239,68,68,0.55)';
    };
    const hitRateOfColor = hitColor;
    const tailStats = ref([]);
    const zoneStats = ref([]);
    const trendStats = ref(null);
    const activeFilter = ref('all'); // 兼容实时驾驶舱等旧单选绑定
    const activeFilters = ref([]); // 矩阵多选池筛选：[]=全部；可同时含 top5/top12/cold/hot
    const matrixFilterMode = ref('or'); // or=任一命中 | and=同时命中
    const matrixMorphFilters = reactive({ roads: [], primes: [], zones: [] });
    // 基础形态叠层：分区 / 012路 / 质合（与池筛选独立，纯前端按号码推算）
    const matrixDimOverlay = ref('none'); // none | zone | road012 | prime
    const primeCompositeData = ref(null);
    const primeCompositeLoading = ref(false);
    const primeCompositeRefreshMsg = ref('');
    const psychologicalGameData = ref(null);
    const psychologicalGameLoading = ref(false);
    const psychologicalGameBacktest = ref(null);
    const psychologicalGameBacktestLoading = ref(false);
    const psychologicalGameBacktestWindow = ref('last_100');

    // 09. 遗传算法自进化推演状态
    const geneticData = ref(null);
    const geneticReviewData = ref(null);
    const isGeneticRunning = ref(false);
    let gaConvergenceChart = null;
    let gaRadarChart = null;

    // 10. 线性代数空间投影量化推演状态
    const linearAlgebraData = ref(null);
    const linearAlgebraReviewData = ref(null);
    const isLinearAlgebraRunning = ref(false);
    const linearAlgebraLoading = ref(false);

    // 随机森林号码预测
    const randomForestData = ref(null);
    const randomForestReviewData = ref(null);
    const isRandomForestRunning = ref(false);
    const randomForestLoading = ref(false);

    // 残差改错 GBDT
    const errorCorrectionData = ref(null);
    const errorCorrectionReviewData = ref(null);
    const isErrorCorrectionRunning = ref(false);
    const errorCorrectionLoading = ref(false);

    // 一胆拖三盾 · 选2组合拳 (2026-10-22 补齐独立驾驶舱)
    const spearShieldData = ref(null);
    const spearShieldReviewData = ref(null);
    const spearShieldLoading = ref(false);
    const spearShieldRerunning = ref(false);

    // 点位012偏态压缩器 (2026-10-22 补齐独立驾驶舱)
    const pointRoadData = ref(null);
    const pointRoadReviewData = ref(null);
    const pointRoadLoading = ref(false);

    // 11. 动态时间规整 DTW 推演状态
    const dtwData = ref(null);
    const dtwReviewData = ref(null);
    const dtwLoading = ref(false);

    // 12. Transformer 全局自注意力推演状态
    const transformerData = ref(null);
    const transformerReviewData = ref(null);
    const transformerLoading = ref(false);

    // 13. 矩阵轮廓 Matrix Profile 查重状态
    const matrixProfileData = ref(null);
    const matrixProfileReviewData = ref(null);
    const matrixProfileLoading = ref(false);

    // 14. 拓扑数据分析 TDA 持续同调状态
    const tdaData = ref(null);
    const tdaReviewData = ref(null);
    const tdaLoading = ref(false);

    // ═════════════════ 六大高维数学与AI模型超级共识计算 ═════════════════
    const aiResonanceSortMode = ref('score');
    const aiMathLoading = ref(false);
    const aiMathConsensusReviewData = ref(null);


    const activeAiModelCount = computed(() => {
      let count = 0;
      if (geneticData.value) count++;
      if (linearAlgebraData.value) count++;
      if (dtwData.value) count++;
      if (transformerData.value) count++;
      if (matrixProfileData.value) count++;
      if (tdaData.value) count++;
      return count;
    });

    const aiMathConsensus = computed(() => {
      // 80 码共振得分与投票追踪
      const balls = Array.from({ length: 80 }, (_, i) => ({
        ball: i + 1,
        score: 0.0,
        vote_count: 0,
        sources: [],
        is_gold: false,
        in_top5: false,
        in_top12: false,
        is_killed: false
      }));

      const addModuleVotes = (data, code, weight = 1.0) => {
        if (!data) return;
        const top5 = data.top5_gold || data.top5_assault || [];
        const top12 = data.top12_elite || data.top12_balanced || [];

        top5.forEach((b, idx) => {
          if (b >= 1 && b <= 80) {
            const item = balls[b - 1];
            item.score += (5.0 - idx * 0.5) * weight;
            item.vote_count += 1;
            if (!item.sources.includes(code)) item.sources.push(code);
          }
        });

        top12.forEach((b, idx) => {
          if (b >= 1 && b <= 80 && !top5.includes(b)) {
            const item = balls[b - 1];
            item.score += (2.5 - idx * 0.15) * weight;
            item.vote_count += 1;
            if (!item.sources.includes(code)) item.sources.push(code);
          }
        });
      };

      // 汇总 6 大前沿数学与AI模型
      addModuleVotes(geneticData.value, 'GA', 1.05);
      addModuleVotes(linearAlgebraData.value, 'SVD', 1.0);
      addModuleVotes(dtwData.value, 'DTW', 1.0);
      addModuleVotes(transformerData.value, 'TRANS', 1.0);
      addModuleVotes(matrixProfileData.value, 'MP', 1.0);
      addModuleVotes(tdaData.value, 'TDA', 1.0);

      // 排序与判定（主口径最优3码；top5/top12 兼容别名）
      const sortedByScore = [...balls].sort((a, b) => b.score - a.score || b.vote_count - a.vote_count);
      
      const top3List = sortedByScore.slice(0, 3);
      const top5List = top3List;
      const top12List = top3List;
      const top3Set = new Set(top3List.map(x => x.ball));
      const killList = [];

      balls.forEach(item => {
        item.is_gold = top3Set.has(item.ball);
        item.in_top5 = top3Set.has(item.ball);
        item.in_top12 = top3Set.has(item.ball);
        item.is_killed = false;
      });

      // 黄金搭档提取
      const pairMap = new Map();
      const recordPair = (p, source) => {
        if (!p || p.length < 2) return;
        const [a, b] = [Math.min(p[0], p[1]), Math.max(p[0], p[1])];
        const key = `${a}-${b}`;
        if (!pairMap.has(key)) {
          pairMap.set(key, { pair: [a, b], count: 0, sources: [] });
        }
        const obj = pairMap.get(key);
        obj.count += 1;
        if (!obj.sources.includes(source)) obj.sources.push(source);
      };

      if (geneticData.value?.gold_pair) recordPair(geneticData.value.gold_pair, 'GA');
      if (linearAlgebraData.value?.top_pairs?.[0]?.pair) recordPair(linearAlgebraData.value.top_pairs[0].pair, 'SVD');
      if (dtwData.value?.top_pairs?.[0]?.pair) recordPair(dtwData.value.top_pairs[0].pair, 'DTW');
      if (transformerData.value?.top_pairs?.[0]?.pair) recordPair(transformerData.value.top_pairs[0].pair, 'TRANS');
      if (matrixProfileData.value?.top_pairs?.[0]?.pair) recordPair(matrixProfileData.value.top_pairs[0].pair, 'MP');
      if (tdaData.value?.top_pairs?.[0]?.pair) recordPair(tdaData.value.top_pairs[0].pair, 'TDA');

      // 兜底高分搭档
      if (top5List.length >= 2) {
        recordPair([top5List[0].ball, top5List[1].ball], '共识金胆连体');
      }

      const pairs = Array.from(pairMap.values()).map(p => ({
        pair: p.pair,
        sources: p.sources.join(' + '),
        count: p.count
      })).sort((a, b) => b.count - a.count);

      return {
        top3_gold: top3List,
        top5: top5List,
        top12: top12List,
        kill_list: killList,
        pairs: pairs,
        balls: balls
      };
    });

    const sortedAiResonanceList = computed(() => {
      const list = [...(aiMathConsensus.value?.balls || [])];
      if (aiResonanceSortMode.value === 'score') {
        return list.sort((a, b) => b.score - a.score || b.vote_count - a.vote_count || a.ball - b.ball);
      } else {
        return list.sort((a, b) => a.ball - b.ball);
      }
    });

    // 逐项兜底执行器：把每项包成 thunk 单独跑，任一模块缺失/抛错只影响它自己。
    // 直接用 Promise.allSettled([a(), b()]) 时，参数求值阶段一旦抛错，
    // allSettled 根本不会被调用，整组请求静默丢失。
    // 返回失败项清单（[{label, message}]），由调用方决定如何呈现。
    const runLoaders = async (loaders) => {
      const settled = await Promise.allSettled(
        loaders.map((item) => Promise.resolve().then(item.run))
      );
      const failures = [];
      settled.forEach((result, index) => {
        if (result.status === 'rejected') {
          const reason = result.reason;
          failures.push({
            label: loaders[index].label,
            message: (reason && reason.message) || String(reason)
          });
        }
      });
      return failures;
    };

    // 批量加载 / 刷新六大高维数学与AI模型
    const fetchAllAiMathModels = async (forceRefresh = false) => {
      aiMathLoading.value = true;
      try {
        const failures = await runLoaders([
          { label: '遗传算法', run: () => fetchGeneticData(forceRefresh) },
          { label: '线性代数', run: () => fetchLinearAlgebraData(forceRefresh) },
          { label: 'DTW', run: () => fetchDTWData(forceRefresh) },
          { label: 'Transformer', run: () => fetchTransformerData(forceRefresh) },
          { label: '矩阵轮廓', run: () => fetchMatrixProfileData(forceRefresh) },
          { label: 'TDA', run: () => fetchTDAData(forceRefresh) },
          { label: '数学共识复盘', run: () => fetchAiMathConsensusReview(30, forceRefresh) }
        ]);
        if (failures.length) {
          addLog(`⚠️ 六大高维数学与AI模型中 ${failures.length} 项未能加载：${failures.map((f) => f.label).join('、')}`, 'warn');
          console.warn('[AI 数学模型] 加载失败:', failures);
        } else {
          addLog('📐 六大高维数学与AI模型最新推演数据已极速汇聚解算完成', 'success');
        }
      } catch (err) {
        console.error('汇聚六大AI/数学模型失败:', err);
      } finally {
        aiMathLoading.value = false;
      }
    };

    // 当前选定窗口的汇总回测数据计算属性
    const activePsychologicalBacktest = computed(() => {
      const summary = psychologicalGameBacktest.value?.multi_window_summary || {};
      return summary[psychologicalGameBacktestWindow.value] || summary['last_100'] || {};
    });

    // 矩阵筛选按钮的真实计数（不再写死 (5)/(12)，按实际分类统计）
    const matrixFilterCounts = computed(() => {
      const m = matrixData.value || [];
      return {
        all: m.length,
        top5: m.filter(c => c.is_top5).length,
        top12: m.filter(c => c.is_top12 && !c.is_top5).length,
        cold: m.filter(c => c.category === 'cold_rebound').length,
        hot: m.filter(c => c.category === 'hot_energy').length
      };
    });

    // 80码开奖走势图状态 (默认100期、日期升序)
    const trendLimit = ref(100);
    const trendCustomInput = ref(100);
    const trendData = ref({ draws: [], ball_stats: [], summary: {} });
    const trendLoading = ref(false);
    const trendShowOmission = ref(true);
    const trendZoneFilter = ref('all');
    const trendViewMode = ref('wide');
    const highlightedBall = ref(null);
    const trendSearchBall = ref('');
    const customPicks = ref([]);

    // ── 全模块预测共识叠加 (2026-10-22 新增) ──
    // 数据源: /api/quant/module-consensus (前瞻账, 与全模块看板同源)
    const consensusData = ref({ status: 'ok', modules: [], consensus: {}, target_period: null });
    const consensusEnabled = ref([]);          // 勾选中的模块 id
    const consensusLoading = ref(false);
    const consensusLegendOpen = ref(true);

    // 历史表格分页
    const historyTable = reactive({
      page: 1,
      page_size: 15,
      total: 0,
      total_pages: 1,
      q: '',
      items: []
    });

    // 研判报告
    const reportList = ref([]);
    const currentReport = ref({ title: '', content: '', date: '', period: '' });
    // G4 整改: 研报总库新旧口径筛选器 (全量 / 诚实新口径 / 历史归档)
    const reportFilter = ref('all');
    const filteredReportList = computed(() => {
      if (reportFilter.value === 'honest') {
        return reportList.value.filter(r => r.is_honest_caliber);
      }
      if (reportFilter.value === 'legacy') {
        return reportList.value.filter(r => !r.is_honest_caliber);
      }
      return reportList.value;
    });

    // 弹窗与详情
    const selectedBall = ref(null);
    const showBallModal = ref(false);

    // 参数微调
    const modelParams = reactive({
      EF: 0.40,
      RW: 0.30,
      FO: 0.30
    });
    const paramSaveMsg = ref('');

    // 控制台与日志
    const terminalLogs = ref([
      `[${new Date().toLocaleTimeString()}] 🚀 K8-Quant 企业级多主题量化决策终端已就绪`,
      `[${new Date().toLocaleTimeString()}] 🎨 当前界面主题: ${themes.find(t => t.id === currentTheme.value)?.name || '深邃赛博'}`
    ]);
    const isRunning = ref(false);
    const currentTaskId = ref(null);
    const autoScroll = ref(true);
    let logPollTimer = null;

    // ECharts 实例引用 (支持驾驶舱与独立 Tab 双向挂载)
    let radarChart = null;
    let radarChartTab = null;
    // Shared with pages/sixteen.js (ECharts instance must outlive page mixin scope)
    const chartHandles = { sixteenDistChart: null };
    let trendChart = null;
    let trendChartTab = null;
    let tailChart = null;
    let tailChartTab = null;
    let zoneChart = null;
    let zoneChartTab = null;
    let trendDistChart = null;
    let trendSumOddChart = null;

    // ──────────────── API 请求方法 ────────────────

    const fetchSystemStatus = async () => {
      try {
        const res = await fetch('/api/system/status');
        if (res.ok) {
          systemStatus.value = await res.json();
        }
      } catch (err) {
        console.error('获取系统状态失败:', err);
      }
    };

    const fetchPrediction = async () => {
      try {
        const res = await fetch('/api/quant/latest-prediction');
        if (res.ok) {
          prediction.value = await res.json();
          modelParams.EF = prediction.value.weights?.EF || 0.40;
          modelParams.RW = prediction.value.weights?.RW || 0.30;
          modelParams.FO = prediction.value.weights?.FO || 0.30;
          updateRadarChart();
        }
      } catch (err) {
        console.error('获取最新预测失败:', err);
      }
    };

    const fetchMatrixData = async () => {
      try {
        const res = await fetch('/api/quant/matrix-80');
        if (res.ok) {
          const data = await res.json();
          matrixData.value = data.matrix || [];
          tailStats.value = data.tail_stats || [];
          zoneStats.value = data.zone_stats || [];
          updateTailChart(data.tail_stats || []);
          updateZoneChart(data.zone_stats || []);
        }
      } catch (err) {
        console.error('获取80码矩阵失败:', err);
      }
    };

    const fetchPrimeCompositeData = async (forceRefresh = false) => {
      primeCompositeLoading.value = true;
      primeCompositeRefreshMsg.value = '';
      try {
        const url = `/api/quant/prime-composite-analysis${forceRefresh ? '?refresh=true' : ''}`;
        const res = await fetch(url);
        if (res.ok) {
          const resp = await res.json();
          if (resp.status === 'ok') {
            primeCompositeData.value = resp.data;
            const d = resp.data || {};
            const fromMsg = d.based_on_period ? `第 ${d.based_on_period} 期` : '最新历史';
            const drawMsg = d.total_draws ? `${d.total_draws} 期开奖` : '';
            primeCompositeRefreshMsg.value = `✅ 已${forceRefresh ? '重新推演' : '加载'}质合与尾数 · 基于 ${fromMsg} / ${drawMsg} ，结果已是最新`;
            return;
          }
        }
        // 双通道降级: 尝试读取静态兜底数据 (带时间戳破坏浏览器磁盘强缓存)
        const cacheBuster = `?_t=${Date.now()}`;
        const fallbackRes = await fetch(`/static/prime_tail_analysis.json${cacheBuster}`, { cache: 'no-store' });
        if (fallbackRes.ok) {
          const fallbackData = await fallbackRes.json();
          // G5: 静态快照可能过期, 必须显式标注来源, 不能冒充实时结果
          primeCompositeData.value = { ...fallbackData, __stale_fallback: true,
            __stale_note: '接口不可用，当前展示的是静态快照，可能已过期' };
        }
      } catch (err) {
        console.warn('优先接口未就绪，切换至静态通道:', err);
        try {
          const fallbackRes = await fetch(`/static/prime_tail_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) {
            const fallbackData = await fallbackRes.json();
            primeCompositeData.value = fallbackData;
          }
        } catch (e) {
          console.error('双通道均获取失败:', e);
        }
      } finally {
        primeCompositeLoading.value = false;
      }
    };

    const fetchPsychologicalGameData = async (forceRefresh = false) => {
      psychologicalGameLoading.value = true;
      try {
        const url = `/api/quant/psychological-game-analysis${forceRefresh ? '?refresh=true' : ''}`;
        const res = await fetch(url);
        if (res.ok) {
          const resp = await res.json();
          if (resp.status === 'ok') {
            psychologicalGameData.value = resp.data;
            return;
          }
        }
        // 双通道降级: 尝试读取静态兜底数据 (带时间戳破坏浏览器磁盘强缓存)
        const cacheBuster = `?_t=${Date.now()}`;
        const fallbackRes = await fetch(`/static/psychological_game_analysis.json${cacheBuster}`, { cache: 'no-store' });
        if (fallbackRes.ok) {
          const fallbackData = await fallbackRes.json();
          psychologicalGameData.value = { ...fallbackData, __stale_fallback: true,
            __stale_note: '接口不可用，当前展示的是静态快照，可能已过期' };
        }
      } catch (err) {
        console.warn('优先接口未就绪，切换至静态通道:', err);
        try {
          const fallbackRes = await fetch(`/static/psychological_game_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) {
            const fallbackData = await fallbackRes.json();
            psychologicalGameData.value = fallbackData;
          }
        } catch (e) {
          console.error('双通道均获取失败:', e);
        }
      } finally {
        psychologicalGameLoading.value = false;
      }
    };

    const fetchPsychologicalGameBacktest = async (forceRefresh = false) => {
      psychologicalGameBacktestLoading.value = true;
      try {
        const url = `/api/quant/psychological-game-backtest${forceRefresh ? '?refresh=true' : ''}`;
        const res = await fetch(url);
        if (res.ok) {
          const resp = await res.json();
          if (resp.status === 'ok') {
            psychologicalGameBacktest.value = resp.data;
            return;
          }
        }
        // 双通道降级: 静态兜底 (带时间戳防缓存)
        const cacheBuster = `?_t=${Date.now()}`;
        const fallbackRes = await fetch(`/static/psychological_game_backtest_ledger.json${cacheBuster}`, { cache: 'no-store' });
        if (fallbackRes.ok) {
          const fallbackData = await fallbackRes.json();
          psychologicalGameBacktest.value = { ...fallbackData, __stale_fallback: true,
            __stale_note: '接口不可用，当前展示的是静态回测快照，可能已过期' };
        }
      } catch (err) {
        console.warn('优先回测接口未就绪，切换至静态通道:', err);
        try {
          const fallbackRes = await fetch(`/static/psychological_game_backtest_ledger.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) {
            const fallbackData = await fallbackRes.json();
            psychologicalGameBacktest.value = fallbackData;
          }
        } catch (e) {
          console.error('双通道回测获取均失败:', e);
        }
      } finally {
        psychologicalGameBacktestLoading.value = false;
      }
    };

    // 09. 遗传算法自进化推演交互与图表渲染
    const initGeneticConvergenceChart = () => {
      const el = document.getElementById('chart-ga-convergence');
      if (!el || typeof echarts === 'undefined') return;
      if (gaConvergenceChart && !gaConvergenceChart.isDisposed()) gaConvergenceChart.dispose();
      gaConvergenceChart = echarts.init(el);
      const curve = geneticData.value?.convergence_curve || [];
      const gens = curve.map(c => `第${c.generation}代`);
      const bestFits = curve.map(c => c.best_fitness);
      const avgFits = curve.map(c => c.avg_fitness);
      gaConvergenceChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', backgroundColor: 'rgba(15, 23, 42, 0.9)', borderColor: '#06b6d4', textStyle: { color: '#f8fafc', fontSize: 11 } },
        legend: { data: ['最优个体适应度', '种群平均适应度'], textStyle: { color: '#94a3b8', fontSize: 10 }, top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
        xAxis: { type: 'category', data: gens.length ? gens : ['第1代', '第5代', '第10代', '第15代', '第20代'], axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8', fontSize: 10 } },
        yAxis: { type: 'value', name: '适应度得分', nameTextStyle: { color: '#64748b', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } }, axisLabel: { color: '#94a3b8', fontSize: 10 } },
        series: [
          { name: '最优个体适应度', type: 'line', smooth: true, data: bestFits.length ? bestFits : [12.5, 14.8, 16.2, 17.5, 18.9], lineStyle: { width: 3, color: '#06b6d4' }, itemStyle: { color: '#06b6d4' }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(6, 182, 212, 0.3)' }, { offset: 1, color: 'rgba(6, 182, 212, 0.0)' }]) } },
          { name: '种群平均适应度', type: 'line', smooth: true, data: avgFits.length ? avgFits : [10.1, 11.5, 13.0, 14.2, 15.1], lineStyle: { width: 2, color: '#6366f1', type: 'dashed' }, itemStyle: { color: '#6366f1' } }
        ]
      });
    };

    const initGeneticRadarChart = () => {
      const el = document.getElementById('chart-ga-radar');
      if (!el || typeof echarts === 'undefined') return;
      if (gaRadarChart && !gaRadarChart.isDisposed()) gaRadarChart.dispose();
      gaRadarChart = echarts.init(el);
      const r = geneticData.value?.radar_features || { '频次势能': 65, '动量热度': 75, '遗漏回补': 80, '重邻粘性': 70, '同尾共振': 55, '分区均衡': 60 };
      gaRadarChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.9)', borderColor: '#06b6d4', textStyle: { color: '#f8fafc', fontSize: 11 } },
        radar: {
          indicator: [
            { name: '长期频次', max: 100 },
            { name: '冷热动量', max: 100 },
            { name: '遗漏回补', max: 100 },
            { name: '重邻粘性', max: 100 },
            { name: '同尾共振', max: 100 },
            { name: '分区均衡', max: 100 }
          ],
          shape: 'polygon', splitNumber: 4,
          axisName: { color: '#94a3b8', fontSize: 10 },
          splitLine: { lineStyle: { color: '#1e293b' } },
          splitArea: { show: false },
          axisLine: { lineStyle: { color: '#334155' } }
        },
        series: [{
          name: '最优特征权重', type: 'radar',
          data: [{
            value: [r['频次势能'] || 60, r['动量热度'] || 70, r['遗漏回补'] || 75, r['重邻粘性'] || 65, r['同尾共振'] || 50, r['分区均衡'] || 60],
            name: '最优基因画像',
            itemStyle: { color: '#06b6d4' },
            areaStyle: { color: 'rgba(6, 182, 212, 0.35)' },
            lineStyle: { width: 2, color: '#22d3ee' }
          }]
        }]
      });
    };

    const fetchGeneticData = async (force = false) => {
      try {
        const res = await fetch(`/api/genetic/summary${force ? '?force_refresh=true' : ''}`);
        if (res.ok) {
          geneticData.value = await res.json();
          nextTick(() => {
            initGeneticConvergenceChart();
            initGeneticRadarChart();
          });
        }
      } catch (e) {
        console.error('获取遗传算法推演失败:', e);
      }
    };

    const fetchGeneticReview = async (n = 30) => {
      try {
        const res = await fetch(`/api/genetic/review?n=${n}`);
        if (res.ok) {
          const data = await res.json();
          if (data && (data.status === 'success' || data.records)) {
            geneticReviewData.value = data;
            return;
          }
        }
      } catch (e) {
        // 静默降级
      }
      try {
        const fallbackRes = await fetch(`/static/genetic_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) geneticReviewData.value = await fallbackRes.json();
      } catch (e) {}
    };

    const triggerGeneticEvolution = async () => {
      isGeneticRunning.value = true;
      try {
        const res = await fetch('/api/genetic/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pop_size: 40, generations: 25, eval_periods: 15 })
        });
        if (res.ok) {
          geneticData.value = await res.json();
          await fetchGeneticReview(30);
          nextTick(() => {
            initGeneticConvergenceChart();
            initGeneticRadarChart();
          });
          addLog('🧬 遗传算法种群自进化寻优完成，最新最优决策已生效', 'info');
        }
      } catch (e) {
        console.error('触发遗传算法进化失败:', e);
        addLog('❌ 遗传算法进化执行失败: ' + (e.message || e), 'error');
      } finally {
        isGeneticRunning.value = false;
      }
    };

    // 10. 线性代数空间投影量化推演数据获取
    const fetchLinearAlgebraReview = async (n = 30) => {
      try {
        const res = await fetch(`/api/quant/linear-algebra/review?n=${n}`);
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            linearAlgebraReviewData.value = resp.data;
            return;
          }
          if (resp.status === 'success' || resp.records) {
            linearAlgebraReviewData.value = resp;
            return;
          }
        }
      } catch (e) {
        // 静默降级
      }
      try {
        const fallbackRes = await fetch(`/static/linear_algebra_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) linearAlgebraReviewData.value = await fallbackRes.json();
      } catch (e) {}
    };

    const fetchLinearAlgebraData = async (forceRefresh = false) => {
      linearAlgebraLoading.value = true;
      try {
        const url = forceRefresh ? '/api/quant/linear-algebra/run' : '/api/quant/linear-algebra/latest';
        const method = forceRefresh ? 'POST' : 'GET';
        const res = await fetch(url, { method });
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            linearAlgebraData.value = resp.data;
            fetchLinearAlgebraReview(30);
            return;
          }
        }
        // 双通道降级: 尝试读取静态兜底数据 (带时间戳破坏缓存)
        const cacheBuster = `?_t=${Date.now()}`;
        const fallbackRes = await fetch(`/static/linear_algebra_analysis.json${cacheBuster}`, { cache: 'no-store' });
        if (fallbackRes.ok) {
          linearAlgebraData.value = await fallbackRes.json();
        }
        fetchLinearAlgebraReview(30);
      } catch (err) {
        console.warn('获取线性代数推演数据失败，切换至静态快照:', err);
        try {
          const fallbackRes = await fetch(`/static/linear_algebra_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) {
            linearAlgebraData.value = await fallbackRes.json();
          }
          fetchLinearAlgebraReview(30);
        } catch (e) {
          console.error('线性代数双通道获取均失败:', e);
        }
      } finally {
        linearAlgebraLoading.value = false;
      }
    };

    const fetchRandomForestReview = async (n = 30, forceRefresh = false) => {
      try {
        const q = forceRefresh ? '&force_refresh=true' : '';
        const res = await fetch(`/api/quant/random-forest/review?n=${n}${q}`);
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            randomForestReviewData.value = resp.data;
            return;
          }
          if (resp.status === 'success' || resp.records) {
            randomForestReviewData.value = resp;
            return;
          }
        }
      } catch (e) {}
      try {
        const fallbackRes = await fetch(`/static/random_forest_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) randomForestReviewData.value = await fallbackRes.json();
      } catch (e) {}
    };

    const fetchRandomForestData = async (forceRefresh = false) => {
      randomForestLoading.value = true;
      try {
        const url = forceRefresh ? '/api/quant/random-forest/run' : '/api/quant/random-forest/latest';
        const method = forceRefresh ? 'POST' : 'GET';
        const res = await fetch(url, { method });
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            randomForestData.value = resp.data;
            fetchRandomForestReview(30);
            return;
          }
        }
        const fallbackRes = await fetch(`/static/random_forest_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) randomForestData.value = await fallbackRes.json();
        fetchRandomForestReview(30);
      } catch (err) {
        console.warn('获取随机森林数据失败:', err);
        try {
          const fallbackRes = await fetch(`/static/random_forest_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) randomForestData.value = await fallbackRes.json();
          fetchRandomForestReview(30);
        } catch (e) {}
      } finally {
        randomForestLoading.value = false;
      }
    };

    const fetchErrorCorrectionReview = async (n = 30, forceRefresh = false) => {
      try {
        const q = forceRefresh ? '&force_refresh=true' : '';
        const res = await fetch(`/api/error_correction/review?n=${n}${q}`);
        if (res.ok) {
          const resp = await res.json();
          if ((resp.status === 'ok' || resp.code === 200) && resp.data) {
            errorCorrectionReviewData.value = resp.data;
            return;
          }
          if (resp.status === 'success' || resp.records) {
            errorCorrectionReviewData.value = resp;
            return;
          }
        }
      } catch (e) {}
      try {
        const fallbackRes = await fetch(`/static/error_correction_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) errorCorrectionReviewData.value = await fallbackRes.json();
      } catch (e) {}
    };

    const fetchErrorCorrectionData = async (forceRefresh = false) => {
      errorCorrectionLoading.value = true;
      try {
        const url = forceRefresh ? '/api/error_correction/run' : '/api/error_correction/latest';
        const method = forceRefresh ? 'POST' : 'GET';
        const res = await fetch(url, { method });
        if (res.ok) {
          const resp = await res.json();
          if ((resp.status === 'ok' || resp.code === 200) && resp.data) {
            errorCorrectionData.value = resp.data;
            fetchErrorCorrectionReview(30);
            return;
          }
        }
        const fallbackRes = await fetch(`/static/error_correction_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) errorCorrectionData.value = await fallbackRes.json();
        fetchErrorCorrectionReview(30);
      } catch (err) {
        console.warn('获取残差改错数据失败:', err);
        try {
          const fallbackRes = await fetch(`/static/error_correction_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) errorCorrectionData.value = await fallbackRes.json();
          fetchErrorCorrectionReview(30);
        } catch (e) {}
      } finally {
        errorCorrectionLoading.value = false;
      }
    };

    // ── 一胆拖三盾 · 选2组合拳 数据获取 (2026-10-22) ──
    const fetchSpearShieldReview = async (n = 0) => {
      try {
        const res = await fetch(`/api/spear_shield/review${n ? '?n=' + n : ''}`);
        if (res.ok) {
          const resp = await res.json();
          if (resp.status === 'ok' && resp.data) spearShieldReviewData.value = resp.data;
        }
      } catch (e) { console.warn('获取一胆拖三盾复盘失败:', e); }
    };

    const fetchSpearShieldData = async () => {
      spearShieldLoading.value = true;
      try {
        const res = await fetch('/api/spear_shield/latest');
        if (res.ok) {
          const resp = await res.json();
          if (resp.status === 'ok' && resp.data) {
            spearShieldData.value = resp.data;
            fetchSpearShieldReview();
            return;
          }
        }
      } catch (err) {
        console.warn('获取一胆拖三盾票面失败:', err);
      } finally {
        spearShieldLoading.value = false;
      }
    };

    const rerunSpearShieldReview = async (n = 30) => {
      if (spearShieldRerunning.value) return;
      spearShieldRerunning.value = true;
      try {
        const res = await fetch(`/api/spear_shield/review-rerun?n=${n}`, { method: 'POST' });
        if (res.ok) {
          const resp = await res.json();
          if (resp.status === 'ok' && resp.data) spearShieldReviewData.value = resp.data;
        }
      } catch (e) {
        console.warn('重跑一胆拖三盾回测失败:', e);
      } finally {
        spearShieldRerunning.value = false;
      }
    };

    // ── 点位012偏态压缩器 数据获取 (2026-10-22) ──
    const fetchPointRoadData = async () => {
      pointRoadLoading.value = true;
      try {
        const [a, b] = await Promise.allSettled([
          fetch('/api/point_road/latest').then(r => r.ok ? r.json() : null),
          fetch('/api/point_road/review?n=30').then(r => r.ok ? r.json() : null),
        ]);
        if (a.status === 'fulfilled' && a.value && a.value.status === 'ok') pointRoadData.value = a.value.data;
        if (b.status === 'fulfilled' && b.value && b.value.status === 'ok') pointRoadReviewData.value = b.value.data;
      } catch (err) {
        console.warn('获取点位012压缩数据失败:', err);
      } finally {
        pointRoadLoading.value = false;
      }
    };

    // 11. 动态时间规整 DTW 数据获取
    const fetchDTWReview = async (n = 30) => {
      try {
        const res = await fetch(`/api/quant/dtw/review?n=${n}`);
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            dtwReviewData.value = resp.data;
            return;
          }
          if (resp.status === 'success' || resp.records) {
            dtwReviewData.value = resp;
            return;
          }
        }
      } catch (e) {
        // 静默降级
      }
      try {
        const fallbackRes = await fetch(`/static/dtw_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) dtwReviewData.value = await fallbackRes.json();
      } catch (e) {}
    };

    const fetchDTWData = async (forceRefresh = false) => {
      dtwLoading.value = true;
      try {
        const url = forceRefresh ? '/api/quant/dtw/run' : '/api/quant/dtw/latest';
        const method = forceRefresh ? 'POST' : 'GET';
        const res = await fetch(url, { method });
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            dtwData.value = resp.data;
            fetchDTWReview(30);
            return;
          }
        }
        const cacheBuster = `?_t=${Date.now()}`;
        const fallbackRes = await fetch(`/static/dtw_analysis.json${cacheBuster}`, { cache: 'no-store' });
        if (fallbackRes.ok) dtwData.value = await fallbackRes.json();
        fetchDTWReview(30);
      } catch (err) {
        console.warn('获取DTW数据失败，读取静态缓存:', err);
        try {
          const fallbackRes = await fetch(`/static/dtw_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) dtwData.value = await fallbackRes.json();
          fetchDTWReview(30);
        } catch (e) {}
      } finally {
        dtwLoading.value = false;
      }
    };

    // 12. Transformer 全局自注意力数据获取
    const fetchTransformerReview = async (n = 30) => {
      try {
        const res = await fetch(`/api/quant/transformer/review?n=${n}`);
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            transformerReviewData.value = resp.data;
            return;
          }
          if (resp.status === 'success' || resp.records) {
            transformerReviewData.value = resp;
            return;
          }
        }
      } catch (e) {
        // 静默降级
      }
      try {
        const fallbackRes = await fetch(`/static/transformer_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) transformerReviewData.value = await fallbackRes.json();
      } catch (e) {}
    };

    const fetchTransformerData = async (forceRefresh = false) => {
      transformerLoading.value = true;
      try {
        const url = forceRefresh ? '/api/quant/transformer/run' : '/api/quant/transformer/latest';
        const method = forceRefresh ? 'POST' : 'GET';
        const res = await fetch(url, { method });
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            transformerData.value = resp.data;
            fetchTransformerReview(30);
            return;
          }
        }
        const cacheBuster = `?_t=${Date.now()}`;
        const fallbackRes = await fetch(`/static/transformer_analysis.json${cacheBuster}`, { cache: 'no-store' });
        if (fallbackRes.ok) transformerData.value = await fallbackRes.json();
        fetchTransformerReview(30);
      } catch (err) {
        console.warn('获取Transformer数据失败，读取静态缓存:', err);
        try {
          const fallbackRes = await fetch(`/static/transformer_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) transformerData.value = await fallbackRes.json();
          fetchTransformerReview(30);
        } catch (e) {}
      } finally {
        transformerLoading.value = false;
      }
    };

    // 13. 矩阵轮廓 Matrix Profile 数据获取
    const fetchMatrixProfileReview = async (n = 30) => {
      try {
        const res = await fetch(`/api/quant/matrix-profile/review?n=${n}`);
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            matrixProfileReviewData.value = resp.data;
            return;
          }
          if (resp.status === 'success' || resp.records) {
            matrixProfileReviewData.value = resp;
            return;
          }
        }
      } catch (e) {
        // 静默降级
      }
      try {
        const fallbackRes = await fetch(`/static/matrix_profile_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) matrixProfileReviewData.value = await fallbackRes.json();
      } catch (e) {}
    };

    const fetchMatrixProfileData = async (forceRefresh = false) => {
      matrixProfileLoading.value = true;
      try {
        const url = forceRefresh ? '/api/quant/matrix-profile/run' : '/api/quant/matrix-profile/latest';
        const method = forceRefresh ? 'POST' : 'GET';
        const res = await fetch(url, { method });
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            matrixProfileData.value = resp.data;
            fetchMatrixProfileReview(30);
            return;
          }
        }
        const cacheBuster = `?_t=${Date.now()}`;
        const fallbackRes = await fetch(`/static/matrix_profile_analysis.json${cacheBuster}`, { cache: 'no-store' });
        if (fallbackRes.ok) matrixProfileData.value = await fallbackRes.json();
        fetchMatrixProfileReview(30);
      } catch (err) {
        console.warn('获取矩阵轮廓数据失败，读取静态缓存:', err);
        try {
          const fallbackRes = await fetch(`/static/matrix_profile_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) matrixProfileData.value = await fallbackRes.json();
          fetchMatrixProfileReview(30);
        } catch (e) {}
      } finally {
        matrixProfileLoading.value = false;
      }
    };

    // 14. 拓扑数据分析 TDA 数据获取
    const fetchTDAReview = async (n = 30) => {
      try {
        const res = await fetch(`/api/quant/tda/review?n=${n}`);
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            tdaReviewData.value = resp.data;
            return;
          }
          if (resp.status === 'success' || resp.records) {
            tdaReviewData.value = resp;
            return;
          }
        }
      } catch (e) {
        // 静默降级
      }
      try {
        const fallbackRes = await fetch(`/static/tda_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) tdaReviewData.value = await fallbackRes.json();
      } catch (e) {}
    };

    const fetchTDAData = async (forceRefresh = false) => {
      tdaLoading.value = true;
      try {
        const url = forceRefresh ? '/api/quant/tda/run' : '/api/quant/tda/latest';
        const method = forceRefresh ? 'POST' : 'GET';
        const res = await fetch(url, { method });
        if (res.ok) {
          const resp = await res.json();
          if (resp.code === 200 && resp.data) {
            tdaData.value = resp.data;
            fetchTDAReview(30);
            return;
          }
        }
        const cacheBuster = `?_t=${Date.now()}`;
        const fallbackRes = await fetch(`/static/tda_analysis.json${cacheBuster}`, { cache: 'no-store' });
        if (fallbackRes.ok) tdaData.value = await fallbackRes.json();
        fetchTDAReview(30);
      } catch (err) {
        console.warn('获取TDA数据失败，读取静态缓存:', err);
        try {
          const fallbackRes = await fetch(`/static/tda_analysis.json?_t=${Date.now()}`, { cache: 'no-store' });
          if (fallbackRes.ok) tdaData.value = await fallbackRes.json();
          fetchTDAReview(30);
        } catch (e) {}
      } finally {
        tdaLoading.value = false;
      }
    };

    // ═════════════════ 六大高维数学与AI超级共识 滚动对账 ═════════════════
    const fetchAiMathConsensusReview = async (n = 30, forceRefresh = false) => {
      try {
        const res = await fetch(`/api/quant/ai-math-consensus/review?n=${n}${forceRefresh ? '&force_refresh=true' : ''}`);
        if (res.ok) {
          const resp = await res.json();
          if (resp.status === 'success' || resp.records) {
            aiMathConsensusReviewData.value = resp;
            return;
          }
        }
      } catch (e) {
        // 静默降级
      }
      try {
        const fallbackRes = await fetch(`/static/ai_consensus_review_${n}.json?_t=${Date.now()}`, { cache: 'no-store' });
        if (fallbackRes.ok) {
          aiMathConsensusReviewData.value = await fallbackRes.json();
        }
      } catch (e) {
        console.warn('静态读取超级共识对账流水失败:', e);
      }
    };

    const fetchHitLeaderboard = async (n = hitRange.value) => {
      hitLoading.value = true;
      try {
        const res = await fetch(`/api/quant/hit-leaderboard?n=${n}`);
        if (res.ok) {
          const data = await res.json();
          hitLeaderboard.value = data;
        }
      } catch (err) {
        console.error('获取命中热力榜失败:', err);
      } finally {
        hitLoading.value = false;
      }
    };

    const fetchHistoryTrends = async (limit = 25) => {
      try {
        const res = await fetch(`/api/quant/history-trends?limit=${limit}`);
        if (res.ok) {
          const data = await res.json();
          trendStats.value = data;
          updateTrendChart(data);
        }
      } catch (err) {
        console.error('获取历史走势失败:', err);
      }
    };

    const fetchLotteryTrends = async (limit = 100) => {
      try {
        trendLoading.value = true;
        trendLimit.value = limit;
        trendCustomInput.value = limit;
        const res = await fetch(`/api/quant/lottery-trends?limit=${limit}`);
        if (res.ok) {
          trendData.value = await res.json();
          nextTick(() => {
            updateTrendDistChart();
            updateTrendSumOddChart();
            const el = document.getElementById('trendTableWrapper');
            if (el) {
              el.scrollTop = el.scrollHeight;
            }
          });
        }
      } catch (err) {
        console.error('获取开奖号码走势图失败:', err);
      } finally {
        trendLoading.value = false;
      }
    };

    // ───────── 全模块预测共识叠加 (2026-10-22) ─────────
    // 默认勾选: 水位 Lift >= 1.15 且非样本不足的现役模块 (强信号优先)
    const DEFAULT_CONSENSUS_MIN_LIFT = 1.15;

    const fetchModuleConsensus = async () => {
      try {
        consensusLoading.value = true;
        const res = await fetch('/api/quant/module-consensus');
        if (!res.ok) return;
        const data = await res.json();
        if (data && data.status === 'ok') {
          consensusData.value = data;
          // 首次加载时给出合理默认勾选, 之后尊重用户手动选择
          if (consensusEnabled.value.length === 0 && (data.modules || []).length) {
            consensusEnabled.value = data.modules
              .filter(m => (m.lift || 0) >= DEFAULT_CONSENSUS_MIN_LIFT)
              .map(m => m.id);
          }
        }
      } catch (err) {
        console.error('获取全模块共识叠加数据失败:', err);
      } finally {
        consensusLoading.value = false;
      }
    };

    const consensusModuleMap = computed(() => {
      const map = {};
      for (const m of (consensusData.value.modules || [])) map[m.id] = m;
      return map;
    });

    // 号码 -> 当前勾选模块中点了它的模块列表 (含颜色)
    const consensusByBall = computed(() => {
      const on = new Set(consensusEnabled.value);
      const out = {};
      const src = consensusData.value.consensus || {};
      for (const [numStr, ids] of Object.entries(src)) {
        const hit = ids.filter(id => on.has(id));
        if (hit.length) out[numStr] = hit;
      }
      return out;
    });

    const toggleConsensusModule = (id) => {
      const i = consensusEnabled.value.indexOf(id);
      if (i > -1) consensusEnabled.value.splice(i, 1);
      else consensusEnabled.value.push(id);
    };

    const selectAllConsensusModules = () => {
      consensusEnabled.value = (consensusData.value.modules || []).map(m => m.id);
    };

    const selectStrongConsensusModules = () => {
      consensusEnabled.value = (consensusData.value.modules || [])
        .filter(m => (m.lift || 0) >= DEFAULT_CONSENSUS_MIN_LIFT)
        .map(m => m.id);
    };

    const clearConsensusModules = () => {
      consensusEnabled.value = [];
    };

    const handleCustomLimitSubmit = () => {
      let n = parseInt(trendCustomInput.value);
      if (isNaN(n) || n < 5) n = 100;
      if (n > 1000) n = 1000;
      fetchLotteryTrends(n);
    };

    const toggleHighlightBall = (num) => {
      if (highlightedBall.value === num) {
        highlightedBall.value = null;
      } else {
        highlightedBall.value = num;
      }
    };

    const handleSearchBallHighlight = () => {
      let n = parseInt(trendSearchBall.value);
      if (!isNaN(n) && n >= 1 && n <= 80) {
        highlightedBall.value = n;
      } else {
        highlightedBall.value = null;
      }
    };

    const toggleCustomPick = (num) => {
      const idx = customPicks.value.indexOf(num);
      if (idx > -1) {
        customPicks.value.splice(idx, 1);
      } else {
        customPicks.value.push(num);
        customPicks.value.sort((a, b) => a - b);
      }
    };

    const loadTop5ToCustomPicks = () => {
      if (prediction.value?.top5_gold?.length) {
        customPicks.value = [...prediction.value.top5_gold];
      }
    };

    const loadHiddenEnergyToCustomPicks = () => {
      if (prediction.value?.hidden_energy_5?.length) {
        customPicks.value = [...prediction.value.hidden_energy_5];
      }
    };

    const clearCustomPicks = () => {
      customPicks.value = [];
    };

    const filteredBallColumns = computed(() => {
      if (trendZoneFilter.value === '1') {
        return Array.from({ length: 20 }, (_, i) => i + 1);
      } else if (trendZoneFilter.value === '2') {
        return Array.from({ length: 20 }, (_, i) => i + 21);
      } else if (trendZoneFilter.value === '3') {
        return Array.from({ length: 20 }, (_, i) => i + 41);
      } else if (trendZoneFilter.value === '4') {
        return Array.from({ length: 20 }, (_, i) => i + 61);
      }
      return Array.from({ length: 80 }, (_, i) => i + 1);
    });

    const getBallStat = (num) => {
      if (!trendData.value || !trendData.value.ball_stats) return {};
      return trendData.value.ball_stats[num - 1] || {};
    };

    const fetchHistoryTable = async (page = 1) => {
      historyTable.page = page;
      try {
        const url = `/api/quant/history-table?page=${historyTable.page}&page_size=${historyTable.page_size}&q=${encodeURIComponent(historyTable.q)}`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          historyTable.items = data.items || [];
          historyTable.total = data.total || 0;
          historyTable.total_pages = data.total_pages || 1;
        }
      } catch (err) {
        console.error('获取历史表格失败:', err);
      }
    };

    // 历史总库：012路 / 质合（优先用后端字段，否则就地从号码推算，免重启也能显示）
    const _KL8_PRIMES = new Set([2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79]);
    const histRoad = (row) => {
      if (row && row.road0 != null && row.road1 != null && row.road2 != null) {
        return { r0: row.road0, r1: row.road1, r2: row.road2 };
      }
      const nums = (row && row.numbers) || [];
      let r0 = 0, r1 = 0, r2 = 0;
      for (const n of nums) {
        const m = Number(n) % 3;
        if (m === 0) r0++; else if (m === 1) r1++; else r2++;
      }
      return { r0, r1, r2 };
    };
    const histPrime = (row) => {
      if (row && row.prime_count != null && row.composite_count != null) {
        return { p: row.prime_count, c: row.composite_count, has01: !!row.has_01 };
      }
      const nums = (row && row.numbers) || [];
      let p = 0, c = 0, has01 = false;
      for (const n of nums) {
        const v = Number(n);
        if (v === 1) { has01 = true; continue; }
        if (_KL8_PRIMES.has(v)) p++; else c++;
      }
      return { p, c, has01 };
    };
    const histBallRoadClass = (num) => {
      const m = Number(num) % 3;
      if (m === 0) return 'bg-rose-500/15 text-rose-300 border-rose-400/40';
      if (m === 1) return 'bg-amber-500/15 text-amber-300 border-amber-400/40';
      return 'bg-emerald-500/15 text-emerald-300 border-emerald-400/40';
    };
    const histBallTip = (num) => {
      const v = Number(num);
      const road = v % 3;
      const kind = v === 1 ? '01(非质非合)' : (_KL8_PRIMES.has(v) ? '质数' : '合数');
      return `${String(v).padStart(2, '0')} · ${road}路 · ${kind}`;
    };

    const fetchReportList = async () => {
      try {
        const res = await fetch('/api/reports/list');
        if (res.ok) {
          reportList.value = await res.json();
          if (reportList.value.length > 0 && !currentReport.value.content) {
            openReportContent(reportList.value[0]);
          }
        }
      } catch (err) {
        console.error('获取报告列表失败:', err);
      }
    };

    const openReportContent = async (item) => {
      try {
        const res = await fetch(`/api/reports/detail/${item.raw_date || item.date}`);
        if (res.ok) {
          const data = await res.json();
          currentReport.value = {
            date: data.date,
            period: data.period,
            title: `第 ${data.period} 期量化研判与复盘审计报告 (${data.date})`,
            content: data.content
          };
        }
      } catch (err) {
        console.error('读取报告全文失败:', err);
      }
    };

    const openBallDetail = async (ball) => {
      try {
        const num = ball && (ball.number != null ? ball.number : ball);
        // 详情要合并金/重/冷/热：矩阵未加载时先拉截面
        if (!(matrixData.value || []).length) {
          await fetchMatrixData();
        }
        const res = await fetch(`/api/quant/number/${num}`);
        if (!res.ok) return;
        const detail = await res.json();
        if (detail.error) return;

        const cell = (matrixData.value || []).find((c) => Number(c.number) === Number(num));
        const merged = { ...detail };
        if (cell) {
          if (cell.omission != null) merged.omission = cell.omission;
          if (cell.freq_30 != null) merged.freq_30 = cell.freq_30;
          if (cell.energy != null) merged.energy = cell.energy;
          merged.is_top5 = !!cell.is_top5;
          merged.is_top12 = !!cell.is_top12;
          merged.category = cell.category || null;
          merged.recommend_tag = cell.recommend_tag || null;
          merged.ladder_name = cell.ladder_name || null;
        } else if (ball && typeof ball === 'object') {
          merged.is_top5 = !!ball.is_top5;
          merged.is_top12 = !!ball.is_top12;
          merged.category = ball.category || null;
        }

        const zone = merged.zone != null ? Number(merged.zone) : (Math.floor((Number(num) - 1) / 20) + 1);
        const road = merged.road != null ? Number(merged.road) : (Number(num) % 3);
        const pk = merged.prime_kind || (Number(num) === 1 ? 'neither' : (
          [2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79].includes(Number(num)) ? 'prime' : 'composite'
        ));
        merged.zone = zone;
        merged.road = road;
        merged.road_label = merged.road_label || `${road}路`;
        merged.prime_kind = pk;
        merged.prime_label = merged.prime_label || (pk === 'prime' ? '质数' : (pk === 'composite' ? '合数' : '非质非合'));

        const tags = [];
        tags.push({ key: 'zone', label: `区${zone}`, tone: `tag-zone-${zone}`, title: `分区 ${zone} · 点击在矩阵筛选` });
        tags.push({ key: 'tail', label: `尾${merged.tail != null ? merged.tail : (num % 10)}`, tone: 'tag-focus', title: '尾数' });
        tags.push({ key: 'road', label: `${road}路`, tone: `tag-road-${road}`, title: `012路 · 点击在矩阵筛选` });
        tags.push({
          key: 'prime',
          label: pk === 'prime' ? '质' : (pk === 'composite' ? '合' : '—'),
          tone: `tag-prime-${pk}`,
          title: `${merged.prime_label} · 点击在矩阵筛选`
        });
        tags.push({
          key: 'oe',
          label: (merged.odd_even === '偶数' || num % 2 === 0) ? '偶' : '奇',
          tone: 'tag-he',
          title: merged.odd_even || (num % 2 ? '奇数' : '偶数')
        });
        if (merged.is_top5) tags.push({ key: 'gold', label: '金', tone: 'tag-gold', title: '金胆 Top5 · 点击在矩阵筛选' });
        else if (merged.is_top12) tags.push({ key: 'focus', label: '重', tone: 'tag-focus', title: '重点候选 · 点击在矩阵筛选' });
        if (merged.category === 'golden_pair') tags.push({ key: 'pair', label: '对', tone: 'tag-gold', title: '黄金搭档' });
        if (merged.category === 'hidden_energy') tags.push({ key: 'he', label: 'HE', tone: 'tag-he', title: 'Hidden Energy' });
        if (merged.category === 'cold_rebound') tags.push({ key: 'cold', label: '冷', tone: 'tag-cold', title: '极冷号 · 点击在矩阵筛选' });
        if (merged.category === 'hot_energy') tags.push({ key: 'hot', label: '热', tone: 'tag-hot', title: '极热码 · 点击在矩阵筛选' });

        merged.dim_tags = tags;
        merged.dim_summary = [
          `区${zone}`,
          `尾${merged.tail != null ? merged.tail : (num % 10)}`,
          `${road}路`,
          merged.prime_label,
          merged.odd_even || (num % 2 ? '奇数' : '偶数'),
          merged.is_top5 ? '金胆' : (merged.is_top12 ? '重点候选' : null),
          merged.category === 'cold_rebound' ? '极冷' : null,
          merged.category === 'hot_energy' ? '极热' : null,
          merged.omission != null ? `遗${merged.omission}` : null,
          merged.freq_30 != null ? `近30·${merged.freq_30}次` : null,
          merged.energy != null ? `E${merged.energy}` : null
        ].filter(Boolean).join(' · ');

        selectedBall.value = merged;
        showBallModal.value = true;
      } catch (err) {
        console.error('获取球号详情失败:', err);
      }
    };

    /** 从号码详情角标跳到 80 码矩阵并套上对应筛选 */
    const focusMatrixFromBallTag = (tag) => {
      const b = selectedBall.value;
      if (!tag || !b) return;
      const key = tag.key;
      if (key === 'tail' || key === 'oe' || key === 'pair' || key === 'he') {
        showBallModal.value = false;
        openTab('matrix_80');
        return;
      }

      activeFilters.value = [];
      activeFilter.value = 'all';
      matrixMorphFilters.roads = [];
      matrixMorphFilters.primes = [];
      matrixMorphFilters.zones = [];
      matrixFilterMode.value = 'or';
      matrixDimOverlay.value = 'none';

      if (key === 'zone') {
        matrixMorphFilters.zones = [Number(b.zone)];
        matrixDimOverlay.value = 'zone';
      } else if (key === 'road') {
        matrixMorphFilters.roads = [Number(b.road)];
        matrixDimOverlay.value = 'road012';
      } else if (key === 'prime') {
        matrixMorphFilters.primes = [b.prime_kind || 'composite'];
        matrixDimOverlay.value = 'prime';
      } else if (key === 'gold') {
        activeFilters.value = ['top5'];
        activeFilter.value = 'top5';
      } else if (key === 'focus') {
        activeFilters.value = ['top12'];
        activeFilter.value = 'top12';
      } else if (key === 'cold') {
        activeFilters.value = ['cold'];
        activeFilter.value = 'cold';
      } else if (key === 'hot') {
        activeFilters.value = ['hot'];
        activeFilter.value = 'hot';
      }

      showBallModal.value = false;
      openTab('matrix_80');
      addLog(`📍 矩阵已按「${tag.label}」筛选（来自号码 ${b.display}）`, 'info');
    };

    // ──────────────── 任务与流水线触发 ────────────────

    const runPipeline = async () => {
      if (isRunning.value) return;
      try {
        openTab('live_terminal');
        isRunning.value = true;
        addLog('⚡ 正在发起【全流程量化预测流水线】任务请求...');
        const res = await fetch('/api/pipeline/run', { method: 'POST' });
        const data = await res.json();
        if (data && data.task_id) {
          currentTaskId.value = data.task_id;
          addLog(`✅ 任务已创建 (ID: ${data.task_id})，正在流式获取计算日志...`, 'success');
          startLogPolling(data.task_id);
        } else {
          addLog(`⚠️ 任务提示: ${data?.message || '已有任务在运行'}`, 'warn');
          isRunning.value = false;
        }
      } catch (err) {
        addLog(`❌ 发起任务失败: ${err}`, 'error');
        isRunning.value = false;
      }
    };

    const syncData = async () => {
      if (isRunning.value) return;
      try {
        openTab('live_terminal');
        isRunning.value = true;
        addLog('🔄 正在拉取并同步历史开奖数据...');
        const res = await fetch('/api/pipeline/sync-data', { method: 'POST' });
        const data = await res.json();
        if (data && data.task_id) {
          currentTaskId.value = data.task_id;
          addLog(`✅ 数据同步任务已就绪 (ID: ${data.task_id})`, 'success');
          startLogPolling(data.task_id, async () => {
            addLog('📌 开奖已同步。正在打开「夜间/开奖流水线」——可一键跑非点位全自动；点位类请录入后再手动跑。', 'info');
            await fetchSystemStatus();
            fetchSchedulerStatus();
            openTab('nightly_scheduler');
          });
        } else {
          addLog(`⚠️ 同步提示: ${data?.message || '任务冲突'}`, 'warn');
          isRunning.value = false;
        }
      } catch (err) {
        addLog(`❌ 同步失败: ${err}`, 'error');
        isRunning.value = false;
      }
    };

    const startLogPolling = (taskId, callback = null) => {
      if (logPollTimer) clearInterval(logPollTimer);
      logPollTimer = setInterval(async () => {
        try {
          const res = await fetch(`/api/pipeline/logs/${taskId}`);
          if (res.ok) {
            const data = await res.json();
            if (data.logs && data.logs.length > 0) {
              terminalLogs.value = data.logs;
              if (autoScroll.value) {
                nextTick(() => {
                  const elem = document.getElementById('terminal-logs-window');
                  if (elem) elem.scrollTop = elem.scrollHeight;
                });
              }
            }
            if (data.status === 'SUCCESS' || data.status === 'FAILED' || data.status === 'ERROR') {
              clearInterval(logPollTimer);
              isRunning.value = false;
              addLog(`🏁 任务【${data.title || taskId}】已结束，状态: ${data.status}`, data.status === 'SUCCESS' ? 'success' : 'error');
              fetchSystemStatus();
              fetchPrediction();
              fetchMatrixData();
              fetchHistoryTrends();
              fetchHistoryTable(1);
              fetchJingleSummary();
              fetchSpatialPointsSummary();
              fetchSpatialPointsMatrix();
              fetchSpatialPointsReview(pointsReviewPeriods.value);
              fetchJingleSummary();
              fetchJingleReview();
              if (typeof callback === 'function') {
                try {
                  await callback();
                } catch (cbErr) {
                  console.error('任务完成回调异常:', cbErr);
                }
              }
            }
          }
        } catch (e) {
          console.error('轮询日志失败:', e);
        }
      }, 1500);
    };

    const pollTaskLogs = startLogPolling;

    const addLog = (msg, type = 'info') => {
      const timeStr = new Date().toLocaleTimeString();
      terminalLogs.value.push(`[${timeStr}] ${msg}`);
      if (autoScroll.value) {
        nextTick(() => {
          const elem = document.getElementById('terminal-logs-window');
          if (elem) elem.scrollTop = elem.scrollHeight;
        });
      }
    };

    const clearLogs = () => {
      terminalLogs.value = [];
    };

    // ──────────────── 参数调优 ────────────────

    const normalizeWeights = () => {
      const total = modelParams.EF + modelParams.RW + modelParams.FO;
      if (total > 0) {
        modelParams.EF = parseFloat((modelParams.EF / total).toFixed(2));
        modelParams.RW = parseFloat((modelParams.RW / total).toFixed(2));
        modelParams.FO = parseFloat((1.0 - modelParams.EF - modelParams.RW).toFixed(2));
      }
      updateRadarChart();
    };

    const saveParams = async () => {
      try {
        const res = await fetch('/api/config/params', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            EF: modelParams.EF,
            RW: modelParams.RW,
            FO: modelParams.FO
          })
        });
        const data = await res.json();
        if (res.ok) {
          paramSaveMsg.value = '✅ 权重参数更新成功！';
          addLog(`⚙️ 操盘手已更新权重参数: EF(蹭热度)=${modelParams.EF}, RW(抓冷门)=${modelParams.RW}, FO(找周期)=${modelParams.FO}`, 'success');
          setTimeout(() => { paramSaveMsg.value = ''; }, 3000);
        } else {
          paramSaveMsg.value = `❌ 错误: ${data.detail || '保存失败'}`;
        }
      } catch (err) {
        paramSaveMsg.value = `❌ 请求异常: ${err}`;
      }
    };

    // ──────────────── ECharts 多主题配色引擎 ────────────────

    const getThemeColors = () => {
      const isLight = currentTheme.value === 'theme-light';
      switch (currentTheme.value) {
        case 'theme-gold':
          return {
            textColor: '#d1c7b7',
            axisColor: 'rgba(245, 158, 11, 0.25)',
            splitColor: 'rgba(245, 158, 11, 0.08)',
            primary: '#f59e0b',
            secondary: '#fbbf24',
            accent: '#d97706',
            tooltipBg: 'rgba(18, 20, 26, 0.95)'
          };
        case 'theme-aurora':
          return {
            textColor: '#d8b4fe',
            axisColor: 'rgba(192, 132, 252, 0.25)',
            splitColor: 'rgba(192, 132, 252, 0.08)',
            primary: '#c084fc',
            secondary: '#f472b6',
            accent: '#2dd4bf',
            tooltipBg: 'rgba(20, 14, 42, 0.95)'
          };
        case 'theme-emerald':
          return {
            textColor: '#a7f3d0',
            axisColor: 'rgba(16, 185, 129, 0.25)',
            splitColor: 'rgba(16, 185, 129, 0.08)',
            primary: '#10b981',
            secondary: '#34d399',
            accent: '#a3e635',
            tooltipBg: 'rgba(8, 28, 18, 0.95)'
          };
        case 'theme-midnight':
          return {
            textColor: '#cbd5e1',
            axisColor: 'rgba(255, 255, 255, 0.2)',
            splitColor: 'rgba(255, 255, 255, 0.06)',
            primary: '#38bdf8',
            secondary: '#ffffff',
            accent: '#818cf8',
            tooltipBg: 'rgba(20, 20, 20, 0.95)'
          };
        case 'theme-light':
          return {
            textColor: '#334155',
            axisColor: 'rgba(15, 23, 42, 0.15)',
            splitColor: 'rgba(15, 23, 42, 0.06)',
            primary: '#0284c7',
            secondary: '#d97706',
            accent: '#7c3aed',
            tooltipBg: 'rgba(255, 255, 255, 0.95)'
          };
        case 'theme-cyber':
        default:
          return {
            textColor: '#94a3b8',
            axisColor: 'rgba(6, 182, 212, 0.25)',
            splitColor: 'rgba(6, 182, 212, 0.06)',
            primary: '#00f0ff',
            secondary: '#f59e0b',
            accent: '#a855f7',
            tooltipBg: 'rgba(14, 20, 36, 0.95)'
          };
      }
    };

    const initCharts = () => {
      const radarElem = document.getElementById('radar-chart');
      if (radarElem) radarChart = echarts.init(radarElem);
      const radarTabElem = document.getElementById('radar-chart-tab');
      if (radarTabElem) radarChartTab = echarts.init(radarTabElem);

      const trendElem = document.getElementById('trend-chart');
      if (trendElem) trendChart = echarts.init(trendElem);
      const trendTabElem = document.getElementById('trend-chart-tab');
      if (trendTabElem) trendChartTab = echarts.init(trendTabElem);

      const tailElem = document.getElementById('tail-chart');
      if (tailElem) tailChart = echarts.init(tailElem);
      const tailTabElem = document.getElementById('tail-chart-tab');
      if (tailTabElem) tailChartTab = echarts.init(tailTabElem);

      const zoneElem = document.getElementById('zone-chart');
      if (zoneElem) zoneChart = echarts.init(zoneElem);
      const zoneTabElem = document.getElementById('zone-chart-tab');
      if (zoneTabElem) zoneChartTab = echarts.init(zoneTabElem);

      const trendDistElem = document.getElementById('lottery-trend-dist-chart');
      if (trendDistElem) trendDistChart = echarts.init(trendDistElem);
      const trendSumOddElem = document.getElementById('lottery-trend-sum-odd-chart');
      if (trendSumOddElem) trendSumOddChart = echarts.init(trendSumOddElem);

      const sixteenElem = document.getElementById('sixteenDistChart');
      if (sixteenElem && !chartHandles.sixteenDistChart) {
        chartHandles.sixteenDistChart = echarts.init(sixteenElem);
      }

      window.addEventListener('resize', handleResize);

      // 注册 ResizeObserver 监听容器尺寸变化（解决隐式 Tab 切换尺寸坍塌问题）
      if (window.ResizeObserver) {
        const resizeObserver = new ResizeObserver(() => {
          handleResize();
        });
        const chartIds = [
          'radar-chart', 'radar-chart-tab', 'trend-chart', 'trend-chart-tab',
          'tail-chart', 'tail-chart-tab', 'zone-chart', 'zone-chart-tab',
          'lottery-trend-dist-chart', 'lottery-trend-sum-odd-chart', 'sixteenDistChart'
        ];
        chartIds.forEach(id => {
          const el = document.getElementById(id);
          if (el) resizeObserver.observe(el);
        });
      }
    };

    const updateAllCharts = () => {
      updateRadarChart();
      if (trendStats.value) updateTrendChart(trendStats.value);
      if (tailStats.value) updateTailChart(tailStats.value);
      if (zoneStats.value) updateZoneChart(zoneStats.value);
      if (trendData.value && trendData.value.ball_stats && trendData.value.ball_stats.length > 0) {
        updateTrendDistChart();
        updateTrendSumOddChart();
      }
      if (sixteenSummary.value) updateSixteenDistChart();
    };

    const handleResize = () => {
      syncEnvironmentClasses();
      if (radarChart) radarChart.resize();
      if (radarChartTab) radarChartTab.resize();
      if (trendChart) trendChart.resize();
      if (trendChartTab) trendChartTab.resize();
      if (tailChart) tailChart.resize();
      if (tailChartTab) tailChartTab.resize();
      if (zoneChart) zoneChart.resize();
      if (zoneChartTab) zoneChartTab.resize();
      if (trendDistChart) trendDistChart.resize();
      if (trendSumOddChart) trendSumOddChart.resize();
      if (chartHandles.sixteenDistChart) chartHandles.sixteenDistChart.resize();
      if (gaConvergenceChart) gaConvergenceChart.resize();
      if (gaRadarChart) gaRadarChart.resize();
    };

    const updateRadarChart = () => {
      const tc = getThemeColors();
      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        radar: {
          indicator: [
            { name: 'EF 蹭热度 (能量场)', max: 100 },
            { name: 'RW 抓冷门 (遗漏回补)', max: 100 },
            { name: 'FO 找周期 (谐波)', max: 100 },
            { name: 'MK 找跟班 (关联度)', max: 100 },
            { name: '香农熵补偿 (扎堆/分散)', max: 100 }
          ],
          shape: 'polygon',
          splitNumber: 4,
          axisName: { color: tc.primary, fontSize: 12, fontWeight: 600 },
          splitLine: { lineStyle: { color: tc.splitColor } },
          splitArea: {
            show: true,
            areaStyle: {
              color: [tc.splitColor, tc.splitColor, tc.splitColor, tc.splitColor]
            }
          },
          axisLine: { lineStyle: { color: tc.axisColor } }
        },
        series: [{
          name: '三维融合量化动能',
          type: 'radar',
          data: [{
            value: [
              Math.round(modelParams.EF * 200),
              Math.round(modelParams.RW * 200),
              Math.round(modelParams.FO * 200),
              75,
              80
            ],
            name: '当前模型赋能',
            symbol: 'circle',
            symbolSize: 6,
            itemStyle: { color: tc.primary },
            areaStyle: {
              color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
                { offset: 0, color: tc.primary + '99' },
                { offset: 1, color: tc.secondary + '26' }
              ])
            },
            lineStyle: { width: 2.5, color: tc.primary }
          }]
        }]
      };

      const elem1 = document.getElementById('radar-chart');
      if (elem1) {
        if (!radarChart || radarChart.isDisposed()) radarChart = echarts.init(elem1);
        radarChart.setOption(option, true);
      }
      const elem2 = document.getElementById('radar-chart-tab');
      if (elem2) {
        if (!radarChartTab || radarChartTab.isDisposed()) radarChartTab = echarts.init(elem2);
        radarChartTab.setOption(option, true);
      }
    };

    const updateTrendChart = (data) => {
      if (!data || !data.periods) return;
      const tc = getThemeColors();
      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        legend: {
          data: ['Top 5 命中数', 'Top 12 命中数', '基准均线 (Top5: 2码)'],
          textStyle: { color: tc.textColor },
          top: 0
        },
        grid: { left: '3%', right: '4%', bottom: '8%', top: '18%', containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: data.periods.map(p => p.slice(-3) + '期'),
          axisLine: { lineStyle: { color: tc.axisColor } },
          axisLabel: { color: tc.textColor, fontSize: 11 }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 8,
          splitLine: { lineStyle: { color: tc.splitColor } },
          axisLabel: { color: tc.textColor }
        },
        series: [
          {
            name: 'Top 5 命中数',
            type: 'line',
            smooth: true,
            data: data.top5_hits,
            itemStyle: { color: tc.secondary },
            lineStyle: { width: 3, shadowColor: tc.secondary + '80', shadowBlur: 10 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: tc.secondary + '55' },
                { offset: 1, color: tc.secondary + '00' }
              ])
            }
          },
          {
            name: 'Top 12 命中数',
            type: 'line',
            smooth: true,
            data: data.top12_hits,
            itemStyle: { color: tc.primary },
            lineStyle: { width: 2, shadowColor: tc.primary + '80', shadowBlur: 8 }
          },
          {
            name: '基准均线 (Top5: 2码)',
            type: 'line',
            data: data.periods.map(() => 2),
            lineStyle: { type: 'dashed', color: tc.accent, width: 1.5 },
            symbol: 'none'
          }
        ]
      };

      const elem1 = document.getElementById('trend-chart');
      if (elem1) {
        if (!trendChart || trendChart.isDisposed()) trendChart = echarts.init(elem1);
        trendChart.setOption(option, true);
      }
      const elem2 = document.getElementById('trend-chart-tab');
      if (elem2) {
        if (!trendChartTab || trendChartTab.isDisposed()) trendChartTab = echarts.init(elem2);
        trendChartTab.setOption(option, true);
      }
    };

    const updateTailChart = (tails) => {
      if (!tails || tails.length === 0) return;
      const tc = getThemeColors();
      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        grid: { left: '3%', right: '3%', bottom: '5%', top: '15%', containLabel: true },
        xAxis: {
          type: 'category',
          data: tails.map(t => '尾' + t.tail),
          axisLine: { lineStyle: { color: tc.axisColor } },
          axisLabel: { color: tc.textColor }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 6,
          splitLine: { lineStyle: { color: tc.splitColor } },
          axisLabel: { color: tc.textColor }
        },
        series: [{
          name: '最新期出现次数',
          type: 'bar',
          data: tails.map(t => {
            let color = tc.primary;
            if (t.count === 0) color = '#ef4444';
            else if (t.count >= 4) color = tc.secondary;
            return {
              value: t.count,
              itemStyle: { color: color, borderRadius: [4, 4, 0, 0] }
            };
          }),
          barWidth: '55%'
        }]
      };

      const elem1 = document.getElementById('tail-chart');
      if (elem1) {
        if (!tailChart || tailChart.isDisposed()) tailChart = echarts.init(elem1);
        tailChart.setOption(option, true);
      }
      const elem2 = document.getElementById('tail-chart-tab');
      if (elem2) {
        if (!tailChartTab || tailChartTab.isDisposed()) tailChartTab = echarts.init(elem2);
        tailChartTab.setOption(option, true);
      }
    };

    const updateZoneChart = (zones) => {
      if (!zones || zones.length === 0) return;
      const tc = getThemeColors();
      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        series: [{
          name: '区间出号分布',
          type: 'pie',
          radius: ['45%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 6, borderColor: 'transparent', borderWidth: 2 },
          label: {
            show: true,
            color: tc.textColor,
            fontSize: 11,
            formatter: '{b}: {c}个'
          },
          data: zones.map((z, idx) => {
            const colors = [tc.primary, tc.secondary, tc.accent, '#10b981'];
            return {
              value: z.count,
              name: z.zone.split(' ')[0],
              itemStyle: { color: colors[idx % colors.length] }
            };
          })
        }]
      };

      const elem1 = document.getElementById('zone-chart');
      if (elem1) {
        if (!zoneChart || zoneChart.isDisposed()) zoneChart = echarts.init(elem1);
        zoneChart.setOption(option, true);
      }
      const elem2 = document.getElementById('zone-chart-tab');
      if (elem2) {
        if (!zoneChartTab || zoneChartTab.isDisposed()) zoneChartTab = echarts.init(elem2);
        zoneChartTab.setOption(option, true);
      }
    };

    const updateTrendDistChart = () => {
      if (!trendData.value || !trendData.value.ball_stats || trendData.value.ball_stats.length === 0) return;
      const tc = getThemeColors();
      const stats = trendData.value.ball_stats;
      const totalP = trendData.value.summary?.total_periods || trendLimit.value;
      const expectedAvg = (totalP * 0.25).toFixed(1);

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor },
          formatter: (params) => {
            const p = params[0];
            const ball = stats[p.dataIndex];
            if (!ball) return '';
            const zoneNames = ['', '一区(01-20)', '二区(21-40)', '三区(41-60)', '四区(61-80)'];
            return `<div style="font-weight:bold;color:${tc.primary};margin-bottom:4px;">号码 ${ball.display} · ${zoneNames[ball.zone]}</div>
                    <div style="font-size:12px;line-height:1.6;">
                      <div>📊 出号频次: <b style="color:${tc.secondary};">${ball.frequency}</b> 次 (占比 ${ball.frequency_rate}%)</div>
                      <div>🎯 理论均值: <b>${expectedAvg}</b> 次</div>
                      <div>❄️ 最大遗漏: <b>${ball.max_omission}</b> 期</div>
                      <div>📉 平均遗漏: <b>${ball.avg_omission}</b> 期</div>
                      <div>🔥 最大连出: <b>${ball.max_consecutive}</b> 期</div>
                      <div>⏳ 当前遗漏: <b>${ball.current_omission}</b> 期</div>
                    </div>`;
          }
        },
        grid: { left: '3%', right: '3%', bottom: '8%', top: '16%', containLabel: true },
        xAxis: {
          type: 'category',
          data: stats.map(b => b.display),
          axisLine: { lineStyle: { color: tc.axisColor } },
          axisLabel: { color: tc.textColor, interval: 1, fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          name: '出现次数',
          nameTextStyle: { color: tc.textColor, fontSize: 11 },
          splitLine: { lineStyle: { color: tc.splitColor } },
          axisLabel: { color: tc.textColor }
        },
        series: [{
          name: '出现次数',
          type: 'bar',
          data: stats.map(b => {
            let color = tc.primary;
            if (b.zone === 1) color = '#06b6d4';
            else if (b.zone === 2) color = '#f59e0b';
            else if (b.zone === 3) color = '#a855f7';
            else if (b.zone === 4) color = '#10b981';
            return {
              value: b.frequency,
              itemStyle: { color: color, borderRadius: [2, 2, 0, 0] }
            };
          }),
          barWidth: '60%',
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
            data: [{ yAxis: parseFloat(expectedAvg), name: '理论平均线' }],
            label: { color: '#ef4444', formatter: `理论均线: ${expectedAvg}次`, position: 'insideEndTop' }
          }
        }]
      };

      const elem = document.getElementById('lottery-trend-dist-chart');
      if (elem) {
        if (!trendDistChart || trendDistChart.isDisposed()) trendDistChart = echarts.init(elem);
        trendDistChart.setOption(option, true);
      }
    };

    const updateTrendSumOddChart = () => {
      if (!trendData.value || !trendData.value.draws || trendData.value.draws.length === 0) return;
      const tc = getThemeColors();
      const draws = trendData.value.draws;

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: tc.tooltipBg,
          borderColor: tc.primary,
          textStyle: { color: tc.textColor }
        },
        legend: {
          data: ['和值走势 (左轴)', '单数(奇数)个数 (右轴)'],
          textStyle: { color: tc.textColor },
          top: 0
        },
        grid: { left: '3%', right: '4%', bottom: '8%', top: '16%', containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: draws.map(d => d.period.slice(-3) + '期'),
          axisLine: { lineStyle: { color: tc.axisColor } },
          axisLabel: { color: tc.textColor, fontSize: 10 }
        },
        yAxis: [
          {
            type: 'value',
            name: '和值',
            nameTextStyle: { color: tc.textColor, fontSize: 11 },
            min: 500,
            max: 1150,
            splitLine: { lineStyle: { color: tc.splitColor } },
            axisLabel: { color: tc.textColor }
          },
          {
            type: 'value',
            name: '奇数个数',
            nameTextStyle: { color: tc.textColor, fontSize: 11 },
            min: 0,
            max: 20,
            splitLine: { show: false },
            axisLabel: { color: tc.textColor }
          }
        ],
        series: [
          {
            name: '和值走势 (左轴)',
            type: 'line',
            smooth: true,
            yAxisIndex: 0,
            data: draws.map(d => d.sum),
            itemStyle: { color: tc.secondary },
            lineStyle: { width: 2.5, color: tc.secondary },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: tc.secondary + '33' },
                { offset: 1, color: tc.secondary + '00' }
              ])
            }
          },
          {
            name: '单数(奇数)个数 (右轴)',
            type: 'line',
            smooth: true,
            yAxisIndex: 1,
            data: draws.map(d => d.odd_count),
            itemStyle: { color: tc.primary },
            lineStyle: { width: 2, color: tc.primary }
          }
        ]
      };

      const elem = document.getElementById('lottery-trend-sum-odd-chart');
      if (elem) {
        if (!trendSumOddChart || trendSumOddChart.isDisposed()) trendSumOddChart = echarts.init(elem);
        trendSumOddChart.setOption(option, true);
      }
    };

    // ──────────────── 辅助计算与衍生视图 ────────────────

    const hasMatrixPoolFilter = computed(() => (activeFilters.value || []).length > 0);
    const hasMatrixMorphFilter = computed(() => {
      const mf = matrixMorphFilters;
      return (mf.roads && mf.roads.length) || (mf.primes && mf.primes.length) || (mf.zones && mf.zones.length);
    });
    const hasMatrixFilter = computed(() => hasMatrixPoolFilter.value || hasMatrixMorphFilter.value);

    const toggleMatrixFilter = (key) => {
      if (key === 'all') {
        activeFilters.value = [];
        activeFilter.value = 'all';
        return;
      }
      const arr = [...(activeFilters.value || [])];
      const i = arr.indexOf(key);
      if (i >= 0) arr.splice(i, 1);
      else arr.push(key);
      activeFilters.value = arr;
      // 同步旧单选：0→all，1→该键，多选→multi
      activeFilter.value = arr.length === 0 ? 'all' : (arr.length === 1 ? arr[0] : 'multi');
    };

    const isMatrixFilterActive = (key) => {
      if (key === 'all') return !(activeFilters.value || []).length;
      return (activeFilters.value || []).includes(key);
    };

    const toggleMatrixMorph = (dim, value) => {
      const mf = matrixMorphFilters;
      const listKey = dim === 'road' ? 'roads' : (dim === 'prime' ? 'primes' : 'zones');
      const arr = [...(mf[listKey] || [])];
      const i = arr.indexOf(value);
      if (i >= 0) arr.splice(i, 1);
      else arr.push(value);
      mf[listKey] = arr;
    };

    const isMatrixMorphActive = (dim, value) => {
      const mf = matrixMorphFilters;
      if (dim === 'road') return (mf.roads || []).includes(value);
      if (dim === 'prime') return (mf.primes || []).includes(value);
      if (dim === 'zone') return (mf.zones || []).includes(value);
      return false;
    };

    const clearMatrixMorphFilters = () => {
      matrixMorphFilters.roads = [];
      matrixMorphFilters.primes = [];
      matrixMorphFilters.zones = [];
    };

    const isMatrixPoolMatch = (cell) => {
      if (!cell) return false;
      const fs = activeFilters.value || [];
      if (!fs.length) {
        // 兼容旧单选 activeFilter
        const f = activeFilter.value;
        if (!f || f === 'all' || f === 'multi') return true;
        if (f === 'top5') return !!cell.is_top5;
        if (f === 'top12') return !!cell.is_top12;
        if (f === 'cold') return cell.category === 'cold_rebound';
        if (f === 'hot') return cell.category === 'hot_energy';
        return true;
      }
      const checks = fs.map((f) => {
        if (f === 'top5') return !!cell.is_top5;
        if (f === 'top12') return !!cell.is_top12;
        if (f === 'cold') return cell.category === 'cold_rebound';
        if (f === 'hot') return cell.category === 'hot_energy';
        return false;
      });
      return matrixFilterMode.value === 'and' ? checks.every(Boolean) : checks.some(Boolean);
    };

    const isMatrixMorphMatch = (cell) => {
      if (!cell) return false;
      const mf = matrixMorphFilters;
      const roadOk = !(mf.roads || []).length || mf.roads.includes(matrixBallRoad(cell));
      const primeOk = !(mf.primes || []).length || mf.primes.includes(matrixBallPrimeKind(cell));
      const zoneOk = !(mf.zones || []).length || mf.zones.includes(matrixBallZone(cell));
      return roadOk && primeOk && zoneOk;
    };

    const isMatrixFilterMatch = (cell) => {
      return isMatrixPoolMatch(cell) && isMatrixMorphMatch(cell);
    };

    const filteredMatrix = computed(() => {
      if (!hasMatrixFilter.value) return matrixData.value;
      return (matrixData.value || []).filter(isMatrixFilterMatch);
    });

    const matrixBallZone = (cell) => {
      const n = cell && cell.number != null ? Number(cell.number) : 0;
      if (cell && cell.zone != null) return Number(cell.zone);
      return n ? (Math.floor((n - 1) / 20) + 1) : 0;
    };
    const matrixBallRoad = (cell) => {
      const n = cell && cell.number != null ? Number(cell.number) : 0;
      return n % 3;
    };
    const matrixBallPrimeKind = (cell) => {
      const n = cell && cell.number != null ? Number(cell.number) : 0;
      if (n === 1) return 'neither';
      return _KL8_PRIMES.has(n) ? 'prime' : 'composite';
    };
    const matrixDimLabel = (cell) => {
      const mode = matrixDimOverlay.value;
      if (mode === 'zone') return '区' + matrixBallZone(cell);
      if (mode === 'road012') return matrixBallRoad(cell) + '路';
      if (mode === 'prime') {
        const k = matrixBallPrimeKind(cell);
        return k === 'prime' ? '质' : (k === 'composite' ? '合' : '—');
      }
      return '';
    };
    const matrixDimCellClass = (cell) => {
      const mode = matrixDimOverlay.value;
      if (mode === 'none' || !cell) return '';
      if (mode === 'zone') return 'dim-zone-' + matrixBallZone(cell);
      if (mode === 'road012') return 'dim-road-' + matrixBallRoad(cell);
      if (mode === 'prime') return 'dim-prime-' + matrixBallPrimeKind(cell);
      return '';
    };
    /**
     * 多维属性叠加角标：池标签（金/重/冷/热…）+ 形态（区/路/质合）。
     * 当前分组轴已由区块标题表达时，不再重复该维，避免噪音。
     */
    const matrixCellAttrTags = (cell) => {
      if (!cell) return [];
      const tags = [];
      const mode = matrixDimOverlay.value;

      if (cell.is_top5) tags.push({ key: 'gold', label: '金', tone: 'tag-gold', title: '金胆 Top5' });
      else if (cell.is_top12) tags.push({ key: 'focus', label: '重', tone: 'tag-focus', title: '重点候选 Top12' });
      if (cell.category === 'golden_pair') tags.push({ key: 'pair', label: '对', tone: 'tag-gold', title: '黄金搭档' });
      if (cell.category === 'hidden_energy') tags.push({ key: 'he', label: 'HE', tone: 'tag-he', title: 'Hidden Energy' });
      if (cell.category === 'cold_rebound') tags.push({ key: 'cold', label: '冷', tone: 'tag-cold', title: '极冷号' });
      if (cell.category === 'hot_energy') tags.push({ key: 'hot', label: '热', tone: 'tag-hot', title: '极热码' });

      if (mode !== 'zone') {
        const z = matrixBallZone(cell);
        tags.push({ key: 'zone', label: '区' + z, tone: 'tag-zone-' + z, title: '分区 ' + z });
      }
      if (mode !== 'road012') {
        const r = matrixBallRoad(cell);
        tags.push({ key: 'road', label: r + '路', tone: 'tag-road-' + r, title: '012路 · mod3=' + r });
      }
      if (mode !== 'prime') {
        const k = matrixBallPrimeKind(cell);
        const label = k === 'prime' ? '质' : (k === 'composite' ? '合' : '—');
        tags.push({
          key: 'prime',
          label,
          tone: 'tag-prime-' + k,
          title: k === 'prime' ? '质数' : (k === 'composite' ? '合数' : '非质非合(01)')
        });
      }
      return tags;
    };
    const matrixAttrTagMap = computed(() => {
      const map = {};
      for (const cell of (matrixData.value || [])) {
        if (cell && cell.number != null) map[cell.number] = matrixCellAttrTags(cell);
      }
      return map;
    });
    /** 分组视图：分区 / 012路 / 质合 各自成块分别展示，不再只叠层着色 */
    const matrixDimGroups = computed(() => {
      const mode = matrixDimOverlay.value;
      const data = Array.isArray(matrixData.value) ? matrixData.value : [];
      if (mode === 'none' || !data.length) return null;
      const withMatchMeta = (cells) => {
        const matched = !hasMatrixFilter.value
          ? cells.length
          : cells.filter((c) => isMatrixFilterMatch(c)).length;
        return { cells, matched, total: cells.length };
      };
      if (mode === 'zone') {
        return [1, 2, 3, 4].map((z) => {
          const meta = withMatchMeta(data.filter((c) => matrixBallZone(c) === z));
          return {
            key: 'zone-' + z,
            tone: 'tone-zone-' + z,
            title: `${['', '一', '二', '三', '四'][z]}区`,
            subtitle: `${String((z - 1) * 20 + 1).padStart(2, '0')}-${String(z * 20).padStart(2, '0')}`,
            ...meta
          };
        });
      }
      if (mode === 'road012') {
        return [0, 1, 2].map((r) => {
          const meta = withMatchMeta(data.filter((c) => matrixBallRoad(c) === r));
          return {
            key: 'road-' + r,
            tone: 'tone-road-' + r,
            title: `${r}路`,
            subtitle: `号码 mod 3 = ${r}`,
            ...meta
          };
        });
      }
      if (mode === 'prime') {
        return [
          { key: 'prime-prime', tone: 'tone-prime-prime', title: '质数', subtitle: '质数码', kind: 'prime' },
          { key: 'prime-composite', tone: 'tone-prime-composite', title: '合数', subtitle: '合数码', kind: 'composite' },
          { key: 'prime-neither', tone: 'tone-prime-neither', title: '非质非合', subtitle: '号码 01', kind: 'neither' }
        ].map((g) => {
          const meta = withMatchMeta(data.filter((c) => matrixBallPrimeKind(c) === g.kind));
          return {
            key: g.key,
            tone: g.tone,
            title: g.title,
            subtitle: g.subtitle,
            ...meta
          };
        });
      }
      return null;
    });
    const setMatrixDimOverlay = (mode) => {
      matrixDimOverlay.value = matrixDimOverlay.value === mode ? 'none' : mode;
    };

    const purePoolDetailed = computed(() => {
      const pool = prediction.value?.pure_pool || [];
      return pool.map(num => {
        const found = matrixData.value.find(b => b.number === num);
        if (found) {
          return {
            ...found,
            display: String(num).padStart(2, '0')
          };
        }
        return {
          number: num,
          display: String(num).padStart(2, '0'),
          tag: '纯净金胆',
          omission: '-',
          freq_30: '-',
          energy: '-'
        };
      });
    });

    const top12Detailed = computed(() => {
      const pool = prediction.value?.top12_pool || [];
      const top5 = prediction.value?.top5_gold || [];
      const he5 = prediction.value?.hidden_energy_5 || [];
      return pool.map((num, idx) => {
        const found = matrixData.value.find(b => b.number === num) || {};
        return {
          rank: idx + 1,
          number: num,
          display: String(num).padStart(2, '0'),
          energy: found.energy || '-',
          zone: found.zone || Math.floor((num - 1) / 20) + 1,
          tail: found.tail !== undefined ? found.tail : (num % 10),
          omission: found.omission !== undefined ? found.omission : '-',
          freq_30: found.freq_30 !== undefined ? found.freq_30 : '-',
          is_gold: top5.includes(num),
          is_he5: he5.includes(num),
          ...found
        };
      });
    });

    const trendDetailedList = computed(() => {
      if (!trendStats.value || !trendStats.value.periods) return [];
      const list = [];
      const p = trendStats.value.periods;
      for (let i = 0; i < p.length; i++) {
        list.push({
          period: p[i],
          date: trendStats.value.dates ? trendStats.value.dates[i] : '---',
          top5_hit: trendStats.value.top5_hits ? trendStats.value.top5_hits[i] : 0,
          top12_hit: trendStats.value.top12_hits ? trendStats.value.top12_hits[i] : 0,
          sum: trendStats.value.draw_sums ? trendStats.value.draw_sums[i] : '---',
          odd_ratio: trendStats.value.odd_ratios ? ((trendStats.value.odd_ratios[i] * 100).toFixed(0) + '%') : '---'
        });
      }
      return list.reverse();
    });

    const tailsWithBalls = computed(() => {
      const result = [];
      const latestDraw = systemStatus.value?.latest_draw_numbers || [];
      const top5 = prediction.value?.top5_gold || [];
      const top12 = prediction.value?.top12_pool || [];

      for (let t = 0; t <= 9; t++) {
        const tailStat = tailStats.value.find(s => s.tail === t) || { count: 0, status: '平稳' };
        const balls = [];
        for (let i = 1; i <= 80; i++) {
          if (i % 10 === t) {
            const found = matrixData.value.find(b => b.number === i) || {};
            balls.push({
              number: i,
              display: String(i).padStart(2, '0'),
              omission: found.omission !== undefined ? found.omission : (latestDraw.includes(i) ? 0 : '-'),
              is_hit_latest: latestDraw.includes(i) || found.omission === 0,
              is_top5: top5.includes(i) || found.is_top5,
              is_top12: top12.includes(i) || found.is_top12,
              ...found
            });
          }
        }
        result.push({
          tail: t,
          count: tailStat.count,
          status: tailStat.status,
          balls: balls
        });
      }
      return result;
    });

    // ─── K8 page modules (extracted fetch/state clusters) ───
    const __k8PageBindings = window.K8Pages.apply(
      { ref, reactive, computed, watch, nextTick },
      {
        isRunning,
        openTab,
        addLog,
        startLogPolling,
        getThemeColors,
        terminalLogs,
        chartHandles,
        fetchPrediction,
        fetchPsychologicalGameData,
        fetchPsychologicalGameBacktest,
        fetchPrimeCompositeData,
        fetchLinearAlgebraData,
        fetchRandomForestData,
        fetchErrorCorrectionData,
        fetchDTWData,
        fetchTransformerData,
        fetchMatrixProfileData,
        fetchTDAData,
        isLinearAlgebraRunning,
        isRandomForestRunning,
        isErrorCorrectionRunning,
        // late-bound wrappers: safe to capture during apply; resolve at call-time
        fetchMetaGoldSummary(...args) {
          return __k8PageBindings.fetchMetaGoldSummary(...args);
        },
        fetchFunnelSummary(...args) {
          return __k8PageBindings.fetchFunnelSummary(...args);
        },
        fetchAllModulesOverview(...args) {
          return __k8PageBindings.fetchAllModulesOverview(...args);
        }
      }
    );
    window.__k8PageBindings = __k8PageBindings;
    const {
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
      fetchJingleReviewEnhanced,
      spatialPointsSummary,
      spatialPointsMatrix,
      spatialPointsReview,
      spatialPointsLoading,
      pointsMatrixFilter,
      pointsReviewPeriods,
      filteredPointsMatrix,
      fetchSpatialPointsSummary,
      fetchSpatialPointsMatrix,
      fetchSpatialPointsReview,
      triggerSpatialPointsRun,
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
      selectTriHighQuickPeriod,
      followSummary,
      followReview,
      followConditions,
      followLoading,
      followReviewPeriods,
      fetchFollowSummary,
      fetchFollowReview,
      fetchFollowConditions,
      triggerFollowRun,
      geminiSummary,
      geminiReview,
      geminiHistory,
      selectedGeminiReport,
      geminiReportDetail,
      geminiLoading,
      geminiReviewPeriods,
      fetchGeminiSummary,
      fetchGeminiReview,
      fetchGeminiHistory,
      selectGeminiReport,
      triggerGeminiRun,
      lstmSummary,
      lstmReview,
      lstmReviewPeriods,
      lstmReports,
      selectedLstmReport,
      lstmReportDetail,
      lstmLoading,
      fetchLstmSummary,
      fetchLstmReview,
      fetchLstmReports,
      selectLstmReport,
      triggerLstmRun,
      suppressionSummary,
      suppressionReview,
      suppressionPatterns,
      suppressionLoading,
      suppressionReviewPeriods,
      fetchSuppressionSummary,
      fetchSuppressionReview,
      fetchSuppressionPatterns,
      triggerSuppressionRun,
      pointOmissionSummary,
      pointOmissionReport,
      pointOmissionReportHtml,
      pointOmissionBacktest,
      pointOmissionHitLedger,
      pointOmissionLoading,
      pointOmissionLedgerLoading,
      pointOmissionSubTab,
      getMethodChineseName,
      fetchPointOmissionSummary,
      fetchPointOmissionReport,
      fetchPointOmissionBacktest,
      fetchPointOmissionHitLedger,
      seedPointOmissionHitLedger,
      triggerPointOmissionRun,
      setPointOmissionSubTab,
      isPointOmissionCore,
      isPointOmissionExpanded,
      isPointOmissionTop5,
      isPointOmissionDefensive,
      getPointOmissionNumScore,
      getPointOmissionNumMiss,
      getPointOmissionMatrixClass,
      goldPick2Summary,
      goldPick2Review,
      goldPick2Matrix,
      goldPick2Logs,
      selectedGoldPick2Log,
      goldPick2LogDetail,
      goldPick2Loading,
      goldPick2ReviewPeriods,
      fetchGoldPick2Summary,
      fetchGoldPick2Review,
      fetchGoldPick2Matrix,
      fetchGoldPick2Logs,
      selectGoldPick2Log,
      triggerGoldPick2Run,
      aggCockpit,
      aggHistory,
      selectedAggReport,
      aggReportDetail,
      aggLoading,
      fetchAggCockpit,
      fetchAggHistory,
      selectAggReport,
      triggerAggRun,
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
      applyBestBucketSort,
      dimensionCross,
      crossMatrixView,
      dimensionProfile,
      dimTailView,
      dimRoadView,
      dimPrimeView,
      optimalPicksView,
      crossCellClass,
      crossCellTitle,
      arbitrageResult,
      arbitrageLoading,
      arbitrageTracks,
      runDimensionArbitrage,
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
      fetchPaperTradingSummary,
      datasourceSummary,
      datasourceReview,
      datasourceLogs,
      selectedDatasourceLog,
      datasourceLogDetail,
      datasourceLoading,
      datasourceReviewPeriods,
      fetchDatasourceSummary,
      fetchDatasourceReview,
      fetchDatasourceLogs,
      selectDatasourceLog,
      triggerDatasourceRun,
      datasourceMatrixData,
      datasourceMatrixLoading,
      datasourceMatrixSelectedPeriod,
      currentMatrixHighlightMode,
      matrixHighlightModes,
      canPrevDatasourcePeriod,
      canNextDatasourcePeriod,
      fetchDatasourceMatrix,
      prevDatasourcePeriod,
      nextDatasourcePeriod,
      isCrossIntersection,
      getMatrixCellClass,
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
      closeEvolutionDetail,
      unifiedBrainData,
      unifiedBrainLoading,
      fetchUnifiedBrain,
      triggerUnifiedBrainRun,
      triggerPsychologicalGameRun,
      triggerPsychologicalGameBacktestRun,
      triggerPrimeCompositeRun,
      triggerLinearAlgebraRun,
      triggerRandomForestRun,
      triggerErrorCorrectionRun,
      triggerDTWRun,
      triggerTransformerRun,
      triggerMatrixProfileRun,
      triggerTDARun
    } = __k8PageBindings;

    // ═════════════════ 经典量化七大子模块汇总大盘 ═════════════════
    const classicLoading = ref(false);

    const activeClassicModelCount = computed(() => {
      return [
        datasourceSummary?.value,
        goldPick2Summary?.value,
        jingleSummary?.value,
        suppressionSummary?.value,
        psychologicalGameData.value,
        pointOmissionSummary?.value
      ].filter(Boolean).length;
    });

    const classicConsensus = computed(() => {
      const balls = Array.from({ length: 80 }, (_, i) => ({
        ball: i + 1,
        score: 0,
        vote_count: 0,
        sources: []
      }));

      const asNums = (list, max = 12) => {
        if (!Array.isArray(list)) return [];
        return list.map((x) => {
          if (typeof x === 'number') return x;
          if (x && typeof x === 'object') return Number(x.number ?? x.num ?? x.ball);
          return Number(x);
        }).filter((n) => Number.isFinite(n) && n >= 1 && n <= 80).slice(0, max);
      };

      const addVotes = (nums, code, weight = 1.0, asTop5 = true) => {
        nums.forEach((b, idx) => {
          const item = balls[b - 1];
          const base = asTop5 ? (5.0 - idx * 0.5) : (2.5 - idx * 0.15);
          item.score += Math.max(0.3, base) * weight;
          item.vote_count += 1;
          if (!item.sources.includes(code)) item.sources.push(code);
        });
      };

      const gp = goldPick2Summary?.value;
      if (gp) {
        const core = asNums([gp.golden, gp.hot].filter((x) => x != null), 5);
        const fromPairs = (gp.top5_golden || []).flatMap((p) => p.pair || []);
        addVotes([...new Set([...core, ...asNums(fromPairs, 10)])].slice(0, 8), '选2', 1.1);
      }

      const jg = jingleSummary?.value;
      if (jg) addVotes(asNums(jg.recommended_numbers, 10), '口诀', 1.0);

      const sp = suppressionSummary?.value;
      if (sp) addVotes(asNums((sp.top3 || []).map((c) => c.num), 5), '反弹', 1.0);

      const ds = datasourceSummary?.value;
      if (ds) {
        addVotes(asNums(ds.top3_gold || ds.top_hot_numbers || ds.consensus_numbers, 3), '数据源', 1.0);
      }

      const pg = psychologicalGameData.value;
      if (pg) {
        addVotes(asNums(pg.top3_gold || pg.top5_assault, 3), '心理', 1.05);
      }

      const po = pointOmissionSummary?.value;
      if (po) addVotes(asNums(po.top3_gold || po.top5, 3), '遗漏', 1.0);

      const sorted = [...balls].sort((a, b) => b.score - a.score || b.vote_count - a.vote_count);
      const top3 = sorted.filter((x) => x.vote_count > 0).slice(0, 3);
      // 兼容旧字段：主口径最优3码
      const top5 = top3;
      const top12 = top3;
      const top3Set = new Set(top3.map((x) => x.ball));
      const kill_list = [];

      const pairMap = new Map();
      const recordPair = (p, source) => {
        if (!p || p.length < 2) return;
        const a = Math.min(p[0], p[1]);
        const b = Math.max(p[0], p[1]);
        if (a < 1 || b > 80) return;
        const key = `${a}-${b}`;
        if (!pairMap.has(key)) pairMap.set(key, { pair: [a, b], count: 0, sources: [] });
        const obj = pairMap.get(key);
        obj.count += 1;
        if (!obj.sources.includes(source)) obj.sources.push(source);
      };

      if (gp?.gold_pair) recordPair(gp.gold_pair, '选2');
      (gp?.top5_golden || []).slice(0, 3).forEach((p) => recordPair(p.pair, '选2'));
      if (ds?.gold_pair) recordPair(ds.gold_pair, '数据源');
      if (top3.length >= 2) recordPair([top3[0].ball, top3[1].ball], '共识');

      const pairs = Array.from(pairMap.values())
        .map((p) => ({ pair: p.pair, sources: p.sources.join(' + '), count: p.count }))
        .sort((a, b) => b.count - a.count);

      balls.forEach((item) => {
        item.is_gold = top3Set.has(item.ball);
        item.in_top5 = top3Set.has(item.ball);
        item.in_top12 = top3Set.has(item.ball);
        item.is_killed = false;
      });

      return { top3_gold: top3, top5, top12, kill_list, pairs, balls };
    });

    const classicResonanceSortMode = ref('score');
    const sortedClassicResonanceList = computed(() => {
      const list = [...(classicConsensus.value?.balls || [])];
      if (classicResonanceSortMode.value === 'score') {
        return list.sort((a, b) => b.score - a.score || b.vote_count - a.vote_count || a.ball - b.ball);
      }
      return list.sort((a, b) => a.ball - b.ball);
    });

    const fetchAllClassicModels = async (forceRefresh = false) => {
      classicLoading.value = true;
      try {
        const failures = await runLoaders([
          { label: '数据源', run: () => fetchDatasourceSummary() },
          { label: '定胆选2', run: () => fetchGoldPick2Summary() },
          { label: '顺口溜', run: () => fetchJingleSummary() },
          { label: '点位抑制', run: () => fetchSuppressionSummary() },
          { label: '心理博弈', run: () => fetchPsychologicalGameData(!!forceRefresh) },
          { label: '点位遗漏', run: () => fetchPointOmissionSummary(!!forceRefresh) },
          { label: '实时推荐', run: () => fetchPrediction() }
        ]);
        if (failures.length) {
          addLog(`⚠️ 经典量化预测层有 ${failures.length} 项未能汇聚：${failures.map((f) => f.label).join('、')}`, 'warn');
        } else {
          addLog('⚡ 经典量化预测层摘要已汇聚完成', 'success');
        }
      } catch (err) {
        console.error('汇聚经典量化子模块失败:', err);
      } finally {
        classicLoading.value = false;
      }
    };

    const CLASSIC_PIPELINE_STEPS = [
      // 开奖侧自动（与夜间 v6 对齐）；点位类请在对应驾驶舱手动跑
      { path: '/api/pipeline/run-gold-pick2', label: '定胆选2' },
      { path: '/api/pipeline/run-jingle', label: '顺口溜' },
      { path: '/api/pipeline/run-psychological-game', label: '心理博弈' }
    ];

    const runAllClassicModels = async () => {
      if (isRunning.value || classicLoading.value) return;
      openTab('live_terminal');
      terminalLogs.value = [];
      classicLoading.value = true;
      isRunning.value = true;
      addLog('⚡ 经典开奖侧子模块串行推演启动（不含点位类）…', 'info');
      addLog('⏸️ 点位类（数据源/未开点位/点位遗漏/HE5）请录入后在对应页手动执行', 'warn');

      const runStep = async (idx) => {
        if (idx >= CLASSIC_PIPELINE_STEPS.length) {
          isRunning.value = false;
          classicLoading.value = false;
          await fetchPrediction();
          await fetchAllClassicModels(true);
          openTab('classic_overview');
          addLog('✨ 经典开奖侧推演完成，已回到汇总大盘', 'success');
          return;
        }
        const step = CLASSIC_PIPELINE_STEPS[idx];
        addLog(`▶️ [${idx + 1}/${CLASSIC_PIPELINE_STEPS.length}] ${step.label}`, 'info');
        try {
          isRunning.value = true;
          const res = await fetch(step.path, { method: 'POST' });
          if (!res.ok) {
            addLog(`⚠️ ${step.label} 启动失败，跳过继续`, 'error');
            await runStep(idx + 1);
            return;
          }
          const data = await res.json();
          startLogPolling(data.task_id, async () => {
            isRunning.value = true;
            await runStep(idx + 1);
          });
        } catch (e) {
          addLog(`❌ ${step.label}: ${e.message}`, 'error');
          await runStep(idx + 1);
        }
      };

      await runStep(0);
    };

    // ═════════════════ 首屏数据加载（逐项兜底 · 拒绝静默装死） ═════════════════
    // 每项包装成 thunk 逐个执行：任何一个模块缺失或抛错只影响它自己。
    // 旧写法把 13 个调用直接塞进 Promise.allSettled([...])，参数求值阶段一旦
    // 抛错 (如 fetchUnifiedBrain 未定义)，allSettled 根本不会被调用，其余
    // 请求全部静默丢失，界面表现为"数据没更新"。
    const bootFailures = ref([]);

    const FIRST_SCREEN_LOADERS = [
      { label: '开奖状态', run: () => fetchSchedulerStatus() },
      { label: '系统状态', run: () => fetchSystemStatus() },
      { label: '实时推荐', run: () => fetchPrediction() },
      { label: 'AI 数学模型', run: () => fetchAllAiMathModels() },
      { label: '统一决策主脑', run: () => fetchUnifiedBrain() },
      { label: '实战决算', run: () => fetchMasterReview(30) },
      { label: '元学习参数', run: () => fetchEvolutionStatus() },
      { label: '历史开奖表', run: () => fetchHistoryTable(1) },
      { label: '近期走势', run: () => fetchHistoryTrends() },
      { label: '点位矩阵', run: () => fetchMatrixData() },
      { label: '走势图', run: () => fetchLotteryTrends(100) },
      { label: '数据新鲜度', run: () => fetchFreshness() },
      { label: '模块注册表', run: () => fetchModuleRegistry() }
    ];

    const PREWARM_LOADERS = [
      { label: '全模块概览', run: () => fetchAllModulesOverview() },
      { label: '报告清单', run: () => fetchReportList() },
      { label: '点位信息', run: () => fetchDailyPointsInfo() },
      { label: '素数合成', run: () => fetchPrimeCompositeData() },
      { label: '心理博弈', run: () => fetchPsychologicalGameData() },
      { label: '空间点位矩阵', run: () => fetchSpatialPointsMatrix() }
    ];

    const loadFirstScreen = async () => {
      bootFailures.value = await runLoaders(FIRST_SCREEN_LOADERS);
      if (bootFailures.value.length) {
        const labels = bootFailures.value.map((f) => f.label).join('、');
        console.error('[首屏数据] 加载失败:', bootFailures.value);
        addLog(`⚠️ 首屏数据有 ${bootFailures.value.length} 项加载失败：${labels}`, 'warn');
      }
      return bootFailures.value;
    };

    onMounted(async () => {
      // 初始化当前主题
      document.documentElement.className = currentTheme.value;
      document.body.className = currentTheme.value;

      initCharts();
      // 2. 【首屏极速性能飞跃】：仅并发加载主驾驶舱首屏核心数据，杜绝串行等待！
      //    逐项兜底，失败项由顶部告警横幅现形，不再静默。
      await loadFirstScreen();

      // 全局点击与滚动自动收起 Tab 右键快捷菜单
      window.addEventListener('click', closeTabContextMenu);
      window.addEventListener('scroll', closeTabContextMenu, true);

      // 3. 定时刷新 22:00 倒计时 (轻量轮询)
      setInterval(fetchSchedulerStatus, 5000);

      // 4. 【后台静默预热 (Idle Prewarm)】：在首屏完全呈现 1.5 秒后，在浏览器空闲时后台静默拉取基础概览，绝不卡顿主界面
      setTimeout(async () => {
        const failures = await runLoaders(PREWARM_LOADERS);
        if (failures.length) {
          console.warn('[首屏预热] 加载失败:', failures);
        }
      }, 1500);
    });

    onBeforeUnmount(() => {
      if (logPollTimer) clearInterval(logPollTimer);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('click', closeTabContextMenu);
      window.removeEventListener('scroll', closeTabContextMenu, true);
    });

    return {
      bootFailures,
      loadFirstScreen,
      isMobile,
      isDesktop,
      isSidebarCollapsed,
      isMobileSidebarOpen,
      toggleMobileSidebar,
      handleSidebarToggle,
      themes,
      currentTheme,
      currentThemeObj,
      showThemeDropdown,
      setTheme,
      menuGroups,
      tabs,
      activeTab,
      isGroupActive,
      toggleGroup,
      toggleAllGroups,
      openTab,
      switchTab,
      openModuleHistory,
      tabContextMenu,
      openTabContextMenu,
      closeTabContextMenu,
      closeTab,
      closeOtherTabs,
      closeRightTabs,
      closeLeftTabs,
      closeAllTabs,
      refreshCurrentTab,
      systemStatus,
      prediction,
      matrixData,
      hitLeaderboard,
      hitLoading,
      hitRange,
      hitSortKey,
      hitSortedModules,
      hitRateOf,
      hitColor,
      hitRateOfColor,
      fetchHitLeaderboard,
      tailStats,
      zoneStats,
      trendStats,
      activeFilter,
      activeFilters,
      matrixFilterMode,
      matrixMorphFilters,
      hasMatrixFilter,
      toggleMatrixFilter,
      isMatrixFilterActive,
      toggleMatrixMorph,
      isMatrixMorphActive,
      clearMatrixMorphFilters,
      matrixDimOverlay,
      matrixDimGroups,
      matrixFilterCounts,
      isMatrixFilterMatch,
      matrixBallZone,
      matrixBallRoad,
      matrixBallPrimeKind,
      matrixDimLabel,
      matrixDimCellClass,
      matrixCellAttrTags,
      matrixAttrTagMap,
      setMatrixDimOverlay,
      primeCompositeData,
      primeCompositeLoading,
      fetchPrimeCompositeData,
      psychologicalGameData,
      psychologicalGameLoading,
      fetchPsychologicalGameData,
      // 衍生与视图计算属性
      filteredMatrix,
      purePoolDetailed,
      top12Detailed,
      trendDetailedList,
      tailsWithBalls,
      // 走势图状态与方法
      trendLimit,
      trendCustomInput,
      trendData,
      trendLoading,
      trendShowOmission,
      trendZoneFilter,
      trendViewMode,
      highlightedBall,
      trendSearchBall,
      customPicks,
      toggleCustomPick,
      loadTop5ToCustomPicks,
      loadHiddenEnergyToCustomPicks,
      clearCustomPicks,
      filteredBallColumns,
      getBallStat,
      fetchLotteryTrends,
      fetchHistoryTrends,
      handleCustomLimitSubmit,
      toggleHighlightBall,
      handleSearchBallHighlight,
      // 全模块预测共识叠加 (2026-10-22)
      consensusData,
      consensusEnabled,
      consensusLoading,
      consensusLegendOpen,
      consensusModuleMap,
      consensusByBall,
      fetchModuleConsensus,
      toggleConsensusModule,
      selectAllConsensusModules,
      selectStrongConsensusModules,
      clearConsensusModules,
      // 历史表格与研报
      historyTable,
      reportList,
      reportFilter,
      filteredReportList,
      currentReport,
      selectedBall,
      showBallModal,
      modelParams,
      paramSaveMsg,
      terminalLogs,
      isRunning,
      autoScroll,
      openBallDetail,
      focusMatrixFromBallTag,
      openReportContent,
      fetchHistoryTable,
      histRoad,
      histPrime,
      histBallRoadClass,
      histBallTip,
      runPipeline,
      syncData,
      clearLogs,
      normalizeWeights,
      saveParams,
      // 每日点位录入与联动
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
      // 顺口溜口诀
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
      // 空间重点点位分析
      spatialPointsSummary,
      spatialPointsMatrix,
      spatialPointsReview,
      spatialPointsLoading,
      pointsMatrixFilter,
      pointsReviewPeriods,
      filteredPointsMatrix,
      fetchSpatialPointsSummary,
      fetchSpatialPointsMatrix,
      fetchSpatialPointsReview,
      triggerSpatialPointsRun,
      // 跟随分析
      followSummary,
      followReview,
      followConditions,
      followLoading,
      followReviewPeriods,
      fetchFollowSummary,
      fetchFollowReview,
      fetchFollowConditions,
      triggerFollowRun,
      // 未开点位反弹追踪
      suppressionSummary,
      suppressionReview,
      suppressionPatterns,
      suppressionLoading,
      suppressionReviewPeriods,
      fetchSuppressionSummary,
      fetchSuppressionReview,
      fetchSuppressionPatterns,
      triggerSuppressionRun,
      // 点位+遗漏号深度研判驾驶舱
      pointOmissionSummary,
      pointOmissionReport,
      pointOmissionReportHtml,
      pointOmissionBacktest,
      pointOmissionHitLedger,
      pointOmissionLoading,
      pointOmissionLedgerLoading,
      pointOmissionSubTab,
      getMethodChineseName,
      fetchPointOmissionSummary,
      fetchPointOmissionReport,
      fetchPointOmissionBacktest,
      fetchPointOmissionHitLedger,
      seedPointOmissionHitLedger,
      triggerPointOmissionRun,
      setPointOmissionSubTab,
      isPointOmissionCore,
      isPointOmissionExpanded,
      isPointOmissionTop5,
      isPointOmissionDefensive,
      getPointOmissionNumScore,
      getPointOmissionNumMiss,
      getPointOmissionMatrixClass,
      // 定金选2决策
      goldPick2Summary,
      goldPick2Review,
      goldPick2Matrix,
      goldPick2Logs,
      selectedGoldPick2Log,
      goldPick2LogDetail,
      goldPick2Loading,
      goldPick2ReviewPeriods,
      fetchGoldPick2Summary,
      fetchGoldPick2Review,
      fetchGoldPick2Matrix,
      fetchGoldPick2Logs,
      selectGoldPick2Log,
      triggerGoldPick2Run,
      // Gemini 选2预测
      geminiSummary,
      geminiReview,
      geminiHistory,
      selectedGeminiReport,
      geminiReportDetail,
      geminiLoading,
      geminiReviewPeriods,
      fetchGeminiSummary,
      fetchGeminiReview,
      fetchGeminiHistory,
      selectGeminiReport,
      triggerGeminiRun,
      // 策略汇总复盘
      aggCockpit,
      aggHistory,
      selectedAggReport,
      aggReportDetail,
      aggLoading,
      fetchAggCockpit,
      fetchAggHistory,
      selectAggReport,
      triggerAggRun,
      // 16期中热频次动态推演与组合决策
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
      applyBestBucketSort,
      dimensionCross,
      crossMatrixView,
      dimensionProfile,
      dimTailView,
      dimRoadView,
      dimPrimeView,
      optimalPicksView,
      crossCellClass,
      crossCellTitle,
      arbitrageResult,
      arbitrageLoading,
      arbitrageTracks,
      runDimensionArbitrage,
      // 双层LSTM深度学习
      lstmSummary,
      lstmReview,
      lstmReviewPeriods,
      lstmReports,
      selectedLstmReport,
      lstmReportDetail,
      lstmLoading,
      fetchLstmSummary,
      fetchLstmReview,
      fetchLstmReports,
      selectLstmReport,
      triggerLstmRun,
      // 顺口溜 & 跟随 滚动复盘
      jingleReviewPeriods,
      jingleLoading,
      fetchJingleReviewEnhanced,
      // 数据源1×2 深层关联推演
      datasourceSummary,
      datasourceReview,
      datasourceLogs,
      selectedDatasourceLog,
      datasourceLogDetail,
      datasourceLoading,
      datasourceReviewPeriods,
      fetchDatasourceSummary,
      fetchDatasourceReview,
      fetchDatasourceLogs,
      selectDatasourceLog,
      triggerDatasourceRun,
      // 数据源1与数据源2 原始阵列全景
      datasourceMatrixData,
      datasourceMatrixLoading,
      datasourceMatrixSelectedPeriod,
      currentMatrixHighlightMode,
      matrixHighlightModes,
      canPrevDatasourcePeriod,
      canNextDatasourcePeriod,
      fetchDatasourceMatrix,
      prevDatasourcePeriod,
      nextDatasourcePeriod,
      isCrossIntersection,
      getMatrixCellClass,
      // 三高特征 (重复高/边高/冷高)
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
      selectTriHighQuickPeriod,
      // 每日自学习复盘总账本 & 全模块总览
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
      // 5 大新增量化决策与风控资产 (Meta-Gold / 三级漏斗 / 宏观环境 / FDR审计 / 模拟盘)
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
      fetchPaperTradingSummary,
      // 22:00 夜间全自动流水线 / 全模块复盘 / 自动进化
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
      closeEvolutionDetail,
      // 全栈统一决策主脑 (无加权)
      unifiedBrainData,
      unifiedBrainLoading,
      fetchUnifiedBrain,
      triggerUnifiedBrainRun,
      // 质合数与心理博弈量化推演 & 样本外滚动回测
      primeCompositeData,
      primeCompositeLoading,
      primeCompositeRefreshMsg,
      fetchPrimeCompositeData,
      triggerPrimeCompositeRun,
      psychologicalGameData,
      psychologicalGameLoading,
      fetchPsychologicalGameData,
      triggerPsychologicalGameRun,
      psychologicalGameBacktest,
      psychologicalGameBacktestLoading,
      psychologicalGameBacktestWindow,
      activePsychologicalBacktest,
      fetchPsychologicalGameBacktest,
      triggerPsychologicalGameBacktestRun,
      // 09. 遗传算法自进化推演战区
      geneticData,
      geneticReviewData,
      isGeneticRunning,
      fetchGeneticData,
      fetchGeneticReview,
      triggerGeneticEvolution,
      initGeneticConvergenceChart,
      initGeneticRadarChart,
      // 10. 线性代数空间投影量化推演
      linearAlgebraData,
      linearAlgebraReviewData,
      linearAlgebraLoading,
      isLinearAlgebraRunning,
      fetchLinearAlgebraData,
      fetchLinearAlgebraReview,
      triggerLinearAlgebraRun,
      // 随机森林号码预测
      randomForestData,
      randomForestReviewData,
      randomForestLoading,
      isRandomForestRunning,
      fetchRandomForestData,
      fetchRandomForestReview,
      triggerRandomForestRun,
      // 残差改错 GBDT
      errorCorrectionData,
      errorCorrectionReviewData,
      errorCorrectionLoading,
      isErrorCorrectionRunning,
      fetchErrorCorrectionData,
      fetchErrorCorrectionReview,
      triggerErrorCorrectionRun,
      // 一胆拖三盾 · 选2组合拳 (2026-10-22)
      spearShieldData,
      spearShieldReviewData,
      spearShieldLoading,
      spearShieldRerunning,
      fetchSpearShieldData,
      fetchSpearShieldReview,
      rerunSpearShieldReview,
      // 点位012偏态压缩器 (2026-10-22)
      pointRoadData,
      pointRoadReviewData,
      pointRoadLoading,
      fetchPointRoadData,
      // 11. 动态时间规整 DTW 推演
      dtwData,
      dtwReviewData,
      dtwLoading,
      fetchDTWData,
      fetchDTWReview,
      triggerDTWRun,
      // 12. Transformer 全局自注意力推演
      transformerData,
      transformerReviewData,
      transformerLoading,
      fetchTransformerData,
      fetchTransformerReview,
      triggerTransformerRun,
      // 13. 矩阵轮廓 Matrix Profile 查重
      matrixProfileData,
      matrixProfileReviewData,
      matrixProfileLoading,
      fetchMatrixProfileData,
      fetchMatrixProfileReview,
      triggerMatrixProfileRun,
      // 14. 拓扑数据分析 TDA 持续同调
      tdaData,
      tdaReviewData,
      tdaLoading,
      fetchTDAData,
      fetchTDAReview,
      triggerTDARun,
      // 六大高维数学与AI超级共识
      aiMathConsensus,
      aiMathConsensusReviewData,
      fetchAiMathConsensusReview,
      aiResonanceSortMode,
      sortedAiResonanceList,
      activeAiModelCount,
      aiMathLoading,
      fetchAllAiMathModels,
      // 经典量化七大子模块汇总
      classicLoading,
      classicConsensus,
      classicResonanceSortMode,
      sortedClassicResonanceList,
      activeClassicModelCount,
      fetchAllClassicModels,
      runAllClassicModels
    };
  }
};

createApp(App).mount('#app');


