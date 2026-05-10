<#
.SYNOPSIS
    Legt einen Login-Autostart-Shortcut fuer C3PO an.

.DESCRIPTION
    Erstellt %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\C3PO.lnk
    der scripts/start_c3po.ps1 mit -WindowStyle Hidden aufruft.
    Idempotent: vorhandene Verknuepfung wird ersetzt.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$StartupDir = [Environment]::GetFolderPath("Startup")
$LinkPath = Join-Path $StartupDir "C3PO.lnk"
$StartScript = Join-Path $RepoRoot "scripts\start_c3po.ps1"

if (-not (Test-Path $StartScript)) {
    Write-Host "FEHLER: $StartScript nicht gefunden" -ForegroundColor Red
    exit 1
}

if (Test-Path $LinkPath) {
    Write-Host "Bestehende Verknuepfung wird ersetzt: $LinkPath" -ForegroundColor Yellow
}

$Shell = New-Object -ComObject WScript.Shell
$Lnk = $Shell.CreateShortcut($LinkPath)
$Lnk.TargetPath = "powershell.exe"
$Lnk.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartScript`""
$Lnk.WorkingDirectory = $RepoRoot
$Lnk.IconLocation = "powershell.exe,0"
$Lnk.Description = "C3PO Voice-Agent (auto-start beim Login)"
$Lnk.Save()

Write-Host "OK: Autostart-Verknuepfung angelegt:" -ForegroundColor Green
Write-Host "    $LinkPath"
Write-Host "Naechster Login startet C3PO automatisch."
Write-Host "Entfernen mit: scripts\uninstall_autostart.ps1"
