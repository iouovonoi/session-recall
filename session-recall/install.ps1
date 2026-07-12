param(
    [switch] $InstallScheduler,
    [switch] $SkipInitialSync,
    [int] $InitialSyncLimit = 200,
    [int] $EveryMinutes = 30
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$SkillRoot = $PSScriptRoot
$MainScript = Join-Path $SkillRoot "scripts\session-recall.ps1"
$SchedulerScript = Join-Path $SkillRoot "scripts\install-session-recall-scheduler.ps1"

if (-not (Test-Path -LiteralPath $MainScript)) {
    throw "session-recall.ps1 not found at: $MainScript"
}

Write-Output "Initializing Session Recall local index..."
$dbPath = & powershell -NoProfile -ExecutionPolicy Bypass -File $MainScript init

if (-not $SkipInitialSync) {
    Write-Output "Importing recent Copilot sessions into the local recall index..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $MainScript sync-copilot --limit $InitialSyncLimit --graph
}

if ($InstallScheduler) {
    if (-not (Test-Path -LiteralPath $SchedulerScript)) {
        throw "Scheduler installer not found at: $SchedulerScript"
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $SchedulerScript -EveryMinutes $EveryMinutes
}

Write-Output "Session Recall installed."
Write-Output "Local index: $dbPath"
if ($SkipInitialSync) {
    Write-Output "Initial session import: skipped"
}
else {
    Write-Output "Initial session import: up to $InitialSyncLimit sessions"
}
Write-Output "No personal session data was bundled or uploaded."
