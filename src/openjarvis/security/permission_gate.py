"""PermissionGate - kanal-aware Tool-Permission-System (Stage 2).

Vor jedem Tool-Call ruft der Agent (oder ein Channel direkt) `check()`. Die
Antwort ist entweder sofort `granted`/`denied`, oder `needs_confirm`/`needs_pin`
mit prompt_id - dann wartet der Aufrufer auf das Future in `_pending[prompt_id]`,
das vom Tray-Daemon (oder Telegram-Channel etc.) ueber `confirm()` resolved wird.

Konfiguration: TOML mit [tools]-Section, Werte sind PermissionLevel-Strings.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple

from openjarvis.core.events import EventBus, EventType
from openjarvis.security.types import (
    PermissionLevel,
    PermissionResult,
    SecurityEvent,
    SecurityEventType,
)

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
        audit: Optional[Any] = None,  # AuditLogger - Forward-Ref vermeiden Zirkular-Import
        default_timeout: float = 30.0,
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
        self._audit = audit
        self._default_timeout = default_timeout
        # Speichert pro prompt_id zusaetzlich tool/args/channel fuer's Audit-Logging
        self._pending: Dict[str, _PendingEntry] = {}
        self._pending_meta: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def _audit_log(
        self,
        event_type: SecurityEventType,
        *,
        tool: str,
        channel: str,
        action: str,
        prompt_id: str = "",
        args: Optional[dict] = None,
        reason: str = "",
    ) -> None:
        """Schreibt einen Eintrag in die Audit-Hash-Chain. Stiller No-Op wenn
        kein AuditLogger injiziert wurde."""
        if self._audit is None:
            return
        payload = {
            "tool": tool,
            "channel": channel,
            "args": args or {},
            "prompt_id": prompt_id,
        }
        if reason:
            payload["reason"] = reason
        self._audit.log(
            SecurityEvent(
                event_type=event_type,
                timestamp=time.time(),
                findings=[],
                content_preview=json.dumps(payload, ensure_ascii=False),
                action_taken=action,
            )
        )

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
            reason = f"tool '{tool_name}' not configured in permissions.toml"
            self._audit_log(
                SecurityEventType.PERMISSION_DENIED,
                tool=tool_name, channel=channel, action="not_configured",
                args=args, reason=reason,
            )
            return PermissionResult.denied(reason)

        if level == PermissionLevel.FREE:
            self._audit_log(
                SecurityEventType.PERMISSION_GRANTED,
                tool=tool_name, channel=channel, action="granted",
                args=args,
            )
            return PermissionResult.granted()

        if level == PermissionLevel.DENIED:
            reason = f"tool '{tool_name}' explicitly denied"
            self._audit_log(
                SecurityEventType.PERMISSION_DENIED,
                tool=tool_name, channel=channel, action="denied",
                args=args, reason=reason,
            )
            return PermissionResult.denied(reason)

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
                reason = f"tool '{tool_name}' nicht in admin_whitelist.toml"
                self._audit_log(
                    SecurityEventType.PERMISSION_DENIED,
                    tool=tool_name, channel=channel, action="not_in_whitelist",
                    args=args, reason=reason,
                )
                return PermissionResult.denied(reason)
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
        """Erzeugt UUID, registriert (Future, kind), publiziert Event,
        startet Auto-Decline-Watcher."""
        prompt_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        async with self._lock:
            self._pending[prompt_id] = (loop.create_future(), kind)
            self._pending_meta[prompt_id] = {
                "tool": tool_name, "args": args, "channel": channel,
            }
        self._audit_log(
            SecurityEventType.PERMISSION_REQUESTED,
            tool=tool_name, channel=channel, action=f"awaiting_{kind}",
            prompt_id=prompt_id, args=args,
        )
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
        loop.create_task(self._auto_decline(prompt_id))
        return result_factory(prompt_id)

    async def _auto_decline(self, prompt_id: str) -> None:
        """Nach default_timeout Sekunden: pop unter Lock, wenn Future noch nicht
        resolved -> set_result(False)."""
        try:
            await asyncio.sleep(self._default_timeout)
        except asyncio.CancelledError:
            return
        async with self._lock:
            entry = self._pending.pop(prompt_id, None)
            meta = self._pending_meta.pop(prompt_id, {})
        if entry is None:
            return  # confirm() war schneller
        fut, _kind = entry
        if not fut.done():
            fut.set_result(False)
            self._audit_log(
                SecurityEventType.PERMISSION_DENIED,
                tool=meta.get("tool", "?"),
                channel=meta.get("channel", "?"),
                args=meta.get("args", {}),
                prompt_id=prompt_id,
                action="timeout",
                reason="timeout",
            )
            if self._bus is not None:
                self._bus.publish(
                    EventType.PERMISSION_RESOLVED,
                    {"prompt_id": prompt_id, "granted": False, "reason": "timeout"},
                )

    async def confirm(self, prompt_id: str, response: str) -> bool:
        """Vom Tray/Channel gerufen mit der User-Antwort.

        Confirm-Pfad: response in {"yes","ja","ok","true","1"} -> True, sonst False.
        Admin-Pfad: response ist die PIN, wird via _pin_check verifiziert.
        """
        async with self._lock:
            entry = self._pending.pop(prompt_id, None)
            meta = self._pending_meta.pop(prompt_id, {})
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
        self._audit_log(
            SecurityEventType.PERMISSION_GRANTED if granted else SecurityEventType.PERMISSION_DENIED,
            tool=meta.get("tool", "?"),
            channel=meta.get("channel", "?"),
            args=meta.get("args", {}),
            prompt_id=prompt_id,
            action="granted" if granted else "user_declined",
        )
        if self._bus is not None:
            self._bus.publish(
                EventType.PERMISSION_RESOLVED,
                {"prompt_id": prompt_id, "granted": granted},
            )
        return granted


__all__ = ["PermissionGate"]
