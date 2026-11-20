# -*- coding: utf-8 -*-
"""Focused diagnostics for the fine cold-miss bucket scan.

Permutation null preserves each number's total hit count and the empirical
per-draw sets; it only destroys the chronological ordering.  This calibrates
the 'miss exactly k' scan against the actual number heterogeneity in the data.
"""
import re
import time
import numpy as np
from scipy import stats

PATH = r"C:\D-pan\Dpanqianyi\Python-Project\data\storage\raw\kl8_history_final.txt"
ALPHA = 0.05
RNG = np.random.default_rng(777)
MAXB = 10


def parse(path):
    pat = re.compile(r"^date:(\d{4}-\d{2}-\d{2}),period:(\d+),numbers:(.+)$")
    recs = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            m = pat.match(line)
            recs.append((m.group(1), int(m.group(2)),
                         [int(x) for x in m.group(3).split("-")]))
    recs.sort(key=lambda r: r[1])
    return recs


def build(recs):
    n = len(recs)
    X = np.zeros((n, 80), dtype=np.int8)
    for t, (_, _, nums) in enumerate(recs):
        X[t, np.array(nums) - 1] = 1
    return X


def cold_scan(X, maxb=MAXB):
    n = X.shape[0]
    miss = 1 - X[0]
    opp = np.zeros(maxb + 1)
    hit = np.zeros(maxb + 1)
    var = np.zeros(maxb + 1)
    per_draw_hits = []
    for t in range(1, n):
        b = np.minimum(miss, maxb)
        mcnt = np.bincount(b, minlength=maxb + 1).astype(float)
        xt = X[t]
        hcnt = np.bincount(b[xt == 1], minlength=maxb + 1).astype(float)
        opp += mcnt
        hit += hcnt
        var += mcnt * 0.25 * 0.75 * (80.0 - mcnt) / 79.0
        per_draw_hits.append(hcnt)
        miss = np.where(xt == 1, 0, miss + 1)
    rate = hit / opp
    z = (hit - 0.25 * opp) / np.sqrt(var)
    w = opp / (0.25 * 0.75 * 60.0 / 79.0)
    pbar = (w * rate).sum() / w.sum()
    chi = (w * (rate - pbar) ** 2).sum()
    return dict(opp=opp, hit=hit, rate=rate, z=z, chi=chi,
                per_draw=np.array(per_draw_hits))


recs = parse(PATH)
X = build(recs)
n = len(X)
years = np.array([int(r[0][:4]) for r in recs])
obs = cold_scan(X)
print(f"n={n}, fine-bucket scan (miss exactly k, k=0..{MAXB})")
print(f"observed homogeneity chi2 = {obs['chi']:.2f}, df={MAXB}, "
      f"p={stats.chi2.sf(obs['chi'], MAXB):.4f}")
print(f"observed max |z| = {np.abs(obs['z']).max():.2f} at bucket "
      f"{int(np.argmax(np.abs(obs['z'])))}")
print("bucket rates:", np.round(obs['rate'], 4).tolist())
print("bucket z    :", np.round(obs['z'], 2).tolist())

print("\nYear-by-year rate for buckets 5..9 (opp in parentheses):")
# build per-draw bucket/hit arrays over full history for slicing by year/half
miss = 1 - X[0]
B = np.zeros((n, 80), dtype=np.int8)
H = X.copy()
for t in range(1, n):
    B[t] = np.minimum(miss, MAXB)
    miss = np.where(X[t] == 1, 0, miss + 1)


def agg(t0, t1):
    o = np.zeros(MAXB + 1)
    h = np.zeros(MAXB + 1)
    v = np.zeros(MAXB + 1)
    for t in range(t0, t1):
        b = B[t]
        xt = X[t]
        for k in range(MAXB + 1):
            m = b == k
            mk = int(m.sum())
            if mk:
                o[k] += mk
                h[k] += int(xt[m].sum())
                v[k] += mk * 0.25 * 0.75 * (80 - mk) / 79.0
    return o, h, v


