/**
 * K8-QUANT sidebar menu registry (single source of truth).
 * app.js wraps buildMenuGroups() into a Vue ref; openTab resolves title/icon via MENU_BY_KEY.
 * shortTitle: sidebar label; title: tab bar / hover full name.
 * badge whitelist: 主推 / LIVE / 默认 only.
 *
 * 侧栏顺序（v6）：
 *  开奖走势(+夜间) → 基础形态(含16期主推) → 经典预测 → 高维AI → 最优策略汇总 → 运维录入
 */
(function (global) {
  const MENU_OPENED_STORAGE_KEY = 'k8.menu.opened.v6';

  const MENU_GROUPS_DEF = [
    {
      id: 'hub_trend_live',
      name: '开奖走势与总库',
      sub: 'DRAW TREND & DATA',
      icon: '📈',
      opened: true,
      children: [
        { key: 'draw_trend_chart', title: '开奖号码全景走势图', shortTitle: '开奖走势图', icon: '📈' },
        { key: 'history_table', title: '历史开奖总库检索', shortTitle: '历史开奖总库', icon: '📋' },
        { key: 'datasource_matrix', title: '数据源1×2 原始阵列', shortTitle: '数据源原始阵列', icon: '🧬' },
        { key: 'nightly_scheduler', title: '开奖后自动流水线（非点位模块）', shortTitle: '夜间/开奖流水线', icon: '⏰' }
      ]
    },
    {
      id: 'hub_basic_form',
      name: '基础形态观测',
      sub: 'BASIC FORM FACTORS',
      icon: '🔍',
      opened: false,
      children: [
        { key: 'matrix_80', title: '80码热力矩阵 · 012路账本（探盘合页）', shortTitle: '80码·012路', icon: '🌐' },
        { key: 'sixteen_cockpit', title: '16期中热频次推演（含频次全景）', shortTitle: '16期中热推演', icon: '🔥', badge: '主推' }
      ]
    },
    {
      id: 'hub_engine',
      name: '经典量化推演',
      sub: 'CLASSIC PREDICTION',
      icon: '⚡',
      opened: true,
      children: [
        { key: 'classic_overview', title: '经典量化推演汇总大盘', shortTitle: '经典推演大盘', icon: '⚡', badge: '默认' },
        { key: 'gold_pick2_cockpit', title: '黄金定胆选2决策驾驶舱', shortTitle: '定胆选2', icon: '💎' },
        { key: 'gold_pairs', title: '今日极简选2 · 黄金搭档', shortTitle: '极简选2', icon: '👑' },
        { key: 'hidden_energy', title: 'Hidden Energy 5 特供码', shortTitle: 'Hidden Energy', icon: '🌟' },
        { key: 'jingle_cockpit', title: '顺口溜组合带出研判', shortTitle: '顺口溜口诀', icon: '📜' },
        { key: 'psychological_game', title: '心理博弈与逆向均值回归', shortTitle: '心理博弈', icon: '🧠' },
        { key: 'datasource_cockpit', title: '数据源1×2 深层关联大屏（需点位）', shortTitle: '数据源关联', icon: '🧬' },
        { key: 'suppression_cockpit', title: '未开点位高压反弹驾驶舱（需点位）', shortTitle: '未开点位反弹', icon: '🪞' },
        { key: 'point_omission_cockpit', title: '点位与遗漏深度研判驾驶舱（需点位）', shortTitle: '点位与遗漏', icon: '🎯' },
        { key: 'spear_shield_cockpit', title: '一胆拖三盾 · 选2组合拳驾驶舱（需点位）', shortTitle: '一胆拖三盾', icon: '⚔️' },
        { key: 'point_road_cockpit', title: '点位012偏态压缩器驾驶舱（需点位）', shortTitle: '点位012压缩', icon: '🧭' }
      ]
    },
    {
      id: 'hub_ai_math',
      name: '高维数学与 AI',
      sub: 'ADVANCED MATH & AI',
      icon: '📐',
      opened: true,
      children: [
        { key: 'markov_line_cockpit', title: '马尔可夫特征直线校准驾驶舱', shortTitle: '马尔可夫直线', icon: '📏', badge: 'NEW' },
        { key: 'genetic_cockpit', title: '遗传算法自进化推演战区', shortTitle: '遗传算法', icon: '🧬', badge: '默认' },
        { key: 'linear_algebra_cockpit', title: '线性代数空间投影驾驶舱', shortTitle: '线性代数投影', icon: '📐' },
        { key: 'random_forest_cockpit', title: '随机森林号码预测驾驶舱', shortTitle: '随机森林模型', icon: '🌲' },
        { key: 'error_correction_cockpit', title: '残差改错 GBDT 驾驶舱', shortTitle: '残差改错 GBDT', icon: '🌳' }
      ]
    },
    {
      id: 'hub_core',
      name: '最优策略汇总',
      sub: 'OPTIMAL STRATEGY MERGE',
      icon: '👑',
      opened: false,
      children: [
        // 实战主推在「16期中热」；本组只留跨模块对照。已下架侧栏：实时主驾驶舱 / 三级漏斗 / 统一主脑（页面与 API 仍保留，openTab 可进）
        { key: 'agg_cockpit', title: '子系统汇总陈列（主推=16期）', shortTitle: '子系统陈列', icon: '🧬' },
        { key: 'meta_gold_cockpit', title: '各模块金胆对照表（16期+经典+AI）', shortTitle: '金胆对照表', icon: '👑' }
      ]
    },
    {
      id: 'hub_ops',
      name: '系统运维与录入',
      sub: 'SYSTEM & OPS',
      icon: '🛠️',
      opened: false,
      children: [
        { key: 'points_input', title: '每日点位录入管理', shortTitle: '点位录入', icon: '📝' },
        { key: 'tri_high_input', title: '三高录入与实战分析（需点位）', shortTitle: '三高录入', icon: '📝' },
        { key: 'live_terminal', title: '流水线黑客实时日志终端', shortTitle: '实时日志终端', icon: '💻', badge: 'LIVE' },
        { key: 'theme_gallery', title: '系统主题外观展厅', shortTitle: '主题展厅', icon: '🎨' },
        { key: 'reports_browser', title: '每日综合研判大研报总库', shortTitle: '研报总库', icon: '📑' }
      ]
    }
  ];

  const MENU_BY_KEY = Object.create(null);
  for (const g of MENU_GROUPS_DEF) {
    for (const c of g.children) {
      MENU_BY_KEY[c.key] = {
        key: c.key,
        title: c.title,
        shortTitle: c.shortTitle || c.title,
        icon: c.icon,
        badge: c.badge || '',
        hub: g.id,
        hubName: g.name
      };
    }
  }
  // 并入「80码·012路」合页后，尾数账本仍可 openTab，但不单独占侧栏
  if (!MENU_BY_KEY.tail_entropy) {
    MENU_BY_KEY.tail_entropy = {
      key: 'tail_entropy',
      title: '尾数分布与012路好码（合页·账本）',
      shortTitle: '012路账本',
      icon: '📊',
      badge: '',
      hub: 'hub_basic_form',
      hubName: '基础形态观测'
    };
  }
  // 从侧栏下架但仍可 openTab 的遗留汇总页
  const HIDDEN_HUB_CORE = [
    { key: 'live_cockpit', title: '实时主量化驾驶舱（已下架侧栏）', shortTitle: '实时主驾驶舱', icon: '⚡' },
    { key: 'funnel_cockpit', title: '三级漏斗全链路拼装（已下架侧栏）', shortTitle: '三级漏斗', icon: '🌪️' },
    { key: 'unified_brain_cockpit', title: '统一主脑（研究用·已下架侧栏）', shortTitle: '统一主脑', icon: '🧠' }
  ];
  for (const item of HIDDEN_HUB_CORE) {
    if (!MENU_BY_KEY[item.key]) {
      MENU_BY_KEY[item.key] = {
        key: item.key,
        title: item.title,
        shortTitle: item.shortTitle,
        icon: item.icon,
        badge: '',
        hub: 'hub_core',
        hubName: '最优策略汇总'
      };
    }
  }

  function readOpenedState() {
    try {
      const raw = global.localStorage && global.localStorage.getItem(MENU_OPENED_STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (e) {
      return null;
    }
  }

  function buildMenuGroups() {
    const saved = readOpenedState();
    return MENU_GROUPS_DEF.map((g) => ({
      id: g.id,
      name: g.name,
      sub: g.sub,
      icon: g.icon,
      opened: saved && Object.prototype.hasOwnProperty.call(saved, g.id)
        ? !!saved[g.id]
        : !!g.opened,
      children: g.children.map((c) => ({
        key: c.key,
        title: c.title,
        shortTitle: c.shortTitle || c.title,
        icon: c.icon,
        badge: c.badge || ''
      }))
    }));
  }

  function resolveMenuItem(key) {
    return MENU_BY_KEY[key] || null;
  }

  global.K8MenuRegistry = {
    MENU_GROUPS_DEF,
    MENU_BY_KEY,
    MENU_OPENED_STORAGE_KEY,
    buildMenuGroups,
    resolveMenuItem
  };
})(typeof window !== 'undefined' ? window : globalThis);
