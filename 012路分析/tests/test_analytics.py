import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.data_loader import KL8Draw
from core.distribution import analyze_distribution
from core.transition import TransitionModel
from core.association import analyze_association


def _fake_draws(n=50):
    out = []
    for i in range(n):
        road = (7, 7, 6) if i % 2 == 0 else (6, 7, 7)
        out.append(KL8Draw("2020-01-01", f"{2020000 + i}", list(range(1, 21)), road))
    return out


def test_distribution_keys():
    r = analyze_distribution(_fake_draws(), window=20, expected=(6.5, 6.75, 6.75))
    assert "mean_all" in r and "top_patterns" in r and "hot_cold" in r


def test_markov_probs():
    m = TransitionModel(_fake_draws())
    dist = m.next_distribution((7, 7, 6))
    assert abs(sum(dist.values()) - 1.0) < 1e-6


def test_association():
    r = analyze_association(_fake_draws(), expected=(6.5, 6.75, 6.75))
    assert "streaks" in r
