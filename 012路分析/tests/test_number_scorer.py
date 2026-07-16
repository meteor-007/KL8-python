import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.model_config import ModelConfig
from core.data_loader import KL8Draw
from core.number_scorer import NumberScorer


def _fake_draws(n=40):
    out = []
    for i in range(n):
        # rotate which numbers appear so omit/freq vary
        base = (i % 60) + 1
        nums = sorted({((base + j - 1) % 80) + 1 for j in range(20)})
        while len(nums) < 20:
            nums.append(len(nums) + 1)
        nums = sorted(nums)[:20]
        road = (7, 7, 6) if i % 2 == 0 else (6, 7, 7)
        out.append(KL8Draw("2020-01-01", f"{2020000 + i}", nums, road))
    return out


def test_layers_disjoint_and_counts():
    cfg = ModelConfig()
    result = NumberScorer(_fake_draws(), cfg).score(predicted_road=(7, 7, 6))
    assert len(result["rec_high"]) == 8
    assert len(result["rec_mid"]) == 8
    assert len(result["rec_low"]) == 6
    assert len(result["kill_high"]) == 8
    assert len(result["kill_mid"]) == 7
    rec = set(result["rec_high"] + result["rec_mid"] + result["rec_low"])
    kill = set(result["kill_high"] + result["kill_mid"])
    assert rec.isdisjoint(kill)
    assert len(rec) == 22
    assert len(kill) == 15
