# -*- coding: utf-8 -*-
"""双层LSTM 逐期回填复盘:
对最近 N 个历史目标期,每期只用"该期之前"的开奖训练并预测(无未来泄露),
重建 history-only 的 prediction_<period>.txt,供 review_recent 复盘命中率。
用法: python backfill_daily.py [N=12]
"""
import os, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import config
from config import SEED_BASE
from core.data_loader import load_history
from core.feature_engine import build_dataset
from core.trainer import train
from core.lstm_model import DoubleLSTM
from core.predictor import predict_with_model


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    draws = load_history()
    m = len(draws)
    print(f"共 {m} 期, 回填最近 {n} 个历史目标期(每期仅用该期之前数据)")
    done = 0
    for i in range(m - n, m):
        period = draws[i].period
        history = draws[:i]          # 不含目标期自身 → 无未来泄露
        ds = build_dataset(history)
        if ds is None:
            print(f"  [{i}] {period} 样本不足,跳过")
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
            print(f"  [{i}] 期{period} ✅ Top10: {'-'.join(f'{x:02d}' for x in info['top10'])}")
            done += 1
    print(f"完成回填 {done} 期")


if __name__ == "__main__":
    main()