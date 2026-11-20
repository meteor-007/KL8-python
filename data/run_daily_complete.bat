@echo off
chcp 65001 > nul
title K8-QUANT 快乐8 每日全流程决策一体机
cd /d "%~dp0"
set PYTHONPATH=%CD%
echo ================================================================
echo    K8-QUANT 快乐8 工业级全流程决策与科学复盘一体机 (v2.0)
echo ================================================================
echo.
python scripts/run_daily_complete.py %*
echo.
echo ================================================================
echo 按任意键退出...
pause > nul
