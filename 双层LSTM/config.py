# -*- coding: utf-8 -*-
"""双层LSTM V3.3 — 每日重建版(v2 2026-08-24,原代码被清空后重新实现)
精简功能版:数据加载/特征/双LSTM训练/预测/复盘,输出格式与原版兼容。
仅依赖 stdlib+numpy+torch,只读共享 data/kl8_history_final.txt。
"""
import os

PROJ = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(os.path.dirname(PROJ), "data")

HISTORY_FILE = os.path.join(DATA_ROOT, "kl8_history_final.txt")
PRED_DIR = os.path.join(PROJ, "outputs", "predictions")
REPORT_DIR = os.path.join(PROJ, "outputs", "reports")
LOG_DIR = os.path.join(PROJ, "logs")
MODEL_DIR = os.path.join(PROJ, "outputs", "models")

SEQ_LEN = 30          # 序列长度
NUM_CLASSES = 80      # 1-80
HIDDEN = 64           # 双层LSTM隐藏
LAYERS = 2
DROPOUT = 0.3
LR = 5e-4
EPOCHS = 8
BATCH = 16
IN_BALLS = 20
VAL_SPLIT = 0.15

SEED_BASE = 2080      # 种子 = SEED_BASE + period_index(复现用)

for d in (PRED_DIR, REPORT_DIR, LOG_DIR, MODEL_DIR):
    os.makedirs(d, exist_ok=True)