<#
The weekly check of the coupons on this PC (ADR-0114), run by Task Scheduler. Today's main, in a worktree of its own outside this
checkout, re-solves every coupon under .local\fea in a copy and sets its numbers beside last week's (fea/tools/weekly_coupons.py).
Nothing in this checkout changes but .local\weekly\, where the report, the log and the snapshots go; the coupons never leave the PC.
A Windows notification says when a coupon's numbers moved or the check failed; a check where nothing moved stays quiet.

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\weekly-coupons.ps1              # one check now
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\weekly-coupons.ps1 -Register    # Sundays at 2 AM, or as soon after as the PC is on
    ... -Ref origin/<branch>                                                                     # one check with a branch's code, before it merges
    Unregister-ScheduledTask -TaskName "Anisotropy weekly coupon check"                           # to stop it
#>
param([switch]$Register, [string]$Repo = (Split-Path -Parent $PSScriptRoot), [string]$Ref = "origin/main")

# Continue, not Stop: Windows PowerShell 5.1 turns a native command's stderr (uv's progress) into an error under Stop. Each step's
# exit code is checked instead.
$ErrorActionPreference = "Continue"
$TaskName = "Anisotropy weekly coupon check"

function Show-Note([string]$Title, [string]$Text) {
  # A toast through Windows PowerShell's own app id; a PC that refuses it still has the report and the log.
  try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $lines = $xml.GetElementsByTagName("text")
    $lines.Item(0).AppendChild($xml.CreateTextNode($Title)) | Out-Null
    $lines.Item(1).AppendChild($xml.CreateTextNode($Text)) | Out-Null
    $app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
  } catch {
    Write-Output "no notification: $_"
  }
}

function Write-Log([string]$Text) { Add-Content -Path $script:Log -Value $Text -Encoding utf8 }

function Invoke-Step([string]$What, [scriptblock]$Command) {
  Write-Log "> $What"
  & $Command 2>&1 | ForEach-Object { Write-Log "$_" }
  if ($LASTEXITCODE -ne 0) { throw "$What exited $LASTEXITCODE" }
}

if ($Register) {
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Repo `"$Repo`""
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2am
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4)
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force `
    -Description "Re-solves the coupons under $Repo\.local\fea with today's main, in a copy, and reports what moved (scripts\weekly-coupons.ps1)." | Out-Null
  Write-Output "Registered '$TaskName': Sundays at 2 AM, or as soon after as the PC is on."
  return
}

$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$weekly = Join-Path $Repo ".local\weekly"
$work = Join-Path $weekly $stamp
$code = Join-Path $env:LOCALAPPDATA "Anisotropy\weekly-code"
New-Item -ItemType Directory -Force -Path $weekly | Out-Null
$script:Log = Join-Path $weekly "$stamp.log"
$status = 3
try {
  Invoke-Step "git fetch" { git -C $Repo fetch --quiet origin }
  if (Test-Path (Join-Path $code ".git")) {
    Invoke-Step "git checkout" { git -C $code checkout --quiet --force --detach $Ref }
  } else {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $code) | Out-Null
    Invoke-Step "git worktree add" { git -C $Repo worktree add --detach $code $Ref }
  }
  $commit = (git -C $code rev-parse HEAD).Trim()
  Write-Log "$Ref at $commit"
  Push-Location $code
  try {
    Invoke-Step "uv sync" { uv sync --project fea --locked --extra mesh }
    Write-Log "> the check"
    uv run --project fea --extra mesh python fea/tools/weekly_coupons.py --from (Join-Path $Repo ".local\fea") --work $work `
      --snapshots (Join-Path $weekly "snapshots") --commit $commit 2>&1 | ForEach-Object { Write-Log "$_" }
    $status = $LASTEXITCODE
  } finally {
    Pop-Location
  }
} catch {
  Write-Log "the check stopped: $_"
}
Write-Log "exit $status"

$report = Join-Path $work "report.md"
switch ($status) {
  0 { }
  1 { Show-Note "Anisotropy: a coupon's numbers moved" "The weekly check found a change or a failed run. Report: $report" }
  2 { Show-Note "Anisotropy: no coupon to check" "The weekly check found no coupon under $Repo\.local\fea." }
  default { Show-Note "Anisotropy: the weekly check stopped" "See the log in $weekly ($stamp.log)." }
}
exit $status
