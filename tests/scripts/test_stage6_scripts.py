"""Tests fuer Stage-6-Skripte (statisch, ohne echte Ausfuehrung).

Diese Tests pruefen Syntax + ENV-Var-Vertrag + Idempotenz-Marker.
Sie starten KEINE echten PowerShell-Skripte (sonst koennten sie den
Autostart einrichten oder Legacy verschieben — beides nicht erwuenscht
in pytest).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def _powershell_syntax_check(script_path: Path) -> tuple[bool, str]:
    """Laeuft den PowerShell-Parser ueber das Skript. Returnt (ok, stderr)."""
    if sys.platform != "win32":
        pytest.skip("PowerShell-Syntax-Check nur auf Windows")
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            f"[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{script_path}', [ref]$null, [ref]$null) | Out-Null; "
            f"Write-Host 'OK'"
        ),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    ok = result.returncode == 0 and "OK" in result.stdout
    return ok, result.stderr


_SCRIPTS = (
    "start_c3po.ps1",
    "install_autostart.ps1",
    "uninstall_autostart.ps1",
    "archive_legacy.ps1",
)


class TestScriptsExist:
    @pytest.mark.parametrize("name", _SCRIPTS)
    def test_script_file_exists(self, name):
        assert (SCRIPTS / name).is_file(), f"Skript fehlt: {name}"


class TestPowerShellSyntax:
    @pytest.mark.parametrize("name", _SCRIPTS)
    def test_syntax_valid(self, name):
        path = SCRIPTS / name
        ok, stderr = _powershell_syntax_check(path)
        assert ok, f"PowerShell-Syntax-Fehler in {name}:\n{stderr}"


class TestStartC3poEnv:
    def test_sets_python_path_and_voice_brain(self):
        content = (SCRIPTS / "start_c3po.ps1").read_text(encoding="utf-8")
        assert "PYTHONPATH" in content
        assert "C3PO_VOICE_BRAIN" in content
        assert "OPENJARVIS_PERMISSIONS_CONFIG" in content
        assert "OPENJARVIS_ADMIN_WHITELIST" in content

    def test_references_voice_smoke_test(self):
        content = (SCRIPTS / "start_c3po.ps1").read_text(encoding="utf-8")
        assert "voice_smoke_test.py" in content

    def test_starts_server_via_jarvis_cli(self):
        content = (SCRIPTS / "start_c3po.ps1").read_text(encoding="utf-8")
        assert "openjarvis.cli" in content
        assert "serve" in content
        assert "8000" in content

    def test_cleanup_stops_server(self):
        """Finally-Block muss den Server wieder beenden."""
        content = (SCRIPTS / "start_c3po.ps1").read_text(encoding="utf-8")
        assert "Stop-Process" in content
        assert "finally" in content


class TestArchiveLegacy:
    def test_default_source_and_archive_root(self):
        content = (SCRIPTS / "archive_legacy.ps1").read_text(encoding="utf-8")
        assert "C3PO-legacy" in content
        assert "Archiv" in content

    def test_aborts_if_destination_exists(self):
        """Idempotenz: bei existierendem Ziel abbrechen statt ueberschreiben."""
        content = (SCRIPTS / "archive_legacy.ps1").read_text(encoding="utf-8")
        assert "Test-Path $DestDir" in content
        assert "exit 1" in content

    def test_uses_move_item(self):
        content = (SCRIPTS / "archive_legacy.ps1").read_text(encoding="utf-8")
        # Move-Item ist schneller als Copy + Delete und braucht nicht den
        # doppelten Plattenplatz
        assert "Move-Item" in content


class TestAutostartLink:
    def test_install_uses_wscript_shell(self):
        content = (SCRIPTS / "install_autostart.ps1").read_text(encoding="utf-8")
        assert "WScript.Shell" in content
        assert "CreateShortcut" in content

    def test_install_target_is_powershell(self):
        content = (SCRIPTS / "install_autostart.ps1").read_text(encoding="utf-8")
        assert "powershell.exe" in content
        assert "start_c3po.ps1" in content

    def test_install_uses_startup_folder(self):
        content = (SCRIPTS / "install_autostart.ps1").read_text(encoding="utf-8")
        assert 'GetFolderPath("Startup")' in content
        assert "C3PO.lnk" in content

    def test_uninstall_removes_lnk(self):
        content = (SCRIPTS / "uninstall_autostart.ps1").read_text(encoding="utf-8")
        assert "Remove-Item" in content
        assert "C3PO.lnk" in content
