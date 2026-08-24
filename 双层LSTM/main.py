# -*- coding: utf-8 -*-
"""双层LSTM 主入口(full/predict/backtest/precheck)—— 每日重建版 v2。"""
import os, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SEED_BASE
from precheck import precheck
from core.data_loader import load_history
from core.feature_engine import build_dataset
from core.trainer import train
from core.predictor import predict_target, format_review, review_recent
import torch


def cmd_full():
    pc = precheck(verbose=False)
    if not pc or pc["target"] is None:
        print("❌ 数据不足/缺失,终止")
        return
    draws = load_history()
    print("═" * 64)
    print(f"  双层LSTM V3.3 每日重建版 v2 | 历史={len(draws)}期 | 目标={pc['target']}")
    print("═" * 64)
    ds = build_dataset(draws)
    if ds is None:
        print("❌ 样本不足,无法训练")
        return
    (Xtr, yb, yz, yt), (Xva, vbb, vbz, vbt) = ds
    seed = SEED_BASE + (len(draws) % 1000)
    torch.manual_seed(seed)
    print("🔄 训练中(纯深度学习,参数精简)...")
    res = train(Xtr, yb, yz, yt, Xva, vbb, vbz, vbt, seed=seed)
    print(f">>> [训练] 验证Loss={res['val_loss']:.6f} | 最佳Epoch {res['best_epoch']}/{res['epochs']} | 参数={res['params']} | 耗时{res['train_s']}s")
    info = predict_target(draws, pc["target"], seed=seed)
    print(f"💎 金胆: {info['gold']:02d}  🥈 银胆: {info['silver']:02d}  🥉 铜胆: {info['bronze']:02d}")
    print(f"🚀 Top10: {'-'.join(f'{x:02d}' for x in info['top10'])}")
    print(f"  一致性评分: {info['consistency']:.2f} | Top10极差: {info['prob_range']:.4f}")
    print("─" * 40)
    print("📈 近10期复盘(Lift相对随机基线25%):")
    print(format_review(review_recent(draws)))
    print("✅ 已完成,预测落盘 outputs/predictions/prediction_%s.txt" % pc["target"])


def cmd_predict():
    pc = precheck(verbose=False)
    draws = load_history()
    seed = SEED_BASE + (len(draws) % 1000)
    info = predict_target(draws, pc["target"], seed=seed)
    print(f"💎 {info['gold']:02d} 🥈{info['silver']:02d} 🥉{info['bronze']:02d} | Top10: {'-'.join(f'{x:02d}' for x in info['top10'])} | 一致性 {info['consistency']:.2f}")


def cmd_backtest(periods=10):
    draws = load_history()
    rows = review_recent(draws, n=periods)
    print(f"近{len(rows)}期 Top10 回测:")
    print(format_review(rows))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "precheck"
    if cmd == "full":
        cmd_full()
    elif cmd == "predict":
        cmd_predict()
    elif cmd == "backtest":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        cmd_backtest(n)
    elif cmd == "precheck":
        precheck()
    else:
        print("用法: python main.py [full|predict|backtest N|precheck]")