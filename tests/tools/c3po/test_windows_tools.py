"""Tests fuer c3po/windows_tools.py — Stage 3 Sub-Stufe 3.2.

WICHTIG: NIEMALS echte Subprocess-Aufrufe in Tests. Alle ``_popen``/``_run``
sind gemockt. Sonst startet pytest auf einem Andre-Win-Notebook tatsaechlich
Notepad oder beendet einen Prozess.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.tools.c3po.windows_tools import (
    WindowsCloseAppTool,
    WindowsKillProcessTool,
    WindowsListProcessesTool,
    WindowsLockScreenTool,
    WindowsNotifyTool,
    WindowsOpenAppTool,
    _resolve_alias,
)


def _mock_completed(*, returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Aliase
# ---------------------------------------------------------------------------


class TestResolveAlias:
    def test_exact_match(self):
        assert _resolve_alias("notepad") == "notepad"

    def test_alias_match(self):
        assert _resolve_alias("vs code") == "code"
        assert _resolve_alias("rechner") == "calc"

    def test_passthrough_unknown(self):
        assert _resolve_alias("xyzunknown") == "xyzunknown"


# ---------------------------------------------------------------------------
# windows.open_app
# ---------------------------------------------------------------------------


class TestWindowsOpenApp:
    def test_spec(self):
        s = WindowsOpenAppTool().spec
        assert s.name == "windows.open_app"
        assert "name" in s.parameters["properties"]

    def test_execute_calls_popen(self):
        with patch("openjarvis.tools.c3po.windows_tools._popen") as popen:
            popen.return_value = MagicMock()
            r = WindowsOpenAppTool().execute(name="notepad")
        assert r.success is True
        popen.assert_called_once()
        cmd = popen.call_args[0][0]
        assert "notepad" in cmd

    def test_execute_resolves_alias(self):
        with patch("openjarvis.tools.c3po.windows_tools._popen") as popen:
            popen.return_value = MagicMock()
            WindowsOpenAppTool().execute(name="vs code")
        cmd = popen.call_args[0][0]
        assert "code" in cmd

    def test_execute_empty_name(self):
        r = WindowsOpenAppTool().execute(name="")
        assert r.success is False

    def test_execute_handles_popen_error(self):
        with patch("openjarvis.tools.c3po.windows_tools._popen", side_effect=OSError("denied")):
            r = WindowsOpenAppTool().execute(name="notepad")
        assert r.success is False
        assert "denied" in r.content


# ---------------------------------------------------------------------------
# windows.close_app
# ---------------------------------------------------------------------------


class TestWindowsCloseApp:
    def test_spec(self):
        assert WindowsCloseAppTool().spec.name == "windows.close_app"

    def test_execute_success(self):
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=0, stdout="ok"),
        ):
            r = WindowsCloseAppTool().execute(name="notepad")
        assert r.success is True
        assert "geschlossen" in r.content

    def test_execute_failure(self):
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=1, stderr="not found"),
        ):
            r = WindowsCloseAppTool().execute(name="ghost")
        assert r.success is False
        assert "not found" in r.content

    def test_execute_uses_taskkill_without_force(self):
        """close_app ist sanft (ohne /F). kill_process ist hart."""
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=0),
        ) as run:
            WindowsCloseAppTool().execute(name="notepad")
        cmd = run.call_args[0][0]
        assert "/F" not in cmd
        assert "/IM" in cmd

    def test_execute_empty_name(self):
        r = WindowsCloseAppTool().execute(name="")
        assert r.success is False


# ---------------------------------------------------------------------------
# windows.kill_process
# ---------------------------------------------------------------------------


class TestWindowsKillProcess:
    def test_spec(self):
        assert WindowsKillProcessTool().spec.name == "windows.kill_process"

    def test_execute_uses_force(self):
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=0),
        ) as run:
            r = WindowsKillProcessTool().execute(pid=1234)
        assert r.success is True
        cmd = run.call_args[0][0]
        assert "/F" in cmd
        assert "/PID" in cmd
        assert "1234" in cmd

    @pytest.mark.parametrize("bad_pid", [0, -1, "abc", None])
    def test_invalid_pid(self, bad_pid):
        r = WindowsKillProcessTool().execute(pid=bad_pid)
        assert r.success is False
        assert "Ungueltige" in r.content


# ---------------------------------------------------------------------------
# windows.list_processes
# ---------------------------------------------------------------------------


class TestWindowsListProcesses:
    def test_spec(self):
        assert WindowsListProcessesTool().spec.name == "windows.list_processes"

    def test_execute_returns_list(self):
        out = "\n".join([f"App{i} title{i}" for i in range(20)])
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=0, stdout=out),
        ):
            r = WindowsListProcessesTool().execute()
        assert r.success is True
        assert "Aktive Anwendungen" in r.content
        # max 15 rows
        assert r.content.count("\n") <= 16

    def test_execute_failure(self):
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=1, stderr="ps not found"),
        ):
            r = WindowsListProcessesTool().execute()
        assert r.success is False


# ---------------------------------------------------------------------------
# windows.lock_screen
# ---------------------------------------------------------------------------


class TestWindowsLockScreen:
    def test_calls_rundll32(self):
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=0),
        ) as run:
            r = WindowsLockScreenTool().execute()
        assert r.success is True
        cmd = run.call_args[0][0]
        assert "rundll32" in cmd[0]
        assert "LockWorkStation" in cmd[1]


# ---------------------------------------------------------------------------
# windows.notify
# ---------------------------------------------------------------------------


class TestWindowsNotify:
    def test_calls_powershell(self):
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=0),
        ) as run:
            r = WindowsNotifyTool().execute(title="Hi", message="Test")
        assert r.success is True
        cmd = run.call_args[0][0]
        assert "powershell" in cmd[0]
        # Title + Message muessen im PS-Command landen
        ps_script = cmd[-1]
        assert "Hi" in ps_script
        assert "Test" in ps_script

    def test_strips_double_quotes_in_message(self):
        """Sicherheit: User-Input darf nicht aus dem PS-String ausbrechen."""
        with patch(
            "openjarvis.tools.c3po.windows_tools._run",
            return_value=_mock_completed(returncode=0),
        ) as run:
            WindowsNotifyTool().execute(title='X"Y', message='A"B')
        ps_script = run.call_args[0][0][-1]
        # Doppelte Anfuehrungszeichen muessen entfernt sein
        assert '"' not in ps_script.split("'C3PO'")[0] or ps_script.count('"') == 0

    def test_empty_message_fails(self):
        r = WindowsNotifyTool().execute(title="X", message="")
        assert r.success is False
