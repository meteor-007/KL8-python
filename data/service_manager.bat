@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title K8-QUANT Web 服务运维管理控制台

cd /d "%~dp0"
set PYTHON_EXE=C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=py
)

:MENU
cls
echo ======================================================================
echo          🧬 K8-QUANT 智能量化操盘决策系统 Web 服务管理中心
echo ======================================================================
echo.
"%PYTHON_EXE%" backend_daemon.py status
echo.
echo ----------------------- [ 服务管理选项 ] -----------------------------
echo   [1] 🚀 启动 Web 服务 (后台静默守护模式，关闭窗口不停止)
echo   [2] 🛑 停止 Web 服务 (停止后台进程/释放8000端口)
echo   [3] 🔄 重启 Web 服务
echo   [4] 🌐 打开浏览器访问 Web 决策大屏 (http://127.0.0.1:8000)
echo   [5] 📋 查看 Web 服务最新运行日志
echo.
echo ------------------- [ Windows 系统服务 (需管理员) ] -------------------
echo   [6] ⚙️  一键安装为 Windows 系统服务 (开机自启/系统后台常驻)
echo   [7] 🗑️  一键卸载 Windows 系统服务
echo   [8] 🟢 启动 Windows 系统服务 (net start K8QuantWebService)
echo   [9] 🔴 停止 Windows 系统服务 (net stop K8QuantWebService)
echo.
echo   [0] 🚪 退出管理控制台
echo ======================================================================
set /p choice=请输入操作编号 (0-9): 

if "%choice%"=="1" goto START_DAEMON
if "%choice%"=="2" goto STOP_DAEMON
if "%choice%"=="3" goto RESTART_DAEMON
if "%choice%"=="4" goto OPEN_UI
if "%choice%"=="5" goto VIEW_LOG
if "%choice%"=="6" goto INSTALL_SVC
if "%choice%"=="7" goto UNINSTALL_SVC
if "%choice%"=="8" goto START_SVC
if "%choice%"=="9" goto STOP_SVC
if "%choice%"=="0" exit /b
goto MENU

:START_DAEMON
echo.
"%PYTHON_EXE%" backend_daemon.py start
echo.
pause
goto MENU

:STOP_DAEMON
echo.
"%PYTHON_EXE%" backend_daemon.py stop
echo.
pause
goto MENU

:RESTART_DAEMON
echo.
"%PYTHON_EXE%" backend_daemon.py restart
echo.
pause
goto MENU

:OPEN_UI
"%PYTHON_EXE%" backend_daemon.py open
goto MENU

:VIEW_LOG
echo.
echo ------------------------- [ 最近 30 条运行日志 ] -------------------------
if exist logs\web_server.log (
    powershell -Command "Get-Content -Tail 30 logs\web_server.log"
) else if exist logs\web_service.log (
    powershell -Command "Get-Content -Tail 30 logs\web_service.log"
) else (
    echo 暂无日志文件。
)
echo --------------------------------------------------------------------------
echo.
pause
goto MENU

:INSTALL_SVC
echo.
echo 正在尝试请求管理员权限安装 Windows 系统服务...
powershell -Command "Start-Process '%PYTHON_EXE%' -ArgumentList '\"%~dp0windows_service.py\" --startup=auto install' -Verb RunAs -Wait"
powershell -Command "Start-Process '%PYTHON_EXE%' -ArgumentList '\"%~dp0windows_service.py\" start' -Verb RunAs -Wait"
echo 安装与启动命令已执行。
echo.
pause
goto MENU

:UNINSTALL_SVC
echo.
echo 正在尝试请求管理员权限卸载 Windows 系统服务...
powershell -Command "Start-Process '%PYTHON_EXE%' -ArgumentList '\"%~dp0windows_service.py\" stop' -Verb RunAs -Wait"
powershell -Command "Start-Process '%PYTHON_EXE%' -ArgumentList '\"%~dp0windows_service.py\" remove' -Verb RunAs -Wait"
echo 卸载命令已执行。
echo.
pause
goto MENU

:START_SVC
echo.
powershell -Command "Start-Process net -ArgumentList 'start K8QuantWebService' -Verb RunAs -Wait"
echo.
pause
goto MENU

:STOP_SVC
echo.
powershell -Command "Start-Process net -ArgumentList 'stop K8QuantWebService' -Verb RunAs -Wait"
echo.
pause
goto MENU
