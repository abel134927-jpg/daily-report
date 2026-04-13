# ============================================================
# 每日財經新聞 - Windows 工作排程設定腳本 (使用 gh CLI)
# 不需要 GitHub PAT，使用已登入的 gh CLI 直接觸發
# 特性：錯過 07:00（電腦未開機）→ 下次開機時自動補跑
# ============================================================
# 使用方式：以「系統管理員」身份開啟 PowerShell，執行：
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup_scheduler.ps1
# ============================================================

$GhPath   = "C:\Program Files\GitHub CLI\gh.exe"
$Repo     = "abel134927-jpg/daily-report"
$Workflow = "daily_report.yml"
$TaskName = "每日財經新聞自動觸發"
$LogDir   = "$env:APPDATA\DailyNewsScheduler"
$LogFile  = "$LogDir\log.txt"
$ScriptFile = "$LogDir\trigger.ps1"

# ---------- 1. 確認 gh CLI 存在 ----------
if (-not (Test-Path $GhPath)) {
    Write-Host "找不到 gh CLI：$GhPath" -ForegroundColor Red
    Write-Host "請先安裝 GitHub CLI：https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

# ---------- 2. 確認 gh 已登入 ----------
$authCheck = & $GhPath auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "gh CLI 尚未登入，請先執行：gh auth login" -ForegroundColor Red
    exit 1
}
Write-Host "gh CLI 登入狀態確認 OK" -ForegroundColor Green

# ---------- 3. 建立設定目錄與觸發腳本 ----------
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

@"
# 每日財經新聞觸發腳本（由 Windows 工作排程器每天 07:00 執行）
`$GhPath  = "$GhPath"
`$LogFile = "$LogFile"
`$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

try {
    `$output = & "`$GhPath" workflow run "$Workflow" --repo "$Repo" 2>&1
    Add-Content -Path `$LogFile -Value "`$timestamp [OK] 觸發成功"
} catch {
    Add-Content -Path `$LogFile -Value "`$timestamp [FAIL] `$(`$_.Exception.Message)"
    exit 1
}
"@ | Out-File -FilePath $ScriptFile -Encoding UTF8

Write-Host "觸發腳本已建立：$ScriptFile" -ForegroundColor Green

# ---------- 4. 建立 Windows 工作排程 ----------
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptFile`""

$Trigger = New-ScheduledTaskTrigger -Daily -At "07:00"

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -MultipleInstances IgnoreNew

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "每天 07:00 觸發每日財經新聞（LINE 推送）。電腦未開機時，下次開機自動補跑。" `
    -Force | Out-Null

Write-Host ""
Write-Host "=== 設定完成！===" -ForegroundColor Green
Write-Host "排程名稱：$TaskName" -ForegroundColor White
Write-Host "執行時間：每天 07:00" -ForegroundColor White
Write-Host "補跑機制：電腦未開機 → 下次開機時自動補跑" -ForegroundColor White
Write-Host "日誌位置：$LogFile" -ForegroundColor White
Write-Host ""

# ---------- 5. 立即測試 ----------
$Test = Read-Host "要立即測試觸發一次嗎？(y/N)"
if ($Test -match '^[yY]$') {
    Write-Host "正在觸發..." -ForegroundColor Cyan
    & powershell.exe -ExecutionPolicy Bypass -File $ScriptFile
    Write-Host "完成，請到 GitHub Actions 確認是否執行。" -ForegroundColor Green
}
