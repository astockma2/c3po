"""Tests fuer ClaudiProxyEngine — Engine-Backend gegen gemi.c3po42.de."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from openjarvis.core.types import Message, Role
from openjarvis.engine.claudi_proxy import ClaudiProxyEngine


class TestClaudiProxyEngineHealth:
    def test_health_ok(self):
        eng = ClaudiProxyEngine(base_url="https://gemi.c3po42.de", token="gemi2026")
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"status": "online"}
        with patch("httpx.get", return_value=fake_resp) as g:
            assert eng.health() is True
        call = g.call_args
        assert call.kwargs["headers"]["Authorization"] == "Bearer gemi2026"

    def test_health_failure(self):
        eng = ClaudiProxyEngine(base_url="https://gemi.c3po42.de", token="gemi2026")
        with patch("httpx.get", side_effect=httpx.ConnectError("nope")):
            assert eng.health() is False


class TestClaudiProxyEngineGenerate:
    def test_generate_returns_content_and_usage(self):
        eng = ClaudiProxyEngine(base_url="https://gemi.c3po42.de", token="gemi2026")
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {
            "response": "Hallo Andre.",
            "model": "claude-opus-4-7",
            "provider": "Claude CLI",
        }
        with patch("httpx.post", return_value=fake_resp) as p:
            result = eng.generate(
                [Message(role=Role.USER, content="Sag Hallo.")],
                model="claude-haiku-4-5",
            )
        assert result["content"] == "Hallo Andre."
        assert "usage" in result
        payload = p.call_args.kwargs["json"]
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "Sag Hallo."

    def test_generate_passes_system_message(self):
        eng = ClaudiProxyEngine(base_url="https://gemi.c3po42.de", token="gemi2026")
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"response": "ok", "model": "x", "provider": "x"}
        fake_resp.raise_for_status.return_value = None
        with patch("httpx.post", return_value=fake_resp) as p:
            eng.generate(
                [
                    Message(role=Role.SYSTEM, content="You are helpful."),
                    Message(role=Role.USER, content="Hi."),
                ],
                model="x",
            )
        msgs = p.call_args.kwargs["json"]["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_generate_handles_http_error(self):
        eng = ClaudiProxyEngine(base_url="https://gemi.c3po42.de", token="gemi2026")
        fake_resp = MagicMock()
        fake_resp.status_code = 500
        fake_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=MagicMock(), response=fake_resp,
        )
        with patch("httpx.post", return_value=fake_resp):
            with pytest.raises(Exception) as exc:
                eng.generate([Message(role=Role.USER, content="x")], model="x")
        assert "boom" in str(exc.value) or "500" in str(exc.value)


class TestClaudiProxyEngineListModels:
    def test_list_models(self):
        eng = ClaudiProxyEngine(base_url="https://gemi.c3po42.de", token="gemi2026")
        models = eng.list_models()
        assert "claude-opus-4-7" in models


@pytest.mark.asyncio
class TestClaudiProxyEngineStream:
    async def test_stream_yields_full_text_in_one_chunk(self):
        eng = ClaudiProxyEngine(base_url="https://gemi.c3po42.de", token="gemi2026")
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"response": "Hallo.", "model": "x", "provider": "x"}
        fake_resp.raise_for_status.return_value = None
        chunks = []
        with patch("httpx.post", return_value=fake_resp):
            async for tok in eng.stream(
                [Message(role=Role.USER, content="x")], model="x"
            ):
                chunks.append(tok)
        assert chunks == ["Hallo."]
