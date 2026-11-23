# -*- coding: utf-8 -*-
"""Independent randomness audit of KL8 (20 of 80) history.

All tests are set-level unless the stored within-draw order is shown to carry
information.  Everything is printed to stdout; no files are written.
"""
import re
import sys
import time
import numpy as np
from scipy import stats

PATH = r"C:\D-pan\Dpanqianyi\Python-Project\data\storage\raw\kl8_history_final.txt"
ALPHA = 0.05
RNG = np.random.default_rng(20261110)


def parse(path):
    pat = re.compile(r"^date:(\d{4}-\d{2}-\d{2}),period:(\d+),numbers:(.+)$")
    recs, bad = [], []
    with open(path, "r", encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            m = pat.match(line)
            if not m:
                bad.append((ln, line[:100]))
                continue
            nums = [int(x) for x in m.group(3).split("-")]
            recs.append(dict(date=m.group(1), period=int(m.group(2)),
                             nums=nums, line=ln))
    return recs, bad


def bh_fdr(pvals):
    p = np.asarray(pvals, dtype=float)
    out = np.full(p.shape, np.nan)
    ok = np.isfinite(p)
    ps = p[ok]
    m = ps.size
    if m == 0:
        return out
    order = np.argsort(ps)
    ranked = ps[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    qs = np.empty(m)
    qs[order] = np.minimum(q, 1.0)
    out[ok] = qs
    return out


def gof_pool(obs, exp, min_exp=5.0):
    """Chi-square GOF, merging adjacent bins until expected >= min_exp."""
    obs = np.asarray(obs, float)
    exp = np.asarray(exp, float)
    # merge from the tail repeatedly
    o, e = list(obs), list(exp)
    while len(e) > 1 and min(e) < min_exp:
        i = int(np.argmin(e))
        if i == 0:
            j = 1
        elif i == len(e) - 1:
            j = i - 1
        else:
            j = i - 1 if e[i - 1] <= e[i + 1] else i + 1
        lo, hi = min(i, j), max(i, j)
        e[lo] += e[hi]
        o[lo] += o[hi]
        del e[hi], o[hi]
    o = np.array(o)
    e = np.array(e)
    chi2 = ((o - e) ** 2 / e).sum()
    df = len(e) - 1
    return chi2, df, stats.chi2.sf(chi2, df), len(e)


def runs_test(x, thresh=None):
    x = np.asarray(x, float)
    if thresh is None:
        thresh = np.median(x)
    b = x > thresh
    n1 = int(b.sum())
    n2 = int(len(b) - n1)
    if n1 == 0 or n2 == 0:
        return dict(n1=n1, n2=n2, runs=0, z=np.nan, p=np.nan)
    runs = 1 + int((b[1:] != b[:-1]).sum())
    mu = 1 + 2.0 * n1 * n2 / (n1 + n2)
    var = (2.0 * n1 * n2 * (2.0 * n1 * n2 - n1 - n2)
           / ((n1 + n2) ** 2 * (n1 + n2 - 1)))
    z = (runs - mu) / np.sqrt(var)
    p = 2 * stats.norm.sf(abs(z))
    return dict(n1=n1, n2=n2, runs=runs, mu=mu, z=z, p=p)


def acf_cols(M, nlags):
    """Autocorrelation lags 1..nlags for every column of a 2-D array."""
    A = M.astype(np.float64)
    A = A - A.mean(axis=0)
    denom = (A * A).sum(axis=0)
    out = np.empty((nlags, A.shape[1]), dtype=float)
    for k in range(1, nlags + 1):
        out[k - 1] = (A[:-k] * A[k:]).sum(axis=0) / denom
    return out


def lb_q(M, nlags=20):
    n = M.shape[0]
    r = acf_cols(M, nlags)
    weights = (r ** 2) / (n - np.arange(1, nlags + 1))[:, None]
    return n * (n + 2) * weights.sum(axis=0)


def acf_1d(x, nlags):
    x = np.asarray(x, float)
    x = x - x.mean()
    denom = (x * x).sum()
    return np.array([(x[:-k] * x[k:]).sum() / denom
                     for k in range(1, nlags + 1)])


def lb_1d(x, nlags=10):
    n = len(x)
    r = acf_1d(x, nlags)
    q = n * (n + 2) * (r ** 2 / (n - np.arange(1, nlags + 1))).sum()
    return q, stats.chi2.sf(q, nlags)


def sep(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


t0 = time.time()
recs, bad = parse(PATH)
recs.sort(key=lambda r: r["period"])
n = len(recs)

print("file:", PATH)
print("parsed draws:", n, "| malformed lines:", len(bad))
if bad:
    print("bad examples:", bad[:3])

dates = [r["date"] for r in recs]
periods = [r["period"] for r in recs]
lens = np.array([len(r["nums"]) for r in recs])
inrange = all(1 <= v <= 80 for r in recs for v in r["nums"])
dups = sum(len(set(r["nums"])) != 20 for r in recs)
sorted_rows = sum(r["nums"] == sorted(r["nums"]) for r in recs)
date_mono = all(dates[i] < dates[i + 1] for i in range(n - 1))
period_diffs = np.diff(periods)
gap_pos = np.where(period_diffs != 1)[0]
print("date range:", dates[0], "->", dates[-1],
      "| dates strictly increasing:", date_mono)
print("period range:", periods[0], "->", periods[-1],
      "| non-unit period gaps:", len(gap_pos))
if len(gap_pos):
    print("  gap examples:", [(periods[i], periods[i + 1])
                              for i in gap_pos[:10]])
print("20 numbers per draw:", bool((lens == 20).all()),
      "| numbers in 1..80:", inrange,
      "| draws with within-draw duplicates:", dups)
print("draws whose stored order is ascending-sorted:", sorted_rows, "/", n,
      "(=> stored order is NOT sorted; per-position tests still run)")

X = np.zeros((n, 80), dtype=np.int8)
O = np.zeros((n, 20), dtype=np.int16)
for t, r in enumerate(recs):
    for j, v in enumerate(r["nums"]):
        O[t, j] = v
        X[t, v - 1] = 1

# ------------------------------------------------------------------ test 1
sep("TEST 1  Per-number frequency chi-square (df = 79)")
cnt = X.sum(axis=0)
exp = n * 20.0 / 80.0
chi2 = ((cnt - exp) ** 2 / exp).sum()
p1 = stats.chi2.sf(chi2, 79)
# Design correction: each draw is a 20-of-80 SRSWOR, so the 80 counts are
# negatively correlated within a draw.  The Pearson statistic then has null
# expectation (N-n_draw)/(N-1)*df = (60/79)*79 = 60, not 79.  The naive
# chi2_79 p-value is therefore conservative.  Scale before the tail call.
design_factor = 60.0 / 79.0
p1_corr = stats.chi2.sf(chi2 / design_factor, 79)
cohen_w = np.sqrt(chi2 / n)
sd_bin = np.sqrt(n * 0.25 * 0.75)
znum = (cnt - exp) / sd_bin
order = np.argsort(znum)
print(f"n = {n}, expected count per number = {exp:.2f}")
print(f"chi2 = {chi2:.3f}, df = 79, naive p = {p1:.6f} "
      f"(CONSERVATIVE under 20-of-80 sampling)")
print(f"null expectation of this chi2 under SRSWOR = 60.0; "
      f"design-corrected p = {p1_corr:.4f}")
print(f"Cohen's w = {cohen_w:.4f} (w=0.1 small, 0.3 medium)")
print(f"count range: {cnt.min()} .. {cnt.max()}  "
      f"(expected sd of a count = {sd_bin:.2f})")
print("coldest (lowest count):",
      [(int(i + 1), int(cnt[i]), round(float(znum[i]), 2)) for i in order[:5]])
print("hottest (highest count):",
      [(int(i + 1), int(cnt[i]), round(float(znum[i]), 2)) for i in order[-5:]])
print("max |z| across numbers =", round(float(np.abs(znum).max()), 3),
      "(null expectation for max of 80 |N(0,1)| ~ 2.7-3.0)")

# ------------------------------------------------------------------ test 2
sep("TEST 2  Pair co-occurrence vs hypergeometric expectation")
Xi = X.astype(np.int32)
C = Xi.T @ Xi
iu = np.triu_indices(80, 1)
cobs = C[iu]
p_pair = 20.0 * 19.0 / (80.0 * 79.0)
mu_pair = n * p_pair
sd_pair = np.sqrt(n * p_pair * (1 - p_pair))
zpair = (cobs - mu_pair) / sd_pair
ppair = 2 * stats.norm.sf(np.abs(zpair))
qpair = bh_fdr(ppair)
n_sig = int((ppair < ALPHA).sum())
bin_p = stats.binomtest(n_sig, len(ppair), ALPHA).pvalue
print(f"pairs tested = {len(cobs)} | per-pair expectation = {mu_pair:.2f} "
      f"(p_pair = {p_pair:.6f}), null sd = {sd_pair:.2f}")
print(f"observed range of pair counts: {cobs.min()} .. {cobs.max()}")
print(f"|z| max = {np.abs(zpair).max():.3f}; "
      f"pairs with p<0.05: {n_sig} (expected {len(cobs)*ALPHA:.1f}, "
      f"binomial p = {bin_p:.3f})")
print(f"BH-FDR: pairs with q<0.05 = {(qpair < ALPHA).sum()}, "
      f"smallest q = {qpair.min():.4g}")
idx = np.argsort(ppair)[:5]
for k in idx:
    i, j = iu[0][k], iu[1][k]
    print(f"  pair {i+1:02d}-{j+1:02d}: obs={cobs[k]}, "
          f"exp={mu_pair:.1f}, z={zpair[k]:+.2f}, p={ppair[k]:.5f}, "
          f"q={qpair[k]:.4f}")

print("\nMonte-Carlo null for the pair battery (i.i.d. uniform draws)...")
B_PAIR = 500
maxz_null = np.empty(B_PAIR)
n05_null = np.empty(B_PAIR)
sumz2_null = np.empty(B_PAIR)
freqchi_null = np.empty(B_PAIR)
maxzc_null = np.empty(B_PAIR)
obs_sumz2 = float((zpair ** 2).sum())
for b in range(B_PAIR):
    R = RNG.random((n, 80))
    idx20 = np.argpartition(R, 20, axis=1)[:, :20]
    Y = np.zeros((n, 80), dtype=np.int32)
    Y[np.arange(n)[:, None], idx20] = 1
    Cy = Y.T @ Y
    zy = (Cy[iu] - mu_pair) / sd_pair
    maxz_null[b] = np.abs(zy).max()
    n05_null[b] = (np.abs(zy) > stats.norm.ppf(0.975)).sum()
    sumz2_null[b] = (zy ** 2).sum()
    cy = Y.sum(axis=0)
    freqchi_null[b] = ((cy - exp) ** 2 / exp).sum()
    maxzc_null[b] = np.abs((cy - exp) / sd_bin).max()
emp = lambda obs, null: (1 + (null >= obs).sum()) / (len(null) + 1)
print(f"  observed max|z| = {np.abs(zpair).max():.3f}; "
      f"null mean={maxz_null.mean():.3f}, 95th={np.quantile(maxz_null, .95):.3f}, "
      f"MC p = {emp(np.abs(zpair).max(), maxz_null):.3f}")
print(f"  observed #p<0.05 = {n_sig}; null mean={n05_null.mean():.1f}, "
      f"95th={np.quantile(n05_null, .95):.0f}, "
      f"MC p = {emp(n_sig, n05_null):.3f}")
print(f"  observed sum z^2 = {obs_sumz2:.1f}; null mean={sumz2_null.mean():.1f}, "
      f"95th={np.quantile(sumz2_null, .95):.1f}, "
      f"MC p = {emp(obs_sumz2, sumz2_null):.3f}")
print(f"  [cross-check T1] observed freq chi2 = {chi2:.2f}; null mean="
      f"{freqchi_null.mean():.1f}, 95th={np.quantile(freqchi_null, .95):.1f}, "
      f"MC p = {emp(chi2, freqchi_null):.3f}; "
      f"observed max count |z| = {np.abs(znum).max():.2f}, MC p = "
      f"{emp(np.abs(znum).max(), maxzc_null):.3f}")

# ------------------------------------------------------------------ test 3
sep("TEST 3  Serial dependence per number: ACF lags 1..20 + Ljung-Box")
NLAG = 20
Q_obs = lb_q(X, NLAG)
pnum = stats.chi2.sf(Q_obs, NLAG)
qnum = bh_fdr(pnum)
nsig_num = int((pnum < ALPHA).sum())
print(f"per-number Ljung-Box (20 lags), {80} tests")
print(f"  Q range {Q_obs.min():.2f}..{Q_obs.max():.2f} (null mean ~20)")
print(f"  numbers with p<0.05: {nsig_num}/80 "
      f"(expected {80*ALPHA:.1f}, binomial p="
      f"{stats.binomtest(nsig_num, 80, ALPHA).pvalue:.3f})")
print(f"  numbers with BH q<0.05: {(qnum < ALPHA).sum()}/80, "
      f"smallest q={qnum.min():.4g}")
print("  strongest numbers:",
      [(int(i + 1), round(float(Q_obs[i]), 1), f"{pnum[i]:.4f}",
        f"{qnum[i]:.3f}") for i in np.argsort(pnum)[:5]])

r_lag = acf_cols(X, NLAG)
p_lag = 2 * stats.norm.sf(np.abs(r_lag) * np.sqrt(n))
sig_per_lag = (p_lag < ALPHA).sum(axis=1)
print("  lag: #numbers p<0.05 (expected 4.0 per lag)  max|r|")
for k in range(NLAG):
    if k < 5 or sig_per_lag[k] >= 8:
        print(f"   lag {k+1:2d}: {int(sig_per_lag[k]):2d}   "
              f"max|r|={np.abs(r_lag[k]).max():.4f}")
print(f"  total lag tests = {80*NLAG}, total p<0.05 = "
      f"{int((p_lag < ALPHA).sum())} (expected {80*NLAG*ALPHA:.0f})")

print("\nPermutation null (permute draw order; 200 permutations)...")
B_PERM = 200
tot_sig_null = np.empty(B_PERM)
maxQ_null = np.empty(B_PERM)
per_lag_null = np.empty((B_PERM, NLAG))
runs_z_null = np.empty((B_PERM, 6))
pq = np.empty(B_PERM)
for b in range(B_PERM):
    perm = RNG.permutation(n)
    Xp = X[perm]
    Qp = lb_q(Xp, NLAG)
    pp = stats.chi2.sf(Qp, NLAG)
    pq[b] = pp.min()
    tot_sig_null[b] = (pp < ALPHA).sum()
    maxQ_null[b] = Qp.max()
    ppl = 2 * stats.norm.sf(np.abs(acf_cols(Xp, NLAG)) * np.sqrt(n))
    per_lag_null[b] = (ppl < ALPHA).sum(axis=1)
    Op = O[perm]
    odd_p = (Op % 2 == 1).sum(axis=1)
    even_p = 20 - odd_p
    tot_p = Op.sum(axis=1).astype(float)
    span_p = (Op.max(axis=1) - Op.min(axis=1)).astype(float)
    Sp = np.sort(Op, axis=1)
    consec_p = (np.diff(Sp, axis=1) == 1).sum(axis=1).astype(float)
    ov_p = (Xp[1:] * Xp[:-1]).sum(axis=1).astype(float)
    runs_z_null[b] = [runs_test(v)["z"] for v in
                      (odd_p, even_p, tot_p, span_p, consec_p, ov_p)]
print(f"  observed numbers with p<0.05 = {nsig_num}; null mean="
      f"{tot_sig_null.mean():.1f}, 95th={np.quantile(tot_sig_null, .95):.0f}, "
      f"perm p={emp(nsig_num, tot_sig_null):.3f}")
print(f"  observed max Q = {Q_obs.max():.2f}; null mean={maxQ_null.mean():.1f}, "
      f"95th={np.quantile(maxQ_null, .95):.1f}, "
      f"perm p={emp(Q_obs.max(), maxQ_null):.3f}")
for k in range(NLAG):
    if k < 3 or sig_per_lag[k] >= 10:
        print(f"   lag {k+1:2d}: obs {int(sig_per_lag[k])}, null mean "
              f"{per_lag_null[:, k].mean():.1f}, "
              f"perm p={emp(sig_per_lag[k], per_lag_null[:, k]):.3f}")

# Family-wise permutation calibration of the draw-level runs tests
odd_o = (O % 2 == 1).sum(axis=1)
even_o = 20 - odd_o
tot_o = O.sum(axis=1).astype(float)
span_o = (O.max(axis=1) - O.min(axis=1)).astype(float)
So = np.sort(O, axis=1)
consec_o = (np.diff(So, axis=1) == 1).sum(axis=1).astype(float)
ov_o = (X[1:] * X[:-1]).sum(axis=1).astype(float)
obs_rz = np.array([runs_test(v)["z"] for v in
                   (odd_o, even_o, tot_o, span_o, consec_o, ov_o)])
null_runs_max = np.abs(runs_z_null).max(axis=1)
null_runs_nsig = (np.abs(runs_z_null) > 1.959964).sum(axis=1)
print(f"\n  Permutation family-wise runs calibration (6 statistics: odd, even, "
      f"sum, span, consec, overlap):")
print(f"   observed |z| per stat: {np.round(obs_rz, 2).tolist()}")
print(f"   observed max|z| = {np.abs(obs_rz).max():.2f}; null mean="
      f"{null_runs_max.mean():.2f}, 95th={np.quantile(null_runs_max, .95):.2f}, "
      f"perm p={emp(np.abs(obs_rz).max(), null_runs_max):.3f}")
print(f"   stats with |z|>1.96: obs {int((np.abs(obs_rz)>1.96).sum())}; "
      f"null mean={null_runs_nsig.mean():.2f}, "
      f"perm p={emp(int((np.abs(obs_rz)>1.96).sum()), null_runs_nsig):.3f}")

# ------------------------------------------------------------------ test 4
sep("TEST 4  Runs tests on draw-level statistics")
odd = X[:, 0::2].sum(axis=1)          # columns 0,2,... are numbers 1,3,...
even = X[:, 1::2].sum(axis=1)
tot = O.sum(axis=1).astype(float)
span = (O.max(axis=1) - O.min(axis=1)).astype(float)
S = np.sort(O, axis=1)
consec = (np.diff(S, axis=1) == 1).sum(axis=1).astype(float)

# theoretical moments
m_odd = 10.0
v_odd = 20 * 0.5 * 0.5 * 60 / 79
m_sum = 20 * 40.5
v_sum = 20 * ((80 ** 2 - 1) / 12.0) * 60 / 79

print(f"{'stat':>10} {'mean':>10} {'theory':>10} {'sd':>8} {'theory':>8} "
      f"{'runs':>6} {'n1':>5} {'n2':>5} {'z':>7} {'p(runs)':>9} {'p(LB10)':>9}")
stats_rows = [("odd", odd, m_odd, v_odd), ("even", even, 10.0, v_odd),
              ("sum", tot, m_sum, v_sum), ("span", span, None, None),
              ("consec", consec, None, None)]

# Monte-Carlo set-level moments for span and consec (20k draws)
B_MC = 20000
R = RNG.random((B_MC, 80))
idx20 = np.argpartition(R, 20, axis=1)[:, :20]
Y = np.zeros((B_MC, 80), dtype=np.int8)
Y[np.arange(B_MC)[:, None], idx20] = 1
O_mc = np.sort(idx20 + 1, axis=1)
sum_mc = O_mc.sum(axis=1)
span_mc = (O_mc.max(axis=1) - O_mc.min(axis=1)).astype(float)
consec_mc = (np.diff(O_mc, axis=1) == 1).sum(axis=1).astype(float)
mc_moments = {"sum": (sum_mc.mean(), sum_mc.std()),
              "span": (span_mc.mean(), span_mc.std()),
              "consec": (consec_mc.mean(), consec_mc.std())}

res4 = {}
for name, x, m0, v0 in stats_rows:
    if m0 is None:
        m0, s0 = mc_moments[name]
        v0 = s0 ** 2
    rr = runs_test(x)
    qlb, plb = lb_1d(x, 10)
    res4[name] = dict(mean=x.mean(), sd=x.std(ddof=1), runs=rr, lb_p=plb)
    print(f"{name:>10} {x.mean():10.3f} {m0:10.3f} {x.std(ddof=1):8.3f} "
          f"{np.sqrt(v0):8.3f} {rr['runs']:6d} {rr['n1']:5d} {rr['n2']:5d} "
          f"{rr['z']:7.2f} {rr['p']:9.3f} {plb:9.3f}")

# GOF odd count vs exact hypergeometric
ks = np.arange(0, 21)
pmf_odd = stats.hypergeom.pmf(ks, 80, 40, 20)
obs_odd = np.bincount(odd.astype(int), minlength=21)
chi_o, df_o, p_o, nb_o = gof_pool(obs_odd, pmf_odd * n)
print(f"\nodd-count GOF vs Hypergeometric(80,40,20): chi2={chi_o:.2f}, "
      f"df={df_o}, p={p_o:.3f} (bins={nb_o})")
# sum GOF vs 10-bin normal quantile bins
qs = stats.norm.ppf(np.linspace(0.1, 0.9, 9), loc=m_sum, scale=np.sqrt(v_sum))
bins = np.concatenate([[-np.inf], qs, [np.inf]])
obs_sum = np.histogram(tot, bins=bins)[0]
exp_sum = np.full(10, n / 10.0)
chi_s, df_s, p_s, nb_s = gof_pool(obs_sum, exp_sum)
print(f"sum GOF vs N(810,90^2), 10 equal-probability bins: chi2={chi_s:.2f}, "
      f"df={df_s}, p={p_s:.3f}")
print(f"sum moment z: mean {tot.mean():.2f} vs 810 "
      f"(z={(tot.mean()-810)/(90/np.sqrt(n)):+.2f}); "
      f"sd {tot.std(ddof=1):.2f} vs 90")
print(f"odd moment z: mean {odd.mean():.3f} vs 10 "
      f"(z={(odd.mean()-10)/np.sqrt(v_odd/n):+.2f}); "
      f"sd {odd.std(ddof=1):.3f} vs {np.sqrt(v_odd):.3f}")
print(f"span: obs mean {span.mean():.2f} vs MC {span_mc.mean():.2f} "
      f"(z={(span.mean()-span_mc.mean())/(span_mc.std()/np.sqrt(n)):+.2f}), "
      f"obs sd {span.std(ddof=1):.2f} vs MC {span_mc.std():.2f}")
print(f"consec: obs mean {consec.mean():.3f} vs MC {consec_mc.mean():.3f} "
      f"(z={(consec.mean()-consec_mc.mean())/(consec_mc.std()/np.sqrt(n)):+.2f}), "
      f"obs sd {consec.std(ddof=1):.3f} vs MC {consec_mc.std():.3f}")

# ------------------------------------------------------------------ test 5
sep("TEST 5  Repeat/repeat-count between consecutive draws")
ov = (X[1:] * X[:-1]).sum(axis=1).astype(int)
ks = np.arange(0, 21)
pmf = stats.hypergeom.pmf(ks, 80, 20, 20)
obs = np.bincount(ov, minlength=21)
m_ov = 20 * 20 / 80.0
v_ov = 20 * (20 / 80) * (60 / 80) * (60 / 79)
chi_v, df_v, p_v, nb_v = gof_pool(obs, pmf * len(ov))
print(f"n transitions = {len(ov)}")
print(f"mean overlap = {ov.mean():.3f} (theory {m_ov:.1f}), "
      f"var = {ov.var(ddof=1):.3f} (theory {v_ov:.3f})")
print(f"distribution GOF vs Hypergeometric(80,20,20): chi2={chi_v:.2f}, "
      f"df={df_v}, p={p_v:.3f} (bins={nb_v})")
print("observed overlap distribution (k: obs, exp):")
for k in range(0, 12):
    print(f"  {k:2d}: {obs[k]:5d}  {pmf[k]*len(ov):8.1f}")
print(f"  >=12: {obs[12:].sum():5d}  {pmf[12:].sum()*len(ov):8.1f}")
rr_ov = runs_test(ov)
qlb_ov, plb_ov = lb_1d(ov, 10)
print(f"runs test on overlap: runs={rr_ov['runs']}, z={rr_ov['z']:+.2f}, "
      f"p={rr_ov['p']:.3f}; Ljung-Box(10) p={plb_ov:.3f}")
print(f"ACF lag1..5: {np.round(acf_1d(ov,5),4).tolist()}")

# ------------------------------------------------------------------ test 6
sep("TEST 6  Cold-number premise: does long current miss raise next-draw hit?")


def bucket_table(maxb, label, use_hot=False):
    opp = np.zeros(maxb + 1)
    hit = np.zeros(maxb + 1)
    var = np.zeros(maxb + 1)
    miss = 1 - X[0]
    # hot counts: appearances in the previous 10 draws
    hist = None
    for t in range(1, n):
        if use_hot:
            if t <= 10:
                hist = X[max(0, t - 10):t].sum(axis=0).astype(int)
            b = np.minimum(hist, maxb)
        else:
            b = np.minimum(miss, maxb)
        xt = X[t]
        for k in range(maxb + 1):
            m = b == k
            mk = int(m.sum())
            if mk == 0:
                continue
            hk = int(xt[m].sum())
            opp[k] += mk
            hit[k] += hk
            var[k] += mk * 0.25 * 0.75 * (80 - mk) / 79.0
        if use_hot and t >= 10:
            hist = hist + X[t] - X[t - 10]
        miss = np.where(xt == 1, 0, miss + 1)
    valid = opp > 0
    phat = np.full(maxb + 1, np.nan)
    z = np.full(maxb + 1, np.nan)
    p = np.full(maxb + 1, np.nan)
    se = np.full(maxb + 1, np.nan)
    phat[valid] = hit[valid] / opp[valid]
    z[valid] = (hit[valid] - 0.25 * opp[valid]) / np.sqrt(var[valid])
    p[valid] = 2 * stats.norm.sf(np.abs(z[valid]))
    q = bh_fdr(p)
    se[valid] = np.sqrt(var[valid]) / opp[valid]
    lo = phat - 1.96 * se
    hi = phat + 1.96 * se
    print(f"\n{label} (bucket {maxb}=last / >= {maxb})")
    print(f"{'bucket':>8} {'opps':>9} {'hits':>9} {'rate':>8} "
          f"{'95% CI (design-adj)':>24} {'z':>7} {'p':>9} {'q':>7}")
    for k in range(maxb + 1):
        print(f"{k:>8} {opp[k]:9.0f} {hit[k]:9.0f} {phat[k]:8.4f} "
              f"  [{lo[k]:.4f}, {hi[k]:.4f}] {z[k]:7.2f} {p[k]:9.4f} {q[k]:7.3f}")
    return dict(opp=opp, hit=hit, rate=phat, z=z, p=p, q=q, lo=lo, hi=hi)


cold = bucket_table(3, "Current miss buckets (0 = hit last draw, 3 = miss >=3)")
fine = bucket_table(10, "Fine current-miss buckets (10 = miss >=10)")
hot = bucket_table(10, "Hot-hand check: hits in previous 10 draws", use_hot=True)

# homogeneity / trend across fine cold buckets: weighted least squares z-test
# Var(rate_k) = 0.25*0.75*(80-m)/79 / opp_k  ~= 0.1424/opp_k, so weight = opp_k/0.1424
k = np.arange(11, dtype=float)
w = fine["opp"] / (0.25 * 0.75 * 60.0 / 79.0)
ph = fine["rate"]
pbar = (w * ph).sum() / w.sum()
chi_h = (w * (ph - pbar) ** 2).sum()
df_h = 10
print(f"\nCold-bucket homogeneity across 11 fine buckets: chi2={chi_h:.2f}, "
      f"df={df_h}, p={stats.chi2.sf(chi_h, df_h):.4f}")
# Cochran-Armitage-like linear trend on bucket score
score = k - (w * k).sum() / w.sum()
slope = (w * score * (ph - pbar)).sum() / (w * score ** 2).sum()
se_slope = 1.0 / np.sqrt((w * score ** 2).sum())
print(f"linear trend per extra miss: {slope*100:+.4f} pp, "
      f"z={slope/se_slope:+.2f}, p={2*stats.norm.sf(abs(slope/se_slope)):.3f}")

# Split-half replication of the fine-bucket scan (guards against scan artefacts)
print("\nSplit-half check of fine cold buckets (per-half hit rate):")
Bmiss = np.zeros((n, 80), dtype=np.int8)
miss = 1 - X[0]
for t in range(1, n):
    Bmiss[t] = np.minimum(miss, 10)
    miss = np.where(X[t] == 1, 0, miss + 1)


def agg_buckets(t0, t1):
    o = np.zeros(11)
    h = np.zeros(11)
    v = np.zeros(11)
    for t in range(t0, t1):
        b = Bmiss[t]
        xt = X[t]
        for kk in range(11):
            m = b == kk
            mk = int(m.sum())
            if mk:
                o[kk] += mk
                h[kk] += int(xt[m].sum())
                v[kk] += mk * 0.25 * 0.75 * (80 - mk) / 79.0
    return o, h, v


print(f"{'bucket':>8} {'rate_H1':>9} {'rate_H2':>9} {'diff':>8} {'z_diff':>7} {'p':>7}")
for kk in range(11):
    parts = []
    for ta, tb in [(1, n // 2), (n // 2, n)]:
        o, h, v = agg_buckets(ta, tb)
        parts.append((o[kk], h[kk], v[kk]))
    o1, h1, v1 = parts[0]
    o2, h2, v2 = parts[1]
    r1 = h1 / o1 if o1 else np.nan
    r2 = h2 / o2 if o2 else np.nan
    if o1 and o2:
        zd = (r1 - r2) / np.sqrt(v1 / o1 ** 2 + v2 / o2 ** 2)
    else:
        zd = np.nan
    pd = 2 * stats.norm.sf(abs(zd)) if np.isfinite(zd) else np.nan
    print(f"{kk:>8} {r1:9.4f} {r2:9.4f} {r1-r2:+8.4f} {zd:7.2f} {pd:7.3f}")

# ------------------------------------------------------------------ test 7
sep("TEST 7  Year/period/order artifacts")

years = np.array([int(r["date"][:4]) for r in recs])
print(f"{'year':>6} {'draws':>6} {'chi2(df=79)':>12} {'p':>8}")
year_chi2 = 0.0
year_p = []
for y in sorted(set(years.tolist())):
    m = years == y
    cy = X[m].sum(axis=0)
    ey = m.sum() * 0.25
    c2 = ((cy - ey) ** 2 / ey).sum()
    year_chi2 += c2
    year_p.append(stats.chi2.sf(c2, 79))
    print(f"{y:>6} {m.sum():6d} {c2:12.2f} {stats.chi2.sf(c2, 79):8.3f}")
# years are independent samples -> chi2 sum with df = 79 * n_years;
# each year's statistic has SRSWOR null expectation 60 (not 79).
dfy = 79 * len(year_p)
p_year_naive = stats.chi2.sf(year_chi2, dfy)
p_year_corr = stats.chi2.sf(year_chi2 / design_factor, dfy)
print(f"combined across years: chi2={year_chi2:.2f}, df={dfy}, "
      f"naive p={p_year_naive:.3f}, design-corrected p={p_year_corr:.3f} "
      f"(null expectation={60*len(year_p):.0f})")

half = n // 2
c1 = X[:half].sum(axis=0)
c2 = X[half:].sum(axis=0)
e_pool = (c1 + c2) / 2.0
chi_half = (((c1 - e_pool) ** 2) / e_pool).sum() + \
           (((c2 - e_pool) ** 2) / e_pool).sum()
print(f"first-half vs second-half number-frequency homogeneity: "
      f"chi2={chi_half:.2f}, df=79, naive p={stats.chi2.sf(chi_half,79):.3f}, "
      f"design-corrected p={stats.chi2.sf(chi_half/design_factor,79):.3f}")

# linear trends in draw-level statistics
print("\nlinear trend over draw index t=0..n-1 (per 1000 draws):")
for name, x in [("sum", tot), ("odd", odd.astype(float)),
                ("span", span), ("consec", consec)]:
    lr = stats.linregress(np.arange(n), x)
    print(f"  {name:>7}: slope/1000draws={lr.slope*1000:+.3f}, "
          f"z={lr.slope/lr.stderr:+.2f}, p={lr.pvalue:.3f}")

# within-draw order (positions)
print("\nper-position uniformity (stored within-draw order; 20 tests, df=79):")
pos_p = []
pos_means = []
for j in range(20):
    cj = np.bincount(O[:, j], minlength=81)[1:]
    e = n / 80.0
    c2 = ((cj - e) ** 2 / e).sum()
    pos_p.append(stats.chi2.sf(c2, 79))
    pos_means.append(O[:, j].mean())
pos_q = bh_fdr(np.array(pos_p))
print(f"  positions with p<0.05: {sum(p < ALPHA for p in pos_p)}/20; "
      f"BH q<0.05: {(pos_q < ALPHA).sum()}/20; smallest q={pos_q.min():.3f}")
print(f"  mean value per position: min={min(pos_means):.2f}, "
      f"max={max(pos_means):.2f} (null sd of a position mean = "
      f"{np.sqrt(((80**2-1)/12.0)/n):.2f})")
# Spearman corr between position index and value per draw, averaged
rhos = []
for t in range(0, n, 20):
    rho = stats.spearmanr(np.arange(20), O[t])[0]
    rhos.append(rho)
print(f"  mean within-draw Spearman(position, value) = {np.mean(rhos):+.4f} "
      f"(null 0, sd ~ {1/np.sqrt(19):.3f}; z={np.mean(rhos)*np.sqrt(19*len(rhos)):+.2f})")

# ------------------------------------------------------------------ verdict
sep("MULTIPLE-TESTING BURDEN / OVERALL VERDICT")
print("Tests performed (families):")
print("  T1: 1 chi-square (df=79); T2: 3160 pair z-tests + 500-draw MC")
print("  T3: 80 Ljung-Box (20 lags) + 1600 lag tests + 200-permutation null")
print("  T4: 5 runs tests + 5 Ljung-Box + 3 GOF; T5: 1 GOF + runs/LB")
print("  T6: 4 + 11 + 11 bucket z-tests (BH within family)")
print("  T7: 7 year chi-squares + 1 homogeneity + 4 trends + 20 position tests")
print(f"Total nominal tests > 4,800; at alpha=0.05 expect >240 false positives "
      f"before correction.")
print(f"Elapsed: {time.time()-t0:.1f}s")