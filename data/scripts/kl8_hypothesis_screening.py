# -*- coding: utf-8 -*-
"""
kl8_hypothesis_screening.py — 快乐8 正交假设族筛查台架 (只读)
=============================================================

用途：一次性把"选号优势是否存在"在多个**正交假设族**上过一遍 BH-FDR 闸门，
      避免每次重新手写检验、避免重复挖已被证伪的因子。

    python scripts/kl8_hypothesis_screening.py                # 只打印
    python scripts/kl8_hypothesis_screening.py --report       # 另存 MD 记录

已覆盖假设族（2026-10-12 首轮全部零幸存，见同目录生成的记录）：
    1 每期结构约束   分区占用/连号对数/同尾对数/和值/奇偶个数/重号个数
    2 记录位置序     20 位置边际 + omnibus + 相邻位置连号
    3 日历效应       星期/月份/期号模 7,10
    4 成对共现矩阵   C(80,2)=3160 对
    5 全转移矩阵     80×80=6400 格 + 条件化对角线
    6 滞后 k 自延续   k=1..5 逐球条件化检验
    7 逐球间隔离散度 是否成簇出现
    8 和值条件偏向   低/高和值分组下的号码偏移
    9 盘面极值       最小号/最大号/跨度

零假设构造三条铁律（都是踩坑换来的，改代码时别退回）：
    a) 以盘面统计量（和值等）为条件时，零分布必须用**同条件 MC**；
       直接拿"随机盘"对比会机械地显著（低和值必然多小号）。
    b) 逐球自延续必须**条件在 b=|上期出现次数|** 上：a|b ~ Bin(b, 0.25)。
       用联合计数配"边际期望 (n·p)"当零假设，会在 b 偏离期望时虚高 z（曾凭空造出 4 个'幸存号'）。
    c) 厚尾统计量（间隔方差等）的 SE 不能用正态公式，一律**整盘 MC**。
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from collections import Counter
from datetime import datetime
from math import comb, erf, sqrt

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(_CURR_DIR)
for _p in [os.path.join(_PROJ_DIR, "backend"), _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scipy.stats import chi2 as chi2d
from scipy.stats import hypergeom

from backend.core.multiple_testing import bh_fdr

TOTAL_BALLS = 80
DRAW_BALLS = 20


def z2p(z: float) -> float:
    """双侧正态 p 值。"""
    return 2.0 * (1.0 - 0.5 * (1.0 + erf(abs(z) / sqrt(2.0))))


def load_raw(path: str):
    """解析原始历史: 返回 [(period, date, 有序号码列表)]，按升序。"""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parts = line.split(",")
                date = parts[0].split(":", 1)[1]
                period = int(parts[1].split(":", 1)[1])
                nums = [int(x) for x in parts[2].split(":", 1)[1].split("-") if x]
            except Exception:
                continue
            if len(nums) == DRAW_BALLS:
                rows.append((period, date, nums))
    rows.sort(key=lambda r: r[0])
    return rows


def _gof_chi2(observed: Counter, n_units: int, prob_fn, lo: int, hi: int):
    """通用拟合优度: 观测计数 vs 精确概率（尾部合并到 hi）。"""
    obs = [observed.get(k, 0) for k in range(lo, hi)] + [sum(observed.get(k, 0) for k in range(hi, n_units + 1))]
    exp = [prob_fn(k) for k in range(lo, hi)] + [max(0.0, 1.0 - sum(prob_fn(k) for k in range(lo, hi)))]
    exp = [e * n_units for e in exp]
    obs = [o for o, e in zip(obs, exp) if e > 1e-9]
    exp = [e for e in exp if e > 1e-9]
    chi = sum((o - e) ** 2 / e for o, e in zip(obs, exp))
    return chi, 1.0 - chi2d.cdf(chi, max(1, len(obs) - 1))


class Screen:
    def __init__(self, rows, seed: int = 20261012, mc: int = 20000):
        self.rows = rows
        self.draws = [set(r[2]) for r in rows]
        self.n = len(self.draws)
        self.rng = random.Random(seed)
        self.mc = mc
        self.findings = []   # (family, name, stat, p, note)
        self.notes = []      # 不产 p 的描述性结论

    def add(self, family, name, stat, p, note=""):
        self.findings.append([family, name, stat, p, note])

    # ── 1. 每期结构约束 ──
    def family_period_structure(self):
        fam = "1 每期结构"
        zc = [[0] * 9 for _ in range(8)]
        for s in self.draws:
            c = Counter((b - 1) // 10 for b in s)
            for z in range(8):
                zc[z][min(c.get(z, 0), 8)] += 1
        for z in range(8):
            chi, p = _gof_chi2(Counter({k: zc[z][k] for k in range(9)}), self.n,
                               lambda k, zz=z: hypergeom.pmf(k, TOTAL_BALLS, 10, DRAW_BALLS), 0, 8)
            self.add(fam, f"第{z + 1}区占用分布", f"chi2={chi:.1f}", p)
        cs = []
        for s in self.draws:
            c = [sum(1 for b in s if (b - 1) // 10 == z) for z in range(8)]
            for i in range(8):
                for j in range(i + 1, 8):
                    cs.append((c[i] - 2.5) * (c[j] - 2.5))
        self.notes.append(f"区内占用平均相关系数={sum(cs) / len(cs) / 1.6621:+.4f} (理论 -0.1429)")

        adj = [sum(1 for b in s if b + 1 in s) for s in self.draws]
        null = []
        for _ in range(self.mc):
            t = set(self.rng.sample(range(1, TOTAL_BALLS + 1), DRAW_BALLS))
            null.append(sum(1 for b in t if b + 1 in t))
        mu, sd = statistics.mean(null), statistics.pstdev(null)
        z = (statistics.mean(adj) - mu) / (sd / sqrt(self.n))
        self.add(fam, "连号对数均值", f"实测{statistics.mean(adj):.3f}/理论{mu:.3f}", z2p(z))

        st = [sum(comb(v, 2) for v in Counter(b % 10 for b in s).values()) for s in self.draws]
        null = [sum(comb(v, 2) for v in Counter(b % 10 for b in self.rng.sample(range(1, TOTAL_BALLS + 1), DRAW_BALLS)).values())
                for _ in range(self.mc)]
        mu, sd = statistics.mean(null), statistics.pstdev(null)
        z = (statistics.mean(st) - mu) / (sd / sqrt(self.n))
        self.add(fam, "同尾对数均值", f"实测{statistics.mean(st):.3f}/理论{mu:.3f}", z2p(z))

        sums = [sum(s) for s in self.draws]
        mu_s = DRAW_BALLS * 40.5
        sd_s = sqrt(DRAW_BALLS * 533.25 * (TOTAL_BALLS - DRAW_BALLS) / (TOTAL_BALLS - 1))
        self.add(fam, "和值均值", f"实测{statistics.mean(sums):.2f}/理论{mu_s:.2f}", z2p((statistics.mean(sums) - mu_s) / (sd_s / sqrt(self.n))))

        oc = Counter(sum(1 for b in s if b % 2) for s in self.draws)
        chi, p = _gof_chi2(oc, self.n, lambda k: hypergeom.pmf(k, TOTAL_BALLS, 40, DRAW_BALLS), 0, 20)
        self.add(fam, "奇偶个数分布", f"chi2={chi:.1f}", p)

        rc = Counter(len(self.draws[i] & self.draws[i - 1]) for i in range(1, self.n))
        chi, p = _gof_chi2(rc, self.n - 1, lambda k: hypergeom.pmf(k, TOTAL_BALLS, DRAW_BALLS, DRAW_BALLS), 0, 20)
        self.add(fam, "重号个数分布", f"chi2={chi:.1f}", p)

    # ── 2. 记录位置序 ──
    def family_positional(self):
        fam = "2 位置序"
        ps = []
        for i in range(DRAW_BALLS):
            cnt = Counter(r[2][i] for r in self.rows)
            e = self.n / TOTAL_BALLS
            chi = sum((cnt.get(b, 0) - e) ** 2 / e for b in range(1, TOTAL_BALLS + 1))
            ps.append(1.0 - chi2d.cdf(chi, TOTAL_BALLS - 1))
        mask, qs = bh_fdr(ps, 0.05)
        self.add(fam, "20 位置边际 (族内 BH)", f"通过 {sum(mask)}/20, min p={min(ps):.4f}", min(qs))
        seqadj = [sum(1 for i in range(DRAW_BALLS - 1) if abs(r[2][i] - r[2][i + 1]) == 1) for r in self.rows]
        null = []
        for _ in range(self.mc):
            s = self.rng.sample(range(1, TOTAL_BALLS + 1), DRAW_BALLS)
            null.append(sum(1 for i in range(DRAW_BALLS - 1) if abs(s[i] - s[i + 1]) == 1))
        mu, sd = statistics.mean(null), statistics.pstdev(null)
        z = (statistics.mean(seqadj) - mu) / (sd / sqrt(self.n))
        self.add(fam, "相邻位置连号", f"实测{statistics.mean(seqadj):.3f}/理论{mu:.3f}", z2p(z))

    # ── 3. 日历 ──
    def family_calendar(self):
        fam = "3 日历"
        def group_p(vals_by_key):
            ps = []
            for k in sorted(vals_by_key):
                vals = vals_by_key[k]
                cnt = Counter(vals)
                e = len(vals) / TOTAL_BALLS
                chi = sum((cnt.get(b, 0) - e) ** 2 / e for b in range(1, TOTAL_BALLS + 1))
                ps.append(1.0 - chi2d.cdf(chi, TOTAL_BALLS - 1))
            return ps
        wk = {}
        for p, d, nums in self.rows:
            try:
                w = datetime.strptime(d, "%Y-%m-%d").weekday()
            except Exception:
                continue
            wk.setdefault(w, []).extend(nums)
        ps = group_p(wk)
        mask, qs = bh_fdr(ps, 0.05)
        self.add(fam, "星期 (族内 BH)", f"通过 {sum(mask)}/{len(ps)}", min(qs))
        mo = {}
        for p, d, nums in self.rows:
            mo.setdefault(d[5:7], []).extend(nums)
        ps = group_p(mo)
        mask, qs = bh_fdr(ps, 0.05)
        self.add(fam, "月份 (族内 BH)", f"通过 {sum(mask)}/{len(ps)}", min(qs))
        for mod in (7, 10):
            grp = {}
            for p, d, nums in self.rows:
                grp.setdefault(p % mod, []).extend(nums)
            ps = group_p(grp)
            mask, qs = bh_fdr(ps, 0.05)
            self.add(fam, f"期号 mod {mod} (族内 BH)", f"通过 {sum(mask)}/{len(ps)}", min(qs))

    # ── 4. 成对共现 ──
    def family_pairwise(self):
        fam = "4 成对共现"
        co = Counter()
        for s in self.draws:
            sl = sorted(s)
            for i in range(len(sl)):
                for j in range(i + 1, len(sl)):
                    co[(sl[i], sl[j])] += 1
        p_both = comb(DRAW_BALLS, 2) / comb(TOTAL_BALLS, 2)
        mu, sd = self.n * p_both, sqrt(self.n * p_both * (1 - p_both))
        zs = [(co.get((a, b), 0) - mu) / sd for a in range(1, TOTAL_BALLS + 1) for b in range(a + 1, TOTAL_BALLS + 1)]
        ps = [z2p(z) for z in zs]
        mask, qs = bh_fdr(ps, 0.05)
        self.add(fam, "3160 对 (全族 BH)", f"max|z|={max(abs(z) for z in zs):.2f} 通过 {sum(mask)}/3160", min(qs))

    # ── 5. 全转移矩阵 + 条件化对角线 ──
    def family_transition(self):
        fam = "5 转移矩阵"
        tr = Counter()
        for i in range(1, self.n):
            for x in self.draws[i - 1]:
                for y in self.draws[i]:
                    tr[(x, y)] += 1
        p_t = 0.0625
        mu, sd = (self.n - 1) * p_t, sqrt((self.n - 1) * p_t * (1 - p_t))
        zs = [(tr.get((x, y), 0) - mu) / sd for x in range(1, TOTAL_BALLS + 1) for y in range(1, TOTAL_BALLS + 1)]
        ps = [z2p(z) for z in zs]
        mask, qs = bh_fdr(ps, 0.05)
        self.add(fam, "6400 格 (全族 BH)", f"max|z|={max(abs(z) for z in zs):.2f} 通过 {sum(mask)}/6400", min(qs))
        # 对角线: a|b ~ Bin(b, 0.25)  ← 铁律 b
        ps, zs = [], []
        for x in range(1, TOTAL_BALLS + 1):
            a = b = 0
            for i in range(1, self.n):
                if x in self.draws[i - 1]:
                    b += 1
                    if x in self.draws[i]:
                        a += 1
            z = (a / b - 0.25) / sqrt(0.25 * 0.75 / b) if b else 0.0
            zs.append(z)
            ps.append(z2p(z))
        mask, qs = bh_fdr(ps, 0.05)
        self.add(fam, "对角线自身延续 (条件化 BH)", f"max|z|={max(abs(z) for z in zs):.2f} 通过 {sum(mask)}/80", min(qs))

    # ── 6. 滞后 k 自延续 ──
    def family_lag_persistence(self):
        fam = "6 滞后自延续"
        allps = []
        for k in range(1, 6):
            ps = []
            for x in range(1, TOTAL_BALLS + 1):
                a = b = 0
                for i in range(0, self.n - k):
                    if x in self.draws[i]:
                        b += 1
                        if x in self.draws[i + k]:
                            a += 1
                ps.append(z2p((a / b - 0.25) / sqrt(0.25 * 0.75 / b)) if b else 1.0)
            allps.extend(ps)
            mask, qs = bh_fdr(ps, 0.05)
            self.add(fam, f"滞后{k} (族内 BH)", f"通过 {sum(mask)}/80", min(qs))
        mask, qs = bh_fdr(allps, 0.05)
        self.add(fam, "滞后1-5 合并 (400 项 BH)", f"通过 {sum(mask)}/400", min(qs))

    # ── 7. 逐球间隔离散度 (整盘 MC 零分布, 铁律 c) ──
    def family_gap_dispersion(self):
        fam = "7 间隔离散度"
        def gap_vars(ds):
            app = {b: [] for b in range(1, TOTAL_BALLS + 1)}
            for i, s in enumerate(ds):
                for b in s:
                    app[b].append(i)
            out = []
            for b in range(1, TOTAL_BALLS + 1):
                g = [app[b][k + 1] - app[b][k] for k in range(len(app[b]) - 1)]
                out.append(statistics.variance(g) if len(g) > 1 else 0.0)
            return out
        obs = gap_vars(self.draws)
        null = []
        for _ in range(40):
            null.extend(gap_vars([set(self.rng.sample(range(1, TOTAL_BALLS + 1), DRAW_BALLS)) for _ in range(self.n)]))
        mu, sd = statistics.mean(null), statistics.pstdev(null)
        ps = [z2p((v - mu) / sd) for v in obs]
        mask, qs = bh_fdr(ps, 0.05)
        self.notes.append(f"零分布间隔方差均值={mu:.3f} (几何理论 12.0)")
        self.add(fam, "逐球间隔方差 (族内 BH)", f"通过 {sum(mask)}/80", min(qs))

    # ── 8. 和值条件偏向 (同条件 MC, 铁律 a) ──
    def family_sum_conditional(self):
        fam = "8 和值条件"
        sums = [sum(s) for s in self.draws]
        srt = sorted(sums)
        cuts = [srt[self.n // 5], srt[2 * self.n // 5], srt[3 * self.n // 5], srt[4 * self.n // 5]]
        def bin_of(v):
            for i, c in enumerate(cuts):
                if v <= c:
                    return i
            return 4
        obs_bin = [bin_of(v) for v in sums]
        lo = [self.draws[i] for i in range(self.n) if obs_bin[i] == 0]
        hi = [self.draws[i] for i in range(self.n) if obs_bin[i] == 4]
        null_lo, null_hi = Counter(), Counter()
        n_lo = n_hi = 0
        for _ in range(self.mc * 5):
            s = self.rng.sample(range(1, TOTAL_BALLS + 1), DRAW_BALLS)
            b = bin_of(sum(s))
            if b == 0:
                null_lo.update(s)
                n_lo += 1
            elif b == 4:
                null_hi.update(s)
                n_hi += 1
        ps = []
        for bb in range(1, TOTAL_BALLS + 1):
            o_lo = sum(1 for s in lo if bb in s) / len(lo)
            o_hi = sum(1 for s in hi if bb in s) / len(hi)
            c_lo = null_lo.get(bb, 0) / n_lo
            c_hi = null_hi.get(bb, 0) / n_hi
            se = sqrt(o_lo * (1 - o_lo) / len(lo) + o_hi * (1 - o_hi) / len(hi))
            ps.append(z2p(((o_lo - o_hi) - (c_lo - c_hi)) / se) if se else 1.0)
        mask, qs = bh_fdr(ps, 0.05)
        self.add(fam, "低/高和值分组偏移 (族内 BH)", f"通过 {sum(mask)}/80", min(qs))

    # ── 9. 盘面极值 ──
    def family_extremes(self):
        fam = "9 盘面极值"
        null = []
        for _ in range(self.mc):
            s = self.rng.sample(range(1, TOTAL_BALLS + 1), DRAW_BALLS)
            null.append((min(s), max(s), max(s) - min(s)))
        for idx, name in [(0, "最小号"), (1, "最大号"), (2, "跨度")]:
            o = statistics.mean(min(r[2]) if idx == 0 else (max(r[2]) if idx == 1 else max(r[2]) - min(r[2])) for r in self.rows)
            mu = statistics.mean(v[idx] for v in null)
            sd = statistics.pstdev(v[idx] for v in null)
            self.add(fam, f"{name}均值", f"实测{o:.3f}/理论{mu:.3f}", z2p((o - mu) / (sd / sqrt(self.n))))

    def run(self):
        for fn in (self.family_period_structure, self.family_positional, self.family_calendar,
                   self.family_pairwise, self.family_transition, self.family_lag_persistence,
                   self.family_gap_dispersion, self.family_sum_conditional, self.family_extremes):
            fn()
        return self.findings


def main() -> int:
    ap = argparse.ArgumentParser(description="快乐8 正交假设族筛查")
    ap.add_argument("--report", action="store_true", help="另存 MD 记录")
    ap.add_argument("--mc", type=int, default=20000, help="MC 次数 (默认 20000)")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    raw = os.path.join(_PROJ_DIR, "storage", "raw", "kl8_history_final.txt")
    rows = load_raw(raw)
    sc = Screen(rows, mc=args.mc)
    print(f"样本 {len(rows)} 期（{rows[0][0]} ~ {rows[-1][0]}）\n")
    findings = sc.run()

    print(f"{'族':<14}{'检验项':<34}{'统计量':<40}{'p':>10}")
    print("-" * 100)
    surv = 0
    for fam, name, stat, p, _ in findings:
        flag = "✅" if p < 0.05 else ""
        print(f"{fam:<14}{name:<34}{stat:<40}{p:>10.4f} {flag}")
        surv += 1 if p < 0.05 else 0
    print("-" * 100)
    print(f"未校正 p<0.05 的检验项: {surv}/{len(findings)}（族内多数已含 BH，需按族阅读）")
    for nt in sc.notes:
        print("  · " + nt)

    if args.report:
        out_dir = os.path.join(_PROJ_DIR, "storage", "outputs", "reports")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"假设族筛查_{datetime.now().strftime('%Y%m%d')}.md")
        L = [f"# 快乐8 正交假设族筛查记录（{len(rows)} 期，{rows[0][0]}~{rows[-1][0]}）", "",
             "> 口径：每族内做 BH-FDR 校正；矩阵族为全族一次性 BH。", "> 零假设构造三铁律见 `scripts/kl8_hypothesis_screening.py` 文件头。", "",
             "| 族 | 检验项 | 统计量 | p |", "| :--- | :--- | :--- | ---: |"]
        for fam, name, stat, p, _ in findings:
            L.append(f"| {fam} | {name} | {stat} | {p:.4f} |")
        L.append("")
        for nt in sc.notes:
            L.append(f"- {nt}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")
        print(f"\n📄 记录已写入: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())