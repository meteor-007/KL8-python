# -*- coding: utf-8 -*-
"""Independent verification of the 'exactly 7 misses' blip."""
import re
import numpy as np
from scipy import stats

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

# method A: running miss counter
missA = np.zeros((n, 80), dtype=np.int16)
miss = 1 - X[0]
for t in range(1, n):
    missA[t] = miss
    miss = np.where(X[t] == 1, 0, miss + 1)

# method B: last occurrence index
missB = np.full((n, 80), -1, dtype=np.int16)
last = np.full(80, -1, dtype=np.int16)
for t in range(n):
    missB[t] = np.where(last >= 0, t - 1 - last, t)
    last = np.where(X[t] == 1, t, last)

print("methods A and B agree:", bool((missA == missB).all()))
print("max absolute difference:", int(np.abs(missA - missB).max()))

# exact and cumulative miss rates using method B (independent of A)
hits = X.astype(int)
print("\nexact-k miss -> next-draw hit rate (n opportunities):")
for k in range(0, 16):
    m = missB == k
    o = int(m.sum())
    h = int((hits * m).sum())
    rate = h / o
    z = (h - 0.25 * o) / np.sqrt(o * 0.25 * 0.75 * 60 / 79)
    print(f"  k={k:2d}: opp={o:6d} hits={h:5d} rate={rate:.4f} z={z:+.2f}")

print("\n'at least k' miss -> next-draw hit rate:")
for k in range(0, 12):
    m = missB >= k
    o = int(m.sum())
    h = int((hits * m).sum())
    rate = h / o
    z = (h - 0.25 * o) / np.sqrt(o * 0.25 * 0.75 * 60 / 79)
    print(f"  k>={k:2d}: opp={o:6d} hits={h:5d} rate={rate:.4f} z={z:+.2f}")

# bucket-7 rate with influential numbers removed
m7 = missB == 7
o7 = int(m7.sum())
for drop in [[], [33], [33, 3], [33, 3, 73], [33, 3, 73, 69, 45, 7]]:
    keep = np.ones(80, dtype=bool)
    keep[np.array(drop, dtype=int) - 1] = False
    m = m7 & keep[None, :]
    o = int(m.sum())
    h = int((hits * m).sum())
    z = (h - 0.25 * o) / np.sqrt(o * 0.25 * 0.75 * 60 / 79)
    print(f"drop={drop}: opp={o:5d} rate={h/o:.4f} z={z:+.2f}")

# per-number stratified test: sum (h_i - p_i o_i), variance approximated
num = []
for i in range(80):
    mi = m7[:, i]
    oi = int(mi.sum())
    hi = int(X[1:, i][mi[1:]].sum()) if False else int((X[:, i] * mi).sum())
    # note: bucket at t uses history before t, so X[t] is fine; t=0 has no bucket
    p_i = X[:, i].mean()
    v_i = oi * p_i * (1 - p_i) * 60 / 79
    num.append((oi, hi, p_i, v_i))
o_sum = sum(r[0] for r in num)
h_sum = sum(r[1] for r in num)
dev = sum(r[1] - r[2] * r[0] for r in num)
var = sum(r[3] for r in num)
print(f"\nstratified by number: opp={o_sum}, hits={h_sum}, "
      f"sum(hit - p_i*opp)={dev:+.1f}, sd={np.sqrt(var):.1f}, "
      f"z={dev/np.sqrt(var):+.2f}, p={2*stats.norm.sf(abs(dev/np.sqrt(var))):.4f}")

# parity split (odd vs even draw index) as an independent-ish split
for name, sel in [("odd t", np.arange(n) % 2 == 1),
                  ("even t", np.arange(n) % 2 == 0)]:
    m = m7 & sel[:, None]
    o = int(m.sum())
    h = int((hits * m).sum())
    z = (h - 0.25 * o) / np.sqrt(o * 0.25 * 0.75 * 60 / 79)
    print(f"{name}: opp={o}, rate={h/o:.4f}, z={z:+.2f}")

# number of distinct numbers with any bucket-7 opportunity
print("\nnumbers with bucket-7 opportunities:",
      int((m7.sum(axis=0) > 0).sum()), "/80")
print("bucket-7 opp per number: min/median/max =",
      int(m7.sum(axis=0).min()), np.median(m7.sum(axis=0)),
      int(m7.sum(axis=0).max()))