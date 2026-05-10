"""Tests fuer create_app: PermissionGate-Singleton + permission_routes (Stage 2 Task 12)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _write_toml(tmp_path: Path, tools: dict[str, str]) -> Path:
    lines = ["[tools]"]
    for name, level in tools.items():
        lines.append(f'"{name}" = "{level}"')
    p = tmp_path / "permissions.toml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_create_app_attaches_permission_gate(tmp_path, monkeypatch):
    """Wenn permissions_config_path uebergeben wird, baut create_app
    einen PermissionGate-Singleton und legt ihn in app.state ab."""
    from openjarvis.security.permission_gate import PermissionGate
    from openjarvis.server.app import create_app

    config = _write_toml(tmp_path, {"calendar.upcoming": "free"})
    monkeypatch.setenv("OPENJARVIS_PERMISSIONS_CONFIG", str(config))

    app = create_app(engine=MagicMock(), model="test-model")
    gate = getattr(app.state, "permission_gate", None)
    assert isinstance(gate, PermissionGate)


def test_create_app_without_env_has_no_permission_gate(monkeypatch):
    """Ohne OPENJARVIS_PERMISSIONS_CONFIG-ENV ist app.state.permission_gate None."""
    from openjarvis.server.app import create_app

    monkeypatch.delenv("OPENJARVIS_PERMISSIONS_CONFIG", raising=False)
    app = create_app(engine=MagicMock(), model="test-model")
    assert getattr(app.state, "permission_gate", None) is None


def test_voice_local_accepts_permission_gate_arg():
    """VoiceLocalChannel akzeptiert permission_gate-Konstruktor-Param."""
    from openjarvis.channels.voice_local import VoiceLocalChannel

    fake_gate = MagicMock()
    ch = VoiceLocalChannel(permission_gate=fake_gate)
    assert ch._permission_gate is fake_gate


def test_voice_local_default_permission_gate_is_none():
    from openjarvis.channels.voice_local import VoiceLocalChannel

    ch = VoiceLocalChannel()
    assert ch._permission_gate is None


def test_create_app_includes_permission_routes(tmp_path, monkeypatch):
    """Permission-Routen sind im Router registriert."""
    from fastapi.testclient import TestClient
    from openjarvis.server.app import create_app

    config = _write_toml(tmp_path, {"calendar.upcoming": "free"})
    monkeypatch.setenv("OPENJARVIS_PERMISSIONS_CONFIG", str(config))

    app = create_app(engine=MagicMock(), model="test-model")
    client = TestClient(app)
    resp = client.get("/voice/status")
    assert resp.status_code == 200
