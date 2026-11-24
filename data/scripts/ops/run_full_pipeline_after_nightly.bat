@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0..\.."

set "AUTO_GIT_SYNC=0"
set "AUTO_GIT_PUSH=0"
set "PYTHONIOENCODING=utf-8"

set "PY_CMD=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

rem Wait until the nightly pipeline releases its lock (or its PID is gone).
:wait_lock
if not exist "storage\cache\nightly_run.lock" goto run
set "NSTATE=DEAD"
for /f %%p in ('powershell -NoProfile -Command "try{$j=Get-Content 'storage\cache\nightly_run.lock' -Raw|ConvertFrom-Json; if(Get-Process -Id $j.pid -ErrorAction SilentlyContinue){'ALIVE'}else{'DEAD'}}catch{'DEAD'}"') do set "NSTATE=%%p"
if /i "%NSTATE%"=="DEAD" goto run
timeout /t 15 /nobreak >nul
goto wait_lock

:run
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%i"
set "LOG=storage\logs\full_pipeline_%TODAY%.log"
if exist "storage\logs\full_pipeline_done.txt" del /q "storage\logs\full_pipeline_done.txt"

"%PY_CMD%" -u -m backend.pipeline.run_full_pipeline > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo EXIT=%RC% > "storage\logs\full_pipeline_done.txt"
exit /b %RC%