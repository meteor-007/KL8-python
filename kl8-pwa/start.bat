@echo off
chcp 65001 >nul 2>&1
echo ════════════════════════════════════════════════════════
echo   KL8 每日全流程调度 PWA
echo   http://localhost:5888
echo ════════════════════════════════════════════════════════
cd /d "%~dp0"
python app.py
pause
