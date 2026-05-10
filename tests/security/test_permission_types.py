"""Tests fuer PermissionLevel + PermissionResult."""
from __future__ import annotations

import pytest


def test_permission_level_values():
    from openjarvis.security.types import PermissionLevel

    assert PermissionLevel.FREE.value == "free"
    assert PermissionLevel.CONFIRM.value == "confirm"
    assert PermissionLevel.ADMIN.value == "admin"
    assert PermissionLevel.DENIED.value == "denied"


def test_permission_result_granted():
    from openjarvis.security.types import PermissionResult

    r = PermissionResult.granted()
    assert r.state == "granted"
    assert r.is_granted is True
    assert r.is_pending is False
    assert r.prompt_id == ""
    assert r.reason == ""


def test_permission_result_denied():
    from openjarvis.security.types import PermissionResult

    r = PermissionResult.denied("not configured")
    assert r.state == "denied"
    assert r.is_granted is False
    assert r.is_pending is False
    assert r.reason == "not configured"


def test_permission_result_needs_confirm():
    from openjarvis.security.types import PermissionResult

    r = PermissionResult.needs_confirm("abc-123")
    assert r.state == "needs_confirm"
    assert r.is_granted is False
    assert r.is_pending is True
    assert r.prompt_id == "abc-123"


def test_permission_result_needs_pin():
    from openjarvis.security.types import PermissionResult

    r = PermissionResult.needs_pin("xyz-789")
    assert r.state == "needs_pin"
    assert r.is_granted is False
    assert r.is_pending is True
    assert r.prompt_id == "xyz-789"


def test_permission_result_immutable():
    """Frozen dataclass - keine Modifikation nach Konstruktion."""
    from openjarvis.security.types import PermissionResult

    r = PermissionResult.granted()
    with pytest.raises((AttributeError, Exception)):
        r.state = "denied"  # type: ignore[misc]
