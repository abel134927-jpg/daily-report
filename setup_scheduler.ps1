# ============================================================
# 每日財經新聞 - Windows 工作排程設定腳本
# 用途：設定每天 07:00 自動觸發 GitHub Actions 新聞推送
# 特性：錯過 07:00（例如電腦未開機）→ 下次開機時自動補跑
# ============================================================
# 使用方式：
#   以「系統管理員」身份開啟 PowerShell，執行：
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup_scheduler.ps1
# ============================================================

$ConfigDir  = "$env:APPDATA\DailyNewsScheduler"
$TokenFile  = "$ConfigDir\token.enc"
$TriggerPs1 = "$ConfigDir\trigger.ps1"
$LogFile    = "$ConfigDir\log.txt"
$TaskName   = "每日財經新聞自動觸發"

# ---------- 1. 建立設定目錄 ----------
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

# ---------- 2. 取得並加密儲存 GitHub PAT ----------
Write-Host ""
Write-Host "=== 每日財經新聞排程設定 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "需要 GitHub Personal Access Token（已有 workflow 權限）" -ForegroundColor Yellow
Write-Host "取得方式：GitHub -> Settings -> Developer settings -> Tokens (classic)"
Write-Host "需要勾選的權限：workflow"
Write-Host ""
$SecurePAT = Read-Host "請貼入 GitHub PAT (ghp_...)" -AsSecureString

# 使用目前 Windows 使用者的身份加密（只有此電腦此使用者可解密）
$EncryptedPAT = ConvertFrom-SecureString $SecurePAT
$EncryptedPAT | Out-File -FilePath $TokenFile -Encoding UTF8
Write-Host "Token 已加密儲存至 $TokenFile" -ForegroundColor Green

# ---------- 3. 建立每日觸發腳本 ----------
$TriggerScript = @"
# 每日財經新聞自動觸發腳本（由工作排程器執行）
`$LogFile = "$LogFile"
`$TokenFile = "$TokenFile"

try {
    # 解密 PAT
    `$enc = Get-Content `$TokenFile -Raw
    `$secure = ConvertTo-SecureString `$enc
    `$pat = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR(`$secure)
    )

    # 呼叫 GitHub API 觸發 workflow_dispatch
    `$headers = @{
        "Authorization" = "Bearer `$pat"
        "Accept"        = "application/vnd.github.v3+json"
        "Content-Type"  = "application/json"
    }
    `$body = '{"ref":"main"}'
    `$url  = "https://api.github.com/repos/abel134927-jpg/daily-report/actions/workflows/daily_report.yml/dispatches"

    Invoke-RestMethod -Method POST -Uri `$url -Headers `$headers -Body `$body -TimeoutSec 15

    `$msg = "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [OK] 已成功觸發每日新聞 GitHub Actions"
    Add-Content -Path `$LogFile -Value `$msg
    Write-Host `$msg
}
catch {
    `$msg = "`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [FAIL] 觸發失敗：`$(`$_.Exception.Message)"
    Add-Content -Path `$LogFile -Value `$msg
    Write-Host `$msg -ForegroundColor Red
    exit 1
}
"@

$TriggerScript | Out-File -FilePath $TriggerPs1 -Encoding UTF8
Write-Host "觸發腳本已建立：$TriggerPs1" -ForegroundColor Green

# ---------- 4. 註冊 Windows 工作排程 ----------
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$TriggerPs1`""

# 每天 07:00 台灣時間
$Trigger = New-ScheduledTaskTrigger -Daily -At "07:00"

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -MultipleInstances IgnoreNew

# 用目前登入使用者執行（不需輸入密碼）
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
    -Description "每天 07:00 觸發每日財經新聞 GitHub Actions（LINE 推送）。錯過時下次開機補跑。" `
    -Force | Out-Null

Write-Host ""
Write-Host "=== 設定完成！===" -ForegroundColor Green
Write-Host ""
Write-Host "排程名稱 : $TaskName" -ForegroundColor White
Write-Host "執行時間 : 每天 07:00" -ForegroundColor White
Write-Host "補跑機制 : 若電腦未開機，下次開機時自動補跑" -ForegroundColor White
Write-Host "日誌位置 : $LogFile" -ForegroundColor White
Write-Host ""
Write-Host "可在「工作排程器」中查看或手動執行測試：" -ForegroundColor Yellow
Write-Host "  工作排程器 -> 工作排程器程式庫 -> '$TaskName'" -ForegroundColor Yellow
Write-Host ""

# ---------- 5. 立即測試執行（可選）----------
$Test = Read-Host "要立即測試觸發一次嗎？(y/N)"
if ($Test -eq "y" -or $Test -eq "Y") {
    Write-Host "正在觸發 GitHub Actions..." -ForegroundColor Cyan
    & powershell.exe -ExecutionPolicy Bypass -File $TriggerPs1
}
