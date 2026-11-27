# ==============================================================================
# 快乐8 每日最新点位与三高特征 Excel 自动解析与入库引擎
# (Daily Excel Points & Tri-High Automated Ingestion Engine)
# ==============================================================================
# 业务功能：
#   1. 自动扫描指定目录（默认 validation/file）下的最新点位 Excel 表格；
#   2. 定位匹配「快乐8点位图」Sheet 页；
#   3. 精准锚定最新期号（7位数字）及对应 K 列 20 码点位（A列编号 1-20）；
#   4. 精准提取副数据源：重复高概率号码、边码高概率号码（左右双翼）、冷号高概率号码；
#   5. 原子化落库更新 daily_points.txt 与 storage/points/tri_high_points.json；
#   6. 【平稳降级设计】：若未提供最新文件，友好提示并优雅退出，绝不阻断后续全流程预测。
# ==============================================================================

param(
    [string]$FilePath = "",
    [string]$FileDir = "",
    [switch]$CheckOnly,
    [switch]$AutoRun,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 确定工作目录与根路径
$CurrentDir = $PSScriptRoot
$DataDir = Split-Path -Parent $CurrentDir
if (-not (Test-Path "$DataDir\storage")) {
    $DataDir = (Get-Location).Path
}

$DefaultFileDir = Join-Path $DataDir "validation\file"
if ($FileDir -ne "") { $ScanDir = $FileDir } else { $ScanDir = $DefaultFileDir }

$DailyPointsFile = Join-Path $DataDir "storage\raw\daily_points.txt"
if (-not (Test-Path $DailyPointsFile)) {
    $DailyPointsFile = Join-Path $DataDir "daily_points.txt"
}
$TriHighFile = Join-Path $DataDir "storage\points\tri_high_points.json"
$HistoryFile = Join-Path $DataDir "storage\raw\kl8_history_final.txt"

function Write-Info([string]$msg, [string]$color = "Cyan") {
    if (-not $Quiet) {
        Write-Host "  [Excel点位引擎] $msg" -ForegroundColor $color
    }
}

# 1. 寻找目标文件
$TargetFile = $null
if ($FilePath -ne "" -and (Test-Path $FilePath)) {
    $TargetFile = Get-Item $FilePath
} else {
    if (Test-Path $ScanDir) {
        # 智能双维排序：优先按文件名内解析出的期号降序，其次按最后修改时间降序
        $candidates = Get-ChildItem -Path $ScanDir -Filter "*.xls*" -File | 
                      Where-Object { $_.Name -notmatch "^\~" -and $_.Length -gt 1024 } | 
                      Sort-Object @{
                          Expression = {
                              if ($_.Name -match "(20\d{5})") {
                                  [int]$Matches[1]
                              } elseif ($_.Name -match "(\d{3})期") {
                                  2026000 + [int]$Matches[1]
                              } else {
                                  0
                              }
                          }; Descending = $true
                      }, @{ Expression = "LastWriteTime"; Descending = $true }
        if ($candidates.Count -gt 0) {
            $TargetFile = $candidates[0]
        }
    }
}

if (-not $TargetFile) {
    Write-Info "⚠️ 未在目录 [$ScanDir] 检测到点位 Excel 文件。" "Yellow"
    Write-Info "💡 触发平稳降级：继续采用已有数据/历史模型推进全流程预测，不阻断任务。" "Green"
    exit 0
}

Write-Info "🎯 锁定分析目标文件: $($TargetFile.Name) (大小: $([math]::Round($TargetFile.Length/1MB, 2)) MB)" "Green"

# 2. 启动 WPS ET COM 进行解析（支持多候选文件回溯探测）
$wps = $null
$wb = $null
$Extracted = @{
    Period = ""
    Date = ""
    Points = @()
    RepeatHigh = @()
    EdgeHighLeft = @()
    EdgeHighRight = @()
    ColdHigh = @()
}

$candidatesToTest = @()
if ($TargetFile) {
    if ($FilePath -ne "") {
        $candidatesToTest = @($TargetFile)
    } else {
        # 取最新前 5 个候选文件逐一探测包含「快乐8点位图」的工作簿
        $candidatesToTest = $candidates | Select-Object -First 5
    }
}

try {
    $wps = New-Object -ComObject "Ket.Application"
    $wps.Visible = $false
    $wps.DisplayAlerts = $false
    
    $matchedFile = $null
    $sh = $null

    foreach ($cand in $candidatesToTest) {
        Write-Info "🔍 探测候选文件: $($cand.Name) (大小: $([math]::Round($cand.Length/1MB, 2)) MB)..." "Gray"
        try {
            $curWb = $wps.Workbooks.Open($cand.FullName, [Type]::Missing, $true)
            foreach ($s in $curWb.Sheets) {
                if ($s.Name -like "*快乐8点位图*") {
                    $sh = $s
                    $wb = $curWb
                    $matchedFile = $cand
                    break
                }
            }
            if ($matchedFile) {
                break
            } else {
                $curWb.Close($false)
            }
        } catch {
            # 单个文件打开失败则尝试下一个
        }
    }
    
    if (-not $sh) {
        Write-Info "❌ 候选文件中未发现名称包含 [快乐8点位图] 的 Sheet 页，本次不写入。" "Red"
        Write-Info "   请确认下载的是点位图工作簿 (如 2026316(2).xls)，而不是找胆图/统计图那两份。" "Yellow"
        exit 1
    }
    
    Write-Info "🎯 成功锁定目标文件: $($matchedFile.Name) -> 工作表: [$($sh.Name)]" "Green"
    
    $maxRow = $sh.UsedRange.Rows.Count
    if ($maxRow -lt 100) { $maxRow = 9500 }
    
    # 从下往上扫描定位最新点位块 (7位数字，如 2026305)
    # 2026-11-26 修正: 点位块是"两行期号 + 点/位 + 20码"的结构，块首行才是这 20 码的目标期；
    # 紧挨着它下面那行是站点自己写的下一期占位标签。原来直接取从下往上第一个期号，
    # 抓到的正是占位行，导致期号整体错位一期 (例: 2026317)，只能靠后面"智能校准"硬掰回来。
    $periodRow = 0
    $foundPeriod = ""
    for ($r = $maxRow; $r -ge 1; $r--) {
        $cellVal = $sh.Cells.Item($r, 1).Text.Trim()
        if ($cellVal -match "^(20\d{5})$") {
            $foundPeriod = $cellVal
            $periodRow = $r
            break
        }
    }
    
    if ($periodRow -eq 0) {
        Write-Info "❌ 未能在 A 列检索到有效的 7 位快乐8期号，本次不写入。" "Red"
        exit 1
    }
    
    if ($periodRow -gt 1) {
        $prevVal = $sh.Cells.Item($periodRow - 1, 1).Text.Trim()
        if ($prevVal -match "^(20\d{5})$" -and [int]$prevVal -lt [int]$foundPeriod) {
            Write-Info "🔧 期号锚定: 块首行 [$prevVal] 为本块目标期 (下一行 [$foundPeriod] 是站点占位标签)" "Gray"
            $foundPeriod = $prevVal
        }
    }
    
    $Extracted.Period = $foundPeriod
    Write-Info "📌 捕获最新目标期号: [$foundPeriod] (点位块首行位于第 $periodRow 行)" "Green"
    
    # 提取 K 列 (第 11 列) 对应的 20 个点位号码 (A列编号 1-20)
    $pts = @()
    for ($i = 1; $i -le 20; $i++) {
        $r = $periodRow + 1 + $i
        $val = $sh.Cells.Item($r, 11).Text.Trim()
        if ($val -ne "") {
            $num = [int]$val
            if ($num -ge 1 -and $num -le 80) {
                $pts += $num.ToString("D2")
            }
        }
    }
    
    if ($pts.Count -lt 19) {
        Write-Info "❌ K 列点位号码不足 19 码 (当前检测到 $($pts.Count) 码)，放弃写入。" "Red"
        exit 1
    }
    if ($pts.Count -lt 20) {
        Write-Info "⚠️ 源表 K 列只给了 $($pts.Count) 码点位 (缺 $(20 - $pts.Count) 码，最后一格是空的)。" "Yellow"
        Write-Info "   按实际 $($pts.Count) 码入库；研报会在缺口清单标注「点位不足 20 码」，点位类模块按实际数量算。" "Yellow"
    }
    
    $Extracted.Points = $pts
    Write-Info "💎 成功提取 $($pts.Count) 码点位: $($pts -join ' ')" "Cyan"
    
    # 提取图2数据源（三高高概率特征池）
    for ($r = $periodRow + 22; $r -le $periodRow + 32; $r++) {
        $label = $sh.Cells.Item($r, 1).Text.Trim()
        if ($label -like "*重复高概率*") {
            for ($c = 12; $c -le 25; $c++) {
                $v = $sh.Cells.Item($r, $c).Text.Trim()
                if ($v -match "^\d+$") { $Extracted.RepeatHigh += [int]$v }
            }
        } elseif ($label -like "*边码高概率*") {
            # 左翼 4 码 (通常列 12..15)
            for ($c = 12; $c -le 15; $c++) {
                $v = $sh.Cells.Item($r, $c).Text.Trim()
                if ($v -match "^\d+$") { $Extracted.EdgeHighLeft += [int]$v }
            }
            # 右翼 4 码 (通常列 17..22)
            for ($c = 17; $c -le 22; $c++) {
                $v = $sh.Cells.Item($r, $c).Text.Trim()
                if ($v -match "^\d+$") { $Extracted.EdgeHighRight += [int]$v }
            }
        } elseif ($label -like "*冷号高概率*") {
            for ($c = 12; $c -le 25; $c++) {
                $v = $sh.Cells.Item($r, $c).Text.Trim()
                if ($v -match "^\d+$") { $Extracted.ColdHigh += [int]$v }
            }
        }
    }
    
    Write-Info "  ├─ 上期重复高概率 ($($Extracted.RepeatHigh.Count)码) : $($Extracted.RepeatHigh -join ', ')" "Gray"
    Write-Info "  ├─ 边码高概率左翼 ($($Extracted.EdgeHighLeft.Count)码) : $($Extracted.EdgeHighLeft -join ', ')" "Gray"
    Write-Info "  ├─ 边码高概率右翼 ($($Extracted.EdgeHighRight.Count)码) : $($Extracted.EdgeHighRight -join ', ')" "Gray"
    Write-Info "  └─ 冷号高概率指标 ($($Extracted.ColdHigh.Count)码) : $($Extracted.ColdHigh -join ', ')" "Gray"
    
} catch {
    Write-Info "❌ Excel 读取或 COM 执行异常: $($_.Exception.Message)" "Red"
    Write-Info "   本次不写入台账。修好 WPS/文件后重跑本脚本，不要带着旧点位往下跑。" "Yellow"
    exit 1
} finally {
    if ($wb) { $wb.Close($false) }
    if ($wps) { 
        $wps.Quit()
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($wps) | Out-Null
    }
}

# 3. 期号校验与日期推断 (2026-11-26 整改: 删掉"超前就掰回"的智能校准)
#    大白话: 原来只要 Excel 期号比开奖库超前 1 期以上，就强行改成 lastPeriod+1 再写库。
#    这个"猜"法会把站点占位标签当真实期号，一旦同步顺序变了就写错期。
#    现在改成"只认唯一合法目标期 = 最新开奖期 + 1"，其余情况一律不写、返回明确退出码。
$targetDate = (Get-Date).ToString("yyyy-MM-dd")
if (Test-Path $HistoryFile) {
    $firstLine = Get-Content -Path $HistoryFile -First 1
    if ($firstLine -match "date:([0-9\-]+),period:(\d+)") {
        $lastDate = [datetime]::ParseExact($Matches[1], "yyyy-MM-dd", $null)
        $lastPeriod = [int]$Matches[2]
        $diff = [int]$Extracted.Period - $lastPeriod
        
        if ($diff -lt 1) {
            Write-Info "⏭️ Excel 最新点位块 [$($Extracted.Period)] 不晚于开奖库最新期 [$lastPeriod]，判定为旧文件。" "Yellow"
            Write-Info "   本次不写入台账 (exit 2)。等站点更新出下一期点位块后再导入。" "Yellow"
            exit 2
        }
        if ($diff -gt 1) {
            Write-Info "❌ Excel 期号 [$($Extracted.Period)] 比开奖库最新期 [$lastPeriod] 超前 $diff 期，拒绝写入 (exit 3)。" "Red"
            Write-Info "   多半是开奖历史没同步到位，或点位文件期号标注错误。先同步开奖再导入。" "Yellow"
            exit 3
        }
        $targetDate = $lastDate.AddDays($diff).ToString("yyyy-MM-dd")
    }
}
$Extracted.Date = $targetDate

if ($CheckOnly) {
    Write-Info "🔎 [CheckOnly 模式] 解析完成，不执行落盘。" "Yellow"
    exit 0
}

# 4. 原子化落库更新 daily_points.txt
Write-Info "💾 正在落库更新: daily_points.txt (期号: $($Extracted.Period), 日期: $targetDate)" "Green"
$newPointLine = "date:$targetDate,period:$($Extracted.Period),points:$($Extracted.Points -join ' ')"

$existingLines = @()
if (Test-Path $DailyPointsFile) {
    $existingLines = Get-Content -Path $DailyPointsFile
}

$updatedLines = @()
$found = $false
foreach ($line in $existingLines) {
    if ($line -match "period:$($Extracted.Period)\b") {
        # 已存在则更新
        $updatedLines += $newPointLine
        $found = $true
    } else {
        $updatedLines += $line
    }
}

if (-not $found) {
    # 不存在则按期号降序插入到顶部
    $updatedLines = @($newPointLine) + $updatedLines
}

# 备份
$backupDir = Join-Path (Split-Path -Parent $DailyPointsFile) "backup"
if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
Copy-Item -Path $DailyPointsFile -Destination "$backupDir\daily_points_$(Get-Date -Format 'yyyyMMdd_HHmmss').bak" -Force -ErrorAction SilentlyContinue

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($DailyPointsFile, ($updatedLines -join "`r`n"), $utf8NoBom)
Write-Info "✅ 点位已成功落盘至 $DailyPointsFile (无BOM UTF-8)" "Green"

# 5. 原子化更新 tri_high_points.json
if (Test-Path $TriHighFile) {
    try {
        $jsonContent = Get-Content -Path $TriHighFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $newRecord = [PSCustomObject]@{
            period = $Extracted.Period.ToString()
            date = $targetDate
            repeat_high = $Extracted.RepeatHigh
            edge_high_left = $Extracted.EdgeHighLeft
            edge_high_right = $Extracted.EdgeHighRight
            cold_high = $Extracted.ColdHigh
        }
        
        $records = @($jsonContent.records)
        $idx = -1
        for ($k = 0; $k -lt $records.Count; $k++) {
            if ($records[$k].period -eq $Extracted.Period) {
                $idx = $k
                break
            }
        }
        
        if ($idx -ge 0) {
            $records[$idx] = $newRecord
        } else {
            $records = @($newRecord) + $records
        }
        
        $jsonContent.records = $records
        $jsonStr = $jsonContent | ConvertTo-Json -Depth 5
        [System.IO.File]::WriteAllText($TriHighFile, $jsonStr, $utf8NoBom)
        Write-Info "✅ 三高特征库已成功更新至 $TriHighFile (无BOM UTF-8)" "Green"
    } catch {
        Write-Info "⚠️ 更新 tri_high_points.json 失败: $($_.Exception.Message)" "Yellow"
    }
}

Write-Info "🎉 目标期 [$($Extracted.Period)] Excel 数据自动解析与双库对齐全部完成！" "Green"
exit 0
