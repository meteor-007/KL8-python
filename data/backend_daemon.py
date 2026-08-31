# -*- coding: utf-8 -*-
"""
K8-Quant Web Server Background Daemon & Status Checker
后台守护进程管理与状态检查器
"""
import os
import sys

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import signal
import socket
import subprocess
import webbrowser
from pathlib import Path

_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_DIR = os.path.join(_PROJ_DIR, "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_PID_FILE = os.path.join(_LOG_DIR, "web_server.pid")
_LOG_FILE = os.path.join(_LOG_DIR, "web_server.log")


def get_python_exe():
    """获取当前 python 解释器路径"""
    py_dir = os.path.dirname(sys.executable)
    py_exe = os.path.join(py_dir, "python.exe")
    if os.path.exists(py_exe):
        return py_exe
    return sys.executable


def is_port_in_use(port: int = 8000, host: str = "127.0.0.1") -> bool:
    """检查指定端口是否被监听"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def get_stored_pid() -> int | None:
    """读取保存的后台进程 PID"""
    if os.path.exists(_PID_FILE):
        try:
            with open(_PID_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return int(content)
        except Exception:
            pass
    return None


def is_pid_running(pid: int) -> bool:
    """检查 PID 是否仍在运行"""
    if not pid:
        return False
    try:
        # 在 Windows 上调用 tasklist 检查
        out = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /NH', shell=True, text=True)
        return str(pid) in out
    except Exception:
        return False


def start_daemon():
    """启动后台静默进程（无黑窗）"""
    if is_port_in_use(8000):
        print("⚠️ 端口 8000 已被占用，Web 服务可能已经在运行中！")
        print("👉 请直接访问: http://127.0.0.1:8000")
        return

    python_exe = get_python_exe()
    script_path = os.path.join(_PROJ_DIR, "service_worker.py")
    
    print(f"🧬 正在以后台静默守护模式启动 K8-Quant Web 服务...")
    print(f"▶ 解释器: {python_exe}")
    print(f"▶ 日志文件: {_LOG_FILE}")

    # 使用 PowerShell Start-Process 启动原生后台脱离进程
    ps_cmd = (
        f"$p = Start-Process -FilePath '{python_exe}' "
        f"-ArgumentList '{script_path}' "
        f"-WorkingDirectory '{_PROJ_DIR}' "
        f"-WindowStyle Hidden -PassThru; "
        f"Write-Output $p.Id"
    )
    
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True
    )
    
    pid_str = res.stdout.strip()
    pid = int(pid_str) if pid_str.isdigit() else None
    
    if pid:
        with open(_PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(pid))

    # 等待检测启动结果
    print("⏳ 等待服务就绪...", end="", flush=True)
    started = False
    for _ in range(25):
        time.sleep(0.5)
        print(".", end="", flush=True)
        if is_port_in_use(8000):
            started = True
            break

    print()
    if started:
        print(f"✅ Web 服务已成功在后台启动 (PID: {pid})！")
        print("💡 您现在可以放心地关闭任何命令行窗口，Web 服务不会停止。")
        print(f"🌐 访问地址: http://127.0.0.1:8000")
    else:
        print("⚠️ 服务已提交后台启动，若页面暂无法访问，请查看日志:")
        print(f"   {_LOG_FILE}")


def stop_daemon():
    """停止后台服务"""
    pid = get_stored_pid()
    killed = False
    
    if pid and is_pid_running(pid):
        print(f"🛑 正在终止后台进程 (PID: {pid})...")
        try:
            subprocess.run(f"taskkill /F /PID {pid} /T", shell=True, check=False)
            killed = True
        except Exception as e:
            print(f"终止进程失败: {e}")

    # 检查是否还有 8000 端口占用的 python 进程
    if is_port_in_use(8000):
        print("🔍 检测到端口 8000 仍被占用，正在通过端口释放...")
        try:
            # 查找占用 8000 端口的 PID 并终止
            out = subprocess.check_output('netstat -ano | findstr :8000', shell=True, text=True)
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and "LISTENING" in parts:
                    port_pid = parts[-1]
                    if port_pid.isdigit() and int(port_pid) > 0:
                        print(f"🛑 终止占用端口 8000 的进程 PID: {port_pid}")
                        subprocess.run(f"taskkill /F /PID {port_pid} /T", shell=True, check=False)
                        killed = True
        except Exception:
            pass

    if os.path.exists(_PID_FILE):
        try:
            os.remove(_PID_FILE)
        except Exception:
            pass

    time.sleep(0.5)
    if not is_port_in_use(8000):
        print("✅ K8-Quant Web 后台服务已成功停止！")
    else:
        print("⚠️ 端口 8000 仍处于占用状态，请检查任务管理器。")


def check_status():
    """查看服务运行状态"""
    port_used = is_port_in_use(8000)
    pid = get_stored_pid()
    pid_running = is_pid_running(pid) if pid else False

    # 检查 Windows 系统服务状态
    svc_status = "未安装 / 未运行"
    try:
        out = subprocess.check_output('sc query K8QuantWebService', shell=True, text=True, stderr=subprocess.DEVNULL)
        if "RUNNING" in out:
            svc_status = "🟢 正在运行 (Windows 系统服务)"
        elif "STOPPED" in out:
            svc_status = "🟡 已停止 (Windows 系统服务)"
        elif "PAUSED" in out:
            svc_status = "🟠 已暂停 (Windows 系统服务)"
        else:
            svc_status = "已注册 Windows 系统服务"
    except Exception:
        svc_status = "未注册为系统服务"

    print("=" * 60)
    print("       🧬 K8-QUANT Web 服务运行状态监视器")
    print("=" * 60)
    print(f"  ▶ 8000 端口监听状态 : {'🟢 正在监听 (正常服务中)' if port_used else '🔴 未监听 (服务未运行)'}")
    print(f"  ▶ Windows 系统服务  : {svc_status}")
    print(f"  ▶ 后台守护进程 PID  : {pid if pid else '无'} ({'🟢 运行中' if pid_running else '🔴 未运行'})")
    print(f"  ▶ 本地 Web 访问入口 : http://127.0.0.1:8000")
    print(f"  ▶ 后台服务日志路径  : {_LOG_FILE}")
    print("=" * 60)


def open_ui():
    """打开浏览器访问"""
    url = "http://127.0.0.1:8000"
    print(f"🚀 正在打开浏览器: {url}")
    webbrowser.open(url)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        check_status()
    else:
        action = sys.argv[1].lower()
        if action == "start":
            start_daemon()
        elif action == "stop":
            stop_daemon()
        elif action == "restart":
            stop_daemon()
            time.sleep(1)
            start_daemon()
        elif action == "status":
            check_status()
        elif action == "open":
            open_ui()
        else:
            print(f"未知参数: {action}，支持参数: start | stop | restart | status | open")
