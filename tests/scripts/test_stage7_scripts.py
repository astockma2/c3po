"""Tests fuer Stage-7-Skripte (statisch, ohne echte npm-Ausfuehrung)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def _powershell_syntax_check(script_path: Path) -> tuple[bool, str]:
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
    return result.returncode == 0 and "OK" in result.stdout, result.stderr


class TestSetupFrontendScript:
    def test_exists(self):
        assert (SCRIPTS / "setup_frontend.ps1").is_file()

    def test_syntax(self):
        ok, stderr = _powershell_syntax_check(SCRIPTS / "setup_frontend.ps1")
        assert ok, stderr

    def test_calls_npm_install_and_build(self):
        content = (SCRIPTS / "setup_frontend.ps1").read_text(encoding="utf-8")
        assert "npm install" in content
        assert "npm run build" in content

    def test_checks_node_modules_idempotent(self):
        content = (SCRIPTS / "setup_frontend.ps1").read_text(encoding="utf-8")
        assert "Test-Path" in content
        assert "node_modules" in content

    def test_verifies_static_index_html_after_build(self):
        content = (SCRIPTS / "setup_frontend.ps1").read_text(encoding="utf-8")
        assert "index.html" in content

    def test_checks_npm_in_path(self):
        content = (SCRIPTS / "setup_frontend.ps1").read_text(encoding="utf-8")
        assert "Get-Command npm" in content


class TestStartC3poPreFlight:
    def test_has_skip_frontend_env_var(self):
        content = (SCRIPTS / "start_c3po.ps1").read_text(encoding="utf-8")
        assert "C3PO_SKIP_FRONTEND" in content

    def test_calls_setup_frontend(self):
        content = (SCRIPTS / "start_c3po.ps1").read_text(encoding="utf-8")
        assert "setup_frontend.ps1" in content

    def test_checks_static_index_html(self):
        content = (SCRIPTS / "start_c3po.ps1").read_text(encoding="utf-8")
        assert "static\\index.html" in content or "static/index.html" in content
