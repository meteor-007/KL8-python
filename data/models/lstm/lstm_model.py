# -*- coding: utf-8 -*-
"""
双层LSTM + 多头输出网络架构 (Double LSTM Multi-Task Network)
===========================================================
- 结构: 双层长短期记忆网络 (LSTM Layers=2, Hidden=64)
- 池化: 自适应时序均值池化 (AdaptiveAvgPool1d)
- 多头输出 (Multi-Head Heads):
  1. 球号头 (head_ball): 80维多标签概率 (Sigmoid)
  2. 分区头 (head_zone): 8维区间密度 (Sigmoid)
  3. 尾数头 (head_tail): 10维尾数偏好 (Sigmoid)
"""
import torch
import torch.nn as nn


class DoubleLSTM(nn.Module):
    def __init__(self, n_in=80, hidden=64, layers=2, dropout=0.3):
        super().__init__()
        self.n_in = n_in
        self.hidden = hidden
        self.layers = layers
        self.dropout = dropout
        
        self.lstm = nn.LSTM(
            n_in, hidden,
            num_layers=layers,
            batch_first=True,
            dropout=dropout if layers > 1 else 0.0
        )
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.head_ball = nn.Linear(hidden, 80)
        self.head_zone = nn.Linear(hidden, 8)
        self.head_tail = nn.Linear(hidden, 10)

    def forward(self, x):
        """
        x: (Batch_Size, Time_Steps, 80) -> (B, T, 80)
        """
        out, _ = self.lstm(x)                    # (B, T, H)
        h = out.transpose(1, 2)                   # (B, H, T)
        h = self.pool(h).squeeze(-1)              # (B, H)
        ball = torch.sigmoid(self.head_ball(h))   # (B, 80)
        zone = torch.sigmoid(self.head_zone(h))   # (B, 8)
        tail = torch.sigmoid(self.head_tail(h))   # (B, 10)
        return ball, zone, tail


def count_params(m: nn.Module) -> int:
    """计算模型可训练参数总量"""
    return sum(p.numel() for p in m.parameters() if p.requires_grad)
