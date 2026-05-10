<#
.SYNOPSIS
    Entfernt den C3PO-Login-Autostart-Shortcut.
#>

$ErrorActionPreference = "Stop"
$StartupDir = [Environment]::GetFolderPath("Startup")
$LinkPath = Join-Path $StartupDir "C3PO.lnk"

if (Test-Path $LinkPath) {
    Remove-Item $LinkPath
    Write-Host "OK: Autostart entfernt." -ForegroundColor Green
} else {
    Write-Host "Keine Verknuepfung gefunden (war nicht installiert)." -ForegroundColor Yellow
}
