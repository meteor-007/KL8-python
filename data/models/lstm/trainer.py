# -*- coding: utf-8 -*-
"""
双层LSTM 训练器模块 (Trainer Module)
==================================
- 优化器: Adam (自适应矩估计)
- 损失函数: 二元交叉熵 (BCE) + 分区均方误差 (MSE*0.3) + 尾数均方误差 (MSE*0.3)
- 早停机制: 基于验证集 Loss 自动追踪并保存最佳权重 (best_model.pt)
"""
import os
import time
from typing import Dict, Any, Optional
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

from . import config
from .lstm_model import DoubleLSTM, count_params


def train(
    Xtr: np.ndarray, ytr_b: np.ndarray, ytr_z: np.ndarray, ytr_t: np.ndarray,
    Xva: np.ndarray, yva_b: np.ndarray, yva_z: np.ndarray, yva_t: np.ndarray,
    seed: Optional[int] = None,
    save: bool = True,
    epochs: Optional[int] = None
) -> Dict[str, Any]:
    """
    执行双层LSTM模型训练与验证
    """
    epochs = epochs or config.EPOCHS
    seed_val = seed if seed is not None else config.SEED_BASE
    torch.manual_seed(seed_val)
    np.random.seed(seed_val)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    mdl = DoubleLSTM(config.NUM_CLASSES, config.HIDDEN, config.LAYERS, config.DROPOUT).to(device)
    opt = torch.optim.Adam(mdl.parameters(), lr=config.LR)
    bce = nn.BCELoss()
    mse = nn.MSELoss()

    ds = TensorDataset(
        torch.from_numpy(Xtr),
        torch.from_numpy(ytr_b),
        torch.from_numpy(ytr_z),
        torch.from_numpy(ytr_t)
    )
    dl = DataLoader(ds, batch_size=config.BATCH, shuffle=True)

    va_x = torch.from_numpy(Xva).to(device)
    va_b = torch.from_numpy(yva_b).to(device)
    va_z = torch.from_numpy(yva_z).to(device)
    va_t = torch.from_numpy(yva_t).to(device)

    best_val = 1e9
    best_state = None
    best_epoch = 0
    start = time.time()

    for ep in range(epochs):
        mdl.train()
        for Xb, b, z, t in dl:
            Xb, b, z, t = Xb.to(device), b.to(device), z.to(device), t.to(device)
            opt.zero_grad()
            pb, pz, pt = mdl(Xb)
            loss = bce(pb, b) + 0.3 * mse(pz, z) + 0.3 * mse(pt, t)
            loss.backward()
            opt.step()

        mdl.eval()
        with torch.no_grad():
            pb, pz, pt = mdl(va_x)
            val_loss = (bce(pb, va_b) + 0.3 * mse(pz, va_z) + 0.3 * mse(pt, va_t)).item()

        if val_loss < best_val - 1e-5:
            best_val = val_loss
            best_state = {k: v.cpu().clone() for k, v in mdl.state_dict().items()}
            best_epoch = ep + 1

    if best_state is not None:
        mdl.load_state_dict({k: v.to(device) for k, v in best_state.items()})

    total_params = count_params(mdl)
    train_sec = round(time.time() - start, 2)

    result = {
        "val_loss": float(best_val),
        "best_epoch": int(best_epoch),
        "epochs": int(epochs),
        "params": int(total_params),
        "train_s": train_sec,
        "best_state": best_state
    }

    if save and best_state is not None:
        save_dict = {
            "state": best_state,
            "best_epoch": best_epoch,
            "epochs": epochs,
            "val_loss": best_val,
            "params": total_params,
            "seed": seed_val
        }
        # 同时保存到 cache/models 与 outputs/models
        for target_dir in [config.MODEL_DIR, os.path.join(config.DATA_ROOT, "outputs", "models")]:
            os.makedirs(target_dir, exist_ok=True)
            save_path = os.path.join(target_dir, "best_model.pt")
            torch.save(save_dict, save_path)

    return result
