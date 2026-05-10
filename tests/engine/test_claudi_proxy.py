"""Tests fuer ClaudiProxyEngine — Engine-Backend gegen gemi.c3po42.de."""
from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from openjarvis.core.types import Message, Role
from openjarvis.engine._base import EngineConnectionError
from openjarvis.engine.claudi_proxy import ClaudiProxyEngine


_BASE_URL = "https://gemi.c3po42.de"
_HEALTH_URL = f"{_BASE_URL}/api/health"
_CHAT_URL = f"{_BASE_URL}/api/chat/sync"


class TestClaudiProxyEngineHealth:
    @respx.mock
    def test_health_ok(self):
        respx.get(_HEALTH_URL).mock(
            return_value=Response(200, json={"status": "online"})
        )
        eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
        try:
            assert eng.health() is True
        finally:
            eng.close()

    @respx.mock
    def test_health_failure(self):
        respx.get(_HEALTH_URL).mock(side_effect=httpx.ConnectError("nope"))
        eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
        try:
            assert eng.health() is False
        finally:
            eng.close()


class TestClaudiProxyEngineGenerate:
    @respx.mock
    def test_generate_returns_content_and_usage(self):
        route = respx.post(_CHAT_URL).mock(
            return_value=Response(
                200,
                json={
                    "response": "Hallo Andre.",
                    "model": "claude-opus-4-7",
                    "provider": "Claude CLI",
                },
            )
        )
        eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
        try:
            result = eng.generate(
                [Message(role=Role.USER, content="Sag Hallo.")],
                model="claude-haiku-4-5",
            )
        finally:
            eng.close()
        assert result["content"] == "Hallo Andre."
        assert "usage" in result
        # Usage ist jetzt geschaetzt — Werte sollten > 0 sein
        assert result["usage"]["prompt_tokens"] > 0
        assert result["usage"]["completion_tokens"] > 0
        assert result["usage"]["total_tokens"] == (
            result["usage"]["prompt_tokens"] + result["usage"]["completion_tokens"]
        )
        # Payload pruefen
        import json as _json
        sent = _json.loads(route.calls.last.request.content)
        assert sent["messages"][0]["role"] == "user"
        assert sent["messages"][0]["content"] == "Sag Hallo."

    @respx.mock
    def test_generate_passes_system_message(self):
        route = respx.post(_CHAT_URL).mock(
            return_value=Response(
                200,
                json={"response": "ok", "model": "x", "provider": "x"},
            )
        )
        eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
        try:
            eng.generate(
                [
                    Message(role=Role.SYSTEM, content="You are helpful."),
                    Message(role=Role.USER, content="Hi."),
                ],
                model="x",
            )
        finally:
            eng.close()
        import json as _json
        sent = _json.loads(route.calls.last.request.content)
        msgs = sent["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    @respx.mock
    def test_generate_handles_http_error(self):
        respx.post(_CHAT_URL).mock(
            return_value=Response(500, text="Internal Server Error boom")
        )
        eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
        try:
            with pytest.raises(RuntimeError) as exc:
                eng.generate([Message(role=Role.USER, content="x")], model="x")
        finally:
            eng.close()
        assert "500" in str(exc.value)

    @respx.mock
    def test_generate_handles_connect_error(self):
        respx.post(_CHAT_URL).mock(side_effect=httpx.ConnectError("nope"))
        eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
        try:
            with pytest.raises(EngineConnectionError):
                eng.generate([Message(role=Role.USER, content="x")], model="x")
        finally:
            eng.close()


class TestClaudiProxyEngineListModels:
    def test_list_models(self):
        eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
        try:
            models = eng.list_models()
        finally:
            eng.close()
        assert "claude-opus-4-7" in models


class TestClaudiProxyEngineClient:
    def test_client_has_bearer_header(self):
        eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
        try:
            assert eng._client.headers["Authorization"] == "Bearer gemi2026"
            assert eng._client.headers["Content-Type"] == "application/json"
        finally:
            eng.close()

    def test_client_uses_env_token(self, monkeypatch):
        monkeypatch.setenv("CLAUDI_PROXY_TOKEN", "env-token-xyz")
        eng = ClaudiProxyEngine(base_url=_BASE_URL)
        try:
            assert eng._client.headers["Authorization"] == "Bearer env-token-xyz"
        finally:
            eng.close()


@pytest.mark.asyncio
class TestClaudiProxyEngineStream:
    async def test_stream_yields_full_text_in_one_chunk(self):
        async with respx.mock:
            respx.post(_CHAT_URL).mock(
                return_value=Response(
                    200,
                    json={"response": "Hallo.", "model": "x", "provider": "x"},
                )
            )
            eng = ClaudiProxyEngine(base_url=_BASE_URL, token="gemi2026")
            try:
                chunks = []
                async for tok in eng.stream(
                    [Message(role=Role.USER, content="x")], model="x"
                ):
                    chunks.append(tok)
            finally:
                eng.close()
        assert chunks == ["Hallo."]


class TestClaudiProxyEngineC3poCustomFlag:
    """Stage 7: Engine ist als C3PO-Custom markiert (umgeht Stanford-Cloud-Routing)."""

    def test_is_c3po_custom_true(self):
        eng = ClaudiProxyEngine()
        try:
            assert eng.is_c3po_custom is True
        finally:
            eng.close()

    def test_base_class_default_is_false(self):
        """Stanford-Engines wie OllamaEngine duerfen nicht versehentlich
        als c3po-custom markiert werden — Default auf der ABC ist False."""
        from openjarvis.engine._stubs import InferenceEngine

        assert InferenceEngine.is_c3po_custom is False
