@echo off
chcp 65001 > nul
title 启动 K8-QUANT Web 后台守护服务

cd /d "%~dp0"
set PYTHON_EXE=C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=py
)

"%PYTHON_EXE%" backend_daemon.py start
echo.
pause
