@echo off
setlocal
rem K8Quant watchdog runner: used by Windows Scheduled Task K8Quant_Watchdog
rem ASCII only on purpose: cmd.exe mangles non-ANSI text on some locales.

cd /d "%~dp0..\.."
if errorlevel 1 (
    echo [ERROR] Cannot change to data directory: %~dp0..\..
    exit /b 1
)

set "PY_CMD="
set "PY_ARGS="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=py"
        set "PY_ARGS=-3"
    )
)
if not defined PY_CMD set "PY_CMD=python"

set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%CD%"

if not exist "storage\logs" mkdir "storage\logs"

echo [%DATE% %TIME%] watchdog start >> "storage\logs\watchdog.log"
"%PY_CMD%" %PY_ARGS% "backend\utils\nightly_watchdog.py" --json %* >> "storage\logs\watchdog.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%DATE% %TIME%] watchdog end rc=%RC% >> "storage\logs\watchdog.log"
exit /b %RC%