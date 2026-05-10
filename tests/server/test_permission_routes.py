"""Tests fuer /permission/respond + /audit/log + /voice/status (Stage 2 Task 9)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.security.audit import AuditLogger
from openjarvis.security.permission_gate import PermissionGate
from openjarvis.server.permission_routes import (
    create_permission_router,
    get_voice_status_snapshot,
)


def _write_toml(tmp_path: Path, tools: dict[str, str]) -> Path:
    lines = ["[tools]"]
    for name, level in tools.items():
        lines.append(f'"{name}" = "{level}"')
    p = tmp_path / "permissions.toml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _build_app(tmp_path: Path) -> tuple[FastAPI, PermissionGate, AuditLogger]:
    audit = AuditLogger(db_path=tmp_path / "audit.db")
    config = _write_toml(tmp_path, {"mail.send": "confirm", "calendar.upcoming": "free"})
    gate = PermissionGate(config_path=config, audit=audit, default_timeout=10.0)
    app = FastAPI()
    app.include_router(create_permission_router(gate=gate, audit=audit))
    return app, gate, audit


@pytest.mark.asyncio
async def test_post_respond_resolves_pending(tmp_path):
    app, gate, _ = _build_app(tmp_path)

    # check() in einer Coroutine, damit das Future existiert
    result = await gate.check("mail.send", {"to": "x"}, channel="voice_local")

    client = TestClient(app)
    resp = client.post(f"/permission/respond/{result.prompt_id}", json={"response": "yes"})
    assert resp.status_code == 200
    assert resp.json() == {"granted": True, "prompt_id": result.prompt_id}


def test_post_respond_unknown_prompt_returns_404(tmp_path):
    app, _, _ = _build_app(tmp_path)
    client = TestClient(app)
    resp = client.post(
        "/permission/respond/00000000-0000-0000-0000-000000000000",
        json={"response": "yes"},
    )
    assert resp.status_code == 404


def test_get_audit_log_returns_recent_events(tmp_path):
    app, gate, _ = _build_app(tmp_path)

    asyncio.run(gate.check("calendar.upcoming", {}, channel="voice_local"))
    asyncio.run(gate.check("calendar.upcoming", {}, channel="telegram"))

    client = TestClient(app)
    resp = client.get("/audit/log?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert len(data["events"]) >= 2
    assert data["events"][0]["event_type"]  # nicht leer


def test_get_voice_status_returns_default_disconnected(tmp_path):
    app, _, _ = _build_app(tmp_path)
    client = TestClient(app)
    resp = client.get("/voice/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "connected" in body
    assert "wake_count" in body
    assert "last_wake" in body


def test_voice_status_snapshot_function_returns_dict():
    """Helper-Funktion liefert ein Default-Dict, das der Endpoint einfach durchreicht."""
    snap = get_voice_status_snapshot()
    assert isinstance(snap, dict)
    assert set(snap.keys()) >= {"connected", "wake_count", "last_wake"}


class TestPendingEndpoint:
    """Stage 5: GET /permission/pending liefert offene Prompts ans Cockpit."""

    def test_pending_empty(self, tmp_path):
        app, _, _ = _build_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/permission/pending")
        assert resp.status_code == 200
        assert resp.json() == {"pending": []}

    def test_pending_returns_entries(self, tmp_path):
        app, gate, _ = _build_app(tmp_path)
        # Pending-Eintrag manuell simulieren — asyncio.Future braucht einen Loop.
        loop = asyncio.new_event_loop()
        try:
            fut = loop.create_future()
            gate._pending["pid-123"] = (fut, "confirm")
            gate._pending_meta["pid-123"] = {
                "tool": "mail.send",
                "args": {"to": "x"},
                "channel": "voice_local",
            }
            client = TestClient(app)
            resp = client.get("/permission/pending")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["pending"]) == 1
            entry = data["pending"][0]
            assert entry["prompt_id"] == "pid-123"
            assert entry["tool"] == "mail.send"
            assert entry["channel"] == "voice_local"
            assert entry["kind"] == "confirm"
            assert entry["args"] == {"to": "x"}
        finally:
            if not fut.done():
                fut.cancel()
            loop.close()

    def test_pending_admin_kind(self, tmp_path):
        app, gate, _ = _build_app(tmp_path)
        loop = asyncio.new_event_loop()
        try:
            fut = loop.create_future()
            gate._pending["pid-pin"] = (fut, "pin")
            gate._pending_meta["pid-pin"] = {
                "tool": "admin.flush_dns",
                "args": {},
                "channel": "voice_local",
            }
            client = TestClient(app)
            resp = client.get("/permission/pending")
            data = resp.json()
            assert data["pending"][0]["kind"] == "pin"
        finally:
            if not fut.done():
                fut.cancel()
            loop.close()
