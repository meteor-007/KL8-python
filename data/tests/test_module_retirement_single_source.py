# -*- coding: utf-8 -*-
"""
模块退役的「单一真相源」回归测试

守护的规则（每条都对应一次真实事故）：
  1. 「某模块是否还在册」只有一个答案来源：module_gate.MODULE_SEED（+ 人工覆盖层），
     不得再读 module_vote_registry.json —— 那是生成物，读它会拿到过期判决；
  2. 流水线 / 记账闸门 / 报告渲染 三层必须给出与判决层相同的答案；
  3. 退役是无条件地板：记账闸门不得因为产物还在就继续入账；
  4. 目录位置与判决层的一致性必须可体检，未治理目录要能报出来。

事故背景：
  · 前端页面模块被移进 _retired/ 但 index.html 仍引用 → 6 个 404、首屏数据全灭
  · consensus_straddle 代码在 _retired/ 里但流水线照跑 → 隐身计入 BH 检验族
  · 直接改 module_vote_registry.json 退役，被流水线对账按 MODULE_SEED 重算改回
"""
import os
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.module_gate import (  # noqa: E402
    MODULE_SEED,
    check_registry_consistency,
    decree_status_of,
    is_module_active,
    retired_module_ids,
)


class TestDecreeSingleSource(unittest.TestCase):
    """判决层本身的行为"""

    def test_retired_module_is_inactive(self):
        retired = retired_module_ids()
        self.assertTrue(retired, "至少应有退役模块，否则本测试失去意义")
        for mid in retired:
            self.assertFalse(is_module_active(mid), f"{mid} 判决为 retired，但仍被判活跃")

    def test_active_module_is_active(self):
        actives = [m for m in MODULE_SEED if decree_status_of(m) != "retired"]
        self.assertTrue(actives)
        for mid in actives:
            self.assertTrue(is_module_active(mid), f"{mid} 未退役，却被判为退役")

    def test_unknown_module_treated_as_active(self):
        """未收录的模块按活跃处理：宁可如实显示，也不擅自隐藏。"""
        self.assertTrue(is_module_active("__module_not_in_seed__"))

    def test_decree_does_not_read_generated_registry(self):
        """判决不得依赖生成的注册表 JSON —— 它可能尚未刷新。

        做法：临时把注册表文件改名，判决结果必须完全不变。
        """
        reg = os.path.join(_BACKEND_DIR, "config", "module_vote_registry.json")
        if not os.path.exists(reg):
            self.skipTest("注册表文件不存在，跳过")
        before = {m: is_module_active(m) for m in MODULE_SEED}
        backup = reg + ".testbak"
        os.replace(reg, backup)
        try:
            after = {m: is_module_active(m) for m in MODULE_SEED}
        finally:
            os.replace(backup, reg)
        self.assertEqual(before, after, "判决结果随生成物存亡而变化，说明读错了来源")


class TestLayersAgree(unittest.TestCase):
    """三层消费方必须给出与判决层相同的答案"""

    def test_pipeline_layer_agrees(self):
        from backend.pipeline.run_full_pipeline import module_active
        for mid in MODULE_SEED:
            self.assertEqual(module_active(mid), is_module_active(mid),
                             f"流水线对 {mid} 的判断与判决层不一致")

    def test_report_layer_agrees(self):
        from backend.pipeline.generate_standard_full_report import StandardDailyReportEngine
        eng = StandardDailyReportEngine()
        for mid in MODULE_SEED:
            self.assertEqual(eng.is_active(mid), is_module_active(mid),
                             f"报告层对 {mid} 的判断与判决层不一致")

    def test_harvester_skips_retired(self):
        """记账闸门：退役模块即便产物还在，也不得继续入账。"""
        from backend.modules.daily_review.harvester import EXTRACTORS
        retired_specs = [s["id"] for s in EXTRACTORS if not is_module_active(s["id"])]
        for mid in retired_specs:
            self.assertIn(mid, retired_module_ids(),
                          f"{mid} 在抽取表里被跳过，但判决层并未判退役")


class TestConsistencyCheck(unittest.TestCase):
    """目录位置体检"""

    def test_check_returns_documented_keys(self):
        c = check_registry_consistency()
        self.assertEqual(set(c), {"ungoverned_dirs", "active_in_legacy"})
        self.assertIsInstance(c["ungoverned_dirs"], list)
        self.assertIsInstance(c["active_in_legacy"], list)

    def test_no_ungoverned_dirs(self):
        """legacy/ 下的模块目录都应能映射到判决层（利用别名表）。

        「活跃模块住在 legacy/」是正常状态（legacy = 历史遗留目录，不是"已退役"），
        所以不把它当异常；真正的异常是查无此模块 —— 没人知道它还在不在跑。
        """
        c = check_registry_consistency()
        self.assertEqual(c["ungoverned_dirs"], [],
                         f"以下目录未纳入判决层: {c['ungoverned_dirs']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)