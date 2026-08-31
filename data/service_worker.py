# -*- coding: utf-8 -*-
"""
K8-Quant Web Server Service Worker
服务工作进程执行器
"""
import os
import sys
import logging
import uvicorn

# 切换工作目录至项目根目录
PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJ_DIR)

if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
backend_dir = os.path.join(PROJ_DIR, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

log_dir = os.path.join(PROJ_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "web_service.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [PID:%(process)d] %(message)s",
    encoding="utf-8"
)

logging.info("=" * 60)
logging.info("🚀 K8-Quant Web 决策大屏 Service Worker 正式启动")
logging.info(f"监听地址: http://127.0.0.1:8000")

try:
    from backend.api.api_server import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info", access_log=False)
except Exception as e:
    logging.exception(f"❌ Web 服务异常退出: {e}")
finally:
    logging.info("🛑 K8-Quant Web Service Worker 已停止")
