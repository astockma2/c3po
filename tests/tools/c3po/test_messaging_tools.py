"""Tests fuer c3po/messaging_tools.py — Stage 3 Sub-Stufe 3.6."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from openjarvis.tools.c3po.messaging_tools import (
    MessagingLastReceivedTool,
    SignalSendTool,
    SlackSendTool,
    TelegramSendTool,
    WhatsAppSendTool,
)


# ---------------------------------------------------------------------------
# telegram.send — voll implementiert
# ---------------------------------------------------------------------------


class TestTelegramSend:
    def test_spec(self):
        assert TelegramSendTool().spec.name == "telegram.send"

    def test_empty_text_fails(self):
        r = TelegramSendTool().execute(text="")
        assert r.success is False

    def test_no_token_fails(self):
        with patch(
            "openjarvis.tools.c3po.messaging_tools._keyring_get", return_value=None
        ):
            r = TelegramSendTool().execute(text="hi")
        assert r.success is False
        assert "Token" in r.content

    def test_no_chat_id_fails(self):
        # Erste keyring-Abfrage liefert Token, zweite (chat_id) None
        def _kg(service, user):
            return "tok123" if user == "bot_token" else None

        with patch(
            "openjarvis.tools.c3po.messaging_tools._keyring_get", side_effect=_kg
        ):
            r = TelegramSendTool().execute(text="hi")
        assert r.success is False
        assert "Chat-ID" in r.content

    def test_send_calls_api(self):
        def _kg(service, user):
            return "tok" if user == "bot_token" else "12345"

        with patch(
            "openjarvis.tools.c3po.messaging_tools._keyring_get", side_effect=_kg
        ), patch(
            "openjarvis.tools.c3po.messaging_tools._telegram_api_post",
            return_value={"ok": True, "result": {"message_id": 7}},
        ) as post:
            r = TelegramSendTool().execute(text="Hallo")
        assert r.success is True
        post.assert_called_once()
        # Token + Methode + Payload
        args, _ = post.call_args
        assert args[0] == "tok"
        assert args[1] == "sendMessage"
        assert args[2]["text"] == "Hallo"
        assert args[2]["chat_id"] == "12345"

    def test_api_error_marked_failure(self):
        def _kg(service, user):
            return "tok" if user == "bot_token" else "12345"

        with patch(
            "openjarvis.tools.c3po.messaging_tools._keyring_get", side_effect=_kg
        ), patch(
            "openjarvis.tools.c3po.messaging_tools._telegram_api_post",
            return_value={"ok": False, "description": "Bad Request"},
        ):
            r = TelegramSendTool().execute(text="Hi")
        assert r.success is False
        assert "Bad Request" in r.content

    def test_explicit_chat_id_overrides(self):
        def _kg(service, user):
            return "tok" if user == "bot_token" else "andre_chat"

        with patch(
            "openjarvis.tools.c3po.messaging_tools._keyring_get", side_effect=_kg
        ), patch(
            "openjarvis.tools.c3po.messaging_tools._telegram_api_post",
            return_value={"ok": True, "result": {"message_id": 1}},
        ) as post:
            TelegramSendTool().execute(text="x", chat_id="other_chat")
        args, _ = post.call_args
        assert args[2]["chat_id"] == "other_chat"


# ---------------------------------------------------------------------------
# Stub-Tools
# ---------------------------------------------------------------------------


class TestStubTools:
    @pytest.mark.parametrize(
        "tool_cls,name",
        [
            (WhatsAppSendTool, "whatsapp.send"),
            (SignalSendTool, "signal.send"),
            (SlackSendTool, "slack.send"),
        ],
    )
    def test_stub_returns_failure_with_hint(self, tool_cls, name):
        r = tool_cls().execute(to="x", text="y", channel="#x")
        assert r.success is False
        assert name in r.content
        assert "konfiguriert" in r.content.lower()


# ---------------------------------------------------------------------------
# messaging.last_received
# ---------------------------------------------------------------------------


class TestLastReceived:
    def test_spec(self):
        assert MessagingLastReceivedTool().spec.name == "messaging.last_received"

    def test_returns_empty_list(self):
        r = MessagingLastReceivedTool().execute()
        assert r.success is True
        assert json.loads(r.content) == []
