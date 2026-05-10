"""PermissionGate - kanal-aware Tool-Permission-System (Stage 2).

Vor jedem Tool-Call ruft der Agent (oder ein Channel direkt) `check()`. Die
Antwort ist entweder sofort `granted`/`denied`, oder `needs_confirm`/`needs_pin`
mit prompt_id - dann wartet der Aufrufer auf das Future in `_pending[prompt_id]`,
das vom Tray-Daemon (oder Telegram-Channel etc.) ueber `confirm()` resolved wird.

Konfiguration: TOML mit [tools]-Section, Werte sind PermissionLevel-Strings.
"""
from __future__ import annotations

import asyncio
import logging
import tomllib
from pathlib import Path
from typing import Dict, Optional

from openjarvis.core.events import EventBus
from openjarvis.security.types import PermissionLevel, PermissionResult

logger = logging.getLogger(__name__)


class PermissionGate:
    """Singleton-Klasse fuer Tool-Permission-Checks.

    Parameters
    ----------
    config_path:
        TOML-Datei mit [tools]-Section: ``"tool.name" = "free"|"confirm"|"admin"|"denied"``.
    bus:
        Optionaler EventBus - PermissionGate publiziert PERMISSION_*_REQUESTED.
    """

    def __init__(
        self,
        *,
        config_path: Path,
        bus: Optional[EventBus] = None,
    ) -> None:
        self._tools: Dict[str, PermissionLevel] = self._load_toml(config_path)
        self._bus = bus
        self._pending: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def _load_toml(self, path: Path) -> Dict[str, PermissionLevel]:
        if not path.exists():
            raise FileNotFoundError(f"permissions.toml nicht gefunden: {path}")
        with path.open("rb") as f:
            data = tomllib.load(f)
        tools_raw = data.get("tools", {}) or {}
        result: Dict[str, PermissionLevel] = {}
        for tool_name, level_str in tools_raw.items():
            try:
                result[tool_name] = PermissionLevel(level_str)
            except ValueError as exc:
                raise ValueError(
                    f"Ungueltiges PermissionLevel '{level_str}' fuer Tool '{tool_name}' "
                    f"in {path} - erlaubt sind: free/confirm/admin/denied"
                ) from exc
        return result

    async def check(
        self,
        tool_name: str,
        args: dict,
        *,
        channel: str,
    ) -> PermissionResult:
        """Pruefe ob `tool_name` von `channel` ausgefuehrt werden darf.

        Args:
            tool_name: vollqualifizierter Tool-Name (z.B. "calendar.upcoming")
            args: das Argument-Dict des Tool-Calls (fuer Audit)
            channel: kanal-Identifier (z.B. "voice_local", "telegram")
        """
        level = self._tools.get(tool_name)

        if level is None:
            return PermissionResult.denied(
                f"tool '{tool_name}' not configured in permissions.toml"
            )

        if level == PermissionLevel.FREE:
            return PermissionResult.granted()

        if level == PermissionLevel.DENIED:
            return PermissionResult.denied(
                f"tool '{tool_name}' explicitly denied"
            )

        if level in (PermissionLevel.CONFIRM, PermissionLevel.ADMIN):
            raise NotImplementedError(
                "Confirm/Admin-Pfade kommen in Task 5+6"
            )

        # Unreachable - alle Enum-Werte oben behandelt
        return PermissionResult.denied(f"unbekanntes Level: {level}")


__all__ = ["PermissionGate"]
