# -*- coding: utf-8 -*-
"""第二轮迁移: 清除 views/*.html 中"整组编造号码"的数组兜底 与 文案过度宣称。

第一轮 (_fix_fabricated_fallbacks.py) 处理了标量兜底 (|| 47 / || 24 ...)。
本轮处理两类:
  1. 数组兜底 `|| [35, 10, 74, 20, 44]` —— 缺数据时整组假号码渲染成一排号码球,
     比标量更危险 (看起来就像一组完整推荐)。
  2. 文案过度宣称 —— "Lift>1.4x 强信标"、"128万候选组合全量回测"、"FDR-BH 免疫"、
     "只认近30期实测胜率高的金牌裁判" 等无出处或与评估宪法冲突的话术。
"""
import io
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = os.path.join(ROOT, "frontend", "static", "views")

# 1) 数组兜底: || [12, 34, 56]  ->  || []
ARRAY_NUM_FALLBACK = re.compile(r"\|\|\s*\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
# 2) 上面数组后面的字符串兜底: .join(', ') || '35, 10'  ->  || '--'
JOIN_STR_FALLBACK = re.compile(r"(\.join\('[^']*'\))\s*\|\|\s*'[\d,\s]+'")

# 3) 文案过度宣称 (逐条精确匹配)
PROSE = [
    ("cockpit_funnel.html",
     "<span>⬇️ 提取 Lift > 1.4x 金牌引擎共识金胆与黄金连体婴选2 ⬇️</span>",
     "<span>⬇️ 提取具备票权引擎的加权共识金胆与黄金连体婴选2 ⬇️</span>"),
    ("cockpit_funnel.html",
     "{{ funnelSummary?.level3_supreme?.desc || '只由 Lift>1.4x 强引擎背书的终极出击组合' }}",
     "{{ funnelSummary?.level3_supreme?.desc || '只由具备票权 (module_gate) 的引擎加权背书的终极出击组合' }}"),
    ("cockpit_modules_overview.html",
     '<span class="cyber-badge cyber-badge-amber font-mono text-[10px]">Lift&gt;1.4x强信标</span>',
     '<span class="cyber-badge cyber-badge-amber font-mono text-[10px]">module_gate 票权加权</span>'),
    ("cockpit_modules_overview.html",
     '<span class="cyber-badge cyber-badge-cyan font-mono text-[10px]">25➔18➔5➔2</span>',
     '<span class="cyber-badge cyber-badge-cyan font-mono text-[10px]">三级漏斗清洗</span>'),
    ("cockpit_meta_gold.html",
     "纯粹强信标驱动（大白话：只认近 30 期实测胜率高的金牌裁判投票，不搞大锅饭平庸平均）",
     "票权加权驱动（大白话：只认在 module_gate 注册表里具备票权的金牌裁判投票，不搞大锅饭平庸平均。票权阈值与样本门槛见注册表）"),
    ("cockpit_agg.html",
     '<div class="text-[10px] text-slate-500">近30期诚实评估 (基线1.25)</div>',
     '<div class="text-[10px] text-slate-500">诚实评估 (Lift=1.00 即随机基线)</div>'),
    ("cockpit_jingle.html",
     "🛡️ 严苛统计审计：经 128 万候选组合全量回测，实施 FDR-BH (α≤0.05) 错误发现率免疫与样本外 (OOF) 双重检验淘汰提纯。",
     "🛡️ 统计审计：口诀均在样本外 (OOF) 口径下评估，并纳入全系统统一的多重检验 (BH-FDR, α≤0.05) 校正；校正后仍不显著者不作优势宣称。"),
]


def main():
    n_arr = n_join = n_prose = 0
    touched = {}

    for fname in sorted(os.listdir(VIEWS)):
        if not fname.endswith(".html"):
            continue
        path = os.path.join(VIEWS, fname)
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
        orig = content

        content, c1 = ARRAY_NUM_FALLBACK.subn("|| []", content)
        content, c2 = JOIN_STR_FALLBACK.subn(r"\1 || '--'", content)

        if c1 or c2:
            n_arr += c1
            n_join += c2
            touched[fname] = touched.get(fname, 0) + c1 + c2
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(content)

    failures = []
    for fname, old, new in PROSE:
        path = os.path.join(VIEWS, fname)
        if not os.path.exists(path):
            failures.append((fname, old, "文件不存在"))
            continue
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
        cnt = content.count(old)
        if cnt != 1:
            failures.append((fname, old, f"命中 {cnt} 次 (应为 1)"))
            continue
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content.replace(old, new))
        n_prose += 1
        touched[fname] = touched.get(fname, 0) + 1

    print(f"✅ 数组兜底 -> [] : {n_arr} 处")
    print(f"✅ 字符串兜底 -> '--': {n_join} 处")
    print(f"✅ 文案去宣称: {n_prose}/{len(PROSE)} 处")
    for fname, c in sorted(touched.items()):
        print(f"   {fname}: {c} 处")
    if failures:
        print(f"\n❌ {len(failures)} 处文案未替换:")
        for fname, old, why in failures:
            print(f"   [{fname}] {why}: {old[:90]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
