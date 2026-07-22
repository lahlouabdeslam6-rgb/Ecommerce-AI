param(
    [string]$OutputDirectory = "",
    [int]$RetentionDays = 14
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot "backups"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFolder = Join-Path $OutputDirectory $timestamp
New-Item -ItemType Directory -Path $backupFolder -Force | Out-Null

Write-Host "Sauvegarde SQLite..."
docker compose cp backend:/app/data/ecommerce.db (Join-Path $backupFolder "ecommerce.db")
if ($LASTEXITCODE -ne 0) {
    throw "La sauvegarde SQLite a echoue."
}

Write-Host "Sauvegarde MongoDB..."
docker compose exec -T mongo sh -lc 'mongodump --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db "$MONGO_INITDB_DATABASE" --archive=/tmp/nutrifit-mongo.archive.gz --gzip'
if ($LASTEXITCODE -ne 0) {
    throw "La sauvegarde MongoDB a echoue."
}

docker compose cp mongo:/tmp/nutrifit-mongo.archive.gz (Join-Path $backupFolder "mongo.archive.gz")
if ($LASTEXITCODE -ne 0) {
    throw "La copie de la sauvegarde MongoDB a echoue."
}

docker compose exec -T mongo rm -f /tmp/nutrifit-mongo.archive.gz
if ($LASTEXITCODE -ne 0) {
    throw "Le nettoyage temporaire MongoDB a echoue."
}

Write-Host "Sauvegarde terminee: $backupFolder"

if ($RetentionDays -gt 0) {
    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    Get-ChildItem -LiteralPath $OutputDirectory -Directory |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object {
            $resolvedBackup = $_.FullName
            $resolvedRoot = (Resolve-Path -LiteralPath $OutputDirectory).Path
            if ($resolvedBackup.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $resolvedBackup -Recurse -Force
            }
        }
}
