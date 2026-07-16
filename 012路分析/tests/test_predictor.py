import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.model_config import ModelConfig
from core.data_loader import KL8Draw
from core.predictor import RoadPredictor


def _fake_draws(n=50):
    out = []
    for i in range(n):
        road = (7, 7, 6) if i % 2 == 0 else (6, 7, 7)
        out.append(KL8Draw("2020-01-01", f"{2020000 + i}", list(range(1, 21)), road))
    return out


def test_predict_sum_20_no_ml():
    cfg = ModelConfig(use_ml=False)
    pred = RoadPredictor(_fake_draws(80), cfg)
    out = pred.predict()
    assert sum(out["best"]) == 20
    assert len(out["top3"]) == 3


def test_predict_with_ml_or_fallback():
    cfg = ModelConfig(use_ml=True, ml_train_periods=60, lookback_k=5)
    out = RoadPredictor(_fake_draws(100), cfg).predict()
    assert sum(out["best"]) == 20
    assert len(out["top3"]) == 3
