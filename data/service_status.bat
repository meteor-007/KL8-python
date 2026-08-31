@echo off
chcp 65001 > nul
title K8-QUANT Web 服务运行状态

cd /d "%~dp0"
set PYTHON_EXE=C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=py
)

"%PYTHON_EXE%" backend_daemon.py status
echo.
pause
