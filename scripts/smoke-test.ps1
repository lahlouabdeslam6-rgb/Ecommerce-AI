param(
    [string]$FrontendUrl = "http://localhost:5173",
    [string]$BackendUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

Write-Host "NUTRIFIT - controle rapide"

$health = Invoke-RestMethod -Uri "$BackendUrl/health" -Method Get
Assert-True ($health.status -eq "healthy") "Le backend n'est pas healthy."
Assert-True ($health.services.mongodb -eq "healthy") "MongoDB n'est pas healthy."
Assert-True ($health.services.sqlite -eq "healthy") "SQLite n'est pas healthy."

$products = Invoke-RestMethod -Uri "$BackendUrl/api/products?page=1&page_size=1" -Method Get
Assert-True ($products.total -gt 0) "Aucun produit n'est disponible."

$homepage = Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing
Assert-True ($homepage.StatusCode -eq 200) "Le frontend ne repond pas."
Assert-True ($homepage.Content -match "NUTRIFIT") "Le branding NUTRIFIT est absent."
Assert-True ($homepage.Content -match "Nutrition &amp; Performance") "Le slogan NUTRIFIT est absent."

Write-Host "OK - API, MongoDB, SQLite, produits et frontend fonctionnent."
