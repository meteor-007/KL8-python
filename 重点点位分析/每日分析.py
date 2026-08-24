# -*- coding: utf-8 -*-
"""
重点点位分析 快乐8 每日分析（重建版 2026-08-24）
================================================================
原系统 V6.0/V6.1 使用 GBDT + 微Hurst + 引力场等复杂特征栈，代码被清空后
无法还原；且其演化日志自证长期无信号（OOF AUC≈0.50，Top10 Lift 0.84~1.16x）。
按"过于复杂且无增益可移除"原则，本版改为透明可审计的简化点位打分：
  特征(全部可解释)：
    · 遗漏强度 gap —— 距上次开出间隔（越大越接近"回补"）
    · 冷热Z   freq —— 近20期出现次数 vs 全局期望
    · 邻区热度 reg —— 点位±1三号区近20期热度
    · 邻居引力 neb —— 点位±2邻域近20期热度
  点位得分 = 加权组合 → sigmoid 映射到 0.50~0.65（与原 raw_score 同尺度）
  p值      = 组合Z 的标准正态近似（stdlib math.erf，不依赖scipy）
结构保持与原系统一致：一级区域/二级精排Top10/Core5/扩展15/置信等级/近N期复盘。
数据: 只读共享 data/kl8_history_final.txt
用法: python 每日分析.py [N=30]
"""
import math, os, re, sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
HISTORY = os.path.join(ROOT, "data", "kl8_history_final.txt")
OUT_DIR = os.path.join(BASE, "output")
OUT_FILE = os.path.join(OUT_DIR, "重点点位预测.txt")

NUM = 80
WIN = 20                     # 热度窗口
LINE = "═" * 74
THIN = "─" * 74

W = {"gap": 0.35, "freq": 0.20, "reg": 0.25, "neb": 0.20}   # 特征权重
BASELINE_TOP10 = 0.25
BASELINE_CORE5 = 0.25
os.makedirs(OUT_DIR, exist_ok=True)


def comb(n, k):
    k = min(k, n - k)
    r = 1
    for i in range(k):
        r = r * (n - i) // (i + 1)
    return r


def region_baseline():
    return 1.0 - comb(77, 20) / comb(80, 20)   # P(3连号区至少一中) ≈0.5835


def load_draws():
    draws = []
    for line in open(HISTORY, encoding="utf-8"):
        m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line.strip())
        if not m:
            continue
        nums = set(int(x) for x in m.group(3).split("-") if x.isdigit())
        if len(nums) == 20:
            draws.append({"period": int(m.group(2)), "date": m.group(1), "nums": nums})
    draws.sort(key=lambda d: d["period"])
    return draws


