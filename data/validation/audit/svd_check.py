# -*- coding: utf-8 -*-
"""Check the SVD 'exceeds the random-matrix edge' claim.

linalg_svd.py compares the leading eigenvalue of the column-centered binary
draw matrix with the Marchenko-Pastur edge computed as
sigma2 * (1 + sqrt(80/(T-1)))^2.  That edge assumes i.i.d. entries; the draw
matrix has exactly 20 ones per row, so the null spectrum is different.
This script calibrates the observed edge against i.i.d. simulations.
"""
import re
import numpy as np

PATH = r"C:\D-pan\Dpanqianyi\Python-Project\data\storage\raw\kl8_history_final.txt"
RNG = np.random.default_rng(999)


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


def edge_stats(X):
    T, m = X.shape
    Xc = X.astype(float) - X.mean(axis=0)
    S = np.linalg.svd(Xc, compute_uv=False)
    eig_max = float(S[0] ** 2 / (T - 1))
    sigma2 = float((Xc * Xc).sum() / ((T - 1) * m))
    gamma = m / (T - 1)
    mp = sigma2 * (1.0 + np.sqrt(gamma)) ** 2
    return eig_max, mp, eig_max / mp, float(S[1] ** 2 / (T - 1))


recs = parse(PATH)
n = len(recs)
X = np.zeros((n, 80), dtype=np.int8)
for t, (_, _, nums) in enumerate(recs):
    X[t, np.array(nums) - 1] = 1

obs = edge_stats(X)
print(f"observed: eig_max={obs[0]:.6f}, MP_edge={obs[1]:.6f}, "
      f"ratio={obs[2]:.6f}, second eig={obs[3]:.6f}")

B = 400
ratios = np.empty(B)
eigs = np.empty(B)
for b in range(B):
    R = RNG.random((n, 80))
    idx = np.argpartition(R, 20, axis=1)[:, :20]
    Y = np.zeros((n, 80), dtype=np.float64)
    Y[np.arange(n)[:, None], idx] = 1
    e, mp, r, _ = edge_stats(Y)
    eigs[b] = e
    ratios[b] = r
emp = lambda x, null: (1 + (null >= x).sum()) / (len(null) + 1)
print(f"null ratio: mean={ratios.mean():.5f}, sd={ratios.std():.5f}, "
      f"95th={np.quantile(ratios, .95):.5f}, max={ratios.max():.5f}")
print(f"observed ratio {obs[2]:.5f} -> MC p={emp(obs[2], ratios):.3f}")
print(f"null eig_max: mean={eigs.mean():.5f}, 95th={np.quantile(eigs,.95):.5f}")
print(f"observed eig_max {obs[0]:.5f} -> MC p={emp(obs[0], eigs):.3f}")
print(f"fraction of i.i.d. simulations exceeding the MP edge: "
      f"{(ratios > 1).mean():.3f}")