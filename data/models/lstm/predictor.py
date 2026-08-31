# -*- coding: utf-8 -*-
"""
双层LSTM 预测器与实测复盘模块 (Predictor & Review)
=================================================
- 概率融合: 球号网络输出 (p_ball) * 分区调节系数 (zone_adj) * 尾数调节系数 (tail_adj)
- 核心指标:
  * 💎金胆 / 🥈银胆 / 🥉铜胆 (Top 3 核心号)
  * 🚀Top10 / Top20 优选梯队
  * 一致性评分 (Consistency Score)
  * Top10 概率极差 (Probability Range)
- 复盘对账: 自动对齐实际开奖，计算 Top10 命中均值、金胆命中率、Lift(相对随机基线倍数)
"""
import os
import re
import glob
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import torch

from . import config
from .lstm_model import DoubleLSTM
from .data_loader import KL8Draw
from .feature_engine import recent_features


def _load_model() -> Tuple[DoubleLSTM, Dict[str, Any]]:
    """加载已持久化的最佳模型权重"""
    candidate_paths = [
        os.path.join(config.MODEL_DIR, "best_model.pt"),
        os.path.join(config.DATA_ROOT, "outputs", "models", "best_model.pt"),
    ]
    fp = None
    for p in candidate_paths:
        if os.path.exists(p):
            fp = p
            break

    if fp is None:
        raise FileNotFoundError(f"未找到可用的模型权重文件: {candidate_paths}")

    ck = torch.load(fp, map_location="cpu")
    mdl = DoubleLSTM(config.NUM_CLASSES, config.HIDDEN, config.LAYERS, config.DROPOUT)
    mdl.load_state_dict(ck["state"])
    mdl.eval()
    return mdl, ck


