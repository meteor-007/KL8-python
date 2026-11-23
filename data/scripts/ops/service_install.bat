@echo off
chcp 65001 > nul
cd /d "%~dp0..\.."

set "PY_CMD=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

"%PY_CMD%" "%~dp0install_service.py" %*
if errorlevel 1 pause
exit /b %ERRORLEVEL%