# -*- coding: utf-8 -*-
"""Check the volatility module's overlapping-window chi-square test.

volatility.py computes D = sum_w (h_w - 7.5)^2 / 5.625 over all T-W+1
overlapping windows and refers D to chi2 with df = n_windows - 1.  Adjacent
windows share 29 of 30 draws, so the terms are strongly dependent and the
chi-square tail is invalid (anti-conservative).  This script calibrates it.
"""
import re
import numpy as np
from scipy import stats

PATH = r"C:\D-pan\Dpanqianyi\Python-Project\data\storage\raw\kl8_history_final.txt"
W = 30
P = 0.25
MU = W * P
VAR = W * P * (1 - P)
ALPHA = 0.05
RNG = np.random.default_rng(4242)


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


def bh(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    q = np.minimum.accumulate((p[o] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]
    out = np.empty_like(q)
    out[o] = np.minimum(q, 1)
    return out


recs = parse(PATH)
n = len(recs)
X = np.zeros((n, 80), dtype=np.int8)
for t, (_, _, nums) in enumerate(recs):
    X[t, np.array(nums) - 1] = 1


def disp_stats(Xm):
    cs = np.cumsum(Xm, axis=0)
    # window sums w=0..n-W
    h = cs[W - 1:] - np.vstack([np.zeros((1, 80), dtype=cs.dtype), cs[:-W]])
    D = ((h - MU) ** 2 / VAR).sum(axis=0)
    df = h.shape[0] - 1
    p = stats.chi2.sf(D, df)
    q = bh(p)
    phi = D / df
    return dict(D=D, p=p, q=q, phi=phi, df=df,
                n_raw=int((p < ALPHA).sum()),
                n_fdr=int((q < ALPHA).sum()),
                med_phi=float(np.median(phi)))


obs = disp_stats(X)
print(f"observed: n_raw={obs['n_raw']}/80, n_fdr={obs['n_fdr']}/80, "
      f"median phi={obs['med_phi']:.3f}, df={obs['df']}")
print(f"  phi range {obs['phi'].min():.2f}..{obs['phi'].max():.2f}; "
      f"top: {[(int(i+1), round(float(obs['phi'][i]),2)) for i in np.argsort(-obs['phi'])[:8]]}")

print("\nPermutation null (200 permutations of draw order; D recomputed, "
      "chi2 p and BH exactly as the module does):")
B = 200
nraw_null = np.empty(B)
nfdr_null = np.empty(B)
maxD_null = np.empty(B)
# per-number permutation p-values for a valid test
Dperm = np.empty((B, 80))
for b in range(B):
    Xp = X[RNG.permutation(n)]
    s = disp_stats(Xp)
    nraw_null[b] = s["n_raw"]
    nfdr_null[b] = s["n_fdr"]
    maxD_null[b] = s["D"].max()
    Dperm[b] = s["D"]
print(f"  null n_raw: mean={nraw_null.mean():.1f}, 95th={np.quantile(nraw_null,.95):.0f}")
print(f"  null n_fdr: mean={nfdr_null.mean():.1f}, 95th={np.quantile(nfdr_null,.95):.0f}, "
      f"max={int(nfdr_null.max())}")
emp = lambda x, null: (1 + (null >= x).sum()) / (len(null) + 1)
print(f"  observed n_fdr={obs['n_fdr']} -> permutation p = "
      f"{emp(obs['n_fdr'], nfdr_null):.3f}")
# valid per-number permutation p: proportion of null D >= observed D
p_perm = (1 + (Dperm >= obs["D"][None, :]).sum(axis=0)) / (B + 1)
q_perm = bh(p_perm)
print(f"\nValid per-number permutation test: numbers with p<0.05 = "
      f"{int((p_perm<ALPHA).sum())}/80, BH q<0.05 = {int((q_perm<ALPHA).sum())}/80")
print("  smallest permutation p:", round(float(p_perm.min()), 4),
      "| smallest q:", round(float(q_perm.min()), 4))
print("  numbers with q<0.05:", [int(i+1) for i in np.where(q_perm < ALPHA)[0]])