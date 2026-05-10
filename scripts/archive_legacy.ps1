<#
.SYNOPSIS
    Verschiebt C3PO-legacy nach ~/Archiv mit Zeitstempel.

.DESCRIPTION
    Wenn das Ziel schon existiert: bricht ab (keine ueberschreibung).
    Wenn die Quelle fehlt: meldet ok (idempotent).
    Verschiebt KOMPLETT (inkl. .venv, Logs).
#>

param(
    [string]$SourceDir = "C:\Users\andre\Projekt\C3PO-legacy",
    [string]$ArchiveRoot = "C:\Users\andre\Archiv"
)

$ErrorActionPreference = "Stop"
$Today = Get-Date -Format "yyyy-MM-dd"
$DestDir = Join-Path $ArchiveRoot "C3PO-legacy-$Today"

if (-not (Test-Path $SourceDir)) {
    Write-Host "Quelle fehlt schon: $SourceDir (bereits archiviert?)" -ForegroundColor Yellow
    exit 0
}

if (Test-Path $DestDir) {
    Write-Host "FEHLER: Ziel existiert bereits: $DestDir" -ForegroundColor Red
    Write-Host "       Loesche es manuell oder waehle anderen Suffix."
    exit 1
}

# Archiv-Root anlegen falls nicht da
if (-not (Test-Path $ArchiveRoot)) {
    New-Item -ItemType Directory -Path $ArchiveRoot -Force | Out-Null
    Write-Host "Archiv-Ordner angelegt: $ArchiveRoot"
}

# Groesse zur Info
$SizeMb = [math]::Round(
    (Get-ChildItem $SourceDir -Recurse -ErrorAction SilentlyContinue |
     Measure-Object -Property Length -Sum).Sum / 1MB, 1
)
Write-Host "Verschiebe $SourceDir (~$SizeMb MB) -> $DestDir ..." -ForegroundColor Cyan

Move-Item -Path $SourceDir -Destination $DestDir

Write-Host "OK: Legacy ist archiviert unter $DestDir" -ForegroundColor Green
Write-Host "Rollback (falls noetig): Move-Item '$DestDir' '$SourceDir'"
