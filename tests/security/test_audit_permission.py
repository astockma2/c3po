"""Tests fuer die Audit-Log-Integration des PermissionGate (Stage 2 Task 8)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from openjarvis.security.audit import AuditLogger
from openjarvis.security.permission_gate import PermissionGate
from openjarvis.security.types import SecurityEventType


def _write_toml(tmp_path: Path, tools: dict[str, str]) -> Path:
    lines = ["[tools]"]
    for name, level in tools.items():
        lines.append(f'"{name}" = "{level}"')
    p = tmp_path / "permissions.toml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_free_check_logs_granted(tmp_path):
    audit = AuditLogger(db_path=tmp_path / "audit.db")
    config = _write_toml(tmp_path, {"calendar.upcoming": "free"})
    gate = PermissionGate(config_path=config, audit=audit)

    await gate.check("calendar.upcoming", {"when": "14:00"}, channel="voice_local")

    granted = audit.query(event_type=SecurityEventType.PERMISSION_GRANTED.value)
    assert len(granted) == 1
    payload = json.loads(granted[0].content_preview)
    assert payload["tool"] == "calendar.upcoming"
    assert payload["channel"] == "voice_local"
    assert granted[0].action_taken == "granted"


@pytest.mark.asyncio
async def test_unknown_tool_logs_denied(tmp_path):
    audit = AuditLogger(db_path=tmp_path / "audit.db")
    config = _write_toml(tmp_path, {})
    gate = PermissionGate(config_path=config, audit=audit)

    await gate.check("nope.unknown", {}, channel="voice_local")
    denied = audit.query(event_type=SecurityEventType.PERMISSION_DENIED.value)
    assert len(denied) == 1
    assert "not configured" in denied[0].action_taken or "not configured" in denied[0].content_preview


@pytest.mark.asyncio
async def test_confirm_grant_logs_two_events(tmp_path):
    """CONFIRM-Pfad: REQUESTED beim check, GRANTED nach confirm()."""
    audit = AuditLogger(db_path=tmp_path / "audit.db")
    config = _write_toml(tmp_path, {"mail.send": "confirm"})
    gate = PermissionGate(config_path=config, audit=audit)

    result = await gate.check("mail.send", {"to": "x"}, channel="voice_local")
    await gate.confirm(result.prompt_id, "yes")

    requested = audit.query(event_type=SecurityEventType.PERMISSION_REQUESTED.value)
    granted = audit.query(event_type=SecurityEventType.PERMISSION_GRANTED.value)
    assert len(requested) == 1
    assert len(granted) == 1

    # Beide Events tragen die selbe prompt_id
    req_payload = json.loads(requested[0].content_preview)
    grt_payload = json.loads(granted[0].content_preview)
    assert req_payload["prompt_id"] == result.prompt_id
    assert grt_payload["prompt_id"] == result.prompt_id


@pytest.mark.asyncio
async def test_confirm_no_logs_denied_with_prompt_id(tmp_path):
    audit = AuditLogger(db_path=tmp_path / "audit.db")
    config = _write_toml(tmp_path, {"mail.send": "confirm"})
    gate = PermissionGate(config_path=config, audit=audit)

    result = await gate.check("mail.send", {}, channel="voice_local")
    await gate.confirm(result.prompt_id, "no")

    denied = audit.query(event_type=SecurityEventType.PERMISSION_DENIED.value)
    assert len(denied) == 1
    payload = json.loads(denied[0].content_preview)
    assert payload["prompt_id"] == result.prompt_id


@pytest.mark.asyncio
async def test_audit_chain_intact_after_permission_events(tmp_path):
    """Hash-Chain bleibt verifizierbar nach Permission-Eintraegen."""
    audit = AuditLogger(db_path=tmp_path / "audit.db")
    config = _write_toml(tmp_path, {"calendar.upcoming": "free", "mail.send": "confirm"})
    gate = PermissionGate(config_path=config, audit=audit)

    await gate.check("calendar.upcoming", {}, channel="voice_local")
    r2 = await gate.check("mail.send", {}, channel="voice_local")
    await gate.confirm(r2.prompt_id, "yes")

    ok, broken = audit.verify_chain()
    assert ok is True, f"Chain broken at row {broken}"
    assert audit.count() >= 3
