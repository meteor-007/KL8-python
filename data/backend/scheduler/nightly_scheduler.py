# -*- coding: utf-8 -*-
"""
nightly_scheduler.py — 开奖后自动流水线调度器 (Nightly / Post-Draw Scheduler)
====================================================================================
v6 契约:
  1. 定时（默认 22:00）或手动触发 → backend.pipeline.run_nightly_pipeline
  2. 流水线：同步开奖 → 自动跑非点位预测模块 → 汇总；点位类跳过待手工
  3. 开箱即用：随 Web 后端自启守护线程；提供状态 API 与一键触发
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.paths import get_python_runner

SCHEDULER_CONFIG_FILE = os.path.join(_PROJ_DIR, "backend", "config", "scheduler_config.json")
os.makedirs(os.path.dirname(SCHEDULER_CONFIG_FILE), exist_ok=True)


class NightlyScheduler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_scheduler()
            return cls._instance

    def _init_scheduler(self):
        self.config = self._load_config()
        self.is_running_task = False
        self.last_run_date = self.config.get("last_run_date", "")
        self.last_status = self.config.get("last_status", "IDLE")
        self.last_message = self.config.get("last_message", "定时调度器已初始化就绪")
        self.last_finished_at = self.config.get("last_finished_at", "")
        self.recent_logs = []
        self._thread = None
        self._stop_event = threading.Event()

    def _load_config(self) -> Dict[str, Any]:
        default_cfg = {
            "enabled": True,
            "target_time": "22:00",
            "retry_minutes": 5,
            "max_retries": 6,
            "last_run_date": "",
            "last_status": "IDLE",
            "last_message": "定时任务处于待命状态",
            "last_finished_at": ""
        }
        if os.path.exists(SCHEDULER_CONFIG_FILE):
            try:
                with open(SCHEDULER_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

    def _save_config(self):
        try:
            with open(SCHEDULER_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存调度器配置失败: {e}")

    def get_next_run_time(self) -> str:
        """计算下一次 22:00 触发的时间戳字符串"""
        now = datetime.now()
        target_str = self.config.get("target_time", "22:00")
        th, tm = [int(x) for x in target_str.split(":")]
        target_today = now.replace(hour=th, minute=tm, second=0, microsecond=0)
        
        today_date_str = now.strftime("%Y-%m-%d")
        if now >= target_today or (self.last_run_date == today_date_str and self.last_status == "SUCCESS"):
            next_run = target_today + timedelta(days=1)
        else:
            next_run = target_today
        return next_run.strftime("%Y-%m-%d %H:%M:%S")

    def get_countdown_seconds(self) -> int:
        """计算距离下次运行的倒计时秒数"""
        next_run_str = self.get_next_run_time()
        next_dt = datetime.strptime(next_run_str, "%Y-%m-%d %H:%M:%S")
        diff = (next_dt - datetime.now()).total_seconds()
        return max(0, int(diff))

    def get_status(self) -> Dict[str, Any]:
        """获取当前调度器全面状态"""
        countdown = self.get_countdown_seconds()
        hours = countdown // 3600
        mins = (countdown % 3600) // 60
        secs = countdown % 60
        countdown_human = f"{hours:02d}小时 {mins:02d}分 {secs:02d}秒"

        return {
            "status": "ok",
            "enabled": self.config.get("enabled", True),
            "target_time": self.config.get("target_time", "22:00"),
            "is_running": self.is_running_task,
            "next_run_time": self.get_next_run_time(),
            "countdown_seconds": countdown,
            "countdown_human": countdown_human,
            "last_status": self.last_status,
            "last_message": self.last_message,
            "last_run_date": self.last_run_date,
            "last_finished_at": self.last_finished_at,
            "recent_logs": self.recent_logs[-30:]
        }

    def start(self):
        """启动后台监视线程"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="NightlySchedulerLoop", daemon=True)
        self._thread.start()
        print(f"⏰ 22:00 夜间全自动定时调度线程已启动 (下次触发: {self.get_next_run_time()})")

    def stop(self):
        """停止后台监视线程"""
        self._stop_event.set()

    def trigger_now(self, async_mode: bool = True) -> Dict[str, Any]:
        """手动一键立即触发一次夜间全流程任务"""
        if self.is_running_task:
            return {"status": "error", "message": "夜间流水线任务正在执行中，请勿重复触发！"}

        if async_mode:
            threading.Thread(target=self._execute_pipeline, daemon=True).start()
            return {"status": "ok", "message": "夜间全自动推演任务已提交后台立即执行！"}
        else:
            return self._execute_pipeline()

    def _execute_pipeline(self) -> Dict[str, Any]:
        """执行夜间流水线核心任务"""
        self.is_running_task = True
        self.last_status = "RUNNING"
        self.last_message = "正在执行 22:00 夜间全自动闭环推演与自学习进化流水线..."
        self.recent_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 启动夜间全流程流水线任务")

        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            from backend.pipeline.run_nightly_pipeline import run_nightly_pipeline
            res = run_nightly_pipeline(verbose=True)
            self.last_status = "SUCCESS"
            self.last_run_date = today_str
            self.last_finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_message = f"✅ 夜间流水线执行圆满成功 (耗时: {res.get('elapsed_seconds', 0)}s)！"
            self.config["last_run_date"] = self.last_run_date
            self.config["last_status"] = self.last_status
            self.config["last_message"] = self.last_message
            self.config["last_finished_at"] = self.last_finished_at
            self._save_config()
            self.recent_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {self.last_message}")
            return res
        except Exception as e:
            self.last_status = "FAILED"
            self.last_message = f"❌ 夜间流水线执行异常: {str(e)}"
            self.config["last_status"] = self.last_status
            self.config["last_message"] = self.last_message
            self._save_config()
            self.recent_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {self.last_message}")
            return {"status": "FAILED", "error": str(e)}
        finally:
            self.is_running_task = False

    def _loop(self):
        """后台轮询主循环"""
        while not self._stop_event.is_set():
            try:
                if self.config.get("enabled", True) and not self.is_running_task:
                    now = datetime.now()
                    today_str = now.strftime("%Y-%m-%d")
                    target_str = self.config.get("target_time", "22:00")
                    th, tm = [int(x) for x in target_str.split(":")]
                    
                    if now.hour == th and now.minute >= tm:
                        if self.last_run_date != today_str:
                            print(f"\n⏰ [NightlyScheduler] 准时到达 {target_str}，自动唤醒并启动夜间全流程！\n")
                            self._execute_pipeline()
            except Exception as e:
                print(f"⚠️ 调度器轮询发生异常: {e}")
            
            time.sleep(15)


# 全局单例
scheduler_instance = NightlyScheduler()
