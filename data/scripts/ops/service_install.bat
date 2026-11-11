@echo off
cd /d "%~dp0..\.."
set PYTHON_EXE=C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=py
)
"%PYTHON_EXE%" "%~dp0install_service.py"
if errorlevel 1 (
    py "%~dp0install_service.py"
)
pause
