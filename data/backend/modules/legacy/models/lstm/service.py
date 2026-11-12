# -*- coding: utf-8 -*-
"""LstmServiceMixin: methods extracted from QuantDataService"""
from __future__ import annotations

import os
import sys
import re
import json
import glob
import math
import logging
import collections
from datetime import datetime
from typing import Dict, List, Any, Optional

from backend.utils.paths import (
    get_cache_dir, get_outputs_dir, get_reports_dir, get_reviews_dir,
    get_project_root, data_path, get_storage_dir, _ensure_project_path,
)

logger = logging.getLogger("k8quant.service")


class LstmServiceMixin:
    def get_lstm_summary(self) -> Dict[str, Any]:
        """获取双层LSTM深度学习最新预测与状态"""
        try:
            from models.lstm.lstm_service import LSTMService
            from models.lstm.predictor import predict_target, review_recent
            from models.lstm.data_loader import load_history as load_lstm_hist
            draws = load_lstm_hist()
            if not draws:
                return {"status": "error", "message": "历史开奖数据为空"}
            
            # 读取最新落盘的预测或重新快速推演
            pred_pattern = os.path.join(get_outputs_dir(), "predictions", "prediction_*.txt")
            pred_files = sorted(glob.glob(pred_pattern))
            latest_pred_info = None
            if pred_files:
                latest_fp = pred_files[-1]
                with open(latest_fp, "r", encoding="utf-8") as f:
                    txt = f.read()
                
                pm = re.search(r"预测期号:\s*(\d+)", txt)
                gm = re.search(r"金胆:\s*(\d+)\s+🥈\s*银胆:\s*(\d+)\s+🥉\s*铜胆:\s*(\d+)", txt)
                tm = re.search(r"Top10:\s*([\d\-]+)", txt)
                cm = re.search(r"一致性评分:\s*([\d\.]+)", txt)
                lm = re.search(r"验证Loss:\s*([\d\.]+)", txt)
                rm = re.search(r"Top10概率极差:\s*([\d\.]+)", txt)
                
                if pm and gm and tm:
                    t10 = [int(x) for x in tm.group(1).split("-") if x.isdigit()]
                    latest_pred_info = {
                        "period": pm.group(1),
                        "gold": int(gm.group(1)),
                        "silver": int(gm.group(2)),
                        "bronze": int(gm.group(3)),
                        "top10": t10,
                        "consistency": float(cm.group(1)) if cm else None,
                        "val_loss": float(lm.group(1)) if lm else None,
                        "prob_range": float(rm.group(1)) if rm else None
                    }
            
            # 补齐近10期对账
            review_rows = review_recent(draws, n=10)
            avg_hit = sum(r["hit"] for r in review_rows) / len(review_rows) if review_rows else None
            gold_hits = sum(1 for r in review_rows if r["gold_hit"]) if review_rows else 0
            
            return {
                "status": "ok",
                "prediction": latest_pred_info,
                "review_summary": {
                    "periods_count": len(review_rows),
                    "avg_hit": round(avg_hit, 2) if avg_hit is not None else None,
                    "lift": round(avg_hit / 2.5, 2) if avg_hit is not None else None,
                    "gold_hit_count": gold_hits,
                    "gold_hit_rate": round(gold_hits / max(len(review_rows), 1) * 100, 1)
                },
                "review_rows": review_rows
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_lstm_review(self, n: int = 15) -> Dict[str, Any]:
        """获取双层LSTM指定期数历史复盘"""
        try:
            from models.lstm.data_loader import load_history as load_lstm_hist
            from models.lstm.predictor import review_recent
            draws = load_lstm_hist()
            rows = review_recent(draws, n=n)
            avg_hit = sum(r["hit"] for r in rows) / len(rows) if rows else None
            gold_hits = sum(1 for r in rows if r["gold_hit"]) if rows else 0
            return {
                "status": "ok",
                "count": len(rows),
                "avg_hit": round(avg_hit, 2) if avg_hit is not None else None,
                "lift": round(avg_hit / 2.5, 2) if avg_hit is not None else None,
                "gold_hit_count": gold_hits,
                "rows": rows
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "rows": []}

    def get_lstm_reports_list(self) -> List[Dict[str, Any]]:
        """获取双层LSTM深度学习历史研报与预测文件清单"""
        results = []
        md_dir = os.path.join(get_outputs_dir(), "reports")
        txt_dir = os.path.join(get_outputs_dir(), "predictions")
        
        # 1. 扫描 MD 报告
        if os.path.exists(md_dir):
            for f in sorted(os.listdir(md_dir), reverse=True):
                if f.startswith("lstm_analysis_report_") and f.endswith(".md"):
                    path = os.path.join(md_dir, f)
                    m = re.search(r"lstm_analysis_report_(\d+)\.md", f)
                    period = m.group(1) if m else "N/A"
                    size = os.path.getsize(path)
                    mod_time = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
                    results.append({
                        "filename": f,
                        "title": f"第 {period} 期 LSTM 时序推演深度研报",
                        "period": period,
                        "type": "markdown",
                        "size_kb": round(size / 1024, 1),
                        "updated_at": mod_time,
                        "path": path
                    })
                    
        # 2. 扫描 TXT 预测单
        if os.path.exists(txt_dir):
            for f in sorted(os.listdir(txt_dir), reverse=True):
                if f.startswith("prediction_") and f.endswith(".txt"):
                    path = os.path.join(txt_dir, f)
                    m = re.search(r"prediction_(\d+)\.txt", f)
                    period = m.group(1) if m else "N/A"
                    size = os.path.getsize(path)
                    mod_time = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
                    results.append({
                        "filename": f,
                        "title": f"第 {period} 期 LSTM 工业级预测推演单",
                        "period": period,
                        "type": "text",
                        "size_kb": round(size / 1024, 1),
                        "updated_at": mod_time,
                        "path": path
                    })
        return results

    def get_lstm_report_detail(self, filename: str) -> Dict[str, Any]:
        """获取指定 LSTM 研报或预测单的内容"""
        safe_name = os.path.basename(filename)
        cand1 = os.path.join(get_outputs_dir(), "reports", safe_name)
        cand2 = os.path.join(get_outputs_dir(), "predictions", safe_name)
        target = cand1 if os.path.exists(cand1) else (cand2 if os.path.exists(cand2) else None)
        if not target or not os.path.exists(target):
            raise FileNotFoundError(f"未找到指定的 LSTM 文件: {safe_name}")
            
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        return {
            "status": "ok",
            "filename": safe_name,
            "type": "markdown" if safe_name.endswith(".md") else "text",
            "content": content
        }

