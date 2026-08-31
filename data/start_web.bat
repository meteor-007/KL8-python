@echo off
chcp 65001 > nul
title K8-QUANT 智能量化操盘决策终端
echo ========================================================
echo   🧬 正在启动 K8-QUANT 智能量化决策系统 Web 终端...
echo ========================================================
cd /d "%~dp0"
python run_server.py
pause
