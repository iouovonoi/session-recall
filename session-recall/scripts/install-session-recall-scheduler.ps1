param(
    [int] $EveryMinutes = 30
)

$ErrorActionPreference = "Stop"

$SkillScript = Join-Path $PSScriptRoot "session-recall.ps1"
$TaskName = "CopilotSessionRecallSync"

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$SkillScript`" sync-copilot --limit 200 --graph"

$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Sync Copilot native sessions into the local Session Recall index and graph." `
    -Force | Out-Null

Write-Output "Installed scheduled task: $TaskName, every $EveryMinutes minutes"
