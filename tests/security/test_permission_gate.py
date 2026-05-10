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
