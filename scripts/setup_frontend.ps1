<#
.SYNOPSIS
    Baut das OpenJarvis-Frontend (Stanford-React-UI).

.DESCRIPTION
    Wenn frontend\node_modules fehlt: npm install (~1-2 Min kalter Cache).
    Immer: npm run build (~15-30 Sek) -> Output landet in src/openjarvis/server/static/.

    Nach diesem Schritt ist http://localhost:8000/ das Stanford-Chat-UI.
    Cockpit-Lite unter /cockpit/ funktioniert unabhaengig davon.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $RepoRoot "frontend"

if (-not (Test-Path $FrontendDir)) {
    Write-Host "FEHLER: frontend/ fehlt unter $RepoRoot" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "FEHLER: npm nicht im PATH. Node.js >= 20 installiert?" -ForegroundColor Red
    exit 1
}

Push-Location $FrontendDir
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "[1/2] npm install (kalter Cache, ~1-2 Min) ..." -ForegroundColor Cyan
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host "FEHLER: npm install fehlgeschlagen." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[1/2] node_modules existiert - install uebersprungen." -ForegroundColor Yellow
    }

    Write-Host "[2/2] npm run build (Vite, ~15-30 Sek) ..." -ForegroundColor Cyan
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FEHLER: Build fehlgeschlagen." -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

$StaticIndex = Join-Path $RepoRoot "src\openjarvis\server\static\index.html"
if (Test-Path $StaticIndex) {
    Write-Host "OK: Frontend gebaut. Server-URL: http://localhost:8000/" -ForegroundColor Green
} else {
    Write-Host "WARNUNG: Build durchgelaufen, aber static/index.html fehlt." -ForegroundColor Yellow
    exit 1
}
