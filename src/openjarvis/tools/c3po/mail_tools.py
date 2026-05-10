"""C3PO Mail-Tools (Stage 3 Sub-Stufe 3.3, Gmail-first).

4 Tools:
- ``mail.list_unread`` (free): die letzten ungelesenen Mails.
- ``mail.read`` (free): eine konkrete Mail per ID anzeigen.
- ``mail.search`` (free): Gmail-Query-Syntax.
- ``mail.send`` (confirm): Mail versenden via Gmail API.

Backend: ``GmailConnector`` aus ``src/openjarvis/connectors/gmail.py``. Andre's
Strato-Connector ist ebenfalls vorhanden, wird aber in Stage 3 nicht
verdrahtet — Gmail-first nach User-Entscheidung.

``mail.send`` ist eine duenne Implementierung gegen die ``users.messages.send``-
Gmail-API. Andre's OAuth-Token mit ``gmail.send``-Scope muss vorhanden sein
(siehe ``connectors/google_auth.py``).
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


# ---------------------------------------------------------------------------
# Connector-Factory (testbar)
# ---------------------------------------------------------------------------


def _get_gmail_connector() -> Any:
    """Liefert eine GmailConnector-Instanz. Tests patchen das."""
    from openjarvis.connectors.gmail import GmailConnector

    return GmailConnector()


def _read_gmail_token(connector: Any) -> Optional[str]:
    """Liest das OAuth-Token aus dem credentials_path des Connectors."""
    from openjarvis.connectors.google_auth import load_tokens

    tokens = load_tokens(connector._credentials_path)
    if not tokens:
        return None
    return tokens.get("token") or tokens.get("access_token")


# ---------------------------------------------------------------------------
# mail.list_unread / mail.read / mail.search — read via sync()
# ---------------------------------------------------------------------------


def _summarize_doc(doc: Any) -> dict:
    """Baut ein kompaktes Summary-Dict aus einem Document."""
    return {
        "id": getattr(doc, "doc_id", ""),
        "from": getattr(doc, "author", ""),
        "subject": getattr(doc, "title", ""),
        "timestamp": getattr(doc, "timestamp", "").isoformat()
        if hasattr(doc, "timestamp") and doc.timestamp
        else "",
        "preview": (getattr(doc, "content", "") or "")[:200],
    }


@ToolRegistry.register("mail.list_unread")
class MailListUnreadTool(BaseTool):
    """Listet die letzten N ungelesenen Mails (Default: 10)."""

    tool_id = "mail.list_unread"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="mail.list_unread",
            description=(
                "Listet die letzten ungelesenen Mails (Gmail). "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximale Anzahl (Default 10).",
                    },
                },
            },
            category="mail",
        )

    def execute(self, **params: Any) -> ToolResult:
        max_results = int(params.get("max_results") or 10)
        try:
            connector = _get_gmail_connector()
            if not connector.is_connected():
                return ToolResult(
                    tool_name="mail.list_unread",
                    content="Gmail nicht verbunden — OAuth-Setup fehlt.",
                    success=False,
                )
            mails: List[dict] = []
            since = datetime.now() - timedelta(days=14)
            for doc in connector.sync(since=since):
                labels = (doc.metadata or {}).get("labels", [])
                if "UNREAD" not in labels:
                    continue
                mails.append(_summarize_doc(doc))
                if len(mails) >= max_results:
                    break
            return ToolResult(
                tool_name="mail.list_unread",
                content=json.dumps(mails, ensure_ascii=False, default=str),
                success=True,
                metadata={"count": len(mails)},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="mail.list_unread",
                content=f"Fehler: {exc}",
                success=False,
            )


@ToolRegistry.register("mail.read")
class MailReadTool(BaseTool):
    """Liest eine Mail per Gmail-ID (Format: ``gmail:<msg_id>`` oder ``<msg_id>``)."""

    tool_id = "mail.read"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="mail.read",
            description=(
                "Liefert vollen Inhalt einer Mail per Gmail-Message-ID. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Gmail-Message-ID (mit oder ohne 'gmail:'-Praefix).",
                    },
                },
                "required": ["id"],
            },
            category="mail",
        )

    def execute(self, **params: Any) -> ToolResult:
        msg_id = (params.get("id") or "").strip()
        if msg_id.startswith("gmail:"):
            msg_id = msg_id[len("gmail:") :]
        if not msg_id:
            return ToolResult(
                tool_name="mail.read",
                content="Keine ID angegeben.",
                success=False,
            )
        try:
            connector = _get_gmail_connector()
            token = _read_gmail_token(connector)
            if not token:
                return ToolResult(
                    tool_name="mail.read",
                    content="Gmail nicht verbunden — kein Token.",
                    success=False,
                )
            from openjarvis.connectors.gmail import (
                _decode_body,
                _extract_header,
                _gmail_api_get_message,
            )

            msg = _gmail_api_get_message(token, msg_id)
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            data = {
                "id": msg_id,
                "from": _extract_header(headers, "From"),
                "to": _extract_header(headers, "To"),
                "subject": _extract_header(headers, "Subject"),
                "date": _extract_header(headers, "Date"),
                "body": _decode_body(payload),
            }
            return ToolResult(
                tool_name="mail.read",
                content=json.dumps(data, ensure_ascii=False),
                success=True,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="mail.read",
                content=f"Fehler: {exc}",
                success=False,
            )


@ToolRegistry.register("mail.search")
class MailSearchTool(BaseTool):
    """Sucht via Gmail-Query-Syntax (z.B. ``from:alice is:unread``)."""

    tool_id = "mail.search"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="mail.search",
            description=(
                "Sucht Mails per Gmail-Query-Syntax. "
                "Beispiele: 'from:alice', 'subject:rechnung is:unread'. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail-Query-String.",
                    },
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
            category="mail",
        )

    def execute(self, **params: Any) -> ToolResult:
        query = (params.get("query") or "").strip()
        if not query:
            return ToolResult(
                tool_name="mail.search",
                content="Keine Query angegeben.",
                success=False,
            )
        max_results = int(params.get("max_results") or 10)
        try:
            connector = _get_gmail_connector()
            token = _read_gmail_token(connector)
            if not token:
                return ToolResult(
                    tool_name="mail.search",
                    content="Gmail nicht verbunden.",
                    success=False,
                )
            from openjarvis.connectors.gmail import (
                _decode_body,
                _extract_header,
                _gmail_api_get_message,
                _gmail_api_list_messages,
            )

            list_resp = _gmail_api_list_messages(token, query=query)
            results: List[dict] = []
            for stub in list_resp.get("messages", [])[:max_results]:
                msg = _gmail_api_get_message(token, stub.get("id", ""))
                payload = msg.get("payload", {})
                headers = payload.get("headers", [])
                results.append(
                    {
                        "id": stub.get("id", ""),
                        "from": _extract_header(headers, "From"),
                        "subject": _extract_header(headers, "Subject"),
                        "preview": _decode_body(payload)[:200],
                    }
                )
            return ToolResult(
                tool_name="mail.search",
                content=json.dumps(results, ensure_ascii=False),
                success=True,
                metadata={"count": len(results)},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="mail.search",
                content=f"Fehler: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# mail.send (confirm)
# ---------------------------------------------------------------------------


def _gmail_api_send_message(token: str, raw_b64: str) -> dict:
    """POST an die Gmail API ``users.messages.send`` (testbar)."""
    import urllib.request

    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw_b64}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _build_raw_email(*, to: str, subject: str, body: str, sender: str = "") -> str:
    """Baut eine RFC822-Mail und base64url-encoded sie."""
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    if sender:
        msg["From"] = sender
    msg.set_content(body)
    raw = msg.as_bytes()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@ToolRegistry.register("mail.send")
class MailSendTool(BaseTool):
    """Versendet eine Mail via Gmail API. Permission: confirm."""

    tool_id = "mail.send"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="mail.send",
            description=(
                "Versendet eine Mail via Gmail. "
                "Braucht 'gmail.send'-Scope im OAuth-Token. "
                "Permission: confirm (Tray-Dialog)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
            category="mail",
        )

    def execute(self, **params: Any) -> ToolResult:
        to = (params.get("to") or "").strip()
        subject = (params.get("subject") or "").strip()
        body = params.get("body") or ""
        if not to or not subject:
            return ToolResult(
                tool_name="mail.send",
                content="'to' und 'subject' sind Pflicht.",
                success=False,
            )
        try:
            connector = _get_gmail_connector()
            token = _read_gmail_token(connector)
            if not token:
                return ToolResult(
                    tool_name="mail.send",
                    content="Gmail nicht verbunden.",
                    success=False,
                )
            raw = _build_raw_email(to=to, subject=subject, body=body)
            resp = _gmail_api_send_message(token, raw)
            return ToolResult(
                tool_name="mail.send",
                content=f"Mail an {to} verschickt (id={resp.get('id', '?')}).",
                success=True,
                metadata={"gmail_id": resp.get("id")},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="mail.send",
                content=f"Versand fehlgeschlagen: {exc}",
                success=False,
            )


__all__ = [
    "MailListUnreadTool",
    "MailReadTool",
    "MailSearchTool",
    "MailSendTool",
]
