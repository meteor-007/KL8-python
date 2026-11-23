# -*- coding: utf-8 -*-
"""K8-Quant Web 服务自包含安装器。

流程：
  1. 检查/安装 pywin32；
  2. 在 Python 的 site-packages 写入服务引导模块
     （pywin32 注册的类名是 k8_windows_service_impl.K8QuantWebService，
      服务宿主启动时按名字导入，必须有这个可导入模块）；
  3. install 或 update 为自动启动的 Windows 服务；
  4. 配置崩溃自动重启；
  5. 停止占用 8000 端口的临时守护进程，启动服务并验证端口；
  6. 清理旧的开机计划任务（若存在）。

无管理员权限时会自动提权；pywin32 不可用时回退为“登录启动项 + 后台守护进程”。
"""
import argparse
import ctypes
import os
import socket
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _resolve_project_root(start_file: str) -> str:
    p = Path(start_file).resolve().parent
    for cand in [p, *p.parents]:
        if (cand / "run_server.py").is_file() and (cand / "backend").is_dir():
            return str(cand)
    return str(p)


OPS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = _resolve_project_root(__file__)
LOG_DIR = os.path.join(PROJ_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
PYTHON_EXE = sys.executable

SVC_NAME = "K8QuantWebService"
BOOTSTRAP_NAME = "k8_windows_service_impl.py"
SVC_SCRIPT = os.path.join(PROJ_DIR, "windows_service.py")
DAEMON_SCRIPT = os.path.join(OPS_DIR, "backend_daemon.py")
TEMP_TASK = "K8QuantWeb_Autostart"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    script = os.path.abspath(__file__)
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", PYTHON_EXE, f'"{script}"', PROJ_DIR, 1
    )
    if ret > 32:
        sys.exit(0)
    print("⚠️ 未获得管理员权限，将以当前用户模式继续配置...")


