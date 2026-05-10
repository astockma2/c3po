"""Tests fuer voice_brain.select_voice_tools."""
from __future__ import annotations

from openjarvis.agents.voice_brain import (
    DEFAULT_VOICE_TOOL_CATEGORIES,
    select_voice_tools,
)


class TestSelectVoiceTools:
    def test_default_excludes_admin(self, reload_c3po_tools):
        tools = select_voice_tools()
        names = {t.spec.name for t in tools}
        assert not any(n.startswith("admin.") for n in names), (
            f"admin-Tools sollten per Default ausgeschlossen sein, fand: "
            f"{[n for n in names if n.startswith('admin.')]}"
        )

    def test_default_includes_mail_calendar_time(self, reload_c3po_tools):
        tools = select_voice_tools()
        names = {t.spec.name for t in tools}
        assert "mail.list_unread" in names
        assert "calendar.upcoming" in names
        assert "time.now" in names

    def test_default_includes_hello_greet(self, reload_c3po_tools):
        """hello.greet hat category=social, ist per Default drin."""
        tools = select_voice_tools()
        names = {t.spec.name for t in tools}
        assert "hello.greet" in names

    def test_explicit_include_admin(self, reload_c3po_tools):
        tools = select_voice_tools(include_admin=True)
        names = {t.spec.name for t in tools}
        assert "admin.flush_dns" in names
        assert "admin.reboot" in names

    def test_categories_param_overrides_default(self, reload_c3po_tools):
        tools = select_voice_tools(categories={"time", "mail"})
        names = {t.spec.name for t in tools}
        assert "time.now" in names
        assert "mail.list_unread" in names
        assert "calendar.upcoming" not in names
        assert "browser.open_url" not in names
        assert "hello.greet" not in names

    def test_categories_param_does_not_include_admin_by_default(self, reload_c3po_tools):
        """Wenn categories={'admin'} explizit, dann ok. Aber include_admin steuert
        unabhaengig — wenn jemand explizit categories={'admin'} setzt, ist das OK."""
        tools = select_voice_tools(categories={"admin"})
        names = {t.spec.name for t in tools}
        # Wenn categories explizit admin enthaelt, kriegen wir admin-Tools
        assert any(n.startswith("admin.") for n in names)

    def test_default_categories_contains_expected(self):
        """DEFAULT_VOICE_TOOL_CATEGORIES ist explizit konfigurierbar."""
        assert "mail" in DEFAULT_VOICE_TOOL_CATEGORIES
        assert "calendar" in DEFAULT_VOICE_TOOL_CATEGORIES
        assert "time" in DEFAULT_VOICE_TOOL_CATEGORIES
        assert "social" in DEFAULT_VOICE_TOOL_CATEGORIES
        assert "windows" in DEFAULT_VOICE_TOOL_CATEGORIES
        assert "browser" in DEFAULT_VOICE_TOOL_CATEGORIES
        assert "messaging" in DEFAULT_VOICE_TOOL_CATEGORIES
        assert "admin" not in DEFAULT_VOICE_TOOL_CATEGORIES

    def test_returns_basetool_instances(self, reload_c3po_tools):
        from openjarvis.tools._stubs import BaseTool
        tools = select_voice_tools(categories={"time"})
        assert len(tools) > 0
        for t in tools:
            assert isinstance(t, BaseTool)
