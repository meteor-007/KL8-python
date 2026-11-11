@echo off
chcp 65001 > nul
title ?? K8-QUANT ?? 22:00 ?????????

echo ======================================================================
echo          ?? K8-QUANT ???????? - ?? 22:00 ??????
echo ======================================================================
echo.

cd /d "%~dp0..\.."
set PYTHON_EXE=C:\Users\zhiwei.chen\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=py
)

set SCRIPT_PATH=%~dp0run_nightly_daily.py

echo ??????????? Windows ?????????? 22:00 ????...
echo.
powershell -NoProfile -Command "Start-Process schtasks -ArgumentList '/Create /SC DAILY /TN \"K8Quant_Nightly_2200\" /TR \"\"\"%PYTHON_EXE%\"\" \"\"%SCRIPT_PATH%\"\"\" /ST 22:00 /F /RL HIGHEST' -Verb RunAs -Wait"

echo.
echo ======================================================================
echo ? ????????????
echo    - ????: ?? 22:00
echo    - ????: K8Quant_Nightly_2200
echo    - ????: run_nightly_daily.py
echo ======================================================================
echo.
pause
