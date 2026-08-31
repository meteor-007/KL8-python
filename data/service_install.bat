@echo off
cd /d "%~dp0"
"C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe" install_service.py
if errorlevel 1 (
    py install_service.py
)
pause
