@echo off
cd /d "%~dp0"
"C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe" uninstall_service.py
if errorlevel 1 (
    py uninstall_service.py
)
pause
