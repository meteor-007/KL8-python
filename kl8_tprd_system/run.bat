@echo off
chcp 65001 > nul
title TPRD v4.0 - 快乐8 智能量化缩水与双螺旋矩阵系统
set "PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

cd /d "%~dp0"
echo ========================================================
echo   正在运行 TPRD v4.0 快乐8 全维量化推演与矩阵系统...
echo ========================================================

"%PYTHON_EXE%" main.py %*
pause
