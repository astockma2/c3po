"""C3PO Windows-Tools (Stage 3 Sub-Stufe 3.2).

6 Tools fuer Windows-Steuerung. ``open_app``, ``close_app`` und
``kill_process`` sind ``confirm`` (Tray-Dialog), die uebrigen drei sind ``free``.

Quelle: ``C3PO-legacy/tools/windows_tool.py`` (212 LOC), portiert + auf BaseTool
umgestellt + Subprocess-Aufrufe in Helper ausgelagert (testbar).
"""

from __future__ import annotations

import subprocess
from typing import Any, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

# ---------------------------------------------------------------------------
# App-Aliase (User-freundliche Sprache → exe-Name)
# ---------------------------------------------------------------------------

APP_ALIASES: dict[str, str] = {
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "browser": "msedge",
    "edge": "msedge",
    "chrome": "chrome",
    "firefox": "firefox",
    "explorer": "explorer",
    "notepad": "notepad",
    "notiz": "notepad",
    "rechner": "calc",
    "taschenrechner": "calc",
    "outlook": "outlook",
    "thunderbird": "thunderbird",
    "spotify": "spotify",
    "discord": "discord",
    "powershell": "powershell",
    "terminal": "wt",
    "cmd": "cmd",
}


def _resolve_alias(name: str) -> str:
    norm = name.lower().strip()
    if norm in APP_ALIASES:
        return APP_ALIASES[norm]
    matches = [v for k, v in APP_ALIASES.items() if k.startswith(norm)]
    if len(matches) == 1:
        return matches[0]
    return name


# ---------------------------------------------------------------------------
# Subprocess-Wrapper (testbar via patch)
# ---------------------------------------------------------------------------


