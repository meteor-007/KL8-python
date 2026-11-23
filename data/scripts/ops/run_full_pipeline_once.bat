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

if exist "storage\logs\full_pipeline_done.txt" del /q "storage\logs\full_pipeline_done.txt"

"%PY_CMD%" -u -m backend.pipeline.run_full_pipeline > "storage\logs\full_pipeline_20261123.log" 2>&1
set "RC=%ERRORLEVEL%"
echo EXIT=%RC% > "storage\logs\full_pipeline_done.txt"
exit /b %RC%