def norm_z(vals):
    mu = sum(vals) / len(vals)
    sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
    return [(v - mu) / sd for v in vals]


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def daily_picks(draws, idx):
    """用 draws[:idx] 预测第 idx 期(不含自身, 无未来泄露)。返回推荐结构。"""
    hist_nums = [d["nums"] for d in draws[:idx]]
    n_hist = len(hist_nums)
    recent = range(max(0, n_hist - WIN), n_hist)

    def feats_of(n):
        appears = [i for i, s in enumerate(hist_nums) if n in s]
        gap = (n_hist - appears[-1]) if appears else n_hist
        freq = sum(1 for i in recent if n in hist_nums[i])
        reg = [(n - 2) % NUM + 1, n, n % NUM + 1]                 # n-1,n,n+1 环绕
        reg_h = sum(1 for i in recent for m in reg if m in hist_nums[i])
        neb = [(n + d - 1) % NUM + 1 for d in (1, 2)] + [(n - d - 1) % NUM + 1 for d in (1, 2)]
        neb_h = sum(1 for i in recent for m in neb if m in hist_nums[i])
        return gap, freq, reg_h, neb_h

    f = {n: feats_of(n) for n in range(1, NUM + 1)}
    gz = norm_z([f[n][0] for n in f])
    fz = norm_z([f[n][1] for n in f])
    rz = norm_z([f[n][2] for n in f])
    nz = norm_z([f[n][3] for n in f])

    pts = {}
    for n in range(1, NUM + 1):
        raw = W["gap"] * gz[n - 1] + W["freq"] * fz[n - 1] + W["reg"] * rz[n - 1] + W["neb"] * nz[n - 1]
        score = 0.5 + 0.15 * sigmoid(raw)
        pval = 0.5 * math.erfc(abs(raw) / math.sqrt(2))
        pts[n] = {"score": score, "p": pval, "region": [(n - 2) % NUM + 1, n, n % NUM + 1]}

    order = sorted(pts, key=lambda n: -pts[n]["score"])
    top_regions = [pts[n]["region"] for n in order[:10]]

    # 二级精排: 依序从点位区域取遗漏最大的号码, 去重直到集满10个
    best = {}
    for n in order:
        cand = sorted(pts[n]["region"], key=lambda m: -f[m][0])
        c = cand[0]
        best[c] = pts[n]["score"] * (1.0 + 0.5 * sigmoid(f[c][0] / 8.0))
        if len(best) >= 15:
            break
    ranked = sorted(best, key=lambda m: -best[m])
    ten = ranked[:10]
    core5 = ten[:5]
    ext15 = ranked[:15]

    zones = ["01-10", "11-20", "21-30", "31-40", "41-50", "51-60", "61-70", "71-80"]
    miss = [z for z in zones if not any(int(z.split("-")[0]) <= m <= int(z.split("-")[1]) for m in ten)]
    return {"pts": pts, "order": order, "top_regions": top_regions,
            "core5": core5, "ten": ten, "ext15": ext15, "miss": miss}


def oof_lift(draws, k=20):
    m = len(draws)
    lo = max(0, m - k)
    acc = 0.0
    n = 0
    for idx in range(lo, m):
        if idx < 2:
            continue
        p = daily_picks(draws, idx)
        acc += len(set(p["ten"]) & draws[idx]["nums"]) / 10.0
        n += 1
    if not n:
        return 0.0, 0.0, 0
    avg = acc / n
    return avg, avg / BASELINE_TOP10, n


def confidence_level(avg, n):
    """avg=近n期Top10平均命中率; 用二项近似做显著性检验, 防小样本虚高。"""
    if n <= 0:
        return "🔴 无置信 (Level 3) - 等权降级"
    p = BASELINE_TOP10
    se = (p * (1 - p) / 10) ** 0.5 / (n ** 0.5)      # 均值标准误(每期10码)
    z = (avg - p) / se if se else 0.0
    if avg / p >= 1.05 and z >= 1.64:
        return f"🟢 高置信 (Level 1)  (z={z:.2f})"
    if avg / p >= 1.00 and z >= 0.84:
        return f"🟡 中置信 (Level 2)  (z={z:.2f})"
    return f"🔴 无置信 (Level 3) - 等权降级 (z={z:.2f})"


def banner(txt):
    print("\n" + LINE)
    print("  " + txt)
    print(LINE)


