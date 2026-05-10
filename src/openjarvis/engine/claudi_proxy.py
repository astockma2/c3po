"""ClaudiProxyEngine — calls Claudi-API auf VPS (gemi.c3po42.de).

Nutzt die OAuth-basierte Claude-Code-CLI auf dem VPS statt eines direkten
Anthropic-API-Keys. Server ignoriert den Modell-Hint und nutzt immer
claude-opus-4-7. Latenz ~5-15 Sek pro Call.

Endpoint: POST {base_url}/api/chat/sync
Body: {"messages": [{"role": "user", "content": "..."}, ...], "model": "..."}
Response: {"response": "...", "model": "...", "provider": "..."}
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List, Sequence

import httpx

from openjarvis.core.registry import EngineRegistry
from openjarvis.core.types import Message
from openjarvis.engine._stubs import InferenceEngine

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://gemi.c3po42.de"
_DEFAULT_TOKEN = "gemi2026"
_HEALTH_TIMEOUT = 5.0
_GENERATE_TIMEOUT = 60.0


@EngineRegistry.register("claudi_proxy")
class ClaudiProxyEngine(InferenceEngine):
    """Engine die gegen den Claudi-Proxy auf gemi.c3po42.de calls."""

    engine_id = "claudi_proxy"
    is_cloud = True

    def __init__(
        self,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        token: str = _DEFAULT_TOKEN,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """POST an /api/chat/sync, gibt {content, usage}-Dict zurueck."""
        payload = {
            "messages": [
                {"role": m.role.value, "content": m.content} for m in messages
            ],
            "model": model,
        }
        resp = httpx.post(
            f"{self._base_url}/api/chat/sync",
            json=payload,
            headers=self._headers(),
            timeout=_GENERATE_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("response", "")
        return {
            "content": content,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "model": data.get("model", model),
            "finish_reason": "stop",
        }

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Proxy hat kein echtes Streaming — wir yielden den ganzen Text einmal."""
        result = self.generate(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        yield result["content"]

    def list_models(self) -> List[str]:
        return ["claude-opus-4-7", "claude-haiku-4-5"]

    def health(self) -> bool:
        try:
            resp = httpx.get(
                f"{self._base_url}/api/health",
                headers=self._headers(),
                timeout=_HEALTH_TIMEOUT,
            )
            return resp.status_code == 200
        except Exception:
            logger.debug("ClaudiProxyEngine health-check failed", exc_info=True)
            return False


__all__ = ["ClaudiProxyEngine"]
