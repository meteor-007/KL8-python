@echo off
setlocal
rem K8Quant nightly runner: used by Windows Scheduled Task K8Quant_Nightly_2200
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

echo [K8Quant] started at %DATE% %TIME%
echo [K8Quant] python: %PY_CMD% %PY_ARGS%
if defined K8Q_DRY_RUN (
    echo [K8Quant] DRY RUN: would execute "%PY_CMD%" %PY_ARGS% "backend\pipeline\run_nightly_daily.py" %*
    exit /b 0
)
"%PY_CMD%" %PY_ARGS% "backend\pipeline\run_nightly_daily.py" %*
set "RC=%ERRORLEVEL%"
echo [K8Quant] finished with exit code %RC%
exit /b %RC%