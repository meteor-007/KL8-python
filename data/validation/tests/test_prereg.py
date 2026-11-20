# -*- coding: utf-8 -*-
"""预注册机制测试：冻结、锁定、防补锁、到期前不输出正式 p。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kl8.prereg import PreregStore


class StubCfg:
    def __init__(self, root: Path):
        self.state_dir = root / "state"
        self.shared_history_file = root / "history.txt"
        self.shared_points_file = root / "points.txt"
        self.raw = {"alpha": 0.05, "thresholds": {"alpha": 0.05}}

    def as_dict(self):
        return self.raw


def _draw_line(period: int, nums: list[int], date: str = "2026-01-01") -> str:
    return (f"date:{date},period:{period:07d},numbers:"
            + "-".join(f"{n:02d}" for n in nums))


def _points_line(period: int, nums: list[int], date: str = "2026-01-01") -> str:
    return (f"date:{date},period:{period:07d},points:"
            + " ".join(f"{n:02d}" for n in nums))


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture()
def store(tmp_path: Path) -> PreregStore:
    cfg = StubCfg(tmp_path)
    draws = [(2026001, list(range(1, 21))),
             (2026002, list(range(2, 22))),
             (2026003, list(range(3, 23)))]
    _write(cfg.shared_history_file,
           [_draw_line(p, nums, f"2026-01-0{i+1}") for i, (p, nums) in enumerate(draws)])
    _write(cfg.shared_points_file,
           [_points_line(p, list(range(1, 21))) for p, _ in draws])
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    return PreregStore(cfg, root=tmp_path, code_root=tmp_path)


def _prediction(period: int, core: list[int]) -> dict:
    return {"model": "main", "period": period, "date": "2026-01-04",
            "core": core, "defensive": [6, 7],
            "pool": list(range(1, 41)), "expanded": list(range(1, 41)),
            "generated_at": "2026-01-04T10:00:00"}


def test_create_freezes_prefix(store: PreregStore):
    reg = store.create("T-001", "main", 3, 2026004, hypothesis="test", min_periods=1)
    assert reg["status"] == "active"
    assert reg["frozen"]["data_cutoff_period"] == 2026003
    assert reg["mde_lift_at_plan"] > 0
    assert "environment" in reg["frozen"]
    assert store.active_path.exists()


def test_lock_and_idempotent(store: PreregStore):
    store.create("T-002", "main", 3, 2026004, min_periods=1)
    pred = _prediction(2026004, [1, 2, 3, 4, 5])
    (store.state / "last_prediction_main.json").write_text(
        json.dumps(pred), encoding="utf-8")
    first = store.lock("main")
    assert first["status"] == "locked"
    second = store.lock("main")
    assert second["status"] == "already_locked"
    pred["core"] = [11, 12, 13, 14, 15]
    (store.state / "last_prediction_main.json").write_text(
        json.dumps(pred), encoding="utf-8")
    with pytest.raises(ValueError):
        store.lock("main")


def test_refuse_lock_after_draw(store: PreregStore):
    store.create("T-003", "main", 3, 2026004, min_periods=1)
    pred = _prediction(2026004, [1, 2, 3, 4, 5])
    (store.state / "last_prediction_main.json").write_text(
        json.dumps(pred), encoding="utf-8")
    # 目标期开奖入档后再锁定 → 必须拒绝
    with open(store.history, "a", encoding="utf-8") as f:
        f.write(_draw_line(2026004, list(range(1, 21))) + "\n")
    with pytest.raises(ValueError, match="已开奖"):
        store.lock("main")


def test_config_change_invalidates(store: PreregStore):
    store.create("T-004", "main", 3, 2026004, min_periods=1)
    pred = _prediction(2026004, [1, 2, 3, 4, 5])
    (store.state / "last_prediction_main.json").write_text(
        json.dumps(pred), encoding="utf-8")
    store.cfg.raw["alpha"] = 0.10
    with pytest.raises(ValueError, match="失效"):
        store.lock("main")
    assert store.load_active()["status"] == "invalidated"


def test_evaluate_final_only(store: PreregStore):
    store.create("T-005", "main", 3, 2026004, min_periods=1)
    cores = {2026004: [1, 2, 3, 4, 5],
             2026005: [11, 12, 13, 14, 15],
             2026006: [21, 22, 23, 24, 25]}
    draws = {2026004: list(range(1, 21)),
             2026005: list(range(11, 31)),
             2026006: list(range(21, 41))}
    for p in cores:
        pred = _prediction(p, cores[p])
        (store.state / "last_prediction_main.json").write_text(
            json.dumps(pred), encoding="utf-8")
        store.lock("main")
        with open(store.history, "a", encoding="utf-8") as f:
            f.write(_draw_line(p, draws[p]) + "\n")

    final = store.evaluate()
    assert final["ready"] is True
    assert final["T"] == 3
    assert final["system"].mean_hits == 5.0
    assert final["same_pool"].T == 3
    text = store.render_evaluation(final)
    assert "预注册" in text and "不构成投注建议" in text


def test_evaluate_not_ready(store: PreregStore):
    store.create("T-006", "main", 30, 2026004, min_periods=1)
    pred = _prediction(2026004, [1, 2, 3, 4, 5])
    (store.state / "last_prediction_main.json").write_text(
        json.dumps(pred), encoding="utf-8")
    store.lock("main")
    with open(store.history, "a", encoding="utf-8") as f:
        f.write(_draw_line(2026004, list(range(1, 21))) + "\n")
    res = store.evaluate()
    assert res["ready"] is False
    assert "尚未达到计划期数" in store.render_evaluation(res)
    exploratory = store.evaluate(exploratory=True)
    assert exploratory["exploratory"] is True
    assert "探索性" in store.render_evaluation(exploratory)

def test_requirements_change_invalidates(store: PreregStore):
    lock = store.code_root / "requirements.lock"
    lock.write_text("numpy==1.0" + chr(10), encoding="utf-8")
    store.create("T-007", "main", 3, 2026004, min_periods=1)
    pred = _prediction(2026004, [1, 2, 3, 4, 5])
    (store.state / "last_prediction_main.json").write_text(
        json.dumps(pred), encoding="utf-8")
    lock.write_text("numpy==2.0" + chr(10), encoding="utf-8")
    with pytest.raises(ValueError, match="失效"):
        store.lock("main")
    assert store.load_active()["status"] == "invalidated"
