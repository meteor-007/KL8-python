# -*- coding: utf-8 -*-
"""
K8-Quant Web 服务系统化一键安装与自启配置器 (Python Native Installer)
采用 Windows 原生 API 提权，彻底避免批处理编码与引号转义错误
"""
import os
import sys
import time
import socket
import subprocess
import ctypes
from pathlib import Path

# 设置控制台编码为 UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJ_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
PYTHON_EXE = sys.executable


def is_admin() -> bool:
    """检查当前是否拥有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """以管理员权限重新启动自身"""
    script = os.path.abspath(__file__)
    params = f'"{script}"'
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        PYTHON_EXE,
        params,
        PROJ_DIR,
        1
    )
    if ret > 32:
        # 提权窗口已成功唤起
        sys.exit(0)
    else:
        print("⚠️ 未获得管理员权限，将以当前用户模式继续配置...")


def is_port_listening(port=8000, host="127.0.0.1") -> bool:
    """检查 8000 端口是否在监听"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def create_startup_shortcut():
    """在 Windows 开机启动组中创建静默自启脚本"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return False
    startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    if not os.path.exists(startup_dir):
        return False
    
    vbs_path = os.path.join(startup_dir, "K8QuantWebAutoStart.vbs")
    vbs_content = (
        'Set ws = CreateObject("Wscript.Shell")\r\n'
        f'ws.Run "cmd.exe /c cd /d ""{PROJ_DIR}"" && ""{PYTHON_EXE}"" run_server.py --no-browser >> ""{LOG_DIR}\\web_server.log"" 2>&1", 0, False\r\n'
    )
    try:
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(vbs_content)
        return vbs_path
    except Exception as e:
        print(f"写入开机自启项失败: {e}")
        return False


def main():
    print("=" * 70)
    print("       🧬 K8-QUANT 智能量化操盘决策系统 Web 服务一键安装")
    print("=" * 70)
    print(f"  ▶ 工作目录 : {PROJ_DIR}")
    print(f"  ▶ Python环境: {PYTHON_EXE}")
    print(f"  ▶ 管理员权限: {'🟢 是' if is_admin() else '🟡 否'}")
    print("=" * 70)
    print()

    # 1. 尝试安装 Windows 系统服务
    svc_installed = False
    if is_admin():
        print("【步骤 1/3】正在注册 Windows 官方系统服务 (K8QuantWebService)...")
        svc_script = os.path.join(PROJ_DIR, "windows_service.py")
        if os.path.exists(svc_script):
            res = subprocess.run([PYTHON_EXE, svc_script, "--startup=auto", "install"], capture_output=True, text=True)
            if res.returncode == 0:
                print("  ✅ Windows 系统服务注册成功！")
                svc_installed = True
                
                # 配置崩溃自动拉起
                print("【步骤 2/3】配置服务崩溃自动恢复 (高可用保障)...")
                subprocess.run(
                    "sc.exe failure K8QuantWebService reset= 86400 actions= restart/5000/restart/10000/restart/60000",
                    shell=True,
                    capture_output=True
                )
                
                print("【步骤 3/3】正在启动 Windows 系统服务...")
                subprocess.run([PYTHON_EXE, svc_script, "start"], capture_output=True)
                subprocess.run("net start K8QuantWebService", shell=True, capture_output=True)
            else:
                print(f"  ⚠️ 系统服务注册提示: {res.stderr.strip() or res.stdout.strip()}")
    
    # 2. 如果系统服务受限于单用户环境，无缝配置开机自启守护
    if not svc_installed:
        print("【模式保障】正在配置 Windows 原生开机自启守护...")
        vbs_path = create_startup_shortcut()
        if vbs_path:
            print(f"  ✅ 已成功添加至系统开机启动项: {vbs_path}")
        
        print("【启动服务】正在以后台脱离模式拉起 Web 决策大屏...")
        daemon_script = os.path.join(PROJ_DIR, "backend_daemon.py")
        subprocess.run([PYTHON_EXE, daemon_script, "start"])

    # 3. 验证服务状态
    print()
    print("=" * 70)
    print("⏳ 正在验证 Web 服务端口响应...")
    time.sleep(2)
    
    if is_port_listening(8000):
        print("🎉【安装与启动大成功】！")
        print("  🟢 8000 端口已正常监听，服务已在后台稳定运行。")
        print("  💡 特性保障: 您现在可以放心关闭任何终端，服务绝不中断，开机自动运行。")
        print("  🌐 本地大屏地址: http://127.0.0.1:8000")
    else:
        print("⚠️ 8000 端口暂未检测到监听，请检查 logs/web_server.log 日志。")
    
    print("=" * 70)
    print()
    input("👉 请按【回车键 (Enter)】完成并退出本窗口...")


if __name__ == "__main__":
    if not is_admin():
        # 如果不是管理员，尝试调用 Windows 提权
        try:
            run_as_admin()
        except Exception:
            pass
    main()
