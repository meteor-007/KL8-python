# -*- coding: utf-8 -*-
"""第三轮: cockpit_datasource.html 硬编码"性能宣称"修正。

背景: 该页把 4 个性能数字 (76.5% / 25.5% / 75.9% / 1.28码) 硬编码在模板里当作实测战绩展示。
经查 backend/core/datasource_predictor.py 的 2026-09-10 全历史审计 (153 有效期,
报告见 outputs/ds2_deep_analysis/数据源2深度分析报告.md), 真实实测值为:

  做多侧 (基线 25%):  蓄力反弹 26.26% (Lift 1.050, p=0.429)
                      B1连庄  23.85% (Lift 0.954, p=0.386)
                      B0静默  25.97% (Lift 1.039, p=0.154)
                      跨规则共识 26.49% (Lift 1.059, p=0.502)
  做空侧 (基线 75%):   D2外部  回避 75.32% (Lift 0.987, p=0.707)
                      B2杀熟  回避 75.99% (Lift 0.960, p=0.471)
                      深度过热 回避 78.16% (Lift 0.874, p=0.247)

即: 页面宣称的 76.5% 回避 与 75.9% 排雷 都略高于 75% 随机基线, 但在 BH-FDR 校正后
【无一显著】, 且 D2外部与B2杀熟的 Lift 都 <1.00 (方向是负的)。把 Lift<1 的
结果标成"S级/高回避"是误导。本脚本改为: 引用审计实测值 + 明示不显著, 并加退役横幅
(做多侧 datasource_1x2_hot 已于 2026-09-10 退役)。
"""
import io
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "frontend", "static", "views", "cockpit_datasource.html")

R = [
    # 顶部徽标: 去掉裸数字宣称
    ("微观状态跃迁 · 跨规则共识 · D2高回避排雷 (76.5%命中)",
     "微观状态跃迁 · 跨规则共识 · D2高回避排雷"),

    # KPI 卡 2: 做多期望
    ('<div class="text-xl font-bold font-mono text-emerald-400 mt-0.5">25.5% 命中率</div>\n'
     '              <div class="text-[10px] text-emerald-500 font-mono mt-0.5">均命中 1.28 码 / Top 5</div>',
     '<div class="text-xl font-bold font-mono text-emerald-400 mt-0.5">23.9%~26.5%</div>\n'
     '              <div class="text-[10px] text-slate-500 font-mono mt-0.5">审计实测, 4 条做多规则; 随机基线 25%</div>'),

    # KPI 卡 3: D2 外部回避率
    ('<div class="text-xl font-bold font-mono text-cyan-400 mt-0.5">76.5% 高回避</div>',
     '<div class="text-xl font-bold font-mono text-cyan-400 mt-0.5">75.3% 高回避</div>'),

    # KPI 卡 4: 规则杀号
    ('<div class="text-xl font-bold font-mono text-rose-400 mt-0.5">75.9% 排雷</div>',
     '<div class="text-xl font-bold font-mono text-rose-400 mt-0.5">76.0% 排雷</div>'),

    # 阵地2 徽标
    ('<span class="text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono font-bold">排除准确率 76.5%</span>',
     '<span class="text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono font-bold">审计实测 ≈75.5% (不显著)</span>'),

    # D2 外部杀号池小字
    ('<span class="text-[10px] text-emerald-400 font-mono">实测回避率 76.5%</span>',
     '<span class="text-[10px] text-slate-400 font-mono">实测回避率 75.3% (Lift 0.99, p=0.71, 不显著)</span>'),

    # "胜率极高" 夸大
    ("统计规律：数据源2开奖点位之外的冷态未激活号码，下一期极少突发开出，是胜率极高的排雷防守池。",
     "统计规律：数据源2开奖点位之外的号码，下一期开出比例略低于随机。2026-09-10 全历史审计实测回避率 "
     "75.32%（随机基线 75%），Lift 0.987、p=0.707 —— 方向对但【不显著】，不能称为“高胜率”。"),

    # 规则防守杀号小字
    ('<span class="text-[10px] font-mono text-slate-400">准确率 75.9%</span>',
     '<span class="text-[10px] font-mono text-slate-400">准确率 76.0% (Lift 0.96, p=0.47, 不显著)</span>'),

    # 阵地3 表头
    ('<span class="text-xs text-slate-400 font-mono">规则做多准确率 25.5% | 规则杀号准确率 75.9%</span>',
     '<span class="text-xs text-slate-400 font-mono">审计实测: 做多 23.9%~26.5% (基线25%) | 杀号回避 ≈75%~78% (基线75%), 全部不显著</span>'),
]

# 退役横幅: 做多侧 (datasource_1x2_hot) 已于 2026-09-10 退役
BANNER_ANCHOR = '<div v-show="activeTab === \'datasource_cockpit\'" class="space-y-6">\n        <!-- 头部概览条 -->'
BANNER = '''<div v-show="activeTab === 'datasource_cockpit'" class="space-y-6">
        <!-- B 类整改: 做多侧模块已退役, 页面必须说真话 -->
        <div class="glass-panel p-4 border-l-4 border-rose-500 text-xs space-y-1">
          <div class="flex items-center gap-2">
            <span class="text-lg">⏹</span>
            <span class="font-bold text-rose-300">做多侧已退役 (2026-09-10)</span>
            <span class="cyber-badge font-mono" style="background: rgba(244,63,94,0.15); color: #fda4af; border: 1px solid rgba(244,63,94,0.4);">爆发 Top5 · 只存档</span>
          </div>
          <p class="text-slate-400 leading-relaxed">
            大白话：本页的<b>做多侧</b>（精选爆发 Top 5 / 跨规则共识金胆 / 黄金连体婴选2）在 module_gate
            注册表里已是 <code>retired</code>，投票权归零，<b>不再进入主推荐</b>。
            2026-09-10 全历史审计（153 有效期，BH-FDR 校正）结论是：做多侧 4 条规则的 Lift 落在
            0.95~1.06，<b class="text-rose-300">无一显著</b>。
          </p>
          <p class="text-slate-500">
            仍然具备票权的是<b>做空侧</b>规则（数据源1×2 高回避杀号池）。下方做多区块保留仅为历史对账，
            页面上的号码是<b>历史存档</b>，不是当前推荐依据。
            审计全文：outputs/ds2_deep_analysis/数据源2深度分析报告.md
          </p>
        </div>

        <!-- 头部概览条 -->'''


def main():
    with io.open(PATH, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    failures = []
    applied = 0
    for old, new in R:
        cnt = content.count(old)
        if cnt != 1:
            failures.append((old[:70], f"命中 {cnt} 次 (应为 1)"))
            continue
        content = content.replace(old, new)
        applied += 1

    # 横幅
    if BANNER_ANCHOR in content:
        content = content.replace(BANNER_ANCHOR, BANNER, 1)
        applied += 1
    else:
        failures.append(("退役横幅锚点", "未找到 <div v-show=\"activeTab === 'datasource_cockpit'\" ...> + 头部概览条 注释"))

    with io.open(PATH, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    print(f"✅ cockpit_datasource.html 已替换 {applied}/{len(R) + 1} 处")
    if failures:
        print(f"\n❌ {len(failures)} 处未替换:")
        for s, why in failures:
            print(f"   {why}: {s}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
