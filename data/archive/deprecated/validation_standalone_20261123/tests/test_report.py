# -*- coding: utf-8 -*-
"""kl8/report.py 测试（§7 报告骨架 / §11.5 合规红线）。

重点：
  1. assert_compliant 必须拦截真实违禁词（§11.5）；
  2. **不得误杀**「不构成投注建议」这类否定式免责表述（刚修复的真实缺陷）
     —— 免责声明本身含"投注"二字，渲染后必须能通过扫描；
  3. 渲染结果包含六章节标题。
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from kl8.contracts import ModuleResult
from kl8.data_io import PointEntry
from kl8.ensemble import DIM_NAMES, FusionResult
from kl8.points import NumberStats
from kl8.report import (DISCLAIMER, FORBIDDEN, SAFE_NEGATIONS, ReportContext,
                        _strength, assert_compliant, conclusion_line,
                        render_markdown, render_stdout, write_report)
from kl8.scoring import Pick52, Selection

CHAPTER_HEADS = (
    "## 〇、输入概览",
    "## 一、N 维评分仪表盘",
    "## 二、本期最值得关注的 Top 5",
    "## 三、宏观趋势",
    "## 四、风险预警与应对",
    "## 五、《趋势简报》决策树",
    "## 六、终极推荐清单",
)


# ── 上下文构造 ────────────────────────────────────────────────

def _health():
    return SimpleNamespace(
        points_count=100, draws_count=110, pairable_count=100, malformed=0,
        dirty=[], points_only=[], duplicate_dates={}, inversions=[],
        points_source="shared/points", draws_source="shared/draws")


def _base_stats(nums):
    return {n: NumberStats(n=n, hit10=2, hit3=1, miss=4, freq_full=25,
                           exp_hit=25.0, std=4.33, z_score=0.1, T=100)
            for n in nums}


def _fusion():
    hv = {d: {n: 0.5 for n in range(1, 81)} for d in DIM_NAMES}
    return FusionResult(method_results={}, h_values=hv,
                        composite={n: 50.0 for n in range(1, 81)},
                        dim_weights={d: 1.0 / 7 for d in DIM_NAMES})


def _ctx(degraded=False, relaxed=False, defensive=(8, 9), extra_results=None,
         staleness="✅ 新鲜（1 天前）"):
    expanded = set(range(1, 41))
    results = {"omission": ModuleResult(
        name="omission", scores={n: 0.5 for n in range(1, 81)},
        metrics={"top_miss": [(20, 12), (19, 9)]})}
    results["omission"].add("macro", "- 遗漏结构：测试叙述块")
    if extra_results:
        results.update(extra_results)
    backtest = SimpleNamespace(T=0, degraded=True, method_tests=None, exp3=None) \
        if degraded else None
    return ReportContext(
        cfg=SimpleNamespace(report=SimpleNamespace(out_dir="output")),
        target=SimpleNamespace(period=2026200, date=date(2026, 1, 1),
                               period_str="2026200"),
        entry=PointEntry(period=2026200, date=date(2026, 1, 1),
                         points=tuple(range(1, 21))),
        dataset=None, health=_health(), staleness=staleness, results=results,
        fusion=_fusion(), selection=Selection(core=[1, 2, 3, 4, 5], relaxed=relaxed),
        picks=Pick52(core=[1, 2, 3, 4, 5], defensive=list(defensive)),
        base_stats=_base_stats(expanded), expanded=expanded,
        generated_at=date(2026, 1, 1), backtest=backtest,
    )


# ── 合规扫描（§11.5）──────────────────────────────────────────

def test_assert_compliant_blocks_forbidden_words():
    for word in ("包号", "稳赚", "倍投", "杀号", "中奖", "单式", "追号", "翻倍"):
        assert word in FORBIDDEN
        with pytest.raises(ValueError):
            assert_compliant(f"本行包含 {word} 字样")


def test_assert_compliant_error_message_lists_hits():
    with pytest.raises(ValueError) as exc:
        assert_compliant("这里有包号和稳赚")
    assert "包号" in str(exc.value) and "稳赚" in str(exc.value)


def test_assert_compliant_allows_negated_disclaimer():
    """不得误杀否定式免责表述（真实缺陷：免责声明含"投注"二字）。"""
    for phrase in SAFE_NEGATIONS:
        assert_compliant(f"本报告{phrase}。")
    # 正式免责声明必须能通过
    assert_compliant(DISCLAIMER)
    assert_compliant("> **免责声明**：" + DISCLAIMER + "\n")
    # 与否定式共存的普通文本
    assert_compliant("本报告不构成任何投注建议，历史统计特征不保证重现。")


def test_assert_compliant_blocks_real_word_even_with_negation():
    """否定式剥离后，正文里仍出现真实违禁词必须拦截。"""
    with pytest.raises(ValueError):
        assert_compliant("不构成任何投注建议，本期稳赚。")
    with pytest.raises(ValueError):
        assert_compliant("非投注建议；可据此包号。")


def test_assert_compliant_clean_text_passes():
    assert_compliant("全部结论均附带显著性检验结果，未达显著的方法已在文中标注。")
    assert_compliant("")


# ── 渲染 ─────────────────────────────────────────────────────

def test_render_markdown_contains_six_chapter_headings():
    md = render_markdown(_ctx())
    for head in CHAPTER_HEADS:
        assert head in md
    # 除六个正文章节外的输概览与附录
    assert "## 附录 A、回测" in md
    assert md.startswith("# 快乐8 点位+遗漏号分析 · 日报 2026-01-01")


def test_render_markdown_is_compliant_and_carries_disclaimer():
    md = render_markdown(_ctx())
    # 含否定式免责声明且未被误杀
    assert "不构成任何投注建议" in md
    assert "免责声明" in md
    assert_compliant(md)


def test_render_markdown_blocks_forbidden_narrative():
    """模块 narrative 中出现违禁词 → 渲染即抛错，报告不落盘。"""
    bad = ModuleResult(name="heatmap", scores={n: 0.5 for n in range(1, 81)})
    bad.add("macro", "- 本期可考虑 包号 操作")
    with pytest.raises(ValueError):
        render_markdown(_ctx(extra_results={"heatmap": bad}))


def test_render_markdown_sections_content():
    md = render_markdown(_ctx())
    assert "### 1.1 Top 5 维度分解" in md
    assert "### 1.2 方法权重" in md
    assert "### 3.1 场域能量" in md
    assert "### 3.2 维度覆盖面" in md
    assert "### 6.1 五码核心" in md
    assert "### 6.2 两码备防" in md
    assert "### 6.3 浓缩" in md
    assert "08 09" in md                       # 两码备防号码
    assert "遗漏结构：测试叙述块" in md          # narrative 路由到宏观趋势
    assert "一致性" not in md                   # 不产出第三份清单


def test_render_markdown_marks_relaxed_selection():
    md = render_markdown(_ctx(relaxed=True))
    assert "多样性约束曾被放宽" in md


def test_render_stdout_compliant_and_shows_core():
    out = render_stdout(_ctx())
    assert "五码核心：01 02 03 04 05" in out
    assert "两码备防：08 09" in out
    assert_compliant(out)


def test_conclusion_line_degraded_branch():
    ctx = _ctx(degraded=True)
    line = conclusion_line(ctx)
    assert "无统计差异" in line
    md = render_markdown(ctx)
    assert "降级状态" in md
    assert "## 六、终极推荐清单" in md


def test_conclusion_line_normal_and_empty_pool():
    line = conclusion_line(_ctx())
    assert "一句话结论" in line
    empty = _ctx()
    empty.selection = Selection(core=[])
    assert "候选池不足" in conclusion_line(empty)


def test_write_report_writes_utf8_crlf(tmp_path):
    ctx = _ctx()
    path = write_report(ctx, tmp_path)
    assert path.exists()
    assert path.parent == tmp_path / "2026-01-01"
    assert path.name == "daily_report.md"
    raw = path.read_bytes()
    # 文件按 CRLF 落盘，内容与 render_markdown 一致（除换行符）
    assert raw.decode("utf-8").replace("\r\n", "\n") == render_markdown(ctx)
    assert b"\r\n" in raw                       # 显式 CRLF
    assert b"\r\r\n" not in raw
    assert ctx.target.period_str in path.read_text(encoding="utf-8")


def test_strength_thresholds():
    assert _strength(0.70) == "强" and _strength(1.0) == "强"
    assert _strength(0.40) == "中" and _strength(0.69) == "中"
    assert _strength(0.0) == "弱" and _strength(0.399) == "弱"


def test_disclaimer_and_forbidden_lists_are_populated():
    assert "不构成任何投注建议" in DISCLAIMER
    assert "不构成任何投注建议" in SAFE_NEGATIONS
    assert len(FORBIDDEN) >= 20
    assert len(set(FORBIDDEN)) == len(FORBIDDEN)
