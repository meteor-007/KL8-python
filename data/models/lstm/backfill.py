# -*- coding: utf-8 -*-
"""
双层LSTM 历史回填复盘模块 (No-Leakage Backfill Engine)
======================================================
逐期严格基于【该期之前】的历史数据进行训练与预测，绝无未来函数，
用于生成干净可靠的历史预测记录，供实战复盘与收益率(Lift)对账。
"""
import os
import sys
from typing import List, Dict, Any, Optional
import torch

from . import config
from .data_loader import KL8Draw, load_history
from .feature_engine import build_dataset
from .trainer import train
from .lstm_model import DoubleLSTM
from .predictor import predict_with_model


def run_backfill(draws: Optional[List[KL8Draw]] = None, n: int = 12, verbose: bool = True) -> int:
    """
    对最近 n 期历史进行无未来泄露的回填训练与预测
    """
    if draws is None:
        draws = load_history()

    m = len(draws)
    if m <= config.SEQ_LEN + 2:
        if verbose:
            print("  ❌ 历史开奖期数过少，无法执行回填")
        return 0

    lo = max(config.SEQ_LEN + 2, m - n)
    if verbose:
        print(f"  🔄 启动双层LSTM无泄露回填: 覆盖近 {m - lo} 期历史...")

    done = 0
    for i in range(lo, m):
        period = draws[i].period
        history = draws[:i]  # 仅取该期之前的历史，确保绝无未来数据泄露

        ds = build_dataset(history)
        if ds is None:
            continue

        (Xtr, yb, yz, yt), (Xva, vbb, vbz, vbt) = ds
        seed = config.SEED_BASE + (len(history) % 1000)
        torch.manual_seed(seed)

        res = train(Xtr, yb, yz, yt, Xva, vbb, vbz, vbt, seed=seed, save=False)
        if res.get("best_state") is None:
            continue

        mdl = DoubleLSTM(config.NUM_CLASSES, config.HIDDEN, config.LAYERS, config.DROPOUT)
        mdl.load_state_dict(res["best_state"])
        ck = {
            "val_loss": res["val_loss"],
            "best_epoch": res["best_epoch"],
            "epochs": res["epochs"]
        }

        info = predict_with_model(history, period, mdl, ck, seed=seed, save=True)
        if info:
            done += 1
            if verbose and done % 5 == 0:
                print(f"    - 已回填期号 {period} | Top10: {'-'.join(f'{x:02d}' for x in info['top10'][:5])}...")

    if verbose:
        print(f"  ✅ 无未来泄露回填完成，共生成 {done} 期历史预测样本")
    return done


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    run_backfill(n=count, verbose=True)
