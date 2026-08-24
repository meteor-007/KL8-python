# -*- coding: utf-8 -*-
"""预测器:加载 best_model -> 目标期概率 -> 金银铜/Top10 -> prediction_<期号>.txt
   并输出近10期实测复盘仪表盘数据(供 main 打印)。"""
import os, re, glob
import numpy as np
import torch
import config
from .lstm_model import DoubleLSTM
from .feature_engine import recent_features, draw_vector, zone_counts, tail_counts


def _load_model():
    fp = os.path.join(config.MODEL_DIR, "best_model.pt")
    ck = torch.load(fp, map_location="cpu")
    mdl = DoubleLSTM()
    mdl.load_state_dict(ck["state"])
    mdl.eval()
    return mdl, ck


def predict_with_model(draws, target_period, mdl, ck, seed=None, save=True):
    """用内存中的模型预测目标期并(可选)落盘。供每日预测与逐期回填复用。"""
    x = recent_features(draws)
    if x is None:
        return None
    with torch.no_grad():
        ball, zone, tail = mdl(torch.from_numpy(x[None]))
    p = ball[0].numpy()
    z_adj = np.clip(zone[0].numpy() * 4.0, 1.0 - 0.04, 1.0 + 0.04)
    t_adj = np.clip(tail[0].numpy() * 2.0, 1.0 - 0.04, 1.0 + 0.04)
    zone_mult = np.array([z_adj[(n - 1) // 10] for n in range(1, 81)])
    tail_mult = np.array([t_adj[n % 10] for n in range(1, 81)])
    fused = p * zone_mult * tail_mult
    order = np.argsort(-fused)
    top10 = [int(x) + 1 for x in order[:10]]
    dan = [int(x) + 1 for x in order[:3]]
    prob_map = {int(x) + 1: float(fused[x]) for x in order[:20]}
    consistency = float(np.clip(1.0 - np.std(p) * 12.0, 0.0, 1.0))
    info = {"period": target_period, "gold": dan[0], "silver": dan[1], "bronze": dan[2],
            "top10": top10, "consistency": consistency, "prob_range": float(round(p[order[0]] - p[order[-1]], 4)),
            "val_loss": float(ck["val_loss"]), "best_epoch": ck["best_epoch"], "epochs": ck["epochs"],
            "seed": seed}
    if save:
        save_prediction(info)
    return info


def predict_target(draws, target_period, seed=None):
    mdl, ck = _load_model()
    return predict_with_model(draws, target_period, mdl, ck, seed=seed, save=True)


def save_prediction(info):
    os.makedirs(config.PRED_DIR, exist_ok=True)
    fname = os.path.join(config.PRED_DIR, f"prediction_{info['period']}.txt")
    lines = [
        "=" * 64,
        "  双层LSTM快乐8分区分析预测 V3.3 (每日重建版 v2)",
        "=" * 64,
        f"  预测期号: {info['period']}",
        f"  💎 金胆: {info['gold']:02d}  🥈 银胆: {info['silver']:02d}  🥉 铜胆: {info['bronze']:02d}",
        f"  Top10: {'-'.join(f'{x:02d}' for x in info['top10'])}",
        f"  一致性评分: {info['consistency']:.2f} | 验证Loss: {info['val_loss']:.6f} | 训练种子: {info['seed']}",
        f"  Top10概率极差: {info['prob_range']:.4f}",
    ]
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return fname


def review_recent(draws, n=10):
    """读取历史 prediction_<period>.txt 并与实际开奖对账。"""
    hist_map = {d.period: d.set for d in draws}
    rows = []
    for fp in sorted(glob.glob(os.path.join(config.PRED_DIR, "prediction_*.txt")),
                     key=lambda s: int(re.search(r"(\d{7})", s).group(1)))[-n:]:
        m = re.search(r"(\d{7})", os.path.basename(fp))
        target = m.group(1)
        txt = open(fp, encoding="utf-8").read()
        gm = re.search(r"金胆: (\d+)", txt)
        g = int(gm.group(1)) if gm else None
        t10 = [int(x) for x in re.findall(r"Top10: ([\d\-]+)", txt)[0].split("-")] if "Top10:" in txt else []
        if target in hist_map and t10:
            hit = len(set(t10) & hist_map[target])
            rows.append({"target": target, "hit": hit, "gold": g,
                         "gold_hit": bool(g and g in hist_map[target])})
    return rows


def format_review(rows):
    if not rows:
        return "  无历史预测可供复盘"
    tot = sum(r["hit"] for r in rows)
    n = len(rows)
    gld = sum(1 for r in rows if r["gold_hit"])
    lines = [f"  近{n}期 Top10 均命中 {tot/n:.2f}/10 | Lift={(tot/n)/2.5:.2f}x | 金胆命中 {gld}/{n}",
             "  期号        Top10命中    金胆"]
    for r in rows:
        flag = "✅" if r["gold_hit"] else "❌"
        lines.append(f"  {r['target']}      {r['hit']}/10        {flag}")
    return "\n".join(lines)