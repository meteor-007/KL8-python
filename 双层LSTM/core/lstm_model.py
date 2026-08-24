# -*- coding: utf-8 -*-
"""双层LSTM + 多头输出(球号/分区/尾数)。"""
import torch
import torch.nn as nn


class DoubleLSTM(nn.Module):
    def __init__(self, n_in=80, hidden=64, layers=2, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(n_in, hidden, num_layers=layers,
                            batch_first=True, dropout=dropout if layers > 1 else 0.0)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.head_ball = nn.Linear(hidden, 80)
        self.head_zone = nn.Linear(hidden, 8)
        self.head_tail = nn.Linear(hidden, 10)

    def forward(self, x):
        # x: (B, T, 80)
        out, _ = self.lstm(x)                    # (B, T, H)
        h = out.transpose(1, 2)                   # (B, H, T)
        h = self.pool(h).squeeze(-1)              # (B, H)
        ball = torch.sigmoid(self.head_ball(h))
        zone = torch.sigmoid(self.head_zone(h))
        tail = torch.sigmoid(self.head_tail(h))
        return ball, zone, tail


def test_load():
    return DoubleLSTM()


def count_params(m):
    return sum(p.numel() for p in m.parameters() if p.requires_grad)