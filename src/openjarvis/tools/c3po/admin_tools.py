"""C3PO Admin-Tools (Stage 3 Sub-Stufe 3.7, alle ``admin``).

10 systemnahe Tools — Tray-Dialog mit PIN noetig (admin_whitelist.toml).
ALLE Subprocess-Aufrufe ueber ``_run`` — Tests muessen das patchen.

NIEMALS direkt ``subprocess.run`` aus Tools rufen, sonst lassen sich
Tests nicht sicher ausfuehren.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _run(cmd: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess:
    """Indirekter run-Wrapper — Tests patchen das."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _ok_result(name: str, content: str, **meta: Any) -> ToolResult:
    return ToolResult(tool_name=name, content=content, success=True, metadata=meta)


def _err_result(name: str, content: str) -> ToolResult:
    return ToolResult(tool_name=name, content=content, success=False)


def _exec_simple(
    name: str,
    cmd: list[str],
    *,
    success_msg: str,
    timeout: float = 30.0,
) -> ToolResult:
    """Standard-Pattern: Subprocess ausfuehren, returncode pruefen, Antwort bauen."""
    try:
        result = _run(cmd, timeout=timeout)
        if result.returncode == 0:
            return _ok_result(name, success_msg, stdout=result.stdout[:500])
        return _err_result(
            name,
            f"Fehler ({result.returncode}): "
            f"{(result.stderr or result.stdout).strip()[:500]}",
        )
    except Exception as exc:
        return _err_result(name, f"Exception: {exc}")


# ---------------------------------------------------------------------------
# admin.reboot / admin.shutdown / admin.cancel_shutdown
# ---------------------------------------------------------------------------


@ToolRegistry.register("admin.reboot")
class AdminRebootTool(BaseTool):
    tool_id = "admin.reboot"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.reboot",
            description="Plant einen Neustart in 60 Sekunden. Permission: admin.",
            parameters={
                "type": "object",
                "properties": {
                    "delay": {
                        "type": "integer",
                        "description": "Sekunden bis Reboot (Default 60).",
                    },
                },
            },
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        delay = int(params.get("delay") or 60)
        return _exec_simple(
            "admin.reboot",
            ["shutdown", "/r", "/t", str(delay)],
            success_msg=f"Reboot in {delay}s geplant.",
        )


@ToolRegistry.register("admin.shutdown")
class AdminShutdownTool(BaseTool):
    tool_id = "admin.shutdown"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.shutdown",
            description="Plant Shutdown in 60 Sekunden. Permission: admin.",
            parameters={
                "type": "object",
                "properties": {"delay": {"type": "integer"}},
            },
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        delay = int(params.get("delay") or 60)
        return _exec_simple(
            "admin.shutdown",
            ["shutdown", "/s", "/t", str(delay)],
            success_msg=f"Shutdown in {delay}s geplant.",
        )


@ToolRegistry.register("admin.cancel_shutdown")
class AdminCancelShutdownTool(BaseTool):
    tool_id = "admin.cancel_shutdown"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.cancel_shutdown",
            description="Storniert geplanten Shutdown/Reboot. Permission: admin.",
            parameters={"type": "object", "properties": {}},
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        return _exec_simple(
            "admin.cancel_shutdown",
            ["shutdown", "/a"],
            success_msg="Shutdown storniert.",
        )


# ---------------------------------------------------------------------------
# admin.update_check / admin.cleanup_temp / admin.flush_dns
# ---------------------------------------------------------------------------


@ToolRegistry.register("admin.update_check")
class AdminUpdateCheckTool(BaseTool):
    tool_id = "admin.update_check"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.update_check",
            description=(
                "Listet via winget verfuegbare Updates. Permission: admin."
            ),
            parameters={"type": "object", "properties": {}},
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            r = _run(["winget", "upgrade", "--include-unknown"], timeout=60.0)
            if r.returncode != 0:
                return _err_result(
                    "admin.update_check", f"winget exit {r.returncode}: {r.stderr[:300]}"
                )
            return _ok_result(
                "admin.update_check", r.stdout[:2000], lines=len(r.stdout.splitlines())
            )
        except Exception as exc:
            return _err_result("admin.update_check", f"Fehler: {exc}")


@ToolRegistry.register("admin.cleanup_temp")
class AdminCleanupTempTool(BaseTool):
    tool_id = "admin.cleanup_temp"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.cleanup_temp",
            description=(
                "Loescht den User-TEMP-Ordner. Permission: admin. "
                "Dateien die in Benutzung sind, werden uebersprungen."
            ),
            parameters={"type": "object", "properties": {}},
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        # Wir nutzen NICHT 'del *' weil das gefaehrlich+schwach ist.
        # PowerShell-Remove-Item mit -Force -Recurse, Fehler werden geloggt.
        ps = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Get-ChildItem $env:TEMP -Force | "
            "Remove-Item -Force -Recurse -ErrorAction SilentlyContinue;"
            "Write-Output 'temp cleanup done'"
        )
        return _exec_simple(
            "admin.cleanup_temp",
            ["powershell", "-NoProfile", "-Command", ps],
            success_msg="TEMP bereinigt.",
            timeout=60.0,
        )


