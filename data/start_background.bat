@echo off
chcp 65001 > nul
title 启动 P2 (快乐8全栈) 后台服务
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

echo [P2 快乐8服务] 正在后台启动量化大屏服务 (端口 8000)...
set "PYTHONPATH=%~dp0"
powershell -Command "$env:PYTHONPATH='%~dp0'; Start-Process python -ArgumentList 'run_server.py --daemon' -WorkingDirectory '%~dp0' -WindowStyle Hidden -RedirectStandardOutput 'logs\web_server.log' -RedirectStandardError 'logs\web_error.log'"

timeout /t 3 > nul
netstat -ano | findstr :8000 > nul
if %ERRORLEVEL% equ 0 (
    echo [P2 快乐8服务] ✅ 启动成功！访问地址: http://127.0.0.1:8000
) else (
    echo [P2 快乐8服务] ⚠️ 启动指令已发出，日志输出请查看: logs\web_server.log
)