def _popen(cmd: list[str]) -> subprocess.Popen:
    """Indirekter Popen-Aufruf — Tests patchen das."""
    return subprocess.Popen(
        cmd,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


def _run(cmd: list[str], *, timeout: float = 10.0) -> subprocess.CompletedProcess:
    """Indirekter run-Aufruf — Tests patchen das."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@ToolRegistry.register("windows.open_app")
class WindowsOpenAppTool(BaseTool):
    """Startet eine bekannte Windows-Anwendung."""

    tool_id = "windows.open_app"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="windows.open_app",
            description=(
                "Startet eine bekannte Windows-Anwendung "
                "(vscode, edge, notepad, ...). Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "App-Name oder Alias (z.B. 'vs code', 'notepad').",
                    },
                },
                "required": ["name"],
            },
            category="windows",
            requires_confirmation=False,  # PermissionGate uebernimmt
        )

    def execute(self, **params: Any) -> ToolResult:
        name = (params.get("name") or "").strip()
        if not name:
            return ToolResult(
                tool_name="windows.open_app",
                content="Kein App-Name angegeben.",
                success=False,
            )
        cmd = _resolve_alias(name)
        try:
            _popen(["cmd", "/c", "start", "", cmd])
            return ToolResult(
                tool_name="windows.open_app",
                content=f"App '{name}' gestartet.",
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="windows.open_app",
                content=f"Konnte '{name}' nicht starten: {exc}",
                success=False,
            )


@ToolRegistry.register("windows.close_app")
class WindowsCloseAppTool(BaseTool):
    """Schliesst eine Anwendung per ``taskkill`` (sanft)."""

    tool_id = "windows.close_app"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="windows.close_app",
            description=(
                "Schliesst eine laufende Anwendung per Name "
                "(z.B. 'notepad'). Sanft, ohne /F. Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Prozess-Name ohne .exe-Endung.",
                    },
                },
                "required": ["name"],
            },
            category="windows",
        )

    def execute(self, **params: Any) -> ToolResult:
        name = (params.get("name") or "").strip()
        if not name:
            return ToolResult(
                tool_name="windows.close_app",
                content="Kein Prozess-Name angegeben.",
                success=False,
            )
        try:
            result = _run(["taskkill", "/IM", f"{name}.exe"])
            if result.returncode == 0:
                return ToolResult(
                    tool_name="windows.close_app",
                    content=f"Anwendung '{name}' geschlossen.",
                    success=True,
                )
            return ToolResult(
                tool_name="windows.close_app",
                content=(
                    f"Konnte '{name}' nicht schliessen: "
                    f"{(result.stderr or result.stdout).strip()}"
                ),
                success=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="windows.close_app",
                content=f"Fehler: {exc}",
                success=False,
            )


@ToolRegistry.register("windows.kill_process")
class WindowsKillProcessTool(BaseTool):
    """Beendet einen Prozess hart per PID (``taskkill /F``)."""

    tool_id = "windows.kill_process"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="windows.kill_process",
            description=(
                "Beendet einen Prozess hart per PID. "
                "Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "Prozess-ID."},
                },
                "required": ["pid"],
            },
            category="windows",
        )

    def execute(self, **params: Any) -> ToolResult:
        pid: Optional[int] = params.get("pid")
        if not isinstance(pid, int) or pid <= 0:
            return ToolResult(
                tool_name="windows.kill_process",
                content="Ungueltige PID.",
                success=False,
            )
        try:
            result = _run(["taskkill", "/F", "/PID", str(pid)])
            if result.returncode == 0:
                return ToolResult(
                    tool_name="windows.kill_process",
                    content=f"Prozess PID {pid} beendet.",
                    success=True,
                )
            return ToolResult(
                tool_name="windows.kill_process",
                content=(
                    f"Konnte PID {pid} nicht beenden: "
                    f"{(result.stderr or result.stdout).strip()}"
                ),
                success=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="windows.kill_process",
                content=f"Fehler: {exc}",
                success=False,
            )


@ToolRegistry.register("windows.list_processes")
class WindowsListProcessesTool(BaseTool):
    """Listet sichtbare Top-Level-Prozesse (free)."""

    tool_id = "windows.list_processes"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="windows.list_processes",
            description=(
                "Listet die ersten 15 sichtbaren Top-Level-Anwendungen. "
                "Permission: free."
            ),
            parameters={"type": "object", "properties": {}},
            category="windows",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            result = _run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Process | Where-Object {$_.MainWindowTitle} | "
                    "Select-Object Name, MainWindowTitle | "
                    "Format-Table -AutoSize | Out-String -Width 200",
                ],
                timeout=15.0,
            )
            if result.returncode != 0:
                return ToolResult(
                    tool_name="windows.list_processes",
                    content=f"Fehler: {result.stderr[:200]}",
                    success=False,
                )
            lines = [l for l in result.stdout.splitlines() if l.strip()][:15]
            return ToolResult(
                tool_name="windows.list_processes",
                content="Aktive Anwendungen:\n" + "\n".join(lines),
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="windows.list_processes",
                content=f"Konnte Prozesse nicht auflisten: {exc}",
                success=False,
            )


@ToolRegistry.register("windows.lock_screen")
class WindowsLockScreenTool(BaseTool):
    """Sperrt den Bildschirm (free, jeder kann's)."""

    tool_id = "windows.lock_screen"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="windows.lock_screen",
            description=(
                "Sperrt den Bildschirm (Win+L-Aequivalent). Permission: free."
            ),
            parameters={"type": "object", "properties": {}},
            category="windows",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            _run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5.0)
            return ToolResult(
                tool_name="windows.lock_screen",
                content="Bildschirm gesperrt.",
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="windows.lock_screen",
                content=f"Fehler beim Sperren: {exc}",
                success=False,
            )


@ToolRegistry.register("windows.notify")
class WindowsNotifyTool(BaseTool):
    """Zeigt eine Toast-Notification (free)."""

    tool_id = "windows.notify"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="windows.notify",
            description=(
                "Zeigt eine Windows-Toast-Notification. Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titel der Notification."},
                    "message": {"type": "string", "description": "Nachrichtentext."},
                },
                "required": ["title", "message"],
            },
            category="windows",
        )

    def execute(self, **params: Any) -> ToolResult:
        title = (params.get("title") or "C3PO").replace('"', "'")
        message = (params.get("message") or "").replace('"', "'")
        if not message:
            return ToolResult(
                tool_name="windows.notify",
                content="Kein Nachrichtentext angegeben.",
                success=False,
            )
        ps_cmd = (
            "[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,"
            "ContentType=WindowsRuntime] | Out-Null;"
            "[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,"
            "ContentType=WindowsRuntime] | Out-Null;"
            f"$xml=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
            f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
            f"$txt=$xml.GetElementsByTagName('text');"
            f"$txt[0].AppendChild($xml.CreateTextNode('{title}'))|Out-Null;"
            f"$txt[1].AppendChild($xml.CreateTextNode('{message}'))|Out-Null;"
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
            "'C3PO').Show([Windows.UI.Notifications.ToastNotification]::new($xml));"
        )
        try:
            result = _run(
                ["powershell", "-NoProfile", "-Command", ps_cmd], timeout=5.0
            )
            if result.returncode == 0:
                return ToolResult(
                    tool_name="windows.notify",
                    content=f"Notification angezeigt: {title}",
                    success=True,
                )
            return ToolResult(
                tool_name="windows.notify",
                content=f"Fehler: {result.stderr[:200]}",
                success=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="windows.notify",
                content=f"Fehler: {exc}",
                success=False,
            )


__all__ = [
    "WindowsOpenAppTool",
    "WindowsCloseAppTool",
    "WindowsKillProcessTool",
    "WindowsListProcessesTool",
    "WindowsLockScreenTool",
    "WindowsNotifyTool",
]