for y in sorted(set(years.tolist())):
    t0 = int(np.searchsorted(years, y, side="left"))
    t1 = int(np.searchsorted(years, y, side="right"))
    o, h, v = agg(t0, t1)
    z = (h - 0.25 * o) / np.sqrt(v)
    rates = h / o
    print(f"  {y}: n={t1-t0:3d} | " + " ".join(
        f"b{k}={rates[k]:.3f}(z={z[k]:+.1f})" for k in range(5, 10)))

print("\nBucket-7 contributions by number (top |z|):")
o, h, v = agg(1, n)
# per-number bucket7
pnum = []
for i in range(80):
    mask = B[1:, i] == 7
    oi = int(mask.sum())
    hi = int((X[1:, i][mask]).sum())
    if oi:
        # number-specific null p from its own overall rate
        pi = X[:, i].mean()
        # approximate binomial variance of hits in bucket7 given pi
        vi = oi * pi * (1 - pi) * 60 / 79
        zi = (hi - pi * oi) / np.sqrt(vi) if vi > 0 else 0.0
        pnum.append((i + 1, oi, hi, pi, zi))
pnum.sort(key=lambda r: -abs(r[4]))
for row in pnum[:10]:
    print(f"  number {row[0]:02d}: opp={row[1]:4d}, hits={row[2]:4d}, "
          f"overall_p={row[3]:.4f}, z_bucket7={row[4]:+.2f}")
print("  sum of per-number (hit - p_i*opp) = "
      f"{sum(r[2]-r[3]*r[1] for r in pnum):+.1f}")

print("\nSplit-sample validation (select extreme bucket on one half, test on other):")
for sel_name, (s0, s1), (t0, t1) in [
        ("select H1, test H2", (1, n // 2), (n // 2, n)),
        ("select H2, test H1", (n // 2, n), (1, n // 2))]:
    o1, h1, v1 = agg(s0, s1)
    r1 = h1 / o1
    z1 = (h1 - 0.25 * o1) / np.sqrt(v1)
    kb = int(np.argmax(np.abs(z1)))
    o2, h2, v2 = agg(t0, t1)
    rate2 = h2[kb] / o2[kb]
    z2 = (h2[kb] - 0.25 * o2[kb]) / np.sqrt(v2[kb])
    p2 = stats.norm.sf(z2)
    print(f"  {sel_name}: selected bucket {kb} (sel rate {r1[kb]:.4f}, "
          f"z={z1[kb]:+.2f}); holdout rate={rate2:.4f}, "
          f"one-sided z={z2:+.2f}, p={p2:.4f}")

print("\nPermutation calibration of the fine-bucket scan (200 permutations)...")
B_PERM = 200
maxz_null = np.empty(B_PERM)
chi_null = np.empty(B_PERM)
b7_null = np.empty(B_PERM)
t0_clock = time.time()
for b in range(B_PERM):
    Xp = X[RNG.permutation(n)]
    res = cold_scan(Xp)
    maxz_null[b] = np.abs(res["z"]).max()
    chi_null[b] = res["chi"]
    b7_null[b] = res["rate"][7]
emp = lambda x, null: (1 + (null >= x).sum()) / (len(null) + 1)
print(f"  observed max|z|={np.abs(obs['z']).max():.2f}; null mean="
      f"{maxz_null.mean():.2f}, 95th={np.quantile(maxz_null,.95):.2f}, "
      f"perm p={emp(np.abs(obs['z']).max(), maxz_null):.3f}")
print(f"  observed homogeneity chi2={obs['chi']:.2f}; null mean="
      f"{chi_null.mean():.2f}, 95th={np.quantile(chi_null,.95):.2f}, "
      f"perm p={emp(obs['chi'], chi_null):.3f}")
print(f"  bucket7 rate={obs['rate'][7]:.4f}; null mean={b7_null.mean():.4f}, "
      f"95th={np.quantile(b7_null,.95):.4f}, "
      f"perm p(one-sided)={emp(obs['rate'][7], b7_null):.3f}")
print(f"  elapsed {time.time()-t0_clock:.1f}s")