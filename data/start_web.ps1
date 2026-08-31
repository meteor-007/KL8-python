# PowerShell Launcher for K8-Quant Web Application
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  🧬 正在启动 K8-QUANT 智能量化决策系统 Web 终端..." -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

Set-Location -Path $PSScriptRoot
python run_server.py
