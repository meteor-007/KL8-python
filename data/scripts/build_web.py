# -*- coding: utf-8 -*-
"""
build_web.py - 极速组装与校验 K8-QUANT 模块化 Web 视图
将 modules/<hub>/<menu>/view.html 与布局拼装为单一高性能 index.html (耗时 < 10ms)
"""
import os
import re
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(PROJ_DIR, "frontend", "static")
MODULES_DIR = os.path.join(STATIC_DIR, "modules")
LAYOUT_DIR = os.path.join(STATIC_DIR, "layout")
os.makedirs(LAYOUT_DIR, exist_ok=True)
os.makedirs(MODULES_DIR, exist_ok=True)

# 视图组装顺序 (相对 modules/ 的路径，按侧边栏 5 大枢纽)
ORDERED_VIEWS = [
    # 1. 终审决策与实战驾驶舱
    "hub_core/unified_brain/view.html",
    "hub_core/nightly_scheduler/view.html",
    "hub_core/meta_gold/view.html",
    "hub_core/funnel/view.html",
    "hub_core/live/view.html",
    "hub_core/agg/view.html",
    "hub_core/gold_pairs/view.html",
    "hub_core/hidden_energy/view.html",

    # 2. 精锐独立量化推演战区
    "hub_engine/classic_overview/view.html",
    "hub_engine/datasource/view.html",
    "hub_engine/gold_pick2/view.html",
    "hub_engine/jingle/view.html",
    "hub_engine/sixteen/view.html",
    "hub_engine/suppression/view.html",
    "hub_engine/psychological_game/view.html",
    "hub_engine/point_omission/view.html",
    "hub_engine/genetic/view.html",
    "hub_engine/linear_algebra/view.html",
    "hub_engine/random_forest/view.html",
    "hub_engine/error_correction/view.html",
    "hub_engine/markov_line/view.html",
    "hub_engine/spear_shield/view.html",
    "hub_engine/point_road/view.html",

    # 3. 复盘审计与实战对账
    "hub_review/master_review/view.html",
    "hub_review/hit_leaderboard/view.html",
    "hub_review/fdr/view.html",
    "hub_review/daily_ledger/view.html",
    "hub_review/paper_trading/view.html",
    "hub_review/env_regime/view.html",
    "hub_review/reports_browser/view.html",
    "hub_review/datasource_review/view.html",
    "hub_review/sixteen_review/view.html",

    # 4. 底层数据中心
    "hub_data/draw_trend/view.html",
    "hub_data/datasource_matrix/view.html",
    "hub_data/matrix_80/view.html",
    "hub_data/tail_entropy/view.html",  # 012路账本合页（matrix_80 内 tab 跳转）
    "hub_data/history_table/view.html",
    "hub_data/sixteen_matrix/view.html",

    # 5. 系统运维与录入
    "hub_ops/theme_gallery/view.html",
    "hub_ops/points_input/view.html",
    "hub_ops/tri_high_input/view.html",
    "hub_ops/live_terminal/view.html",

    # 退役辅助 (仍组装进 index，侧边栏不展示)
    "_retired/aux_lstm/view.html",
]


def build_index_html():
    t0 = time.time()
    header_file = os.path.join(LAYOUT_DIR, "header.html")
    modals_file = os.path.join(MODULES_DIR, "shared", "common_modals.html")
    index_out = os.path.join(STATIC_DIR, "index.html")

    if not os.path.exists(header_file):
        print(f"⚠️ 找不到头部布局文件: {header_file}")
        return False

    with open(header_file, "r", encoding="utf-8") as f:
        header_content = f.read()

    views_content = []
    included_count = 0
    for vname in ORDERED_VIEWS:
        vpath = os.path.join(MODULES_DIR, vname.replace("/", os.sep))
        if os.path.exists(vpath):
            with open(vpath, "r", encoding="utf-8") as f:
                c = f.read().strip()
                if c:
                    views_content.append(f"\n<!-- ═══ SUBVIEW: {vname} ═══ -->\n" + c)
                    included_count += 1
        else:
            print(f"⚠️ 缺失子视图文件: {vname}")

    modals_content = ""
    if os.path.exists(modals_file):
        with open(modals_file, "r", encoding="utf-8") as f:
            modals_content = f.read()

    v_tag = time.strftime("%Y%m%d_%H%M%S")
    # 同步刷新主题 CSS 缓存戳，避免角标等样式改完仍吃旧缓存
    header_content = re.sub(
        r'(cyber_theme\.css\?v=)[^"\']+',
        rf'\g<1>{v_tag}',
        header_content,
        count=1,
    )

    footer_content = f"""
    </main>
  </div>

{modals_content}

  <!-- Vue App Logic: registry → page mixins → shell -->
  <script src="/static/js/k8_pages.js?v={v_tag}"></script>
  <script src="/static/js/menu_registry.js?v={v_tag}"></script>
  <script src="/static/js/pages/jingle.js?v={v_tag}"></script>
  <script src="/static/js/pages/data_hub.js?v={v_tag}"></script>
  <script src="/static/js/pages/ops.js?v={v_tag}"></script>
  <script src="/static/js/pages/retired.js?v={v_tag}"></script>
  <script src="/static/js/pages/suppression.js?v={v_tag}"></script>
  <script src="/static/js/pages/point_omission.js?v={v_tag}"></script>
  <script src="/static/js/pages/gold_pick2.js?v={v_tag}"></script>
  <script src="/static/js/pages/aggregation.js?v={v_tag}"></script>
  <script src="/static/js/pages/sixteen.js?v={v_tag}"></script>
  <script src="/static/js/pages/cockpit_live.js?v={v_tag}"></script>
  <script src="/static/js/pages/datasource.js?v={v_tag}"></script>
  <script src="/static/js/pages/reviews_audit.js?v={v_tag}"></script>
  <script src="/static/js/pages/unified_brain.js?v={v_tag}"></script>
  <script src="/static/js/pages/psychological_game.js?v={v_tag}"></script>
  <script src="/static/js/pages/linear_algebra.js?v={v_tag}"></script>
  <script src="/static/js/pages/random_forest.js?v={v_tag}"></script>
  <script src="/static/js/pages/error_correction.js?v={v_tag}"></script>
  <script src="/static/js/pages/genetic.js?v={v_tag}"></script>
  <script src="/static/js/pages/markov_line.js?v={v_tag}"></script>
  <script src="/static/js/pages/dtw.js?v={v_tag}"></script>
  <script src="/static/js/pages/transformer.js?v={v_tag}"></script>
  <script src="/static/js/pages/matrix_profile.js?v={v_tag}"></script>
  <script src="/static/js/pages/tda.js?v={v_tag}"></script>
  <script src="/static/js/app.js?v={v_tag}"></script>
  <!-- AI 智能操盘大脑中继助手 -->
  <script src="/static/js/ai_assistant.js?v={v_tag}"></script>
</body>
</html>
"""

    full_html = header_content + "\n" + "\n".join(views_content) + "\n" + footer_content

    with open(index_out, "w", encoding="utf-8") as f:
        f.write(full_html)

    lines = full_html.count("\n") + 1
    size_kb = len(full_html.encode("utf-8")) / 1024.0
    cost_ms = (time.time() - t0) * 1000.0

    print(f"🚀 Web 视图组装完成: 包含 {included_count} 个模块化视图, 总行数 {lines} 行, 体积 {size_kb:.1f} KB (耗时 {cost_ms:.1f}ms)")
    return True


if __name__ == "__main__":
    build_index_html()
