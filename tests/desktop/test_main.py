"""Tests fuer desktop/main.py Event-Routing (Stage 2 Task 10)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_event_router_dispatches_confirm_request():
    from desktop.main import EventRouter

    on_confirm = MagicMock()
    on_pin = MagicMock()
    router = EventRouter(on_confirm=on_confirm, on_pin=on_pin)

    router.handle({
        "event_type": "permission_confirm_requested",
        "data": {"prompt_id": "p1", "tool": "mail.send", "args": {}, "channel": "voice_local"},
    })

    on_confirm.assert_called_once()
    args, _ = on_confirm.call_args
    payload = args[0]
    assert payload["prompt_id"] == "p1"
    assert payload["tool"] == "mail.send"
    on_pin.assert_not_called()


def test_event_router_dispatches_pin_request():
    from desktop.main import EventRouter

    on_confirm = MagicMock()
    on_pin = MagicMock()
    router = EventRouter(on_confirm=on_confirm, on_pin=on_pin)

    router.handle({
        "event_type": "permission_pin_requested",
        "data": {"prompt_id": "p2", "tool": "admin.reboot", "args": {}, "channel": "telegram"},
    })

    on_pin.assert_called_once()
    on_confirm.assert_not_called()


def test_event_router_ignores_unknown_event_type():
    from desktop.main import EventRouter

    on_confirm = MagicMock()
    on_pin = MagicMock()
    router = EventRouter(on_confirm=on_confirm, on_pin=on_pin)

    router.handle({"event_type": "permission_resolved", "data": {}})
    router.handle({"event_type": "something.unrelated", "data": {}})

    on_confirm.assert_not_called()
    on_pin.assert_not_called()


def test_server_client_post_response(monkeypatch):
    """ServerClient.respond posted JSON an /permission/respond/{prompt_id}."""
    from desktop.main import ServerClient

    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout

        class R:
            status_code = 200
            def json(self_inner): return {"granted": True, "prompt_id": "p1"}
        return R()

    import desktop.main as desktop_main
    monkeypatch.setattr(desktop_main.requests, "post", fake_post)

    client = ServerClient(server_url="http://127.0.0.1:8000")
    granted = client.respond("p1", "yes")

    assert granted is True
    assert captured["url"] == "http://127.0.0.1:8000/permission/respond/p1"
    assert captured["json"] == {"response": "yes"}
    assert captured["timeout"] == 10


def test_server_client_returns_false_on_http_error(monkeypatch):
    from desktop.main import ServerClient

    def fake_post(url, json, timeout):
        class R:
            status_code = 500
            text = "boom"
            def json(self_inner): return {}
        return R()

    import desktop.main as desktop_main
    monkeypatch.setattr(desktop_main.requests, "post", fake_post)

    client = ServerClient(server_url="http://127.0.0.1:8000")
    granted = client.respond("p1", "yes")
    assert granted is False
