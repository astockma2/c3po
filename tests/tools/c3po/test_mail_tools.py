"""Tests fuer c3po/mail_tools.py — Stage 3 Sub-Stufe 3.3.

Alle Gmail-API-Aufrufe sind gemockt. Test-Strategie: Connector-Factory
patchen, dann den Connector-Mock so verdrahten dass er sync()/credentials_path
liefert. Fuer .send: gmail_api_send_message direkt patchen.
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.tools.c3po.mail_tools import (
    MailListUnreadTool,
    MailReadTool,
    MailSearchTool,
    MailSendTool,
    _build_raw_email,
)


def _fake_doc(*, doc_id="gmail:1", author="Alice", title="Test", body="Hi", labels=None):
    return SimpleNamespace(
        doc_id=doc_id,
        author=author,
        title=title,
        content=body,
        timestamp=datetime(2026, 5, 10, 12, 0),
        metadata={"labels": labels or ["UNREAD", "INBOX"]},
    )


# ---------------------------------------------------------------------------
# mail.list_unread
# ---------------------------------------------------------------------------


class TestMailListUnread:
    def test_spec(self):
        assert MailListUnreadTool().spec.name == "mail.list_unread"

    def test_not_connected(self):
        connector = MagicMock()
        connector.is_connected.return_value = False
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=connector,
        ):
            r = MailListUnreadTool().execute()
        assert r.success is False
        assert "nicht verbunden" in r.content.lower()

    def test_filters_unread_only(self):
        connector = MagicMock()
        connector.is_connected.return_value = True
        connector.sync.return_value = iter(
            [
                _fake_doc(doc_id="1", labels=["UNREAD"]),
                _fake_doc(doc_id="2", labels=["INBOX"]),  # nicht unread
                _fake_doc(doc_id="3", labels=["UNREAD"]),
            ]
        )
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=connector,
        ):
            r = MailListUnreadTool().execute()
        assert r.success is True
        data = json.loads(r.content)
        assert len(data) == 2
        assert all(m["id"] in ("1", "3") for m in data)

    def test_respects_max_results(self):
        connector = MagicMock()
        connector.is_connected.return_value = True
        connector.sync.return_value = iter(
            [_fake_doc(doc_id=str(i), labels=["UNREAD"]) for i in range(20)]
        )
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=connector,
        ):
            r = MailListUnreadTool().execute(max_results=5)
        data = json.loads(r.content)
        assert len(data) == 5


# ---------------------------------------------------------------------------
# mail.read
# ---------------------------------------------------------------------------


class TestMailRead:
    def test_spec(self):
        assert MailReadTool().spec.name == "mail.read"

    def test_empty_id_fails(self):
        r = MailReadTool().execute(id="")
        assert r.success is False

    def test_no_token_fails(self):
        connector = MagicMock()
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=connector,
        ), patch(
            "openjarvis.tools.c3po.mail_tools._read_gmail_token",
            return_value=None,
        ):
            r = MailReadTool().execute(id="abc123")
        assert r.success is False

    def test_strips_gmail_prefix(self):
        connector = MagicMock()
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=connector,
        ), patch(
            "openjarvis.tools.c3po.mail_tools._read_gmail_token",
            return_value="tok",
        ), patch(
            "openjarvis.connectors.gmail._gmail_api_get_message",
            return_value={
                "payload": {
                    "headers": [
                        {"name": "From", "value": "a@b"},
                        {"name": "Subject", "value": "Hi"},
                    ],
                    "body": {"data": ""},
                }
            },
        ) as get_msg:
            MailReadTool().execute(id="gmail:abc123")
        # gmail:-prefix muss raus
        assert get_msg.call_args[0][1] == "abc123"


# ---------------------------------------------------------------------------
# mail.search
# ---------------------------------------------------------------------------


class TestMailSearch:
    def test_empty_query_fails(self):
        r = MailSearchTool().execute(query="")
        assert r.success is False

    def test_search_returns_results(self):
        connector = MagicMock()
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=connector,
        ), patch(
            "openjarvis.tools.c3po.mail_tools._read_gmail_token",
            return_value="tok",
        ), patch(
            "openjarvis.connectors.gmail._gmail_api_list_messages",
            return_value={"messages": [{"id": "m1"}, {"id": "m2"}]},
        ), patch(
            "openjarvis.connectors.gmail._gmail_api_get_message",
            side_effect=[
                {
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "alice@x"},
                            {"name": "Subject", "value": "Hello"},
                        ]
                    }
                },
                {
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "bob@x"},
                            {"name": "Subject", "value": "World"},
                        ]
                    }
                },
            ],
        ):
            r = MailSearchTool().execute(query="from:alice")
        assert r.success is True
        data = json.loads(r.content)
        assert len(data) == 2
        assert {d["from"] for d in data} == {"alice@x", "bob@x"}


# ---------------------------------------------------------------------------
# mail.send
# ---------------------------------------------------------------------------


class TestMailSend:
    def test_spec(self):
        assert MailSendTool().spec.name == "mail.send"

    def test_missing_required_field(self):
        r = MailSendTool().execute(to="", subject="x", body="y")
        assert r.success is False

    def test_no_token_fails(self):
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.mail_tools._read_gmail_token",
            return_value=None,
        ):
            r = MailSendTool().execute(to="a@b", subject="x", body="y")
        assert r.success is False

    def test_send_calls_gmail_api(self):
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.mail_tools._read_gmail_token",
            return_value="tok",
        ), patch(
            "openjarvis.tools.c3po.mail_tools._gmail_api_send_message",
            return_value={"id": "sent-123"},
        ) as send:
            r = MailSendTool().execute(
                to="andre@astockma.de", subject="Test", body="Hi"
            )
        assert r.success is True
        assert "sent-123" in r.content
        # Token + raw-string wurden uebergeben
        token, raw = send.call_args[0]
        assert token == "tok"
        assert isinstance(raw, str) and len(raw) > 10

    def test_build_raw_email_contains_fields(self):
        raw_b64 = _build_raw_email(
            to="x@y", subject="Subj", body="Body"
        )
        # base64url - decode to plain bytes and check headers
        import base64

        # Pad re-add for decode
        pad = "=" * (-len(raw_b64) % 4)
        decoded = base64.urlsafe_b64decode(raw_b64 + pad).decode("utf-8", errors="ignore")
        assert "x@y" in decoded
        assert "Subj" in decoded
        assert "Body" in decoded