def main():
    n_review = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    banner("重点点位分析 快乐8 每日分析  v2 (重建版 2026-08-24)")
    draws = load_draws()
    by = {d["period"]: d for d in draws}
    m = len(draws)
    latest = draws[-1]
    target = latest["period"] + 1
    print(f"  📁 历史 {m} 期 | 最新 {latest['period']} ({latest['date']}) | 🎯 目标 {target}")

    # ① 为最近 n_review 期 + 目标期 生成无泄露推荐
    lo = max(0, m - n_review)
    pred = {}
    for idx in range(lo, m):
        pred[draws[idx]["period"]] = daily_picks(draws, idx)
    pred[target] = daily_picks(draws, m)
    print(f"  ✅ 已生成 {len(pred)} 期推荐(仅用各期之前数据, 无泄露): "
          f"{min(pred)} ~ {max(pred)}")

    # ② 置信评估
    oof_avg, oof_lift_v, oof_n = oof_lift(draws, 20)
    lvl = confidence_level(oof_avg, oof_n)
    banner("② 置信评估 (walk-forward 近20期)")
    print(f"  Top10 均命中 {oof_avg*10:.2f} 码 | Lift={oof_lift_v:.3f}x (随机基线25%) | {lvl}")

    # ③ 今日预测展示
    p = pred[target]
    banner(f"③ 今日预测 {target}  (基于 {latest['period']} 之前数据)")
    print(f"  置信等级: {lvl} | OOF Lift: {oof_lift_v:.3f}x")
    print(f"  核心五码: {'-'.join('%02d' % x for x in p['core5'])}")
    print(f"  精选十码: {'-'.join('%02d' % x for x in p['ten'])}")
    print(f"  扩展十五: {'-'.join('%02d' % x for x in p['ext15'])}")
    print(f"  空间均衡: {'✅ 8区覆盖' if not p['miss'] else '缺失 ' + ' '.join(p['miss'])}")
    print("  " + THIN)
    print("  点位Top10 (区域/得分/p值):")
    for n in p["order"][:10]:
        r = p["pts"][n]
        sig = "✅显著" if r["p"] < 0.05 else "非显著"
        print(f"    点位[{n:02d}] 区域[{','.join('%02d' % x for x in r['region'])}] "
              f"得分:{r['score']:.4f} p:{r['p']:.4f} ({sig})")

    # ④ 近N期命中率复盘
    periods = [d["period"] for d in draws[-n_review:]]
    rows = []
    for per in periods:
        d, pk = by.get(per), pred.get(per)
        if not d or not pk:
            continue
        rows.append({"per": per, "ten": pk["ten"], "core5": pk["core5"],
                     "t10": len(set(pk["ten"]) & d["nums"]),
                     "c5": len(set(pk["core5"]) & d["nums"]),
                     "reg": sum(1 for r in pk["top_regions"] if d["nums"] & set(r))})
    banner(f"④ 近 {len(rows)} 期命中率复盘(随机基线: Top10/Core5=25%, 区域≈58.3%)")
    print("   期号     精选十码                 命中/10  Core5/5  区域")
    print("  " + THIN)
    for r in rows:
        ten_s = " ".join("%02d" % x for x in r["ten"])
        print(f"   {r['per']}   {ten_s:<26} {r['t10']:>3}/10   {r['c5']}/5   {r['reg']}/10")
    print("  " + THIN)
    n = len(rows)
    if n:
        t10 = sum(r["t10"] for r in rows) / n
        c5 = sum(r["c5"] for r in rows) / n
        rg = sum(r["reg"] for r in rows) / (n * 10)
        rb = region_baseline()
        def mark(v, base):
            return "✅" if v >= base * 1.05 else ("⚠️" if v >= base else "❌")
        print(f"  📊 Top10 均命中 {t10:.2f}/10 | Lift={t10/2.5:.2f}x {mark(t10/10, BASELINE_TOP10)}")
        print(f"     Core5 均命中 {c5:.2f}/5  | Lift={c5/1.25:.2f}x {mark(c5/5, BASELINE_CORE5)}")
        print(f"     区域命中率  {rg*100:.1f}%  | Lift={rg/rb:.2f}x {mark(rg, rb)} (随机基线{rb*100:.1f}%)")

    # ⑤ 对照: 原系统 2026218 记录
    old_ten = ["65", "34", "64", "05", "20", "24", "79", "35", "60", "67"]
    old_act = by.get(2026218)
    if old_act:
        ohit = len(set(int(x) for x in old_ten) & old_act["nums"])
        banner("⑤ 对照: 原系统2026218记录(代码清空前)精选十码 vs 实开")
        print(f"  原系统精选十码: {'-'.join(old_ten)}")
        print(f"  实开命中: {ohit}/10 (Lift={ohit/10/BASELINE_TOP10:.2f}x)")

    # ⑥ 落盘
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"重点点位分析 每日预测 {target} (重建版 {datetime.now():%Y-%m-%d %H:%M})\n")
        f.write(f"置信: {lvl} | OOF Lift: {oof_lift_v:.3f}x\n")
        f.write(f"核心五码: {'-'.join('%02d' % x for x in p['core5'])}\n")
        f.write(f"精选十码: {'-'.join('%02d' % x for x in p['ten'])}\n")
    print(f"\n  📄 预测落盘: {os.path.relpath(OUT_FILE, BASE)}")
    banner("完成 ✅")


if __name__ == "__main__":
    main()