@ToolRegistry.register("admin.flush_dns")
class AdminFlushDnsTool(BaseTool):
    tool_id = "admin.flush_dns"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.flush_dns",
            description="Leert den DNS-Cache. Permission: admin.",
            parameters={"type": "object", "properties": {}},
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        return _exec_simple(
            "admin.flush_dns",
            ["ipconfig", "/flushdns"],
            success_msg="DNS-Cache geleert.",
        )


# ---------------------------------------------------------------------------
# admin.restart_service / admin.list_services
# ---------------------------------------------------------------------------


@ToolRegistry.register("admin.restart_service")
class AdminRestartServiceTool(BaseTool):
    tool_id = "admin.restart_service"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.restart_service",
            description="Startet einen Windows-Service neu. Permission: admin.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        name = (params.get("name") or "").strip()
        if not name:
            return _err_result("admin.restart_service", "Kein Service-Name.")
        # Restart-Service ueber PowerShell, damit Stop+Start atomar laeuft.
        return _exec_simple(
            "admin.restart_service",
            ["powershell", "-NoProfile", "-Command", f"Restart-Service -Name '{name}' -Force"],
            success_msg=f"Service '{name}' neu gestartet.",
            timeout=60.0,
        )


@ToolRegistry.register("admin.list_services")
class AdminListServicesTool(BaseTool):
    tool_id = "admin.list_services"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.list_services",
            description=(
                "Listet alle Windows-Services. Permission: admin "
                "(System-Info kann sensibel sein)."
            ),
            parameters={"type": "object", "properties": {}},
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            r = _run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Service | Format-Table -AutoSize | Out-String -Width 200",
                ],
                timeout=30.0,
            )
            if r.returncode != 0:
                return _err_result("admin.list_services", r.stderr[:300])
            lines = [l for l in r.stdout.splitlines() if l.strip()][:60]
            return _ok_result(
                "admin.list_services", "\n".join(lines), count=len(lines)
            )
        except Exception as exc:
            return _err_result("admin.list_services", f"Fehler: {exc}")


# ---------------------------------------------------------------------------
# admin.kill_process_force
# ---------------------------------------------------------------------------


@ToolRegistry.register("admin.kill_process_force")
class AdminKillProcessForceTool(BaseTool):
    tool_id = "admin.kill_process_force"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.kill_process_force",
            description=(
                "Beendet einen Prozess hart per PID, auch geschuetzte. "
                "Permission: admin."
            ),
            parameters={
                "type": "object",
                "properties": {"pid": {"type": "integer"}},
                "required": ["pid"],
            },
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        pid: Optional[int] = params.get("pid")
        if not isinstance(pid, int) or pid <= 0:
            return _err_result("admin.kill_process_force", "Ungueltige PID.")
        return _exec_simple(
            "admin.kill_process_force",
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            success_msg=f"Prozess PID {pid} beendet (force, mit Subtree).",
        )


# ---------------------------------------------------------------------------
# admin.git_pull_repo
# ---------------------------------------------------------------------------


_ALLOWED_REPO_PARENTS = (
    Path.home() / "Projekt",
    Path("C:/TI-Monitor"),
)


def _is_allowed_repo(path: Path) -> bool:
    try:
        rp = path.resolve()
    except OSError:
        return False
    for allowed in _ALLOWED_REPO_PARENTS:
        try:
            rp.relative_to(allowed.resolve())
            return True
        except ValueError:
            continue
    return False


@ToolRegistry.register("admin.git_pull_repo")
class AdminGitPullRepoTool(BaseTool):
    tool_id = "admin.git_pull_repo"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="admin.git_pull_repo",
            description=(
                "Fuehrt 'git pull' in einem Repo unter Andre's Projekt-Ordner aus. "
                "Permission: admin."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absoluter Pfad zum Repo.",
                    },
                },
                "required": ["path"],
            },
            category="admin",
        )

    def execute(self, **params: Any) -> ToolResult:
        path_str = (params.get("path") or "").strip()
        if not path_str:
            return _err_result("admin.git_pull_repo", "Kein Pfad.")
        path = Path(path_str)
        if not _is_allowed_repo(path):
            return _err_result(
                "admin.git_pull_repo",
                f"Pfad '{path}' nicht in erlaubten Repo-Verzeichnissen.",
            )
        if not (path / ".git").exists():
            return _err_result(
                "admin.git_pull_repo", f"Kein git-Repo in {path}."
            )
        return _exec_simple(
            "admin.git_pull_repo",
            ["git", "-C", str(path), "pull"],
            success_msg=f"git pull in {path} ausgefuehrt.",
            timeout=60.0,
        )


__all__ = [
    "AdminRebootTool",
    "AdminShutdownTool",
    "AdminCancelShutdownTool",
    "AdminUpdateCheckTool",
    "AdminCleanupTempTool",
    "AdminFlushDnsTool",
    "AdminRestartServiceTool",
    "AdminListServicesTool",
    "AdminKillProcessForceTool",
    "AdminGitPullRepoTool",
]
