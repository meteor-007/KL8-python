# -*- coding: utf-8 -*-
"""
双层LSTM 核心服务门面 (LSTM Service Facade)
===========================================
为整个量化主系统提供统一、标准、优雅的深度学习调用入口。
支持单步预测、每日全流程编排、历史复盘查询与报告输出。
"""
import os
import sys
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import torch

from . import config
from .data_loader import KL8Draw, load_history, get_latest
from .period_utils import next_period
from .feature_engine import build_dataset
from .trainer import train
from .lstm_model import DoubleLSTM
from .predictor import predict_with_model, review_recent, format_review, save_prediction
from .backfill import run_backfill


class LSTMService:
    """双层LSTM 深度学习子系统服务类"""

    @staticmethod
    def precheck() -> Optional[Dict[str, Any]]:
        """数据预检：校验时效性与目标期号"""
        draws = load_history()
        latest = get_latest(draws)
        if not latest:
            return None
        target = next_period(latest.period)
        return {
            "latest_period": latest.period,
            "latest_date": latest.date,
            "target": target,
            "total_draws": len(draws)
        }

    @staticmethod
    def train_and_predict(
        draws: Optional[List[KL8Draw]] = None,
        target_period: Optional[str] = None,
        epochs: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        全量训练双层LSTM并预测目标期
        """
        if draws is None:
            draws = load_history()
        if not draws:
            return None

        if target_period is None:
            latest = get_latest(draws)
            target_period = next_period(latest.period) if latest else "2026001"

        ds = build_dataset(draws)
        if ds is None:
            return None

        (Xtr, yb, yz, yt), (Xva, vbb, vbz, vbt) = ds
        seed = config.SEED_BASE + (len(draws) % 1000)
        torch.manual_seed(seed)

        train_res = train(Xtr, yb, yz, yt, Xva, vbb, vbz, vbt, seed=seed, save=True, epochs=epochs)
        if train_res.get("best_state") is None:
            return None

        mdl = DoubleLSTM(config.NUM_CLASSES, config.HIDDEN, config.LAYERS, config.DROPOUT)
        mdl.load_state_dict(train_res["best_state"])
        ck = {
            "val_loss": train_res["val_loss"],
            "best_epoch": train_res["best_epoch"],
            "epochs": train_res["epochs"]
        }

        info = predict_with_model(draws, target_period, mdl, ck, seed=seed, save=True)
        if info:
            info["train_time"] = train_res["train_s"]
            info["params"] = train_res["params"]
        return info

    @staticmethod
    def run_daily_pipeline(backfill_n: int = 10, verbose: bool = True) -> Dict[str, Any]:
        """
        每日全流程一键调度：
        1. 预检数据
        2. 无泄露回填最近 N 期历史
        3. 全量训练与目标期预测
        4. 统计复盘数据
        5. 生成独立报告与落盘
        """
        pc = LSTMService.precheck()
        if not pc:
            raise RuntimeError("历史开奖数据为空或不可读取，无法执行双层LSTM分析")

        draws = load_history()
        target = pc["target"]

        if verbose:
            print("=" * 68)
            print(f"  🧠 双层LSTM 深度学习引擎 | 历史: {len(draws)}期 | 最新: {pc['latest_period']} | 目标: {target}")
            print("=" * 68)

        # 1. 回填近 N 期历史
        if backfill_n > 0:
            run_backfill(draws, n=backfill_n, verbose=verbose)

        # 2. 全量训练与目标期预测
        if verbose:
            print(f"\n  🚀 正在执行全量数据深度学习训练 (多任务复合损失)...")
        info = LSTMService.train_and_predict(draws, target)

        # 3. 复盘对账
        review_rows = review_recent(draws, n=max(10, backfill_n))
        review_text = format_review(review_rows)

        if verbose and info:
            print(f"  💎 金胆: {info['gold']:02d}  🥈 银胆: {info['silver']:02d}  🥉 铜胆: {info['bronze']:02d}")
            print(f"  🎯 Top10: {'-'.join(f'{x:02d}' for x in info['top10'])}")
            print(f"  📈 一致性评分: {info['consistency']:.2f} | 验证Loss: {info['val_loss']:.6f} | 参数量: {info.get('params', 0):,}")
            print("\n" + review_text)

        # 4. 生成独立报告
        report_path = None
        if info:
            report_path = LSTMService.generate_report(target, info, review_rows)
            if verbose:
                print(f"\n  📄 双层LSTM 每日分析报告已落盘: {report_path}")

        return {
            "prediction": info,
            "review_rows": review_rows,
            "review_text": review_text,
            "report_path": report_path
        }

    @staticmethod
    def generate_report(target: str, info: Dict[str, Any], review_rows: List[Dict[str, Any]]) -> str:
        """生成并保存独立的 LSTM 研报"""
        os.makedirs(config.REPORT_DIR, exist_ok=True)
        fp = os.path.join(config.REPORT_DIR, f"lstm_analysis_report_{target}.md")
        lines = [
            f"# 双层LSTM 快乐8 深度学习分析报告 (期号: {target})",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 一、AI 深度学习核心研判",
            f"- **目标预测期号:** {target}",
            f"- **💎 核心金胆:** {info['gold']:02d}",
            f"- **🥈 核心银胆:** {info['silver']:02d}",
            f"- **🥉 核心铜胆:** {info['bronze']:02d}",
            f"- **🚀 Top10 核心推荐:** {' - '.join(f'{x:02d}' for x in info['top10'])}",
            f"- **📋 Top20 扩充大名单:** {' - '.join(f'{x:02d}' for x in info['top20'])}",
            f"- **指标质量:** 一致性评分 {info['consistency']:.2f} | 验证集Loss {info['val_loss']:.6f} | 最佳轮次 {info['best_epoch']}/{info['epochs']}",
            "",
            "## 二、历史实测命中率复盘 (近10期对账)",
            format_review(review_rows),
            ""
        ]
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return fp
