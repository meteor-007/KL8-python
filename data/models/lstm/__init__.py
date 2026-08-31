# -*- coding: utf-8 -*-
"""
双层LSTM 深度学习子系统
======================
基于 PyTorch 的双层 LSTM 时序建模与多任务输出架构。
"""
from .config import SEQ_LEN, NUM_CLASSES, HIDDEN, LAYERS, DROPOUT, LR, EPOCHS, BATCH
from .data_loader import KL8Draw, load_history, get_latest
from .period_utils import parse_period, next_period, diff_period
from .feature_engine import draw_vector, zone_counts, tail_counts, build_dataset, recent_features
from .lstm_model import DoubleLSTM, count_params
from .trainer import train
from .predictor import predict_target, predict_with_model, save_prediction, review_recent, format_review
from .backfill import run_backfill
from .lstm_service import LSTMService

__all__ = [
    "SEQ_LEN", "NUM_CLASSES", "HIDDEN", "LAYERS", "DROPOUT", "LR", "EPOCHS", "BATCH",
    "KL8Draw", "load_history", "get_latest",
    "parse_period", "next_period", "diff_period",
    "draw_vector", "zone_counts", "tail_counts", "build_dataset", "recent_features",
    "DoubleLSTM", "count_params",
    "train",
    "predict_target", "predict_with_model", "save_prediction", "review_recent", "format_review",
    "run_backfill",
    "LSTMService"
]
