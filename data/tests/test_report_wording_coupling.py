# -*- coding: utf-8 -*-
"""报告措辞与解析器的耦合回归测试

背景（差点踩到的坑）：
`battle_rank_optimizer` 是从「全模块预测明细」的**文本**里按关键词抠号码的：

    if any(k in line for k in ["码：", "Top", "大底", ..., "金胆", ...])

也就是说，报告里改一个称呼，优化器就可能整行抠不到 —— 而且不会报错，
只会静默少几票，最终选1~选10 阵容悄悄变了都没人知道。

本测试守住两件事：
  1. 报告展示区不得再用「金胆 / 必开 / 稳中」这类暗示确定性的措辞；
  2. 优化器的关键词表必须覆盖报告现在使用的称呼（改了文案要同步改关键词）。
"""
import os
import re
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT_SRC = os.path.join(_BACKEND_DIR, "pipeline", "generate_standard_full_report.py")
OPTIMIZER_SRC = os.path.join(_BACKEND_DIR, "modules", "battle_rank_optimizer", "service.py")

# 报告模板正文起点：此行之前是数据抽取逻辑（解析各模块产物文件的正则，
# 那些正则必须继续匹配产物里的旧措辞，不能跟着展示文案一起改）
TEMPLATE_START_MARK = "doc = f\"\"\"# 快乐8"

BANNED_IN_DISPLAY = ("金胆", "必开", "必中", "稳中", "包赚")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestReportWording(unittest.TestCase):
    def test_display_area_has_no_hype_terms(self):
        src = _read(REPORT_SRC)
        idx = src.find(TEMPLATE_START_MARK)
        self.assertGreater(idx, 0, "找不到报告模板起点，测试需随模板结构调整")
        display = src[idx:]
        for term in BANNED_IN_DISPLAY:
            self.assertNotIn(term, display, f"报告展示区仍在用「{term}」这类措辞")

    def test_parser_regexes_untouched(self):
        """产物文件里的旧措辞还在，解析正则必须继续认它们，否则号码直接抽不到。"""
        src = _read(REPORT_SRC)
        idx = src.find(TEMPLATE_START_MARK)
        logic = src[:idx]
        for pattern in ("至尊共识金胆", "核心金胆", "反弹Top3金胆"):
            self.assertIn(pattern, logic, f"解析正则里的「{pattern}」被误改，产物将抽不到号")


class TestOptimizerCoupling(unittest.TestCase):
    def test_keyword_list_covers_current_wording(self):
        """优化器关键词表必须包含报告现在用的称呼。"""
        src = _read(OPTIMIZER_SRC)
        m = re.search(r"any\(k in line for k in \[([^\]]+)\]\)", src)
        self.assertIsNotNone(m, "找不到关键词匹配语句，测试需随实现调整")
        keywords = re.findall(r"\"([^\"]+)\"", m.group(1))
        self.assertIn("首选号", keywords,
                      "报告已改用「首选号」，优化器关键词表没同步 —— 会静默丢票")
        # 旧报告文件仍在磁盘上，保留旧关键词以便回看历史期
        self.assertIn("金胆", keywords, "旧关键词应保留，兼容历史报告")

    def test_keywords_readable(self):
        src = _read(OPTIMIZER_SRC)
        m = re.search(r"any\(k in line for k in \[([^\]]+)\]\)", src)
        keywords = re.findall(r"\"([^\"]+)\"", m.group(1))
        self.assertGreaterEqual(len(keywords), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)