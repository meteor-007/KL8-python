# -*- coding: utf-8 -*-
"""数据预检:时效性 + 目标期识别(只读,不修改数据)。"""
import os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import HISTORY_FILE
from core.data_loader import load_history, get_latest
from core.period_utils import next_period


def precheck(verbose=True):
    draws = load_history()
    latest = get_latest(draws)
    if latest is None:
        return None
    target = next_period(latest.period)
    out = {"latest_period": latest.period, "latest_date": latest.date,
           "target": target, "n": len(draws)}
    if verbose:
        print("双层LSTM 数据预检 (只读)")
        print(f"  最新期号: {latest.period} | 日期: {latest.date} | 总期数: {len(draws)}")
        try:
            days = (datetime.strptime(latest.date, "%Y-%m-%d").date() -
                    datetime.now().date()).days
            print(f"  数据时效: 距今 {days} 天 {'✅正常' if days <= 1 else '⚠️需更新'}")
        except Exception:
            pass
        print(f"  🎯 目标预测期号: {target}")
    return out


if __name__ == "__main__":
    precheck()