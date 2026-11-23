@echo off
chcp 65001 > nul
title K8-QUANT 快乐8 每日全流程决策一体机
cd /d "%~dp0"
set PYTHONPATH=%CD%
rem 2026-11-22 修复：PATH 默认 python 指向妙手托管运行时 3.12，缺 numpy/pandas，
rem 直接双击会报 ModuleNotFoundError。优先使用依赖齐全的系统 Python 3.11，缺失时回退 python。
set PY311=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
if exist "%PY311%" (
    set PYRUN=%PY311%
) else (
    set PYRUN=python
)
echo ================================================================
echo    K8-QUANT 快乐8 工业级全流程决策与科学复盘一体机 (v2.0)
echo ================================================================
echo.
%PYRUN% scripts\run_daily_complete.py %*
echo.
echo ================================================================
echo 按任意键退出...
pause > nul
