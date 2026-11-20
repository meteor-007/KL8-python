# -*- coding: utf-8 -*-
"""Exact hit-count distributions, p-values and power for the reported buckets."""
import numpy as np
from scipy import stats
from math import sqrt


def pmf_hits(k, N=80, K=20):
    return stats.hypergeom.pmf(np.arange(0, k + 1), N, K, k)


def convolve(p, T):
    out = np.array([1.0])
    for _ in range(T):
        out = np.convolve(out, p)
    return out


def summarize(name, k, T, obs):
    p = pmf_hits(k)
    dist = convolve(p, T)
    exp = T * k * 0.25
    sd = sqrt(T * k * 0.25 * 0.75 * (80 - k) / 79)
    p_lo = dist[: obs + 1].sum()
    p_hi = dist[obs:].sum()
    w = 1.96
    n = T * k
    ph = obs / n
    den = 1 + w * w / n
    center = (ph + w * w / (2 * n)) / den
    half = w / den * sqrt(ph * (1 - ph) / n + w * w / (4 * n * n))
    # MDE at 80% power, one-sided alpha .05
    mde_hits = (1.6449 + 0.8416) * sd / sqrt(T)
    print(f"{name}: picks={n}, obs={obs}, rate={ph:.3f}, expected={exp:.2f} "
          f"({k*0.25:.0%} per pick), sd={sd:.2f}, z={(obs-exp)/sd:+.2f}")
    print(f"   exact P(X<=obs)={p_lo:.4f}, P(X>=obs)={p_hi:.4f}, "
          f"two-sided={min(1,2*min(p_lo,p_hi)):.4f}")
    print(f"   Wilson 95% CI rate=[{center-half:.3f},{center+half:.3f}]; "
          f"MDE(80% power)= +/-{mde_hits:.2f} hits = "
          f"{mde_hits/ (T*k*0.25) *100:.1f}% relative")


print("=== Last 10 periods (T=10), from hitrate_evaluation.md ===")
summarize("选2", 2, 10, 2)
summarize("Top5", 5, 10, 10)
summarize("Top7", 7, 10, 14)
summarize("Top10", 10, 10, 20)

print("\n=== Last 60 periods (T=60), from daily_report.md ===")
summarize("系统 Top5", 5, 60, 76)
summarize("原始 20 点位", 20, 60, 286)
summarize("点位拓展集合 ~48", 48, 60, 717)

print("\n=== Single-draw zero-hit probabilities (yesterday's 独胆/选2/选3) ===")
for k in (1, 2, 3, 5, 7, 10):
    p0 = stats.hypergeom.pmf(0, 80, 20, k)
    p1 = stats.hypergeom.pmf(1, 80, 20, k)
    print(f"  pick {k:2d}: P(0 hit)={p0:.3f}, P(1 hit)={p1:.3f}, "
          f"P(0 or 1)={p0+p1:.3f}")

print("\n=== Power: draws needed to detect a relative lift (5 picks) ===")
sd1 = sqrt(5 * 0.25 * 0.75 * 75 / 79)
for lift in (0.05, 0.10, 0.20, 0.242):
    T = ((1.6449 + 0.8416) * sd1 / (lift * 1.25)) ** 2
    print(f"  +{lift*100:.1f}% lift: T ~ {T:.0f} draws")
sd20 = sqrt(20 * 0.25 * 0.75 * 60 / 79)
print("20 picks:")
for lift in (0.05, 0.10, 0.20):
    T = ((1.6449 + 0.8416) * sd20 / (lift * 5.0)) ** 2
    print(f"  +{lift*100:.1f}% lift: T ~ {T:.0f} draws")