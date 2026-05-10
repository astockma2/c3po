"""Tests for the PermissionGate-hook in ToolExecutor (Stage 3, Task 2 + 3).

Task 2 deckt: ``ToolCall.channel``-Feld + ``ToolExecutor.permission_gate``-ctor-Param.
Task 3 deckt: Hook-Aufruf, Granted/Denied-Pfad, Pending-Resolve.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from openjarvis.core.types import ToolCall, ToolResult
from openjarvis.security.types import PermissionResult
from openjarvis.tools._stubs import BaseTool, ToolExecutor, ToolSpec


class _EchoTool(BaseTool):
    tool_id = "echo"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(name="echo", description="Echoes back.")

    def execute(self, **params: Any) -> ToolResult:
        return ToolResult(tool_name="echo", content="ok", success=True)


# ---------------------------------------------------------------------------
# Task 2 — ToolCall.channel + ToolExecutor.permission_gate-Param
# ---------------------------------------------------------------------------


class TestToolCallChannelField:
    def test_default_is_empty_string(self):
        tc = ToolCall(id="1", name="echo", arguments="{}")
        assert tc.channel == ""

    def test_channel_can_be_set(self):
        tc = ToolCall(id="1", name="echo", arguments="{}", channel="voice_local")
        assert tc.channel == "voice_local"


class TestToolExecutorPermissionGateParam:
    def test_accepts_permission_gate_kwarg(self):
        gate = MagicMock()
        ex = ToolExecutor([_EchoTool()], permission_gate=gate)
        assert ex._permission_gate is gate

    def test_default_permission_gate_is_none(self):
        ex = ToolExecutor([_EchoTool()])
        assert ex._permission_gate is None

    def test_accepts_permission_loop_kwarg(self):
        gate = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            ex = ToolExecutor(
                [_EchoTool()],
                permission_gate=gate,
                permission_loop=loop,
            )
            assert ex._permission_loop is loop
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Task 3 — Hook in execute()
# ---------------------------------------------------------------------------


def _make_async_mock_returning(result: PermissionResult) -> MagicMock:
    """Build a MagicMock whose ``check()`` returns ``result`` from an async coroutine."""
    gate = MagicMock()

    async def _check(*args, **kwargs):
        return result

    gate.check = MagicMock(side_effect=_check)
    return gate


class TestPermissionHookInExecute:
    def test_skips_gate_when_none(self):
        """Ohne permission_gate laeuft das Tool wie bisher."""
        ex = ToolExecutor([_EchoTool()])
        result = ex.execute(ToolCall(id="1", name="echo", arguments="{}"))
        assert result.success is True
        assert result.content == "ok"

    def test_calls_gate_check_with_name_args_channel(self):
        """Der Hook ruft gate.check(tool_name, args, channel=...)."""
        gate = _make_async_mock_returning(PermissionResult.granted())
        ex = ToolExecutor([_EchoTool()], permission_gate=gate)
        tc = ToolCall(
            id="1",
            name="echo",
            arguments='{"text": "hi"}',
            channel="voice_local",
        )
        result = ex.execute(tc)
        assert result.success is True
        gate.check.assert_called_once()
        # check(tool_name, args, *, channel=...)
        args_pos, kwargs = gate.check.call_args
        assert args_pos[0] == "echo"
        assert args_pos[1] == {"text": "hi"}
        assert kwargs.get("channel") == "voice_local"

    def test_blocks_when_gate_denies(self):
        """Wenn der Gate denied liefert, wird das Tool NICHT ausgefuehrt."""
        gate = _make_async_mock_returning(PermissionResult.denied("explicit"))

        class _SpyTool(BaseTool):
            tool_id = "spy"
            executed = False

            @property
            def spec(self) -> ToolSpec:
                return ToolSpec(name="spy", description="spy tool")

            def execute(self, **params: Any) -> ToolResult:
                _SpyTool.executed = True
                return ToolResult(tool_name="spy", content="ran", success=True)

        spy = _SpyTool()
        ex = ToolExecutor([spy], permission_gate=gate)
        result = ex.execute(ToolCall(id="1", name="spy", arguments="{}"))
        assert result.success is False
        assert "permission" in result.content.lower()
        assert "explicit" in result.content
        assert _SpyTool.executed is False

    def test_pending_confirm_resolved_to_true_runs_tool(self):
        """needs_confirm + Future resolves to True -> Tool laeuft."""
        prompt_id = "pid-yes"

        async def _confirm_after_check(*args, **kwargs):
            # Simuliere: gate.check liefert needs_confirm und legt Future ab.
            # Wir setzen das Future auf True bevor wir zurueckkehren -
            # damit der Adapter es sofort beim Warten findet.
            fut = asyncio.get_running_loop().create_future()
            fut.set_result(True)
            gate._pending[prompt_id] = (fut, "confirm")
            return PermissionResult.needs_confirm(prompt_id)

        gate = MagicMock()
        gate._pending = {}
        gate.check = MagicMock(side_effect=_confirm_after_check)

        ex = ToolExecutor([_EchoTool()], permission_gate=gate)
        result = ex.execute(ToolCall(id="1", name="echo", arguments="{}"))
        assert result.success is True
        assert result.content == "ok"

    def test_pending_confirm_resolved_to_false_blocks_tool(self):
        """needs_confirm + Future resolves to False -> Tool laeuft NICHT."""
        prompt_id = "pid-no"

        async def _confirm_after_check(*args, **kwargs):
            fut = asyncio.get_running_loop().create_future()
            fut.set_result(False)
            gate._pending[prompt_id] = (fut, "confirm")
            return PermissionResult.needs_confirm(prompt_id)

        gate = MagicMock()
        gate._pending = {}
        gate.check = MagicMock(side_effect=_confirm_after_check)

        class _SpyTool(BaseTool):
            tool_id = "spy"
            executed = False

            @property
            def spec(self) -> ToolSpec:
                return ToolSpec(name="spy", description="spy tool")

            def execute(self, **params: Any) -> ToolResult:
                _SpyTool.executed = True
                return ToolResult(tool_name="spy", content="ran", success=True)

        ex = ToolExecutor([_SpyTool()], permission_gate=gate)
        result = ex.execute(ToolCall(id="1", name="spy", arguments="{}"))
        assert result.success is False
        assert "denied" in result.content.lower()
        assert _SpyTool.executed is False

    def test_pending_pin_resolved_to_true_runs_tool(self):
        """needs_pin + Future True -> Tool laeuft (admin-Pfad)."""
        prompt_id = "pid-pin-ok"

        async def _check(*args, **kwargs):
            fut = asyncio.get_running_loop().create_future()
            fut.set_result(True)
            gate._pending[prompt_id] = (fut, "pin")
            return PermissionResult.needs_pin(prompt_id)

        gate = MagicMock()
        gate._pending = {}
        gate.check = MagicMock(side_effect=_check)

        ex = ToolExecutor([_EchoTool()], permission_gate=gate)
        result = ex.execute(ToolCall(id="1", name="echo", arguments="{}"))
        assert result.success is True

    def test_unknown_channel_default_passes_unknown_string(self):
        """Bei leerem channel passt der Adapter 'unknown' an gate.check weiter."""
        gate = _make_async_mock_returning(PermissionResult.granted())
        ex = ToolExecutor([_EchoTool()], permission_gate=gate)
        ex.execute(ToolCall(id="1", name="echo", arguments="{}"))  # channel=""
        _, kwargs = gate.check.call_args
        assert kwargs.get("channel") == "unknown"


# ---------------------------------------------------------------------------
# Adapter mit explizit injiziertem Loop (run_coroutine_threadsafe-Pfad)
# ---------------------------------------------------------------------------


class TestPermissionGateWithExplicitLoop:
    def test_uses_provided_loop_for_check(self):
        """Wenn permission_loop gesetzt ist, laeuft der Check in diesem Loop."""
        gate = _make_async_mock_returning(PermissionResult.granted())
        loop = asyncio.new_event_loop()

        # Hilfs-Thread, der den Loop am Leben haelt
        import threading

        def _run_loop() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=_run_loop, daemon=True)
        t.start()
        try:
            ex = ToolExecutor(
                [_EchoTool()],
                permission_gate=gate,
                permission_loop=loop,
            )
            result = ex.execute(ToolCall(id="1", name="echo", arguments="{}"))
            assert result.success is True
            assert gate.check.call_count == 1
        finally:
            loop.call_soon_threadsafe(loop.stop)
            t.join(timeout=2)
            loop.close()
