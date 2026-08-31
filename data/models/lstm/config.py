# -*- coding: utf-8 -*-
"""
双层LSTM 深度学习子系统 — 模块配置 (Integration Version)
=====================================================
统一接入主系统 data，路径自动锚定，支持超参数与缓存管理。
"""
import os
import sys

# 导入主系统统一路径工具
try:
    from utils.paths import get_project_root, data_path
    DATA_ROOT = get_project_root()
except Exception:
    DATA_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

# 核心数据文件
HISTORY_FILE = os.path.join(DATA_ROOT, "kl8_history_final.txt")

# 输出与缓存路径
PRED_DIR = os.path.join(DATA_ROOT, "outputs", "predictions")
REPORT_DIR = os.path.join(DATA_ROOT, "outputs", "reports")
LOG_DIR = os.path.join(DATA_ROOT, "logs")
MODEL_DIR = os.path.join(DATA_ROOT, "cache", "models")

# 模型与训练超参数
SEQ_LEN = 30          # 滑动窗口序列长度（看过去30期）
NUM_CLASSES = 80      # 快乐8号码总数 1-80
HIDDEN = 64           # 双层LSTM隐藏层单元数
LAYERS = 2            # LSTM堆叠层数
DROPOUT = 0.3         # 随机失活率（防止过拟合/死记硬背）
LR = 5e-4             # 学习率（步长大小）
EPOCHS = 8            # 训练轮数（刷题次数）
BATCH = 16            # 批大小
IN_BALLS = 20         # 每期开奖球数
VAL_SPLIT = 0.15      # 验证集切分比例

SEED_BASE = 2080      # 随机种子基数（保证结果可复现）

# 自动创建必要目录
for d in (PRED_DIR, REPORT_DIR, LOG_DIR, MODEL_DIR):
    os.makedirs(d, exist_ok=True)
