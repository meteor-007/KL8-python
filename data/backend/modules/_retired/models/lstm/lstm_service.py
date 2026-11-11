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
        epochs: Optional[int] = None,
        respect_retirement: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        全量训练双层LSTM并预测目标期

        退役门控 (2026-10-22 Bug#10 修正版)：注册表 status=retired 时默认不训练、
        不落盘当期预测文件，避免退役模块的当期票面污染收割器与看板。

        分层说明：门控属于「出号策略」，应放在**生产入口**；本方法是可被直接调用的
        引擎 API，单元测试需要能独立验证模型本身。故提供 `respect_retirement=False`
        供测试/科研显式绕过策略层（生产调用方一律用默认 True，不受影响）。
        """
        if respect_retirement and LSTMService._is_retired():
            return None
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
    def _is_retired() -> bool:
        """读取注册表判决：退役则任何入口都不再产出当期票面。

        2026-10-22 缺陷修复 (Bug#10)：此前退役守门只写在 full_report_engine 的
        日报分支里，`run_daily_pipeline()`（Web 任务入口 run_lstm_daily.py 走这里）
        与 `train_and_predict()` 均未守门 —— 实测在模块已判 retired 之后，
        storage/outputs/reports/lstm_analysis_report_2026281.md 仍被继续生成，
        退役模块的当期产物继续污染收割器与看板。现在把门控下沉到服务层单一事实来源，
        无论从哪个入口调用都不再产票（需要复现历史档案时显式走 archive 流程）。
        """
        try:
            from backend.core.module_gate import ModuleGate
            return ModuleGate().status_of("lstm") == "retired"
        except Exception:
            # 注册表不可读时按退役处理（保守优先：宁可不出票，不可污染当期推荐）
            return True

    @staticmethod
    def run_daily_pipeline(backfill_n: int = 10, verbose: bool = True) -> Dict[str, Any]:
        """
        每日全流程一键调度：
        1. 预检数据
        2. 无泄露回填最近 N 期历史
        3. 全量训练与目标期预测
        4. 统计复盘数据
        5. 生成独立报告与落盘

        退役门控：注册表 status=retired 时直接短路返回，不训练、不落盘、不产票。
        """
        if LSTMService._is_retired():
            msg = ("双层LSTM 注册表 status=`retired`（无出号表决权）：本次不训练、不落盘当期研报与票面。"
                   "如需复现历史档案，请显式改注册表判决或走 archive 流程。")
            if verbose:
                print(f"  ⛔ {msg}")
            return {"prediction": None, "review_rows": [], "review_text": msg,
                    "report_path": None, "skipped": "retired"}

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
            print(f"  📊 时序宏观概率前3: {info['gold']:02d}, {info['silver']:02d}, {info['bronze']:02d} (仅供后台宏观参考，不作为推荐金银胆)")
            print(f"  🎯 宏观时序Top10: {'-'.join(f'{x:02d}' for x in info['top10'])}")
            print(f"  📈 一致性评分: {info['consistency']:.2f} | 验证Loss: {info['val_loss']:.6f} | 参数量: {info.get('params', 0):,}")
            print("\n" + review_text)

        # 4. 生成独立报告
        report_path = None
        if info:
            report_path = LSTMService.generate_report(target, info, review_rows)
            if verbose:
                print(f"\n  📄 双层LSTM 每日宏观分析报告已落盘: {report_path}")

        return {
            "prediction": info,
            "review_rows": review_rows,
            "review_text": review_text,
            "report_path": report_path
        }

    @staticmethod
    def generate_report(target: str, info: Dict[str, Any], review_rows: List[Dict[str, Any]]) -> str:
        """生成并保存独立的 LSTM 研报

        退役门控：注册表 status=retired 时不再落盘当期研报（避免退役产物污染收割/看板）。
        """
        if LSTMService._is_retired():
            return ""
        os.makedirs(config.REPORT_DIR, exist_ok=True)
        fp = os.path.join(config.REPORT_DIR, f"lstm_analysis_report_{target}.md")
        lines = [
            f"# 双层LSTM 快乐8 深度学习宏观分析报告 (期号: {target})",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 一、🔬 【后台辅助宏观参考】双层LSTM 时序模型概率输出",
            "> **老派操盘手大白话提示**：双层LSTM仅作为时序概率辅助指标在后台观察，已彻底剥夺出号表决权（防追热过拟合），不作为推荐下注依据。",
            f"- **目标预测期号:** {target}",
            f"- **📊 宏观时序概率前3位 (非推荐胆码):** {info['gold']:02d}, {info['silver']:02d}, {info['bronze']:02d}",
            f"- **📊 宏观时序概率 Top 10:** {' - '.join(f'{x:02d}' for x in info['top10'])}",
            f"- **📋 宏观时序概率 Top 20:** {' - '.join(f'{x:02d}' for x in info['top20'])}",
            f"- **指标质量:** 一致性评分 {info['consistency']:.2f} | 验证集Loss {info['val_loss']:.6f} | 最佳轮次 {info['best_epoch']}/{info['epochs']}",
            "",
            "## 二、历史实测命中率复盘 (近10期对账)",
            format_review(review_rows),
            ""
        ]
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return fp
