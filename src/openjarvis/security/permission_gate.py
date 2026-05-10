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
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple

from openjarvis.core.events import EventBus, EventType
from openjarvis.security.types import PermissionLevel, PermissionResult

logger = logging.getLogger(__name__)

PinCheck = Callable[[str], bool]
_PendingEntry = Tuple[asyncio.Future, str]  # (future, kind: "confirm"|"pin")


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
        admin_whitelist_path: Optional[Path] = None,
        pin_check: Optional[PinCheck] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        self._tools: Dict[str, PermissionLevel] = self._load_toml(config_path)
        self._admin_whitelist: Set[str] = (
            self._load_admin_whitelist(admin_whitelist_path)
            if admin_whitelist_path is not None
            else set()
        )
        # Default: alle PINs ablehnen, wenn kein Checker injiziert wurde.
        self._pin_check: PinCheck = pin_check or (lambda pin: False)
        self._bus = bus
        self._pending: Dict[str, _PendingEntry] = {}
        self._lock = asyncio.Lock()

    def _load_admin_whitelist(self, path: Path) -> Set[str]:
        if not path.exists():
            raise FileNotFoundError(f"admin_whitelist.toml nicht gefunden: {path}")
        with path.open("rb") as f:
            data = tomllib.load(f)
        admin = data.get("admin", {}) or {}
        tools = admin.get("tools", []) or []
        if not isinstance(tools, list):
            raise ValueError(
                f"[admin].tools muss eine Liste sein in {path}"
            )
        return set(tools)

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

        if level == PermissionLevel.CONFIRM:
            return await self._start_pending(
                tool_name=tool_name,
                args=args,
                channel=channel,
                kind="confirm",
                event_type=EventType.PERMISSION_CONFIRM_REQUESTED,
                result_factory=PermissionResult.needs_confirm,
            )

        if level == PermissionLevel.ADMIN:
            if tool_name not in self._admin_whitelist:
                return PermissionResult.denied(
                    f"tool '{tool_name}' nicht in admin_whitelist.toml"
                )
            return await self._start_pending(
                tool_name=tool_name,
                args=args,
                channel=channel,
                kind="pin",
                event_type=EventType.PERMISSION_PIN_REQUESTED,
                result_factory=PermissionResult.needs_pin,
            )

        # Unreachable - alle Enum-Werte oben behandelt
        return PermissionResult.denied(f"unbekanntes Level: {level}")

    async def _start_pending(
        self,
        *,
        tool_name: str,
        args: dict,
        channel: str,
        kind: str,  # "confirm" oder "pin"
        event_type: EventType,
        result_factory,
    ) -> PermissionResult:
        """Erzeugt UUID, registriert (Future, kind), publiziert Event."""
        prompt_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        async with self._lock:
            self._pending[prompt_id] = (loop.create_future(), kind)
        if self._bus is not None:
            self._bus.publish(
                event_type,
                {
                    "prompt_id": prompt_id,
                    "tool": tool_name,
                    "args": args,
                    "channel": channel,
                },
            )
        return result_factory(prompt_id)

    async def confirm(self, prompt_id: str, response: str) -> bool:
        """Vom Tray/Channel gerufen mit der User-Antwort.

        Confirm-Pfad: response in {"yes","ja","ok","true","1"} -> True, sonst False.
        Admin-Pfad: response ist die PIN, wird via _pin_check verifiziert.
        """
        async with self._lock:
            entry = self._pending.pop(prompt_id, None)
        if entry is None:
            return False
        fut, kind = entry
        if fut.done():
            return False
        if kind == "pin":
            granted = bool(self._pin_check(response))
        else:
            granted = response.strip().lower() in ("yes", "ja", "ok", "true", "1")
        fut.set_result(granted)
        if self._bus is not None:
            self._bus.publish(
                EventType.PERMISSION_RESOLVED,
                {"prompt_id": prompt_id, "granted": granted},
            )
        return granted


__all__ = ["PermissionGate"]
