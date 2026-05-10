"""Tests fuer c3po/admin_tools.py — Stage 3 Sub-Stufe 3.7.

KEINE echten Subprocess-Aufrufe! ``_run`` wird in jedem Test gemockt.
Wenn dieser Test einen echten ``shutdown /r``-Befehl absetzt, ist der
Code falsch verdrahtet und der Test muss fail-en, BEVOR irgendein Reboot
geplant ist.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from openjarvis.tools.c3po.admin_tools import (
    AdminCancelShutdownTool,
    AdminCleanupTempTool,
    AdminFlushDnsTool,
    AdminGitPullRepoTool,
    AdminKillProcessForceTool,
    AdminListServicesTool,
    AdminRebootTool,
    AdminRestartServiceTool,
    AdminShutdownTool,
    AdminUpdateCheckTool,
    _is_allowed_repo,
)


def _ok(stdout="ok", stderr="") -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=stdout, stderr=stderr)


def _fail(stdout="", stderr="boom", returncode=1) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# admin.reboot / shutdown / cancel
# ---------------------------------------------------------------------------


class TestAdminReboot:
    def test_default_delay_60(self):
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            r = AdminRebootTool().execute()
        assert r.success is True
        cmd = run.call_args[0][0]
        assert cmd == ["shutdown", "/r", "/t", "60"]

    def test_custom_delay(self):
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            AdminRebootTool().execute(delay=300)
        assert run.call_args[0][0] == ["shutdown", "/r", "/t", "300"]


class TestAdminShutdown:
    def test_calls_shutdown_s(self):
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            r = AdminShutdownTool().execute()
        assert r.success is True
        assert run.call_args[0][0][:2] == ["shutdown", "/s"]


class TestAdminCancelShutdown:
    def test_calls_shutdown_a(self):
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            r = AdminCancelShutdownTool().execute()
        assert r.success is True
        assert run.call_args[0][0] == ["shutdown", "/a"]


# ---------------------------------------------------------------------------
# admin.update_check / cleanup_temp / flush_dns
# ---------------------------------------------------------------------------


class TestAdminUpdateCheck:
    def test_calls_winget(self):
        with patch(
            "openjarvis.tools.c3po.admin_tools._run",
            return_value=_ok(stdout="Mozilla Firefox  v100->v101\nGit  v2.40->v2.41"),
        ) as run:
            r = AdminUpdateCheckTool().execute()
        assert r.success is True
        assert "winget" in run.call_args[0][0][0]
        assert "Firefox" in r.content

    def test_failure(self):
        with patch(
            "openjarvis.tools.c3po.admin_tools._run", return_value=_fail()
        ):
            r = AdminUpdateCheckTool().execute()
        assert r.success is False


class TestAdminCleanupTemp:
    def test_powershell_remove_item(self):
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            r = AdminCleanupTempTool().execute()
        assert r.success is True
        cmd = run.call_args[0][0]
        assert cmd[0] == "powershell"
        assert "TEMP" in cmd[-1]


class TestAdminFlushDns:
    def test_calls_ipconfig(self):
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            r = AdminFlushDnsTool().execute()
        assert r.success is True
        assert run.call_args[0][0] == ["ipconfig", "/flushdns"]


# ---------------------------------------------------------------------------
# admin.restart_service / list_services
# ---------------------------------------------------------------------------


class TestAdminRestartService:
    def test_no_name_fails(self):
        r = AdminRestartServiceTool().execute(name="")
        assert r.success is False

    def test_calls_restart(self):
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            r = AdminRestartServiceTool().execute(name="Spooler")
        assert r.success is True
        ps_cmd = run.call_args[0][0][-1]
        assert "Restart-Service" in ps_cmd
        assert "Spooler" in ps_cmd


class TestAdminListServices:
    def test_lists_via_powershell(self):
        out = "\n".join([f"Service{i} Running" for i in range(80)])
        with patch(
            "openjarvis.tools.c3po.admin_tools._run", return_value=_ok(stdout=out)
        ):
            r = AdminListServicesTool().execute()
        assert r.success is True
        assert r.metadata["count"] <= 60


# ---------------------------------------------------------------------------
# admin.kill_process_force
# ---------------------------------------------------------------------------


class TestAdminKillProcessForce:
    @pytest.mark.parametrize("bad", [None, 0, -1, "abc"])
    def test_invalid_pid(self, bad):
        r = AdminKillProcessForceTool().execute(pid=bad)
        assert r.success is False

    def test_calls_taskkill_force(self):
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            r = AdminKillProcessForceTool().execute(pid=4321)
        assert r.success is True
        cmd = run.call_args[0][0]
        assert "/F" in cmd and "/T" in cmd and "4321" in cmd


# ---------------------------------------------------------------------------
# admin.git_pull_repo
# ---------------------------------------------------------------------------


class TestAllowedRepo:
    def test_under_projekt_is_allowed(self):
        assert _is_allowed_repo(Path.home() / "Projekt" / "c3po") is True

    def test_under_ti_monitor_is_allowed(self):
        assert _is_allowed_repo(Path("C:/TI-Monitor/some/sub")) is True

    def test_random_path_is_denied(self):
        assert _is_allowed_repo(Path("C:/Windows/System32")) is False
        assert _is_allowed_repo(Path.home() / "Desktop") is False


class TestAdminGitPullRepo:
    def test_no_path_fails(self):
        r = AdminGitPullRepoTool().execute(path="")
        assert r.success is False

    def test_unauthorized_path_fails(self):
        r = AdminGitPullRepoTool().execute(path="C:/Windows")
        assert r.success is False
        assert "nicht in erlaubten" in r.content

    def test_no_git_dir_fails(self, tmp_path, monkeypatch):
        # Tmp-Pfad als erlaubt markieren
        monkeypatch.setattr(
            "openjarvis.tools.c3po.admin_tools._ALLOWED_REPO_PARENTS",
            (tmp_path,),
        )
        # tmp_path hat kein .git
        r = AdminGitPullRepoTool().execute(path=str(tmp_path))
        assert r.success is False
        assert "git-Repo" in r.content

    def test_pull_calls_git_c(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "openjarvis.tools.c3po.admin_tools._ALLOWED_REPO_PARENTS",
            (tmp_path,),
        )
        repo = tmp_path / "myrepo"
        (repo / ".git").mkdir(parents=True)
        with patch("openjarvis.tools.c3po.admin_tools._run", return_value=_ok()) as run:
            r = AdminGitPullRepoTool().execute(path=str(repo))
        assert r.success is True
        cmd = run.call_args[0][0]
        assert cmd[:3] == ["git", "-C", str(repo)]
        assert cmd[3] == "pull"
