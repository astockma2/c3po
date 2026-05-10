"""Sync→Async-Bridge zwischen ToolExecutor (sync) und PermissionGate (async).

Stage 3, Variante A der Architektur-Entscheidung in
``docs/architecture/tools_c3po.md``.

Aufrufer ist immer synchron (Engine-Loop, Skill-Step, Workflow-Engine, ...).
PermissionGate.check() ist async (asyncio.Future-basierte Pending-Map).

Strategie:
- Wenn ein **laufender** Loop injiziert ist (z.B. Voice-Channel-Loop):
  ``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=…)``.
- Sonst: ``asyncio.run(coro)`` (frischer Loop pro Aufruf — okay, weil
  Permission-Checks selten genug sind).

Dieser Adapter ist die EINZIGE Stelle im Code, die diese Bruecke kennt.
ToolExecutor importiert ihn, sonst niemand.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from openjarvis.security.types import PermissionResult

logger = logging.getLogger(__name__)


class PermissionGateAdapter:
    """Sync-Wrapper um eine async ``PermissionGate``.

    Parameters
    ----------
    gate:
        ``PermissionGate``-Instanz (oder MagicMock im Test).
    loop:
        Optionaler laufender asyncio-Loop. Wenn gesetzt, werden Coroutines via
        ``run_coroutine_threadsafe`` an diesen Loop delegiert. Wenn ``None``,
        wird pro Aufruf ein neuer Loop via ``asyncio.run()`` aufgemacht.
    timeout:
        Sekunden, die wir auf das ``Future`` warten, das ``PermissionGate.check``
        oder die Pending-Resolution liefert. Default 60s — Auto-Decline im Gate
        feuert bereits nach 30s, wir geben etwas Puffer.
    """

    def __init__(
        self,
        gate: Any,
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        timeout: float = 60.0,
    ) -> None:
        self._gate = gate
        self._loop = loop
        self._timeout = timeout

    def check_sync(
        self,
        tool_name: str,
        args: dict,
        *,
        channel: str,
    ) -> PermissionResult:
        """Ruft ``gate.check`` synchron auf, wickelt den Loop-Sprung ab.

        Wenn das Ergebnis ``is_pending`` ist, wartet der Adapter zusaetzlich
        auf das Future in ``gate._pending[prompt_id]`` und liefert ein
        finales ``PermissionResult`` zurueck (granted oder denied).

        Returns
        -------
        PermissionResult
            ``state="granted"``, ``"denied"`` — niemals ``needs_confirm``/
            ``needs_pin`` (die Pending-Aufloesung passiert hier intern).
        """
        result = self._run(self._gate.check(tool_name, args, channel=channel))

        if not result.is_pending:
            return result

        prompt_id = result.prompt_id
        granted = self._await_pending(prompt_id)
        if granted:
            return PermissionResult.granted()
        return PermissionResult.denied(
            f"User declined or timed out (prompt_id={prompt_id})"
        )

    def _await_pending(self, prompt_id: str) -> bool:
        """Wartet auf das Future in ``gate._pending[prompt_id]``.

        Liefert ``True`` bei Confirm/PIN-OK, ``False`` bei Decline/Timeout/
        unbekannter prompt_id.
        """
        pending = getattr(self._gate, "_pending", None)
        if pending is None:
            logger.warning(
                "PermissionGateAdapter: gate has no _pending attr — "
                "cannot wait for pending resolution"
            )
            return False
        entry = pending.get(prompt_id)
        if entry is None:
            return False
        fut, _kind = entry

        async def _wait() -> bool:
            try:
                return await asyncio.wait_for(
                    asyncio.shield(fut),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                return False

        return self._run(_wait())

    def _run(self, coro: Any) -> Any:
        """Fuehrt eine Coroutine synchron aus, mit oder ohne injizierten Loop."""
        if self._loop is not None and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result(timeout=self._timeout)
        # Frischer Loop pro Call.
        return asyncio.run(coro)


__all__ = ["PermissionGateAdapter"]
