"""Tests fuer PermissionGate (Stage 2)."""
from __future__ import annotations

from pathlib import Path

import pytest


def _write_toml(tmp_path: Path, tools: dict[str, str]) -> Path:
    """Schreibt eine permissions.toml mit [tools]-Section."""
    lines = ["[tools]"]
    for name, level in tools.items():
        lines.append(f'"{name}" = "{level}"')
    p = tmp_path / "permissions.toml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_check_free_returns_granted(tmp_path):
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {"calendar.upcoming": "free"})
    gate = PermissionGate(config_path=config)
    result = await gate.check("calendar.upcoming", {}, channel="voice_local")
    assert result.is_granted
    assert result.state == "granted"


@pytest.mark.asyncio
async def test_check_unknown_tool_default_denied(tmp_path):
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {})
    gate = PermissionGate(config_path=config)
    result = await gate.check("calendar.upcoming", {}, channel="voice_local")
    assert not result.is_granted
    assert "not configured" in result.reason


@pytest.mark.asyncio
async def test_check_explicit_denied(tmp_path):
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {"shell.exec": "denied"})
    gate = PermissionGate(config_path=config)
    result = await gate.check(
        "shell.exec", {"cmd": "rm -rf /"}, channel="voice_local"
    )
    assert not result.is_granted
    assert "denied" in result.reason.lower()


def test_check_invalid_level_in_toml_raises(tmp_path):
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {"foo": "yolo"})
    with pytest.raises(ValueError, match="yolo"):
        PermissionGate(config_path=config)


def test_check_missing_config_raises(tmp_path):
    from openjarvis.security.permission_gate import PermissionGate

    with pytest.raises(FileNotFoundError):
        PermissionGate(config_path=tmp_path / "missing.toml")


def test_check_loads_empty_tools_section(tmp_path):
    from openjarvis.security.permission_gate import PermissionGate

    config = tmp_path / "empty.toml"
    config.write_text("[tools]\n", encoding="utf-8")
    gate = PermissionGate(config_path=config)
    assert gate._tools == {}


@pytest.mark.asyncio
async def test_check_confirm_returns_pending_with_uuid(tmp_path):
    """CONFIRM: check() returnt needs_confirm mit UUID, _pending hat Eintrag."""
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {"mail.send": "confirm"})
    gate = PermissionGate(config_path=config)
    result = await gate.check("mail.send", {"to": "x@y"}, channel="voice_local")
    assert result.state == "needs_confirm"
    assert len(result.prompt_id) == 36  # UUID4
    assert result.prompt_id in gate._pending


@pytest.mark.asyncio
async def test_check_confirm_publishes_event(tmp_path):
    """CONFIRM: PERMISSION_CONFIRM_REQUESTED wird auf den Bus publiziert."""
    from openjarvis.core.events import EventBus, EventType
    from openjarvis.security.permission_gate import PermissionGate

    bus = EventBus(record_history=True)
    received = []
    bus.subscribe(EventType.PERMISSION_CONFIRM_REQUESTED, lambda e: received.append(e))

    config = _write_toml(tmp_path, {"mail.send": "confirm"})
    gate = PermissionGate(config_path=config, bus=bus)
    result = await gate.check("mail.send", {"to": "x@y"}, channel="voice_local")

    assert len(received) == 1
    payload = received[0].data
    assert payload["prompt_id"] == result.prompt_id
    assert payload["tool"] == "mail.send"
    assert payload["args"] == {"to": "x@y"}
    assert payload["channel"] == "voice_local"


@pytest.mark.asyncio
async def test_confirm_yes_resolves_future_to_true(tmp_path):
    """confirm("yes") setzt das Future auf True."""
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {"mail.send": "confirm"})
    gate = PermissionGate(config_path=config)
    result = await gate.check("mail.send", {}, channel="voice_local")
    pid = result.prompt_id

    granted = await gate.confirm(pid, "yes")
    assert granted is True
    assert pid not in gate._pending


@pytest.mark.asyncio
async def test_confirm_no_resolves_future_to_false(tmp_path):
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {"mail.send": "confirm"})
    gate = PermissionGate(config_path=config)
    result = await gate.check("mail.send", {}, channel="voice_local")
    granted = await gate.confirm(result.prompt_id, "no")
    assert granted is False


@pytest.mark.asyncio
async def test_confirm_unknown_prompt_id_returns_false(tmp_path):
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {"mail.send": "confirm"})
    gate = PermissionGate(config_path=config)
    granted = await gate.confirm(
        "00000000-0000-0000-0000-000000000000", "yes"
    )
    assert granted is False


@pytest.mark.asyncio
async def test_concurrent_check_then_confirm_flow(tmp_path):
    """Producer/Consumer-Flow: check() in Task A, confirm() in Task B,
    Task A liest das Future."""
    import asyncio
    from openjarvis.security.permission_gate import PermissionGate

    config = _write_toml(tmp_path, {"mail.send": "confirm"})
    gate = PermissionGate(config_path=config)

    result = await gate.check("mail.send", {}, channel="voice_local")
    pid = result.prompt_id

    async def respond_after_delay():
        await asyncio.sleep(0.02)
        await gate.confirm(pid, "yes")

    fut = gate._pending[pid]
    asyncio.create_task(respond_after_delay())
    granted = await fut
    assert granted is True
