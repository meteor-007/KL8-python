@echo off
chcp 65001 > nul
setlocal
title K8Quant Nightly Task Setup (daily 22:00)

set "TASK_NAME=K8Quant_Nightly_2200"
set "RUNNER=%~dp0run_nightly_task.bat"

if not exist "%RUNNER%" (
    echo [ERROR] Runner not found: %RUNNER%
    exit /b 1
)

echo Registering Windows Scheduled Task...
echo   Name  : %TASK_NAME%
echo   Time  : 22:00 daily
echo   Runner: %RUNNER%
echo.

schtasks /Create /SC DAILY /TN "%TASK_NAME%" /TR "%RUNNER%" /ST 22:00 /F
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to register the task. If access was denied, run this file as Administrator.
    exit /b 1
)

echo.
echo [OK] Task registered.
schtasks /Query /TN "%TASK_NAME%" /V /FO LIST
exit /b 0