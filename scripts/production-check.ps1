param(
    [string]$EnvironmentFile = ".env"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw "Fichier $EnvironmentFile introuvable."
}

$content = Get-Content -Raw -LiteralPath $EnvironmentFile
$required = @(
    "MONGO_ROOT_PASSWORD",
    "JWT_SECRET_KEY",
    "AUTOMATION_API_KEY",
    "N8N_ENCRYPTION_KEY"
)
$unsafe = @(
    "change_this_password",
    "generate_a_secure_random_secret",
    "local-automation-key-change-me",
    "local-n8n-key-change-me"
)

foreach ($name in $required) {
    if ($content -notmatch "(?m)^$name=(.+)$") {
        throw "Variable obligatoire absente: $name"
    }
}
foreach ($value in $unsafe) {
    if ($content.Contains($value)) {
        throw "Valeur de demonstration detectee: $value"
    }
}

docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Configuration Docker production invalide."
}

Write-Host "OK - secrets presents et configuration production valide."
