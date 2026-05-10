"""Test: Stage 3 Auto-Import laedt alle 39 Tools in die ToolRegistry.

Konftest leert ALLE Registries vor jedem Test. Die @ToolRegistry.register()-
Decorator-Aufrufe passieren beim Modul-Import — ein erneuter `import` (ohne
reload) tut nichts, weil das Modul schon im sys.modules cache liegt.

Loesung: per Test mit ``importlib.reload`` die c3po-Sub-Module zurueck-
laden, damit die Decorators erneut greifen und die Registry sich fuellt.
"""

from __future__ import annotations

import importlib

import pytest

from openjarvis.core.registry import ToolRegistry

_C3PO_SUBMODULES = (
    "openjarvis.tools.c3po.time_tools",
    "openjarvis.tools.c3po.windows_tools",
    "openjarvis.tools.c3po.mail_tools",
    "openjarvis.tools.c3po.calendar_tools",
    "openjarvis.tools.c3po.browser_tools",
    "openjarvis.tools.c3po.messaging_tools",
    "openjarvis.tools.c3po.admin_tools",
)


@pytest.fixture
def reload_c3po_tools():
    """Fuehrt alle c3po-Tool-Module frisch aus, damit die @register()-
    Decorators in die (von conftest geleerte) ToolRegistry schreiben.

    Vorgehen: c3po-Module aus sys.modules entfernen, dann ToolRegistry
    leeren, dann importieren. Nach dem Test stellen wir den vorherigen
    sys.modules-Stand wieder her, damit nachfolgende Tests in anderen
    Modulen weiter mit denselben Modul-Objekten arbeiten (sonst greifen
    deren ``patch('...time_tools._now')`` ins Leere).
    """
    import sys

    saved = {
        name: sys.modules.pop(name, None)
        for name in (*_C3PO_SUBMODULES, "openjarvis.tools.c3po")
    }
    ToolRegistry.clear()
    try:
        importlib.import_module("openjarvis.tools.c3po")
        yield
    finally:
        # alte Modul-Objekte wieder einsetzen
        for name, mod in saved.items():
            if mod is not None:
                sys.modules[name] = mod
            else:
                sys.modules.pop(name, None)


# Erwartete Tool-Liste — wenn diese Liste sich aendert, ist Stage 3 nicht mehr "39".
_EXPECTED_TOOLS = [
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


def test_total_count_is_39():
    assert len(_EXPECTED_TOOLS) == 39


def test_auto_import_registers_all_tools(reload_c3po_tools):
    keys = set(ToolRegistry.keys())
    missing = [t for t in _EXPECTED_TOOLS if t not in keys]
    assert not missing, f"Fehlende Tool-Registrierungen: {missing}"


def test_each_tool_instance_has_correct_spec_name(reload_c3po_tools):
    for tool_name in _EXPECTED_TOOLS:
        cls = ToolRegistry.get(tool_name)
        instance = cls()
        assert instance.spec.name == tool_name, (
            f"{cls.__name__} hat spec.name='{instance.spec.name}', "
            f"erwartet '{tool_name}'"
        )


def test_categories_are_set(reload_c3po_tools):
    for tool_name in _EXPECTED_TOOLS:
        cls = ToolRegistry.get(tool_name)
        spec = cls().spec
        assert spec.category, f"{tool_name} hat keine category"