def predict_with_model(
    draws: List[KL8Draw],
    target_period: str,
    mdl: DoubleLSTM,
    ck: Dict[str, Any],
    seed: Optional[int] = None,
    save: bool = True
) -> Optional[Dict[str, Any]]:
    """
    使用模型对指定目标期进行多维推理
    """
    x = recent_features(draws)
    if x is None:
        return None

    device = next(mdl.parameters()).device
    inp = torch.from_numpy(x[None]).to(device)

    mdl.eval()
    with torch.no_grad():
        ball, zone, tail = mdl(inp)

    p = ball[0].cpu().numpy()
    z_raw = zone[0].cpu().numpy()
    t_raw = tail[0].cpu().numpy()

    # 区间与尾数微调因子 (限制在 ±4% 波动)
    z_adj = np.clip(z_raw * 4.0, 1.0 - 0.04, 1.0 + 0.04)
    t_adj = np.clip(t_raw * 2.0, 1.0 - 0.04, 1.0 + 0.04)

    zone_mult = np.array([z_adj[(n - 1) // 10] for n in range(1, 81)])
    tail_mult = np.array([t_adj[n % 10] for n in range(1, 81)])

    fused = p * zone_mult * tail_mult
    order = np.argsort(-fused)

    top10 = [int(n) + 1 for n in order[:10]]
    top20 = [int(n) + 1 for n in order[:20]]
    dan = [int(n) + 1 for n in order[:3]]

    prob_map = {int(n) + 1: float(fused[n]) for n in order}
    consistency = float(np.clip(1.0 - np.std(p) * 12.0, 0.0, 1.0))
    prob_range = float(round(float(p[order[0]] - p[order[-1]]), 4))

    val_loss = float(ck.get("val_loss", 0.0))
    best_epoch = int(ck.get("best_epoch", 0))
    epochs = int(ck.get("epochs", config.EPOCHS))

    info = {
        "period": str(target_period).strip(),
        "gold": dan[0],
        "silver": dan[1],
        "bronze": dan[2],
        "top3": dan,
        "top10": top10,
        "top20": top20,
        "prob_map": prob_map,
        "consistency": consistency,
        "prob_range": prob_range,
        "val_loss": val_loss,
        "best_epoch": best_epoch,
        "epochs": epochs,
        "seed": seed
    }

    if save:
        save_prediction(info)

    return info


def predict_target(
    draws: List[KL8Draw],
    target_period: str,
    seed: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """加载已存权重并预测目标期"""
    mdl, ck = _load_model()
    return predict_with_model(draws, target_period, mdl, ck, seed=seed, save=True)


def save_prediction(info: Dict[str, Any]) -> str:
    """将单期预测结果写入 outputs/predictions/prediction_<期号>.txt"""
    os.makedirs(config.PRED_DIR, exist_ok=True)
    fname = os.path.join(config.PRED_DIR, f"prediction_{info['period']}.txt")
    lines = [
        "=" * 64,
        "  双层LSTM快乐8分区分析预测 V3.3 (工业级整合版)",
        "=" * 64,
        f"  预测期号: {info['period']}",
        f"  💎 金胆: {info['gold']:02d}  🥈 银胆: {info['silver']:02d}  🥉 铜胆: {info['bronze']:02d}",
        f"  Top10: {'-'.join(f'{x:02d}' for x in info['top10'])}",
        f"  一致性评分: {info['consistency']:.2f} | 验证Loss: {info['val_loss']:.6f} | 训练种子: {info.get('seed', 'N/A')}",
        f"  Top10概率极差: {info['prob_range']:.4f}",
    ]
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return fname


def review_recent(draws: List[KL8Draw], n: int = 10) -> List[Dict[str, Any]]:
    """
    读取 outputs/predictions/prediction_*.txt 历史预测文件，并与实际开奖对账
    """
    hist_map = {d.period: d.set for d in draws}
    rows = []
    pattern = os.path.join(config.PRED_DIR, "prediction_*.txt")
    files = sorted(
        glob.glob(pattern),
        key=lambda s: int(re.search(r"(\d{7})", os.path.basename(s)).group(1))
        if re.search(r"(\d{7})", os.path.basename(s)) else 0
    )

    for fp in files[-n:]:
        m = re.search(r"(\d{7})", os.path.basename(fp))
        if not m:
            continue
        target = m.group(1)
        if target not in hist_map:
            continue

        try:
            with open(fp, "r", encoding="utf-8") as f:
                txt = f.read()
        except Exception:
            continue

        gm = re.search(r"金胆:\s*(\d+)", txt)
        g = int(gm.group(1)) if gm else None
        
        t10 = []
        mt = re.search(r"Top10:\s*([0-9\-]+)", txt)
        if mt:
            t10 = [int(x) for x in mt.group(1).split("-") if x.isdigit()]

        if t10 and target in hist_map:
            actual_set = hist_map[target]
            hit = len(set(t10) & actual_set)
            rows.append({
                "target": target,
                "hit": hit,
                "gold": g,
                "gold_hit": bool(g and g in actual_set),
                "top10": t10,
                "actual": sorted(actual_set)
            })

    rows.sort(key=lambda r: int(r["target"]))
    return rows


def format_review(rows: List[Dict[str, Any]]) -> str:
    """格式化近 N 期复盘对账报表"""
    if not rows:
        return "  ⚠️ 暂无历史预测落盘文件可供复盘"

    tot = sum(r["hit"] for r in rows)
    n = len(rows)
    avg_hit = tot / n
    lift = avg_hit / 2.5  # 随机基线: 10 * 20/80 = 2.5
    gld_hits = sum(1 for r in rows if r["gold_hit"])

    lines = [
        f"  📊 近 {n} 期 Top10 均命中 {avg_hit:.2f}/10 | Lift={lift:.2f}x | 💎金胆命中 {gld_hits}/{n} ({gld_hits/n*100:.0f}%)",
        "  " + "─" * 48,
        "   期号        Top10命中    金胆命中    Top10号码",
        "  " + "─" * 48
    ]
    for r in rows:
        flag = "✅ 命中" if r["gold_hit"] else "❌ 未中"
        t10_str = " ".join(f"{x:02d}" for x in r["top10"])
        lines.append(f"   {r['target']}      {r['hit']:>2}/10        {flag:<6}   {t10_str}")

    return "\n".join(lines)
