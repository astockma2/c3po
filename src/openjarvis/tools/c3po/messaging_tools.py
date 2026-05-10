"""C3PO Messaging-Tools (Stage 3 Sub-Stufe 3.6).

5 Tools — alle ``send`` sind ``confirm``, ``last_received`` ist ``free``:
- ``telegram.send`` (Andres Hauptkanal, voll implementiert via keyring + Bot-API)
- ``whatsapp.send``, ``signal.send``, ``slack.send`` (Stubs — liefern klare
  Fehlermeldung wenn nicht konfiguriert; Implementierung in Stage 4 oder
  spaeter)
- ``messaging.last_received`` (Stub — gibt aktuell leer zurueck, Stage 4 wird
  das mit dem Channel-Inbox-Pattern verdrahten)

Telegram-Setup (analog zu C3PO-legacy/tools/telegram_tool.py):
1. ``@BotFather`` → ``/newbot`` → Token kopieren
2. Token im Windows Credential Manager: Service ``C3PO-Telegram``,
   Username ``bot_token``
3. Andre's Chat-ID per ``/start`` an den Bot — wird im selben Service unter
   ``andre_chat_id`` gespeichert.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

KEYRING_SERVICE = "C3PO-Telegram"


# ---------------------------------------------------------------------------
# keyring-Helper (testbar)
# ---------------------------------------------------------------------------


def _keyring_get(service: str, username: str) -> Optional[str]:
    """Indirektion fuer Tests — patched in test files."""
    try:
        import keyring

        return keyring.get_password(service, username)
    except ImportError:
        return None


def _telegram_api_post(token: str, method: str, payload: dict) -> dict:
    """POST an die Telegram-Bot-API (testbar)."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# telegram.send (echt)
# ---------------------------------------------------------------------------


@ToolRegistry.register("telegram.send")
class TelegramSendTool(BaseTool):
    """Sendet eine Telegram-Nachricht an Andre. Permission: confirm."""

    tool_id = "telegram.send"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="telegram.send",
            description=(
                "Schickt eine Telegram-Nachricht an den festgelegten Chat "
                "(Default: Andre). Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "chat_id": {
                        "type": "string",
                        "description": "Optional anderer Chat — Default ist Andre.",
                    },
                },
                "required": ["text"],
            },
            category="messaging",
        )

    def execute(self, **params: Any) -> ToolResult:
        text = params.get("text") or ""
        if not text:
            return ToolResult(
                tool_name="telegram.send", content="Kein Text.", success=False
            )
        token = _keyring_get(KEYRING_SERVICE, "bot_token")
        if not token:
            return ToolResult(
                tool_name="telegram.send",
                content="Telegram-Bot-Token fehlt im Keyring.",
                success=False,
            )
        chat_id = params.get("chat_id") or _keyring_get(
            KEYRING_SERVICE, "andre_chat_id"
        )
        if not chat_id:
            return ToolResult(
                tool_name="telegram.send",
                content="Andre's Chat-ID fehlt — /start im Bot senden.",
                success=False,
            )
        try:
            resp = _telegram_api_post(
                token, "sendMessage", {"chat_id": chat_id, "text": text}
            )
            if not resp.get("ok"):
                return ToolResult(
                    tool_name="telegram.send",
                    content=f"Telegram-API-Fehler: {resp.get('description', resp)}",
                    success=False,
                )
            return ToolResult(
                tool_name="telegram.send",
                content=f"Telegram-Nachricht an {chat_id} verschickt.",
                success=True,
                metadata={"message_id": resp.get("result", {}).get("message_id")},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="telegram.send",
                content=f"Versand fehlgeschlagen: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# Stub-Send-Tools (Stage 4 oder spaeter konfigurieren)
# ---------------------------------------------------------------------------


def _stub_send(name: str, configured_hint: str) -> ToolResult:
    return ToolResult(
        tool_name=name,
        content=(
            f"{name} ist noch nicht konfiguriert. "
            f"Anleitung: {configured_hint}"
        ),
        success=False,
    )


@ToolRegistry.register("whatsapp.send")
class WhatsAppSendTool(BaseTool):
    """WhatsApp-Send — Stub bis Cloud-API-Token gesetzt ist."""

    tool_id = "whatsapp.send"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="whatsapp.send",
            description=(
                "Sendet WhatsApp-Nachricht (Stub — braucht Cloud-API-Token). "
                "Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["to", "text"],
            },
            category="messaging",
        )

    def execute(self, **params: Any) -> ToolResult:
        return _stub_send(
            "whatsapp.send",
            "WhatsApp Cloud API Token im Keyring 'C3PO-WhatsApp'/'token' ablegen.",
        )


@ToolRegistry.register("signal.send")
class SignalSendTool(BaseTool):
    """Signal-Send — Stub bis signal-cli verdrahtet ist."""

    tool_id = "signal.send"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="signal.send",
            description=(
                "Sendet Signal-Nachricht (Stub — braucht signal-cli). "
                "Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["to", "text"],
            },
            category="messaging",
        )

    def execute(self, **params: Any) -> ToolResult:
        return _stub_send(
            "signal.send",
            "signal-cli installieren und SIGNAL_CLI_PATH in env setzen.",
        )


@ToolRegistry.register("slack.send")
class SlackSendTool(BaseTool):
    """Slack-Send — Stub bis SlackConnector verdrahtet ist."""

    tool_id = "slack.send"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="slack.send",
            description=(
                "Sendet Slack-Nachricht (Stub — braucht Bot-Token). "
                "Permission: confirm."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
            category="messaging",
        )

    def execute(self, **params: Any) -> ToolResult:
        return _stub_send(
            "slack.send",
            "Slack-Bot-Token im Keyring 'C3PO-Slack'/'bot_token' ablegen.",
        )


# ---------------------------------------------------------------------------
# messaging.last_received
# ---------------------------------------------------------------------------


@ToolRegistry.register("messaging.last_received")
class MessagingLastReceivedTool(BaseTool):
    """Liefert die letzten N empfangenen Nachrichten (Stub Stage 3)."""

    tool_id = "messaging.last_received"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="messaging.last_received",
            description=(
                "Letzte empfangene Messaging-Nachrichten ueber alle Kanaele. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {"max_results": {"type": "integer"}},
            },
            category="messaging",
        )

    def execute(self, **params: Any) -> ToolResult:
        # Stage 4 wird das mit dem Channel-Inbox-Pattern verdrahten.
        return ToolResult(
            tool_name="messaging.last_received",
            content=json.dumps([]),
            success=True,
            metadata={"note": "Stage 3 stub — wird in Stage 4 implementiert"},
        )


__all__ = [
    "TelegramSendTool",
    "WhatsAppSendTool",
    "SignalSendTool",
    "SlackSendTool",
    "MessagingLastReceivedTool",
]
