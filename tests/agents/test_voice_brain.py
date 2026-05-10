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


from unittest.mock import MagicMock, patch

from openjarvis.agents.voice_brain import build_voice_brain
from openjarvis.channels._stubs import ChannelMessage


class TestBuildVoiceBrain:
    def test_returns_callable(self, reload_c3po_tools):
        with patch("openjarvis.agents.voice_brain._build_agent", return_value=MagicMock()):
            handler = build_voice_brain(model="claude-haiku-4-5")
        assert callable(handler)

    def test_handler_calls_agent_run_with_content(self, reload_c3po_tools):
        fake_agent = MagicMock()
        fake_result = MagicMock()
        fake_result.content = "Es ist 14:23."
        fake_agent.run.return_value = fake_result
        with patch(
            "openjarvis.agents.voice_brain._build_agent",
            return_value=fake_agent,
        ):
            handler = build_voice_brain(model="claude-haiku-4-5")
            msg = ChannelMessage(
                channel="voice_local",
                sender="local_mic",
                content="Wie spaet ist es?",
            )
            response = handler(msg)
        assert response == "Es ist 14:23."
        fake_agent.run.assert_called_once()
        # input ist erstes positional ODER kwarg
        call = fake_agent.run.call_args
        passed_input = call.kwargs.get("input") or (call.args[0] if call.args else "")
        assert passed_input == "Wie spaet ist es?"

    def test_handler_returns_none_on_empty_content(self, reload_c3po_tools):
        with patch("openjarvis.agents.voice_brain._build_agent", return_value=MagicMock()):
            handler = build_voice_brain(model="claude-haiku-4-5")
            msg = ChannelMessage(channel="voice_local", sender="x", content="")
        assert handler(msg) is None

    def test_handler_returns_none_on_whitespace_content(self, reload_c3po_tools):
        with patch("openjarvis.agents.voice_brain._build_agent", return_value=MagicMock()):
            handler = build_voice_brain(model="claude-haiku-4-5")
            msg = ChannelMessage(channel="voice_local", sender="x", content="   \n\t")
        assert handler(msg) is None

    def test_handler_returns_apology_on_exception(self, reload_c3po_tools):
        fake_agent = MagicMock()
        fake_agent.run.side_effect = RuntimeError("anthropic timeout")
        with patch(
            "openjarvis.agents.voice_brain._build_agent",
            return_value=fake_agent,
        ):
            handler = build_voice_brain(model="claude-haiku-4-5")
            msg = ChannelMessage(
                channel="voice_local", sender="x", content="Lies meine Mails.",
            )
            response = handler(msg)
        assert response is not None
        assert "Entschuldigung" in response or "fehler" in response.lower()

    def test_handler_returns_none_if_agent_returned_empty(self, reload_c3po_tools):
        fake_agent = MagicMock()
        fake_result = MagicMock()
        fake_result.content = ""
        fake_agent.run.return_value = fake_result
        with patch(
            "openjarvis.agents.voice_brain._build_agent",
            return_value=fake_agent,
        ):
            handler = build_voice_brain(model="claude-haiku-4-5")
            msg = ChannelMessage(channel="voice_local", sender="x", content="Hi")
            response = handler(msg)
        assert response is None

    def test_build_agent_uses_claudi_proxy_engine(self, reload_c3po_tools):
        """_build_agent baut intern eine ClaudiProxyEngine, kein anderes Backend."""
        # Wir patchen ToolExecutor und NativeReActAgent damit der Test schnell und
        # frei von HTTP-Calls bleibt. ClaudiProxyEngine wird instanziiert -- aber
        # ohne Netzwerk-Call, weil wir keine generate()/health() aufrufen.
        from openjarvis.agents.voice_brain import _build_agent

        with patch(
            "openjarvis.agents.voice_brain.NativeReActAgent"
        ) as MockAgent, patch(
            "openjarvis.agents.voice_brain.ToolExecutor"
        ) as MockExec, patch(
            "openjarvis.agents.voice_brain.ClaudiProxyEngine"
        ) as MockEng:
            MockAgent.return_value = MagicMock()
            agent = _build_agent(
                model="claude-haiku-4-5",
                tools=[],
                permission_gate=None,
                permission_loop=None,
                max_turns=4,
            )
        MockEng.assert_called_once()
        MockAgent.assert_called_once()
        # _executor ueberschrieben mit unserer Permission-Gate-faehigen Version
        MockExec.assert_called_once()

    def test_build_agent_passes_permission_gate_to_executor(self, reload_c3po_tools):
        from openjarvis.agents.voice_brain import _build_agent
        fake_gate = MagicMock()
        fake_loop = MagicMock()
        with patch(
            "openjarvis.agents.voice_brain.NativeReActAgent"
        ), patch(
            "openjarvis.agents.voice_brain.ToolExecutor"
        ) as MockExec, patch(
            "openjarvis.agents.voice_brain.ClaudiProxyEngine"
        ):
            _build_agent(
                model="claude-haiku-4-5",
                tools=[],
                permission_gate=fake_gate,
                permission_loop=fake_loop,
                max_turns=4,
            )
        kwargs = MockExec.call_args.kwargs
        assert kwargs.get("permission_gate") is fake_gate
        assert kwargs.get("permission_loop") is fake_loop

    def test_build_voice_brain_with_defaults_selects_tools(self, reload_c3po_tools):
        """build_voice_brain ruft select_voice_tools wenn tools=None."""
        with patch(
            "openjarvis.agents.voice_brain._build_agent",
            return_value=MagicMock(),
        ) as MockBuild:
            build_voice_brain(model="x")
        kwargs = MockBuild.call_args.kwargs
        # tools=... muss eine Liste sein, NICHT None
        assert isinstance(kwargs.get("tools"), list)
        assert len(kwargs["tools"]) > 0
