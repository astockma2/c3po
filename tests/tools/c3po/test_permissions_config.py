"""Verifikation: configs/c3po/permissions.toml + admin_whitelist.toml
deckt alle 39 Stage-3-Tools ab, und PermissionGate laedt ohne Fehler.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openjarvis.security.permission_gate import PermissionGate
from openjarvis.security.types import PermissionLevel

# Gleiche Liste wie in test_auto_import.py, hier duplizieren um zirkulaere
# Test-Abhaengigkeit zu vermeiden.
ALL_39_TOOLS = [
    # 3.1 Time + Hello (3)
    "time.now", "time.date", "hello.greet",
    # 3.2 Windows (6)
    "windows.open_app", "windows.close_app", "windows.kill_process",
    "windows.list_processes", "windows.lock_screen", "windows.notify",
    # 3.3 Mail (4)
    "mail.list_unread", "mail.read", "mail.search", "mail.send",
    # 3.4 Calendar (3)
    "calendar.upcoming", "calendar.list", "calendar.search",
    # 3.5 Browser (8)
    "browser.open_url", "browser.new_tab", "browser.list_tabs",
    "browser.close_tab", "browser.click", "browser.fill",
    "browser.screenshot", "browser.read_page",
    # 3.6 Messaging (5)
    "telegram.send", "whatsapp.send", "signal.send", "slack.send",
    "messaging.last_received",
    # 3.7 Admin (10)
    "admin.reboot", "admin.shutdown", "admin.cancel_shutdown",
    "admin.update_check", "admin.cleanup_temp", "admin.flush_dns",
    "admin.restart_service", "admin.list_services",
    "admin.kill_process_force", "admin.git_pull_repo",
]


CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs" / "c3po"


@pytest.fixture
def gate():
    return PermissionGate(
        config_path=CONFIG_DIR / "permissions.toml",
        admin_whitelist_path=CONFIG_DIR / "admin_whitelist.toml",
    )


def test_permissions_toml_loads_clean(gate):
    """PermissionGate akzeptiert die Datei ohne ValueError."""
    assert isinstance(gate._tools, dict)
    # Mindestens unsere 39 Eintraege
    assert len(gate._tools) >= 39


def test_every_tool_has_a_permission_entry(gate):
    """Jedes der 39 Stage-3-Tools hat einen Eintrag in permissions.toml."""
    configured = set(gate._tools.keys())
    missing = [t for t in ALL_39_TOOLS if t not in configured]
    assert not missing, f"Tools ohne permissions.toml-Eintrag: {missing}"


def test_admin_whitelist_matches_admin_level_tools(gate):
    """admin_whitelist.toml enthaelt genau die Tools mit level=admin."""
    admin_in_perms = {
        name for name, level in gate._tools.items()
        if level == PermissionLevel.ADMIN
    }
    whitelist = set(gate._admin_whitelist)
    # Alle admin-Tools muessen whitelisted sein
    not_whitelisted = admin_in_perms - whitelist
    assert not not_whitelisted, (
        f"admin-Tools NICHT in admin_whitelist.toml: {not_whitelisted}"
    )


def test_counts_match_18_11_10_0():
    """Permission-Matrix: 18 free / 11 confirm / 10 admin / 0 denied (39 total)."""
    gate = PermissionGate(
        config_path=CONFIG_DIR / "permissions.toml",
        admin_whitelist_path=CONFIG_DIR / "admin_whitelist.toml",
    )
    stage3 = {n: gate._tools[n] for n in ALL_39_TOOLS}
    by_level: dict[PermissionLevel, int] = {}
    for level in stage3.values():
        by_level[level] = by_level.get(level, 0) + 1
    assert by_level.get(PermissionLevel.FREE, 0) == 18
    assert by_level.get(PermissionLevel.CONFIRM, 0) == 11
    assert by_level.get(PermissionLevel.ADMIN, 0) == 10
    assert by_level.get(PermissionLevel.DENIED, 0) == 0
