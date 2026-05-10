<#
.SYNOPSIS
    Startet C3PO (Server + Voice-Brain mit Mic + Cockpit).

.DESCRIPTION
    Background: jarvis serve (FastAPI auf Port 8000)
    Foreground: voice_smoke_test mit C3PO_VOICE_BRAIN=1 (Mic + Wake-Word + LLM-Loop)
    Stop: Ctrl+C - beide Prozesse werden sauber beendet.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# UTF-8 fuer Umlaute aus Spracherkennung
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "src"

# Permission-Gate-Configs (sonst sind Cockpit-Routes nicht gemounted)
$env:OPENJARVIS_PERMISSIONS_CONFIG = Join-Path $RepoRoot "configs\c3po\permissions.toml"
$env:OPENJARVIS_ADMIN_WHITELIST = Join-Path $RepoRoot "configs\c3po\admin_whitelist.toml"

# Voice-Brain aktivieren
$env:C3PO_VOICE_BRAIN = "1"

# venv-Python
$Py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "FEHLER: .venv nicht gefunden in $RepoRoot. Setup nicht durchgelaufen?" -ForegroundColor Red
    exit 1
}

# Stage 7: Frontend-Pre-Flight (mit $env:C3PO_SKIP_FRONTEND = "1" ueberspringbar)
$SkipFrontend = $env:C3PO_SKIP_FRONTEND -eq "1"
$StaticIndex = Join-Path $RepoRoot "src\openjarvis\server\static\index.html"

if (-not $SkipFrontend -and -not (Test-Path $StaticIndex)) {
    Write-Host "[0/2] Frontend nicht gebaut - starte automatischen Build ..." -ForegroundColor Yellow
    & (Join-Path $RepoRoot "scripts\setup_frontend.ps1")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNUNG: Frontend-Build fehlgeschlagen. Server startet trotzdem - UI evtl. nicht verfuegbar." -ForegroundColor Yellow
    }
}

# Server als Background-Prozess
Write-Host "[1/2] Starte jarvis serve (Port 8000) ..." -ForegroundColor Cyan
$ServerProc = Start-Process -FilePath $Py `
    -ArgumentList @("-m", "openjarvis.cli", "serve", "--port", "8000") `
    -WorkingDirectory $RepoRoot `
    -PassThru `
    -WindowStyle Hidden

# Warten bis Server steht
Start-Sleep -Seconds 5
try {
    $null = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "      Server steht auf http://localhost:8000" -ForegroundColor Green
    Write-Host "      Cockpit: http://localhost:8000/cockpit/" -ForegroundColor Green
} catch {
    Write-Host "WARNUNG: Server-Health-Check schlug fehl. Fahre trotzdem fort." -ForegroundColor Yellow
}

# Voice-Brain im Vordergrund
Write-Host "[2/2] Starte Voice-Brain (Mic + Wake-Word 'Hey Jarvis') ..." -ForegroundColor Cyan
try {
    & $Py -u -X utf8 (Join-Path $RepoRoot "scripts\voice_smoke_test.py")
} finally {
    Write-Host "`nBeende Server (PID $($ServerProc.Id)) ..." -ForegroundColor Cyan
    try { Stop-Process -Id $ServerProc.Id -Force -ErrorAction SilentlyContinue } catch {}
    Write-Host "C3PO ist aus." -ForegroundColor Green
}