def is_port_listening(port: int = 8000, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def ensure_pywin32() -> bool:
    try:
        import win32serviceutil  # noqa: F401
        return True
    except ImportError:
        pass
    print("【步骤 1/6】未检测到 pywin32，正在安装 ...")
    res = _run([PYTHON_EXE, "-m", "pip", "install", "pywin32"])
    if res.returncode != 0:
        print(f"  ⚠️ pywin32 安装失败: {(res.stderr or res.stdout).strip()[:300]}")
        return False
    try:
        import win32serviceutil  # noqa: F401
        return True
    except ImportError:
        print("  ⚠️ pywin32 安装后仍无法导入")
        return False


def write_bootstrap() -> str:
    """把服务引导模块写入当前解释器的 site-packages。"""
    purelib = sysconfig.get_paths().get("purelib")
    if not purelib:
        raise RuntimeError("无法定位 site-packages")
    path = os.path.join(purelib, BOOTSTRAP_NAME)
    impl = os.path.join(OPS_DIR, "windows_service.py")
    content = f'''# -*- coding: utf-8 -*-
"""pywin32 Windows service bootstrap for K8QuantWebService (auto-generated).

pywin32 registered PythonClass ``{BOOTSTRAP_NAME[:-3]}.K8QuantWebService``.
The service host imports that module by name before the project is on sys.path,
so this shim loads the real implementation from the project checkout.
"""
import importlib.util
import sys
from pathlib import Path

_IMPL = Path({impl!r})
if not _IMPL.is_file():
    raise ImportError(f"Missing Windows service implementation: {{_IMPL}}")

_spec = importlib.util.spec_from_file_location(__name__, str(_IMPL))
_mod = importlib.util.module_from_spec(_spec)
sys.modules[__name__] = _mod
_spec.loader.exec_module(_mod)

K8QuantWebService = _mod.K8QuantWebService
run_standalone = _mod.run_standalone
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ 服务引导模块已写入: {path}")
    return path


def service_installed() -> bool:
    return _run(["sc.exe", "query", SVC_NAME]).returncode == 0


def service_running() -> bool:
    out = _run(["sc.exe", "query", SVC_NAME]).stdout.upper()
    return "RUNNING" in out


def configure_recovery():
    res = _run([
        "sc.exe", "failure", SVC_NAME,
        "reset=", "86400",
        "actions=", "restart/5000/restart/10000/restart/60000",
    ])
    if res.returncode == 0:
        print("  ✅ 崩溃自动重启已配置（5s / 10s / 60s）")
    else:
        print(f"  ⚠️ 崩溃自动重启配置失败: {(res.stderr or res.stdout).strip()[:200]}")


def remove_temp_task():
    ps = (
        f'Unregister-ScheduledTask -TaskName "{TEMP_TASK}" '
        '-Confirm:$false -ErrorAction SilentlyContinue'
    )
    _run(["powershell", "-NoProfile", "-Command", ps])


def create_startup_shortcut() -> str | None:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return None
    startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    if not os.path.exists(startup_dir):
        return None
    vbs_path = os.path.join(startup_dir, "K8QuantWebAutoStart.vbs")
    vbs = (
        'Set ws = CreateObject("Wscript.Shell")\r\n'
        f'ws.Run "cmd.exe /c cd /d ""{PROJ_DIR}"" && ""{PYTHON_EXE}"" run_server.py --no-browser '
        f'>> ""{LOG_DIR}\\web_server.log"" 2>&1", 0, False\r\n'
    )
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs)
    return vbs_path


def wait_for_port(seconds: int = 20) -> bool:
    for _ in range(seconds * 2):
        if is_port_listening(8000):
            return True
        time.sleep(0.5)
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="K8-Quant Web 服务自包含安装器")
    parser.add_argument("--no-pause", action="store_true", help="结束后不等待回车")
    parser.add_argument("--skip-install", action="store_true", help="只补齐依赖与引导模块，不改动服务")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("       🧬 K8-QUANT Web 服务自包含安装器")
    print("=" * 70)
    print(f"  ▶ 工作目录 : {PROJ_DIR}")
    print(f"  ▶ Python   : {PYTHON_EXE}")
    print(f"  ▶ 管理员   : {'是' if is_admin() else '否'}")
    print("=" * 70)

    if not is_admin():
        run_as_admin()
        return 0

    has_pywin32 = ensure_pywin32()

    print("【步骤 2/6】写入服务导入引导模块 ...")
    write_bootstrap()

    if args.skip_install:
        print("✅ 依赖与引导模块已就绪（--skip-install）")
        return 0

    if not has_pywin32:
        print("【回退模式】pywin32 不可用，配置登录启动项 + 后台守护进程 ...")
        vbs = create_startup_shortcut()
        if vbs:
            print(f"  ✅ 已加入启动项: {vbs}")
        _run([PYTHON_EXE, DAEMON_SCRIPT, "start"])
        ok = wait_for_port()
        print("🎉 回退启动完成" if ok else "⚠️ 端口未就绪，请查看 logs/web_server.log")
        return 0 if ok else 1

    action = "update" if service_installed() else "install"
    print(f"【步骤 3/6】{'更新' if action == 'update' else '安装'} Windows 服务 ...")
    res = _run([PYTHON_EXE, SVC_SCRIPT, "--startup=auto", action])
    if res.returncode != 0:
        print(f"  ❌ 服务{action}失败: {(res.stderr or res.stdout).strip()[:400]}")
        return 1
    print("  ✅ 服务已注册为自动启动")

    print("【步骤 4/6】配置崩溃自动重启 ...")
    configure_recovery()

    print("【步骤 5/6】启动服务 ...")
    remove_temp_task()
    if service_running():
        print("  ℹ️ 服务已在运行")
    else:
        if is_port_listening(8000):
            print("  ▶ 停止占用 8000 端口的后台守护进程 ...")
            _run([PYTHON_EXE, DAEMON_SCRIPT, "stop"])
        _run(["net", "start", SVC_NAME])
        if not wait_for_port():
            print("  ❌ 服务已提交启动，但 8000 端口未监听")
            print(f"     请查看服务日志: {os.path.join(LOG_DIR, 'web_service.log')}")
            return 1

    print("【步骤 6/6】验证 ...")
    ok = is_port_listening(8000)
    print(f"  {'✅' if ok else '❌'} 8000 端口: {'监听中' if ok else '未监听'}")
    print("=" * 70)
    if ok:
        print("🎉 安装完成：服务开机自启、崩溃自动重启")
        print("🌐 访问地址: http://127.0.0.1:8000")
    print("=" * 70)

    if not args.no_pause and sys.stdin and sys.stdin.isatty():
        input("👉 按回车键退出 ...")
    return 0 if ok else 1


if __name__ == "__main__":
    if not is_admin():
        try:
            run_as_admin()
        except Exception:
            pass
    raise SystemExit(main())