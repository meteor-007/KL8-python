# -*- coding: utf-8 -*-
"""
Compatibility entry for Windows service registration.

pywin32 registers: <project_root>\\windows_service.K8QuantWebService
Implementation lives in scripts/ops/windows_service.py after layout migration.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_OPS_SVC = Path(__file__).resolve().parent / "scripts" / "ops" / "windows_service.py"
if not _OPS_SVC.is_file():
    raise FileNotFoundError(f"Missing Windows service implementation: {_OPS_SVC}")

_spec = importlib.util.spec_from_file_location("k8_windows_service_impl", _OPS_SVC)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load Windows service module: {_OPS_SVC}")

_mod = importlib.util.module_from_spec(_spec)
# Keep a stable module name for pywin32 class lookup on this shim file.
sys.modules.setdefault("k8_windows_service_impl", _mod)
_spec.loader.exec_module(_mod)

K8QuantWebService = _mod.K8QuantWebService
run_standalone = _mod.run_standalone

if __name__ == "__main__":
    # Forward install/start/stop/remove to the real implementation.
    sys.argv[0] = str(_OPS_SVC)
    if len(sys.argv) == 1:
        if getattr(_mod, "servicemanager", None):
            try:
                _mod.servicemanager.Initialize()
                _mod.servicemanager.PrepareToHostSingle(K8QuantWebService)
                _mod.servicemanager.StartServiceCtrlDispatcher()
            except Exception:
                run_standalone()
        else:
            run_standalone()
    elif sys.argv[1].lower() == "standalone":
        run_standalone()
    elif getattr(_mod, "win32serviceutil", None):
        _mod.win32serviceutil.HandleCommandLine(K8QuantWebService)
    else:
        print("未安装 pywin32 模块，无法管理 Windows 服务。")
