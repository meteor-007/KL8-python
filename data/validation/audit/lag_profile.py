# -*- coding: utf-8 -*-
"""Lag profile / weekly-cycle checks to explain the bucket-7 blip."""
import re
import numpy as np
from scipy import stats
from datetime import date

PATH = r"C:\D-pan\Dpanqianyi\Python-Project\data\storage\raw\kl8_history_final.txt"


def parse(path):
    pat = re.compile(r"^date:(\d{4}-\d{2}-\d{2}),period:(\d+),numbers:(.+)$")
    recs = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            m = pat.match(line.strip())
            recs.append((m.group(1), int(m.group(2)),
                         [int(x) for x in m.group(3).split("-")]))
    recs.sort(key=lambda r: r[1])
    return recs


recs = parse(PATH)
n = len(recs)
X = np.zeros((n, 80), dtype=np.int8)
for t, (_, _, nums) in enumerate(recs):
    X[t, np.array(nums) - 1] = 1

print("overlap with the draw k positions earlier (null mean 5, sd "
      "sqrt(2.848)):")
sd_ov = np.sqrt(2.848)
for k in list(range(1, 16)) + [21, 28, 35]:
    ov = (X[k:] * X[:-k]).sum(axis=1)
    z = (ov.mean() - 5.0) / (sd_ov / np.sqrt(len(ov)))
    print(f"  lag {k:2d}: mean={ov.mean():.4f} z={z:+.2f} "
          f"max={ov.max()}")

print("\nper-number binary autocorrelation at lag 7:")
r7 = np.array([np.corrcoef(X[:-7, i], X[7:, i])[0, 1] for i in range(80)])
z7 = r7 * np.sqrt(n - 7)
print(f"  mean r={r7.mean():+.4f}, min={r7.min():+.4f}, "
      f"max={r7.max():+.4f}")
print(f"  numbers with |z|>1.96: {int((np.abs(z7)>1.96).sum())}/80 "
      f"(expected 4); max|z|={np.abs(z7).max():.2f}")

print("\ndate/weekday integrity:")
ds = [date.fromisoformat(r[0]) for r in recs]
diffs = np.array([(ds[i + 1] - ds[i]).days for i in range(n - 1)])
vals, cnts = np.unique(diffs, return_counts=True)
print("  date-diff distribution:", dict(zip(vals.tolist(), cnts.tolist())))
wd = np.array([d.weekday() for d in ds])
print("  weekday counts (Mon=0):", np.bincount(wd, minlength=7).tolist())

print("\nper-weekday number-frequency chi-square (design-corrected p):")
for w in range(7):
    m = wd == w
    c = X[m].sum(axis=0)
    e = m.sum() * 0.25
    chi = ((c - e) ** 2 / e).sum()
    print(f"  weekday {w}: n={m.sum():3d} chi2={chi:.1f} "
          f"p_naive={stats.chi2.sf(chi,79):.3f} "
          f"p_corr={stats.chi2.sf(chi/(60/79),79):.3f}")

print("\noverlap separated by date gap (7-day vs non-7-day):")
d7 = (diffs == 7)
print(f"  consecutive calendar days: {int(d7.sum())}/{len(diffs)}")
ov1 = (X[1:] * X[:-1]).sum(axis=1)
for name, m in [("gap=7d", d7), ("gap!=7d", ~d7)]:
    print(f"  {name}: n={int(m.sum())}, mean overlap={ov1[m].mean():.4f}")

# Is the bucket-7 effect present only when the last hit 8 draws ago was itself
# part of a draw whose date is 8 calendar days earlier (no gaps)?
missB = np.zeros((n, 80), dtype=np.int16)
last = np.full(80, -1, dtype=np.int16)
for t in range(n):
    missB[t] = np.where(last >= 0, t - 1 - last, t)
    last = np.where(X[t] == 1, t, last)
m7 = missB == 7
# date gap between t and t-8
gap8 = np.array([(ds[t] - ds[t - 8]).days for t in range(8, n)])
print("\nbucket-7 by calendar gap between draw t and t-8:")
for g in sorted(set(gap8.tolist())):
    if g > 10:
        continue
    rows = np.arange(8, n)[gap8 == g]
    mm = m7[rows]
    o = int(mm.sum())
    if o < 100:
        continue
    h = int((X[rows] * mm).sum())
    z = (h - 0.25 * o) / np.sqrt(o * 0.25 * 0.75 * 60 / 79)
    print(f"  gap={g:2d}d: opp={o:5d} rate={h/o:.4f} z={z:+.2f}")