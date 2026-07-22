param(
    [string]$TaskName = "NUTRIFIT Daily Backup",
    [string]$RunAt = "02:00"
)

$ErrorActionPreference = "Stop"
$backupScript = Join-Path $PSScriptRoot "backup.ps1"
if (-not (Test-Path -LiteralPath $backupScript)) {
    throw "backup.ps1 introuvable."
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$backupScript`""
$trigger = New-ScheduledTaskTrigger -Daily -At $RunAt
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Sauvegarde quotidienne MongoDB et SQLite pour NUTRIFIT" `
    -Force

Write-Host "Tache planifiee creee: $TaskName a $RunAt"
