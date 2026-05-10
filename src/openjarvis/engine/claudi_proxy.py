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
import os
from collections.abc import AsyncIterator, Sequence
from typing import Any, Dict, List

import httpx

from openjarvis.core.registry import EngineRegistry
from openjarvis.core.types import Message
from openjarvis.engine._base import (
    EngineConnectionError,
    InferenceEngine,
    estimate_prompt_tokens,
    messages_to_dicts,
)

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
    # Stage 7: bypass das Stanford-Cloud-Routing (stream_cloud/stream_local),
    # der Proxy hat OAuth statt API-Key und kann selbst streamen.
    is_c3po_custom = True

    def __init__(
        self,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        token: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token or os.environ.get("CLAUDI_PROXY_TOKEN", _DEFAULT_TOKEN)
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=_GENERATE_TIMEOUT,
        )

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
            "messages": messages_to_dicts(messages),
            "model": model,
        }
        try:
            resp = self._client.post("/api/chat/sync", json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise EngineConnectionError(
                f"Claudi-Proxy nicht erreichbar: {exc}"
            ) from exc
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = (resp.text or "")[:200]
            raise RuntimeError(
                f"Claudi-Proxy HTTP {resp.status_code}: {body}"
            ) from exc
        data = resp.json()
        content = data.get("response", "")
        prompt_tokens = estimate_prompt_tokens(messages)
        completion_tokens = max(1, len(content) // 4)  # grobe Schaetzung 1 Token ≈ 4 Zeichen
        return {
            "content": content,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
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
            resp = self._client.get("/api/health", timeout=_HEALTH_TIMEOUT)
            return resp.status_code == 200
        except Exception:
            logger.debug("ClaudiProxyEngine health-check failed", exc_info=True)
            return False

    def close(self) -> None:
        self._client.close()


__all__ = ["ClaudiProxyEngine"]
