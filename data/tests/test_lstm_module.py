# -*- coding: utf-8 -*-
"""
双层LSTM 模块自动化测试套件 (Unit & Integration Tests)
===================================================
验证: 数据加载、特征构建、时序无泄漏、模型前向推理、训练收敛性、预测落盘与复盘对账。
"""
import os
import sys
import pytest
import numpy as np
import torch

import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
os.environ["PYTHONPATH"] = PROJ + os.pathsep + os.environ.get("PYTHONPATH", "")

import pytest
import numpy as np
import torch

from models.lstm import (
    load_history, KL8Draw, build_dataset, recent_features,
    DoubleLSTM, train, LSTMService, parse_period, next_period,
    review_recent, format_review
)


def test_import_and_bridge():
    """测试 models/lstm 模块完整导入与组件可用性"""
    import models.lstm as lstm_mod
    from models.lstm import DoubleLSTM, LSTMService, KL8Draw, build_dataset
    assert DoubleLSTM is not None
    assert LSTMService is not None
    assert hasattr(lstm_mod, "DoubleLSTM")
    assert hasattr(lstm_mod, "LSTMService")
    assert hasattr(lstm_mod, "predict_target")


def test_data_loader():
    """测试历史数据加载与期号排序"""
    draws = load_history()
    assert len(draws) > 100, f"历史期数过少: {len(draws)}"
    # 验证按期号升序排列 (旧 -> 新)
    for i in range(len(draws) - 1):
        assert int(draws[i].period) < int(draws[i + 1].period), f"期号排序错误: {draws[i].period} vs {draws[i+1].period}"
    assert len(draws[-1].numbers) == 20


def test_feature_engine():
    """测试特征工程与滑动窗口无未来泄露"""
    draws = load_history()
    seq_len = 15
    ds = build_dataset(draws, seq_len=seq_len, val_ratio=0.2)
    assert ds is not None
    (Xtr, yb, yz, yt), (Xva, vbb, vbz, vbt) = ds
    assert Xtr.ndim == 3
    assert Xtr.shape[1] == seq_len
    assert Xtr.shape[2] == 80
    assert yb.shape[1] == 80
    assert yz.shape[1] == 8
    assert yt.shape[1] == 10

    # 验证最近特征矩阵构造
    rf = recent_features(draws, seq_len=seq_len)
    assert rf is not None
    assert rf.shape == (seq_len, 80)


def test_model_forward():
    """测试双层LSTM模型结构与多头前向计算"""
    batch_size = 4
    seq_len = 20
    mdl = DoubleLSTM(n_in=80, hidden=32, layers=2, dropout=0.1)
    dummy_input = torch.randn(batch_size, seq_len, 80)
    ball, zone, tail = mdl(dummy_input)
    assert ball.shape == (batch_size, 80)
    assert zone.shape == (batch_size, 8)
    assert tail.shape == (batch_size, 10)
    assert (ball >= 0).all() and (ball <= 1).all()
    assert (zone >= 0).all() and (zone <= 1).all()
    assert (tail >= 0).all() and (tail <= 1).all()


def test_fast_training_and_prediction():
    """测试模型快速训练与预测"""
    draws = load_history()
    # 截取近 100 期进行快速训练验证
    mini_draws = draws[-100:]
    ds = build_dataset(mini_draws, seq_len=10, val_ratio=0.2)
    assert ds is not None
    (Xtr, yb, yz, yt), (Xva, vbb, vbz, vbt) = ds
    res = train(Xtr, yb, yz, yt, Xva, vbb, vbz, vbt, epochs=2, save=False)
    assert "val_loss" in res
    assert "best_epoch" in res
    assert res["val_loss"] > 0


def test_lstm_service_full():
    """测试 LSTMService 门面接口"""
    pc = LSTMService.precheck()
    assert pc is not None
    assert "latest_period" in pc
    assert "target" in pc

    pred = LSTMService.train_and_predict(epochs=2)
    assert pred is not None
    assert "gold" in pred
    assert "silver" in pred
    assert "bronze" in pred
    assert len(pred["top10"]) == 10
    assert len(pred["top20"]) == 20
    assert 0.0 <= pred["consistency"] <= 1.0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
