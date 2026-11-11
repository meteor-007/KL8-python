# PowerShell Launcher for K8-Quant Web Application
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Starting K8-QUANT Web terminal..." -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -Path $root
python run_server.py
