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

function Invoke-FrontendWithRetry {
    param(
        [string]$Uri,
        [int]$Attempts = 15
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            return Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 10
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw
            }
            Start-Sleep -Seconds 1
        }
    }
}

Write-Host "NUTRIFIT - controle rapide"

$health = Invoke-RestMethod -Uri "$BackendUrl/health" -Method Get
Assert-True ($health.status -eq "healthy") "Le backend n'est pas healthy."
Assert-True ($health.services.mongodb -eq "healthy") "MongoDB n'est pas healthy."
Assert-True ($health.services.sqlite -eq "healthy") "SQLite n'est pas healthy."

$products = Invoke-RestMethod -Uri "$BackendUrl/api/products?page=1&page_size=1" -Method Get
Assert-True ($products.total -gt 0) "Aucun produit n'est disponible."

$openApi = Invoke-RestMethod -Uri "$BackendUrl/openapi.json" -Method Get
$paths = $openApi.paths.PSObject.Properties.Name
Assert-True ($paths -contains "/api/admin/ai/delivery/report") "La route Delivery Agent est absente."
Assert-True ($paths -contains "/api/admin/ai/seo/audit") "La route SEO Agent est absente."
Assert-True ($paths -contains "/api/automations/delivery/scan") "La route n8n Delivery est absente."
Assert-True ($paths -contains "/api/automations/carts/abandoned") "La route n8n panier abandonne est absente."

$homepage = Invoke-FrontendWithRetry -Uri $FrontendUrl
Assert-True ($homepage.StatusCode -eq 200) "Le frontend ne repond pas."
Assert-True ($homepage.Content -match "NUTRIFIT") "Le branding NUTRIFIT est absent."
Assert-True ($homepage.Content -match "Nutrition &amp; Performance") "Le slogan NUTRIFIT est absent."

Write-Host "OK - API, bases, produits, Delivery, SEO, n8n et frontend fonctionnent."
