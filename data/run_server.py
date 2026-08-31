#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K8-Quant Web Server Launcher
一键启动 K8-Quant Web 端量化决策终端服务 (Modular Edition)
"""
import os
import sys

# 确保在 Windows 无控制台 (Hidden/Service/Daemon) 模式下 print 不会触发 WinError 6 崩溃
_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_DIR = os.path.join(_PROJ_DIR, "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE_PATH = os.path.join(_LOG_DIR, "web_server.log")


class SafeStream:
    def __init__(self, filepath):
        self.filepath = filepath
        self._file = None

    def _get_file(self):
        if self._file is None or self._file.closed:
            self._file = open(self.filepath, "a", encoding="utf-8", errors="replace")
        return self._file

    def write(self, s):
        try:
            f = self._get_file()
            f.write(s)
            f.flush()
        except Exception:
            pass

    def flush(self):
        try:
            if self._file and not self._file.closed:
                self._file.flush()
        except Exception:
            pass


# 如果当前没有控制台或者句柄异常，统一使用 SafeStream 写入日志
try:
    if sys.stdout is None or not hasattr(sys.stdout, "write"):
        sys.stdout = SafeStream(_LOG_FILE_PATH)
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stdout = SafeStream(_LOG_FILE_PATH)

try:
    if sys.stderr is None or not hasattr(sys.stderr, "write"):
        sys.stderr = SafeStream(_LOG_FILE_PATH)
    else:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stderr = SafeStream(_LOG_FILE_PATH)

import io
import webbrowser
import threading
import time
import uvicorn

if sys.stdin is None:
    sys.stdin = io.StringIO()

_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR


def open_browser(url: str, delay: float = 1.2):
    time.sleep(delay)
    print(f"\n🚀 正在为您自动打开量化大屏浏览器: {url}\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"⚠️ 自动打开浏览器失败: {e}，请手动访问 {url}")


class ServiceSafeUvicornServer(uvicorn.Server):
    """支持 Windows Service 及后台无窗口模式的安全 Uvicorn Server"""
    def install_signal_handlers(self):
        try:
            super().install_signal_handlers()
        except Exception:
            pass


def main():
    # 动态适配云端部署（如 Render / Railway / Docker 等平台）与本地开发环境
    is_cloud = bool(os.environ.get("RENDER") or os.environ.get("PORT"))
    default_host = "0.0.0.0" if is_cloud else "127.0.0.1"
    host = os.environ.get("HOST", default_host)
    port = int(os.environ.get("PORT", 8000))
    url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}"
    
    is_daemon = "--daemon" in sys.argv
    auto_open = "--no-browser" not in sys.argv and not is_daemon and not is_cloud

    print("=" * 70)
    print("       🧬 K8-QUANT 智能量化操盘决策终端 (Web Cyber Edition)")
    print("=" * 70)
    print(f"  ▶ 本地 Web 大屏地址 : {url}")
    print(f"  ▶ 交互式 API 接口文档: {url}/docs")
    print(f"  ▶ 系统工作根目录   : {PROJ_DIR}")
    print(f"  ▶ 后端服务模块     : backend.api.api_server")
    print(f"  ▶ 前端静态资源     : frontend/static")
    print("=" * 70)
    
    if auto_open:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    
    try:
        import asyncio
        from backend.api.api_server import app
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info",
            reload=False,
            access_log=False,
            lifespan="off"
        )
        server = uvicorn.Server(config)
        server.run()
        print(f"⚠️ Uvicorn Server 退出，should_exit={server.should_exit}")
    except Exception as e:
        import traceback
        print(f"❌ Web 服务器发生未捕获异常: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
