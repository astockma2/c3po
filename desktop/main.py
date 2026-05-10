"""Tray-Daemon - eigener Prozess, getrennt vom Server.

Verbindet sich mit dem Server (HTTP-Polling oder WebSocket), routet
Permission-Events an die passenden Dialog-Funktionen aus tray.py /
confirm_dialog.py / pin_dialog.py (PORT in Task 11), schickt die User-
Antwort per HTTP an /permission/respond/{prompt_id} zurueck.

In Task 10 nur die testbare Logik (EventRouter, ServerClient).
Der GUI-Bootstrapping-Teil (_entry_point) ist in eigenen Funktionen
isoliert, damit Tests ohne PyQt6 laufen koennen.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

import requests

logger = logging.getLogger(__name__)


PermissionHandler = Callable[[Dict[str, Any]], None]


class EventRouter:
    """Routet eingehende Server-Events an die passenden Dialog-Handler.

    Der Tray bindet on_confirm an confirm_dialog.show(),
    on_pin an pin_dialog.show().
    """

    def __init__(
        self,
        *,
        on_confirm: PermissionHandler,
        on_pin: PermissionHandler,
    ) -> None:
        self._on_confirm = on_confirm
        self._on_pin = on_pin

    def handle(self, event: Dict[str, Any]) -> None:
        etype = event.get("event_type", "")
        data = event.get("data", {}) or {}

        if etype == "permission_confirm_requested":
            self._on_confirm(data)
        elif etype == "permission_pin_requested":
            self._on_pin(data)
        else:
            logger.debug("EventRouter ignoriert unbekanntes Event: %s", etype)


class ServerClient:
    """HTTP-Client zum Server. Schickt User-Antworten zurueck.

    Polling fuer Events kommt in Task 12+ (Lifecycle-Verdrahtung).
    """

    def __init__(self, *, server_url: str = "http://127.0.0.1:8000") -> None:
        self._base = server_url.rstrip("/")

    def respond(self, prompt_id: str, response: str) -> bool:
        """POST /permission/respond/{prompt_id} mit JSON-Body.

        Returns True wenn Server granted=True meldet, False bei
        HTTP-Error oder Server granted=False.
        """
        url = f"{self._base}/permission/respond/{prompt_id}"
        try:
            resp = requests.post(url, json={"response": response}, timeout=10)
        except requests.RequestException as exc:
            logger.warning("ServerClient.respond: HTTP-Exception: %s", exc)
            return False

        if resp.status_code != 200:
            logger.warning(
                "ServerClient.respond: HTTP %d - %s",
                resp.status_code, getattr(resp, "text", "")[:200],
            )
            return False

        body = resp.json()
        return bool(body.get("granted", False))


def _entry_point() -> int:
    """GUI-Bootstrapping. Wird NICHT in Tests gerufen.

    Baut PyQt6 QApplication, Tray-Icon, Confirm/PIN-Dialoge,
    ServerClient-Polling-Loop. Wird in Task 11+12 vervollstaendigt.
    """
    raise NotImplementedError("kommt in Task 11/12")


__all__ = ["EventRouter", "ServerClient"]
