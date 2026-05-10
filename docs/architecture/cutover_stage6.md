# C3PO Stage 6 — Cutover

**Stand:** 2026-05-10. Stage 6 ist die finale Stage der OpenJarvis-Migration.

## Was Stage 6 leistet

- **`scripts/start_c3po.ps1`** — startet Server (Port 8000) + Voice-Brain (Mic) + Cockpit in einem Aufruf.
- **`scripts/install_autostart.ps1`** — legt eine `.lnk` im Windows-Startup-Ordner an. Bei Login startet C3PO automatisch.
- **`scripts/uninstall_autostart.ps1`** — entfernt den Shortcut.
- **`scripts/archive_legacy.ps1`** — verschiebt `C:\Users\andre\Projekt\C3PO-legacy\` nach `C:\Users\andre\Archiv\C3PO-legacy-YYYY-MM-DD\`.

## Cutover-Schritte (einmalig, manuell)

```powershell
# 1. Voice-Brain testen (Backend, kein Mic)
$env:PYTHONPATH = "src"
./.venv/Scripts/python.exe scripts/voice_brain_smoke_test.py
# Erwartet: STAGE-4-CUTOVER OK

# 2. Live-Mic-Test
./scripts/start_c3po.ps1
# Sag "Hey Jarvis, wie spaet ist es?" -- Charon-Stimme antwortet
# Stop: Ctrl+C

# 3. (Optional) Andere Projekte auf Legacy-Referenzen pruefen
Get-ChildItem C:\Users\andre\Projekt -Recurse -Include *.py,*.ps1,*.md `
  | Select-String "C3PO-legacy" -List `
  | Select-Object Filename, Path

# 4. Legacy archivieren
./scripts/archive_legacy.ps1
# Erwartet: OK: Legacy ist archiviert unter C:\Users\andre\Archiv\C3PO-legacy-2026-05-10

# 5. Login-Autostart aktivieren
./scripts/install_autostart.ps1
# Naechster Login: C3PO startet automatisch.
```

## Rollback (wenn neuer Stack nicht funktioniert)

```powershell
# 1. Autostart aus
./scripts/uninstall_autostart.ps1

# 2. Legacy zurueck
Move-Item C:\Users\andre\Archiv\C3PO-legacy-2026-05-10 C:\Users\andre\Projekt\C3PO-legacy

# 3. Legacy starten wie frueher
cd C:\Users\andre\Projekt\C3PO-legacy
./start_phase0.ps1
```

## Bekannte Schwaechen

- **Autostart laeuft erst NACH Login.** Wenn der PC bootet aber niemand sich einloggt, startet C3PO nicht. Fuer Andre's Dev-PC-Use-Case ok.
- **Kein Auto-Restart bei Crash.** Wenn der Voice-Brain stirbt (Python-Exception nach Wake), ist es still bis zum naechsten Login. Fuer dauerhaften Hintergrund-Service waere Task Scheduler oder NSSM besser — wurde fuer Stage 6 ausgespart (Andre's Entscheidung).
- **Server-Port 8000 hartkodiert.** Wenn Andre's Port-Tabelle das umlegen will: `start_c3po.ps1` editieren.
- **start_c3po.ps1 wartet 5s starr auf Server-Start.** Bei kalter venv mit nicht-cachten Imports kann das knapp sein. Health-Check schluckt's und warnt nur.
- **Skript-Output ist bei Login-Autostart hidden.** `-WindowStyle Hidden` heisst: kein Fenster sichtbar, keine Logs im UI. Beim Debug: `uninstall_autostart.ps1`, dann `start_c3po.ps1` manuell mit sichtbarer Konsole.

## Naechste Etappen (optional)

- **Task Scheduler** statt Startup-Shortcut: laeuft auch ohne Login, Auto-Restart, Run-Whether-User-Logged-On-Or-Not.
- **Auth fuer Cockpit:** PIN-only oder OAuth via Andre's Bot Dashboard.
- **Tauri/React-Frontend** statt Vanilla-Cockpit (vom urspruenglichen Stage-5-Brainstorm).
- **`gate.snapshot_pending()`-Helper** rausziehen statt `gate._pending` direkt zu lesen.
- **CSRF-Schutz** falls der Server jemals an LAN/WAN exposed wird.
