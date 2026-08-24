# -*- coding: utf-8 -*-
"""
双层LSTM 快乐8 每日分析（一键版 v2）
================================================
流程: ①数据预检(时效/目标期) → ②近N期无泄露回填(重算干净预测)
      → ③全量训练 → ④预测目标期 → ⑤近N期命中率复盘(Lift vs 随机基线25%)
      → ⑥结果落盘 outputs/predictions + outputs/reports
用法: python 每日分析.py [N=30]           # N=复盘期数,默认30
"""
import os, re, glob, sys, time
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from config import SEED_BASE
from precheck import precheck
from core.data_loader import load_history
from core.feature_engine import build_dataset
from core.trainer import train
from core.predictor import predict_with_model, save_prediction
from core.lstm_model import DoubleLSTM

import numpy as np
import torch

LINE = "═" * 72
THIN = "─" * 72


def banner(txt):
    print("\n" + LINE)
    print("  " + txt)
    print(LINE)


def step_backfill(draws, n):
    """逐期只回填【该期之前】的训练数据预测(无泄露),覆盖近n期 prediction_*.txt。"""
    m = len(draws)
    lo = max(0, m - n)
    done = 0
    banner(f"② 无泄露回填: 近 {n} 期(每期仅用该期之前数据训练/预测)")
    for i in range(lo, m):
        period = draws[i].period
        history = draws[:i]                     # 不含目标期自身 → 无未来泄露
        ds = build_dataset(history)
        if ds is None:
            continue
        (Xtr, yb, yz, yt), (Xva, vbb, vbz, vbt) = ds
        seed = SEED_BASE + (len(history) % 1000)
        torch.manual_seed(seed)
        res = train(Xtr, yb, yz, yt, Xva, vbb, vbz, vbt, seed=seed, save=False)
        mdl = DoubleLSTM(config.NUM_CLASSES, config.HIDDEN, config.LAYERS, config.DROPOUT)
        mdl.load_state_dict(res["best_state"])
        ck = {"val_loss": res["val_loss"], "best_epoch": res["best_epoch"], "epochs": res["epochs"]}
        info = predict_with_model(history, period, mdl, ck, seed=seed, save=True)
        if info:
            done += 1
    print(f"  ✅ 回填完成 {done} 期")
    return done


def step_predict(draws, target):
    """全量数据训练 → 目标期预测 → 落盘。"""
    banner("③④ 全量训练 + 目标期预测")
    ds = build_dataset(draws)
    if ds is None:
        print("  ❌ 样本不足,无法训练"); return None
    (Xtr, yb, yz, yt), (Xva, vbb, vbz, vbt) = ds
    seed = SEED_BASE + (len(draws) % 1000)
    torch.manual_seed(seed)
    t0 = time.time()
    res = train(Xtr, yb, yz, yt, Xva, vbb, vbz, vbt, seed=seed, save=True)
    print(f"  >> [训练] 验证Loss={res['val_loss']:.6f} | 最佳Epoch {res['best_epoch']}/{res['epochs']} "
          f"| 参数={res['params']} | 耗时{res['train_s']}s | 种子{seed}")
    torch.manual_seed(seed)
    mdl = DoubleLSTM(config.NUM_CLASSES, config.HIDDEN, config.LAYERS, config.DROPOUT)
    mdl.load_state_dict(res["best_state"])
    ck = {"val_loss": res["val_loss"], "best_epoch": res["best_epoch"], "epochs": res["epochs"]}
    info = predict_with_model(draws, target, mdl, ck, seed=seed, save=True)
    return info


def collect_review(draws, n):
    """读取近n期 prediction_*.txt 与实开奖对账 → 列表(无序)。"""
    hist_map = {d.period: d.set for d in draws}
    rows = []
    files = sorted(glob.glob(os.path.join(config.PRED_DIR, "prediction_*.txt")),
                   key=lambda s: int(re.search(r"(\d{7})", s).group(1)))[-n:]
    for fp in files:
        m = re.search(r"(\d{7})", os.path.basename(fp))
        target = m.group(1)
        if target not in hist_map:
            continue
        txt = open(fp, encoding="utf-8").read()
        gm = re.search(r"金胆: (\d+)", txt)
        g = int(gm.group(1)) if gm else None
        t10 = []
        mt = re.search(r"Top10: ([\d\-]+)", txt)
        if mt:
            t10 = [int(x) for x in mt.group(1).split("-")]
        if not t10:
            continue
        rows.append({"target": target, "hit": len(set(t10) & hist_map[target]),
                     "gold": g, "gold_hit": bool(g and g in hist_map[target]),
                     "top10": t10,
                     "act": sorted(hist_map[target])})
    rows.sort(key=lambda r: int(r["target"]))
    return rows


