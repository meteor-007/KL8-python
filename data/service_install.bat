@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title K8-QUANT Web 服务一键安装与自启配置

:: ------------------ 检查是否具备管理员权限 ------------------
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
echo          🧬 K8-QUANT 智能量化决策系统 Web 服务安装程序
echo ======================================================================
echo  工作目录: %~dp0
echo  Python路径: %PYTHON_EXE%
echo ======================================================================
echo.

echo [步骤 1/3] 正在注册 Windows 系统服务 (K8QuantWebService)...
"%PYTHON_EXE%" "%~dp0windows_service.py" --startup=auto install
set INSTALL_ERR=%errorlevel%

if %INSTALL_ERR% EQU 0 (
    echo  ▶ 系统服务注册成功！
    echo.
    echo [步骤 2/3] 配置服务崩溃自动恢复机制 (高可用保障)...
    sc.exe failure K8QuantWebService reset= 86400 actions= restart/5000/restart/10000/restart/60000 >nul 2>&1
    echo  ▶ 崩溃自动拉起已配置完成。
    echo.
    echo [步骤 3/3] 正在启动系统服务...
    "%PYTHON_EXE%" "%~dp0windows_service.py" start
    net start K8QuantWebService >nul 2>&1
) else (
    echo.
    echo ⚠️ 系统底层服务注册受限于用户环境，正在为您无缝切换至【Windows 后台自启守护模式】...
    echo.
    echo [步骤 2/3] 正在创建 Windows 开机自启守护启动器...
    set STARTUP_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\K8QuantWebAutoStart.vbs
    (
        echo Set ws = CreateObject^("Wscript.Shell"^)
        echo ws.Run "cmd.exe /c cd /d ""%~dp0"" && ""%PYTHON_EXE%"" run_server.py --no-browser >> logs\web_server.log 2>&1", 0, False
    ) > "!STARTUP_VBS!"
    echo  ▶ 已成功写入 Windows 开机启动组: !STARTUP_VBS!
    echo.
    echo [步骤 3/3] 正在以后台静默守护模式启动 Web 服务...
    wscript.exe "%~dp0start_web_background.vbs"
)

echo.
echo ======================================================================
echo  🔍 正在检测 Web 服务运行状态...
echo ======================================================================
timeout /t 2 >nul
"%PYTHON_EXE%" "%~dp0backend_daemon.py" status

echo.
echo ----------------------------------------------------------------------
echo 🎉 配置完成！
echo   ▶ 访问地址: http://127.0.0.1:8000
echo   ▶ 特性保障: 后台静默运行，关闭任何窗口都不会停止，开机自动启动！
echo ----------------------------------------------------------------------
echo.
pause
