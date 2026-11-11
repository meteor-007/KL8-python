# -*- coding: utf-8 -*-
"""第三轮补丁: 处理 _fix_datasource_claims.py 中两处多行替换
(原脚本用 \\n, 而该文件是 CRLF, 故多行字面量未命中)。"""
import io
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "frontend", "static", "views", "cockpit_datasource.html")

NL = "\r\n"

OLD_KPI2 = (
    '<div class="text-xl font-bold font-mono text-emerald-400 mt-0.5">25.5% 命中率</div>' + NL +
    '              <div class="text-[10px] text-emerald-500 font-mono mt-0.5">均命中 1.28 码 / Top 5</div>'
)
NEW_KPI2 = (
    '<div class="text-xl font-bold font-mono text-emerald-400 mt-0.5">23.9%~26.5%</div>' + NL +
    '              <div class="text-[10px] text-slate-500 font-mono mt-0.5">审计实测, 4 条做多规则; 随机基线 25%</div>'
)

ANCHOR = ('<div v-show="activeTab === \'datasource_cockpit\'" class="space-y-6">' + NL +
          '        <!-- 头部概览条 -->')

BANNER = (
    '<div v-show="activeTab === \'datasource_cockpit\'" class="space-y-6">' + NL +
    '        <!-- B 类整改: 做多侧模块已退役, 页面必须说真话 -->' + NL +
    '        <div class="glass-panel p-4 border-l-4 border-rose-500 text-xs space-y-1">' + NL +
    '          <div class="flex items-center gap-2">' + NL +
    '            <span class="text-lg">⏹</span>' + NL +
    '            <span class="font-bold text-rose-300">做多侧已退役 (2026-09-10)</span>' + NL +
    '            <span class="cyber-badge font-mono" style="background: rgba(244,63,94,0.15); color: #fda4af; border: 1px solid rgba(244,63,94,0.4);">爆发 Top5 · 只存档</span>' + NL +
    '          </div>' + NL +
    '          <p class="text-slate-400 leading-relaxed">' + NL +
    '            大白话：本页的<b>做多侧</b>（精选爆发 Top 5 / 跨规则共识金胆 / 黄金连体婴选2）在 module_gate' + NL +
    '            注册表里已是 <code>retired</code>，投票权归零，<b>不再进入主推荐</b>。' + NL +
    '            2026-09-10 全历史审计（153 有效期，BH-FDR 校正）结论是：做多侧 4 条规则的 Lift 落在' + NL +
    '            0.95~1.06，<b class="text-rose-300">无一显著</b>。' + NL +
    '          </p>' + NL +
    '          <p class="text-slate-500">' + NL +
    '            仍然具备票权的是<b>做空侧</b>规则（数据源1×2 高回避杀号池）。下方做多区块保留仅为历史对账，' + NL +
    '            页面上的号码是<b>历史存档</b>，不是当前推荐依据。' + NL +
    '            审计全文：outputs/ds2_deep_analysis/数据源2深度分析报告.md' + NL +
    '          </p>' + NL +
    '        </div>' + NL +
    NL +
    '        <!-- 头部概览条 -->'
)


def main():
    with io.open(PATH, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    failures = []
    for label, old, new in (("KPI卡2 做多期望", OLD_KPI2, NEW_KPI2),
                            ("退役横幅", ANCHOR, BANNER)):
        cnt = content.count(old)
        if cnt != 1:
            failures.append((label, f"命中 {cnt} 次 (应为 1)"))
            continue
        content = content.replace(old, new, 1)

    with io.open(PATH, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    print("✅ 补丁应用完成" if not failures else f"❌ {len(failures)} 处失败")
    for label, why in failures:
        print(f"   [{label}] {why}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
