# -*- coding: utf-8 -*-
"""
三高手账的备份轮转与缩水自愈回归测试

守护的规则（对应真实事故）：
  1. 手账被外部覆盖成只剩几期时，必须能自动发现并从备份重建；
  2. 重建以「备份 ∪ 当前」合并，同期以当前为准 —— 不能为了恢复历史而丢掉刚录入的那期；
  3. 坏文件必须另存留证，不能直接丢弃；
  4. 备份要轮转，不能无限增长；
  5. 手账完整时不得误报为损坏、不得改动文件。

背景：点位台账 daily_points.txt 曾被外部手写覆盖两次、331 期历史被一次性冲掉；
三高手账同一时期也从 17+ 期掉到 4 期，全程无人发现 —— 因为所有读取方都是
「没有就跳过」，故障完全静默。本测试守住这条防线。
"""
import json
import os
import sys
import tempfile
import shutil
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.modules.tri_high import tri_high_engine as th  # noqa: E402


def _rec(period: int) -> dict:
    return {
        "period": str(period),
        "date": "2026-11-12",
        "repeat_high": [49, 60, 68],
        "edge_high_left": [12, 35, 33, 48],
        "edge_high_right": [61, 15, 50, 52],
        "cold_high": [19, 3, 59, 55, 65],
    }


def _write(path: str, periods) -> None:
    records = [_rec(p) for p in periods]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"records": records}, f, ensure_ascii=False)


def _read_periods(path: str):
    with open(path, encoding="utf-8") as f:
        return [r["period"] for r in json.load(f)["records"]]


class TestTriHighRepair(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bdir = os.path.join(self.tmp, "bak")
        os.makedirs(self.bdir)
        self.target = os.path.join(self.tmp, "tri_high_points.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _backup(self, periods, name="tri_high_points_20261112_120000.bak"):
        path = os.path.join(self.bdir, name)
        _write(path, periods)
        return path

    def test_repairs_when_shrunk(self):
        self._backup(range(2026200, 2026300))      # 备份 100 期
        _write(self.target, [2026299, 2026300])    # 当前只剩 2 期

        res = th.repair_tri_high_file(self.target, self.bdir)

        self.assertEqual(res["status"], "repaired")
        self.assertEqual(res["before_records"], 2)
        self.assertEqual(res["after_records"], 101)
        self.assertEqual(len(_read_periods(self.target)), 101)

    def test_keeps_newly_entered_record(self):
        """同期以当前为准：不能为了恢复历史而丢掉刚录入的值。"""
        self._backup(range(2026200, 2026300))
        newest = _rec(2026300)
        newest["repeat_high"] = [1, 2, 3]           # 今天刚录的新值
        with open(self.target, "w", encoding="utf-8") as f:
            json.dump({"records": [newest]}, f, ensure_ascii=False)

        th.repair_tri_high_file(self.target, self.bdir)

        with open(self.target, encoding="utf-8") as f:
            recs = {r["period"]: r for r in json.load(f)["records"]}
        self.assertEqual(recs["2026300"]["repeat_high"], [1, 2, 3])

    def test_preserves_broken_file_as_evidence(self):
        self._backup(range(2026200, 2026300))
        _write(self.target, [2026299])

        res = th.repair_tri_high_file(self.target, self.bdir)

        self.assertTrue(res["evidence"], "必须留证坏文件")
        self.assertTrue(os.path.exists(res["evidence"]))

    def test_no_change_when_complete(self):
        self._backup(range(2026200, 2026300))
        _write(self.target, range(2026200, 2026301))   # 当前更全

        before = open(self.target, encoding="utf-8").read()
        res = th.repair_tri_high_file(self.target, self.bdir)

        self.assertEqual(res["status"], "ok")
        self.assertEqual(open(self.target, encoding="utf-8").read(), before, "完整时不得改动文件")

    def test_idempotent(self):
        self._backup(range(2026200, 2026300))
        _write(self.target, [2026299])
        th.repair_tri_high_file(self.target, self.bdir)
        self.assertEqual(th.repair_tri_high_file(self.target, self.bdir)["status"], "ok")

    def test_skips_without_backup(self):
        _write(self.target, [2026299])
        self.assertEqual(th.repair_tri_high_file(self.target, self.bdir)["status"], "skipped")

    def test_skips_without_backup_dir(self):
        _write(self.target, [2026299])
        res = th.repair_tri_high_file(self.target, os.path.join(self.tmp, "nope"))
        self.assertEqual(res["status"], "skipped")


class TestTriHighBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = os.path.join(self.tmp, "tri_high_points.json")
        _write(self.target, [2026300])
        self._orig_dir = th.TRI_HIGH_BACKUP_DIR
        self._orig_keep = th.TRI_HIGH_BACKUP_KEEP
        th.TRI_HIGH_BACKUP_DIR = os.path.join(self.tmp, "bak")

    def tearDown(self):
        th.TRI_HIGH_BACKUP_DIR = self._orig_dir
        th.TRI_HIGH_BACKUP_KEEP = self._orig_keep
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_backup(self):
        path = th.backup_tri_high_file(self.target)
        self.assertTrue(path and os.path.exists(path))
        self.assertEqual(_read_periods(path), ["2026300"])

    def test_rotation_keeps_limit(self):
        th.TRI_HIGH_BACKUP_KEEP = 3
        os.makedirs(th.TRI_HIGH_BACKUP_DIR, exist_ok=True)
        for i in range(6):                      # 造 6 份旧备份
            _write(os.path.join(th.TRI_HIGH_BACKUP_DIR,
                                f"tri_high_points_2026110{i}_120000.bak"), [2026300])

        th.backup_tri_high_file(self.target)    # 触发轮转

        baks = [n for n in os.listdir(th.TRI_HIGH_BACKUP_DIR)
                if th._TRI_HIGH_BACKUP_RE.match(n)]
        self.assertLessEqual(len(baks), 3, f"轮转失效，仍有 {len(baks)} 份备份")


if __name__ == "__main__":
    unittest.main(verbosity=2)