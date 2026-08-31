@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title 卸载 K8-QUANT Web 服务与开机自启

:: ------------------ 检查管理员权限 ------------------
fltmc >nul 2>&1
if %errorlevel% NEQ 0 (
    echo ======================================================================
    echo 🔐 正在请求管理员权限，请在弹出的 Windows 确认框中点击【是 (Yes)】...
    echo ======================================================================
    powershell -Command "Start-Process cmd -ArgumentList '/c', '\"\"%~f0\"\"' -Verb RunAs"
    exit /b
)
:: ---------------------------------------------------------

cd /d "%~dp0"
set PYTHON_EXE=C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    for /f "tokens=*" %%i in ('where python 2^>nul') do set PYTHON_EXE=%%i
)

echo ======================================================================
echo          🗑️  正在卸载 K8-QUANT Web 后台服务与开机启动项...
echo ======================================================================
echo.

echo [1/3] 正在停止后台 Web 运行进程...
"%PYTHON_EXE%" "%~dp0backend_daemon.py" stop

echo.
echo [2/3] 正在清理 Windows 系统服务...
"%PYTHON_EXE%" "%~dp0windows_service.py" stop >nul 2>&1
"%PYTHON_EXE%" "%~dp0windows_service.py" remove >nul 2>&1
sc delete K8QuantWebService >nul 2>&1

echo.
echo [3/3] 正在清理开机自启项目...
set STARTUP_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\K8QuantWebAutoStart.vbs
if exist "!STARTUP_VBS!" (
    del /f /q "!STARTUP_VBS!"
    echo  ▶ 已清除开机自启动项: !STARTUP_VBS!
)

echo.
echo ======================================================================
echo  ✅ 卸载与清理完成！当前状态:
echo ======================================================================
"%PYTHON_EXE%" "%~dp0backend_daemon.py" status
echo.
pause