def show_review(rows):
    banner("⑤ 近 %d 期命中率复盘(随机基线: Top10均≈2.5/10=25%%)" % len(rows))
    if not rows:
        print("  ⚠️ 无历史预测可供复盘"); return
    n = len(rows)
    tot = sum(r["hit"] for r in rows)
    avg = tot / n
    lift = avg / 2.5
    gld_hit = sum(1 for r in rows if r["gold_hit"])
    print(f"  📊 Top10 均命中 {avg:.2f}/10 | Lift={lift:.2f}x {'✅超过基线' if lift>=1.05 else ('⚠️持平基线' if lift>=1.00 else '❌低于基线')} | 金胆命中 {gld_hit}/{n} ({gld_hit/n*100:.0f}%)")
    print("  " + THIN)
    print("   期号      实际20码(前12展示)                       Top10推荐                    命中/10  金胆")
    print("  " + THIN)
    for r in rows:
        act_str = " ".join(f"{x:02d}" for x in r["act"][:12]) + ("…" if len(r["act"]) > 12 else "")
        t10_str = " ".join(f"{x:02d}" for x in r["top10"])
        flag = "✅" if r["gold_hit"] else ("·" if r["hit"] >= 3 else "❌")
        print(f"   {r['target']}   {act_str:<28} {t10_str:<32} {r['hit']:>3}/10   {flag}")
    print("  " + THIN)
    # 近10段滚动
    win = min(10, n)
    recent = rows[-win:]
    ravg = sum(r["hit"] for r in recent) / len(recent)
    rlift = ravg / 2.5
    rg = sum(1 for r in recent if r["gold_hit"])
    print(f"  🕐 近{len(recent)}期滚动: Top10均命中 {ravg:.2f}/10 | Lift={rlift:.2f}x | 金胆 {rg}/{len(recent)}")
    # 连续命中>=3期次数(信号稳定性参考)
    c = 0
    for r in rows:
        if r["hit"] >= 3:
            c += 1
    print(f"  🎯 复盘期内 Top10≥3码头次数 {c}/{n} ({c/n*100:.0f}%)")


def report_save(target, info, rows):
    os.makedirs(config.REPORT_DIR, exist_ok=True)
    fp = os.path.join(config.REPORT_DIR, f"每日分析_{target}.txt")
    with open(fp, "w", encoding="utf-8") as f:
        f.write("双层LSTM 每日分析报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 64 + "\n")
        if info:
            f.write(f"目标期: {info['period']}\n")
            f.write(f"金胆: {info['gold']:02d} 银胆: {info['silver']:02d} 铜胆: {info['bronze']:02d}\n")
            f.write(f"Top10: {'-'.join(f'{x:02d}' for x in info['top10'])}\n")
            f.write(f"一致性: {info['consistency']:.2f} | 验证Loss: {info['val_loss']:.6f}\n")
            f.write("-" * 64 + "\n")
        f.write("近%d期命中率复盘:\n" % len(rows))
        for r in rows:
            f.write(f"  {r['target']} 命中{r['hit']}/10 金胆{'✅' if r['gold_hit'] else '❌'}\n")
        if rows:
            avg = sum(r["hit"] for r in rows) / len(rows)
            f.write(f"  Top10均命中 {avg:.2f}/10  Lift={avg/2.5:.2f}x (随机基线25%)\n")
    return fp


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    banner("双层LSTM 快乐8 每日分析  v2  (2026-08-24 重建)")
    pc = precheck(verbose=True)
    if not pc or pc["target"] is None:
        print("❌ 数据不足/缺失,终止"); return
    draws = load_history()
    print(f"  📁 载入 {len(draws)} 期历史 | 最新 {pc['latest_period']} ({pc['latest_date']}) | 🎯 目标 {pc['target']}")
    step_backfill(draws, n)
    info = step_predict(draws, pc["target"])
    if info:
        banner("💎 目标期推荐")
        print(f"  💎金胆 {info['gold']:02d}   🥈银胆 {info['silver']:02d}   🥉铜胆 {info['bronze']:02d}")
        print(f"  🚀 Top10:  {info['top10']}")
        print(f"     推荐码: {'-'.join(f'{x:02d}' for x in info['top10'])}")
        print(f"     一致性评分 {info['consistency']:.2f} | Top10概率极差 {info['prob_range']:.4f} | 验证Loss {info['val_loss']:.6f}")
    rows = collect_review(draws, n)
    show_review(rows)
    if info:
        rp = report_save(info["period"], info, rows)
        print(f"\n  📄 报告落盘: {os.path.relpath(rp, os.getcwd())}")
    banner("完成 ✅")


if __name__ == "__main__":
    main()