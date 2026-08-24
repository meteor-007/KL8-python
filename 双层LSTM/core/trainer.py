# -*- coding: utf-8 -*-
"""训练器:早停 + best_model.pt 落盘;输出验证Loss。"""
import os, time
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
import config
from .lstm_model import DoubleLSTM


def train(Xtr, ytr_b, ytr_z, ytr_t, Xva, yva_b, yva_z, yva_t, seed=None, save=True):
    torch.manual_seed(seed if seed is not None else 42)
    np.random.seed(seed if seed is not None else 42)
    mdl = DoubleLSTM(config.NUM_CLASSES, config.HIDDEN, config.LAYERS, config.DROPOUT)
    opt = torch.optim.Adam(mdl.parameters(), lr=config.LR)
    bce = nn.BCELoss()
    mse = nn.MSELoss()

    ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(ytr_b),
                       torch.from_numpy(ytr_z), torch.from_numpy(ytr_t))
    dl = DataLoader(ds, batch_size=config.BATCH, shuffle=True)
    va = (torch.from_numpy(Xva), torch.from_numpy(yva_b),
          torch.from_numpy(yva_z), torch.from_numpy(yva_t))

    best_val, best_state, best_epoch = 1e9, None, 0
    start = time.time()
    for ep in range(config.EPOCHS):
        mdl.train()
        for Xb, b, z, t in dl:
            opt.zero_grad()
            pb, pz, pt = mdl(Xb)
            loss = bce(pb, b) + 0.3 * mse(pz, z) + 0.3 * mse(pt, t)
            loss.backward()
            opt.step()
        mdl.eval()
        with torch.no_grad():
            pb, pz, pt = mdl(va[0])
            val_loss = (bce(pb, va[1]) + 0.3 * mse(pz, va[2]) + 0.3 * mse(pt, va[3])).item()
        if val_loss < best_val - 1e-5:
            best_val, best_state, best_epoch = val_loss, {k: v.clone() for k, v in mdl.state_dict().items()}, ep + 1
    mdl.load_state_dict(best_state)
    if save:
        os.makedirs(config.MODEL_DIR, exist_ok=True)
        torch.save({"state": best_state, "best_epoch": best_epoch, "epochs": config.EPOCHS,
                    "val_loss": best_val, "params": count(mdl)}, os.path.join(config.MODEL_DIR, "best_model.pt"))
    return {"val_loss": best_val, "best_epoch": best_epoch, "epochs": config.EPOCHS, "params": count(mdl),
            "train_s": round(time.time() - start, 1), "best_state": best_state}


def count(m):
    return sum(p.numel() for p in m.parameters() if p.requires_grad)