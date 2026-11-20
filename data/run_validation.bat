@echo off
chcp 65001 > nul
title KL8 Validation - 点位与遗漏科学检验裁判
cd /d "%~dp0"
python main_validation.py %*
