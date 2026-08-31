# 快乐8 每日全流程执行脚本 v4.2 (模块化重构版)
# ============================================================
# 用法：在 PowerShell 中执行：
#   cd D:\Dpanqianyi\Python-Project\data
#   PowerShell -ExecutionPolicy Bypass -File run_daily_quant_v4.ps1
# ============================================================

$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "快乐8 每日全流程推演 v4.2"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Banner {
    param([string]$text, [string]$fg = "Cyan")
    $line = "=" * 75
    Write-Host $line -ForegroundColor $fg
    Write-Host "  $text" -ForegroundColor $fg
    Write-Host $line -ForegroundColor $fg
}

function Write-Step {
    param([string]$num, [string]$title, [string]$fg = "Yellow")
    Write-Host ""
    Write-Host "+----- [$num] $title" -ForegroundColor $fg
    Write-Host "|" -ForegroundColor $fg
}

function ok  { Write-Host "  OK  $_" -ForegroundColor Green }
function warn{ Write-Host "  **  $_" -ForegroundColor Yellow }
function err { Write-Host "  !!  $_" -ForegroundColor Red }

Set-Location "D:\Dpanqianyi\Python-Project\data"

Write-Banner "快乐8预测系统 每日全流程分析脚本 v4.2 [模块化标准版] [$(Get-Date -Format 'yyyy-MM-dd HH:mm')]" "Cyan"

# ═══ 任务0：环境预检 ═══
Write-Step "任务0" "环境预检与清理"
$locks = Get-ChildItem -Path "." -Filter "*.excel_lock" -Recurse -File -ErrorAction SilentlyContinue
if ($locks) {
    Write-Host "  发现残留锁文件，正在清理..." -ForegroundColor Yellow
    $locks | Remove-Item -Force
    ok "锁文件已清理"
} else {
    ok "无残留锁文件"
}
$pyVer = python --version 2>&1
ok "Python: $pyVer"

# ═══ 任务0.0：数据一致性强制校验 ═══
Write-Step "任务0.0" "数据一致性强制校验与自动修复"
Write-Host "  执行: python backend\utils\data_validator.py --auto-fix" -ForegroundColor Gray
python backend\utils\data_validator.py --auto-fix
if ($LASTEXITCODE -eq 0) { ok "校验完成" } else { warn "校验有警告，继续执行..." }

# ═══ 任务1.1：开奖历史抓取 ═══
Write-Step "任务1.1" "双源抓取最新开奖历史"
Write-Host "  执行: python backend\data_acquisition\fetch_kl8_history.py" -ForegroundColor Gray
python backend\data_acquisition\fetch_kl8_history.py
if ($LASTEXITCODE -eq 0) { ok "历史数据抓取完成" } else { warn "抓取有异常，继续..." }

# 显示最新期号
$historyFile = "kl8_history_final.txt"
if (-not (Test-Path $historyFile)) { $historyFile = "storage\raw\kl8_history_final.txt" }
if (Test-Path $historyFile) {
    $firstLine = Get-Content $historyFile -First 1
    if ($firstLine -match "period:(\d+)") { ok "历史最新期号: $($matches[1])" }
}

# ═══ 任务1.2：热码统计生成 ═══
Write-Step "任务1.2-A" "热码缺期补偿 (--fill-missing)"
python backend\data_acquisition\generate_hot_excel.py --fill-missing
if ($LASTEXITCODE -eq 0) { ok "缺期补偿完成" }

Write-Step "任务1.2-B" "生成最新期热码统计"
python backend\data_acquisition\generate_hot_excel.py
if ($LASTEXITCODE -eq 0) { ok "热码统计生成完成" }

Write-Step "任务1.2-C" "批量同步热码到Excel"
python backend\data_acquisition\process_hot_numbers.py --sync-all-missing
if ($LASTEXITCODE -eq 0) { ok "热码同步完成" }

# 验证热码统计
$hotDir = "热码统计\"
if (-not (Test-Path $hotDir)) { $hotDir = "storage\raw\热码统计\" }
$hotFiles = Get-ChildItem $hotDir -Filter "*.xlsx" -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 3
if ($hotFiles) {
    ok "热码统计最新文件:"
    $hotFiles | ForEach-Object { Write-Host "    $($_.Name)" -ForegroundColor White }
} else {
    warn "热码统计目录提示: 正在同步中"
}

# ═══ 任务1.3：历史同步 ═══
Write-Step "任务1.3" "历史数据同步到Excel"
python backend\data_acquisition\sync_history_to_excel.py
if ($LASTEXITCODE -eq 0) { ok "历史同步完成" }

# ═══ 任务1.4：点位验证 ═══
Write-Step "任务1.4" "点位数据验证"
$pointsFile = "daily_points.txt"
if (-not (Test-Path $pointsFile)) { $pointsFile = "storage\raw\daily_points.txt" }
if (Test-Path $pointsFile) {
    $points = Get-Content $pointsFile -First 3
    ok "最新点位数据:"
    $points | ForEach-Object { Write-Host "    $_" -ForegroundColor White }
}

# ═══ 任务1.5：Excel格式化 ═══
Write-Step "任务1.5" "Excel增量格式化"
python backend\format\apply_formats.py
if ($LASTEXITCODE -eq 0) { ok "格式化完成" }

# ═══ 任务4：核心分析推演 ═══
Write-Step "任务4" "核心量化推演引擎 (backend\pipeline\auto_generate_daily_report.py)" "Green"
Write-Host ""
Write-Host "  ##########################################" -ForegroundColor Magenta
Write-Host "  ##  正在执行量化推演，请稍候...        ##" -ForegroundColor Magenta
Write-Host "  ##########################################" -ForegroundColor Magenta
Write-Host ""
python backend\pipeline\auto_generate_daily_report.py

# ═══ 任务5：报告验证 ═══
Write-Step "任务5" "报告完整性验证"
$today = Get-Date -Format "yyyyMMdd"
$reportPath = "reports\daily_analysis_report_$today.md"
if (-not (Test-Path $reportPath)) { $reportPath = "storage\reports\daily_analysis_report_$today.md" }
if (Test-Path $reportPath) {
    $size = (Get-Item $reportPath).Length
    ok "今日报告已生成: $reportPath ($size bytes)"
    Write-Host ""
    Write-Host "  ─── 报告摘要 (前100行) ─────────────────────────────" -ForegroundColor Cyan
    Get-Content $reportPath -Encoding UTF8 | Select-Object -First 100 | ForEach-Object {
        Write-Host "  $_" -ForegroundColor White
    }
} else {
    err "未找到今日报告！"
    Write-Host "  检查 backend\pipeline\auto_generate_daily_report.py 的错误输出" -ForegroundColor Yellow
}

# ═══ 任务6：清理缓存 ═══
Write-Step "任务6" "清理 __pycache__"
Get-ChildItem -Path "." -Include "__pycache__" -Recurse -Force -Directory -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
ok "缓存清理完成"

Write-Host ""
Write-Banner "全域推演完成！报告: $reportPath" "Green"
Write-Host ""
