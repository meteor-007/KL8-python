# -*- coding: utf-8 -*-
"""
K8-Quant Windows Service Manager
将 K8-Quant Web 终端封装为标准的 Windows 系统服务
实现后台无人值守、关闭窗口不停止、开机自启与状态监管
"""
import os
import sys

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import logging
import threading
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 确保 logs 目录存在
_LOG_DIR = os.path.join(_PROJ_DIR, "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, "web_service.log")

# 配置日志记录器
logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [PID:%(process)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    import winerror
except ImportError:
    win32serviceutil = None
    win32service = None
    win32event = None
    servicemanager = None


class K8QuantWebService(win32serviceutil.ServiceFramework if win32serviceutil else object):
    """K8-Quant Web 决策大屏 Windows 后台守护服务"""
    _svc_name_ = "K8QuantWebService"
    _svc_display_name_ = "K8-QUANT 智能量化操盘决策终端 Web 服务"
    _svc_description_ = "K8-Quant 智能量化决策系统 Web 终端守护服务 (FastAPI Uvicorn 8000端口)"

    def __init__(self, args):
        if win32serviceutil:
            super().__init__(args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.server = None
        self.host = "127.0.0.1"
        self.port = 8000

    def SvcStop(self):
        """服务停止通知"""
        logging.info("收到 Windows 服务停止 (SvcStop) 指令，正在安全退出...")
        if win32service:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_running = False
        if self.server:
            self.server.should_exit = True
        if win32serviceutil and self.hWaitStop:
            win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        """服务运行主入口"""
        logging.info("=" * 60)
        logging.info("🚀 K8QuantWebService Windows 服务正式启动中...")
        logging.info(f"项目根目录: {_PROJ_DIR}")
        logging.info(f"监听地址: http://{self.host}:{self.port}")
        
        # 切换工作目录至项目根目录
        os.chdir(_PROJ_DIR)
        
        if servicemanager:
            try:
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, "")
                )
            except Exception:
                pass

        try:
            self.run_web_server()
        except Exception as e:
            logging.exception(f"❌ Web 服务运行异常崩溃: {e}")
        finally:
            logging.info("🛑 K8QuantWebService Windows 服务已安全停止")
            logging.info("=" * 60)

    def run_web_server(self):
        """启动 Uvicorn FastAPI 服务"""
        import uvicorn
        
        # 导入 API 应用
        try:
            from backend.api.api_server import app
        except Exception as e:
            logging.exception(f"导入 backend.api.api_server 失败: {e}")
            raise e

        # 配置 Uvicorn
        config = uvicorn.Config(
            app=app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
            reload=False
        )
        self.server = uvicorn.Server(config)
        self.server.install_signal_handlers = lambda: None
        
        logging.info(f"✅ Uvicorn 服务器正在监听 {self.host}:{self.port}")
        self.server.run()


def run_standalone():
    """非服务模式下的直接运行（用于本地测试）"""
    print(f"🧬 以独立模式启动 K8-Quant Web 服务...")
    print(f"日志输出至: {_LOG_FILE}")
    import uvicorn
    os.chdir(_PROJ_DIR)
    from backend.api.api_server import app
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        if servicemanager:
            try:
                servicemanager.Initialize()
                servicemanager.PrepareToHostSingle(K8QuantWebService)
                servicemanager.StartServiceCtrlDispatcher()
            except Exception as e:
                # 可能是非服务控制台直接运行双击
                run_standalone()
        else:
            run_standalone()
    else:
        if sys.argv[1].lower() == "standalone":
            run_standalone()
        elif win32serviceutil:
            win32serviceutil.HandleCommandLine(K8QuantWebService)
        else:
            print("❌ 未安装 pywin32 模块，无法管理 Windows 服务。")
