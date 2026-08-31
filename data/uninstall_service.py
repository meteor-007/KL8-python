# -*- coding: utf-8 -*-
"""
K8-Quant Web 服务系统化一键卸载器 (Python Native Uninstaller)
"""
import os
import sys
import time
import subprocess
import ctypes

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    script = os.path.abspath(__file__)
    params = f'"{script}"'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", PYTHON_EXE, params, PROJ_DIR, 1)
    if ret > 32:
        sys.exit(0)


def main():
    print("=" * 70)
    print("       🧬 K8-QUANT Web 服务与自启动项一键卸载清理")
    print("=" * 70)
    print()

    # 1. 停止运行中的进程
    print("【步骤 1/3】正在停止运行中的后台 Web 进程...")
    daemon_script = os.path.join(PROJ_DIR, "backend_daemon.py")
    subprocess.run([PYTHON_EXE, daemon_script, "stop"])

    # 2. 清理系统服务
    print("【步骤 2/3】正在清理 Windows 系统服务...")
    svc_script = os.path.join(PROJ_DIR, "windows_service.py")
    if os.path.exists(svc_script):
        subprocess.run([PYTHON_EXE, svc_script, "stop"], capture_output=True)
        subprocess.run([PYTHON_EXE, svc_script, "remove"], capture_output=True)
    subprocess.run("sc delete K8QuantWebService", shell=True, capture_output=True)

    # 3. 清理开机自启
    print("【步骤 3/3】正在清理开机自启项...")
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        vbs_path = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "K8QuantWebAutoStart.vbs")
        if os.path.exists(vbs_path):
            try:
                os.remove(vbs_path)
                print(f"  ✅ 已清除自启文件: {vbs_path}")
            except Exception as e:
                print(f"  ⚠️ 清除自启文件失败: {e}")

    print()
    print("=" * 70)
    print("🎉【卸载与清理完成】！所有服务及开机项已全部清空。")
    print("=" * 70)
    print()
    input("👉 请按【回车键 (Enter)】完成并退出本窗口...")


if __name__ == "__main__":
    if not is_admin():
        try:
            run_as_admin()
        except Exception:
            pass
    main()
