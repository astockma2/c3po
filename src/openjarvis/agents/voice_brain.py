"""Voice-Brain Hilfsfunktionen fuer den Voice-Channel (Stage 4).

Enthaelt:

- ``select_voice_tools()`` -- kuratierte Tool-Liste aus der ToolRegistry.
- ``build_voice_brain()`` -- ChannelHandler-Factory, die einen
  ``NativeReActAgent`` + ``ClaudiProxyEngine`` + Permission-Gate-faehigen
  ``ToolExecutor`` verdrahtet und einen sync Callback fuer den
  Voice-Channel liefert.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Optional

from openjarvis.agents.native_react import NativeReActAgent
from openjarvis.channels._stubs import ChannelMessage
from openjarvis.core.registry import ToolRegistry
from openjarvis.engine.claudi_proxy import ClaudiProxyEngine
from openjarvis.tools._stubs import BaseTool, ToolExecutor

logger = logging.getLogger(__name__)

ChannelHandler = Callable[[ChannelMessage], Optional[str]]

# Default-Kategorien, die der Voice-Brain anbietet. ``admin`` ist NICHT
# enthalten — PIN-Eingabe per Sprache ist zu fehleranfaellig, und der
# Tray-Daemon laeuft im Voice-Smoke-Test nicht mit.
DEFAULT_VOICE_TOOL_CATEGORIES: set[str] = {
    "time",
    "social",
    "mail",
    "calendar",
    "browser",
    "messaging",
    "windows",
}


def select_voice_tools(
    *,
    categories: Optional[Iterable[str]] = None,
    include_admin: bool = False,
) -> list[BaseTool]:
    """Liefert BaseTool-Instanzen aus der ToolRegistry, gefiltert nach Kategorie.

    Parameters
    ----------
    categories:
        Iterable von Kategorien (entspricht ``ToolSpec.category``). Wenn
        ``None``, wird ``DEFAULT_VOICE_TOOL_CATEGORIES`` genutzt.
    include_admin:
        Wenn True, wird die ``admin``-Kategorie zur Auswahl hinzugefuegt
        (egal ob sie in ``categories`` stand). Brauchst du nur in
        kontrollierten Test-Umgebungen oder wenn der Tray-Daemon laeuft.

    Returns
    -------
    list[BaseTool]
        Instanziierte Tools. Tools, die beim Instanziieren scheitern
        (z.B. fehlende optionale Dependency), werden uebersprungen.
    """
    wanted: set[str] = (
        set(categories) if categories is not None else set(DEFAULT_VOICE_TOOL_CATEGORIES)
    )
    if include_admin:
        wanted.add("admin")

    tools: list[BaseTool] = []
    for name in ToolRegistry.keys():
        cls = ToolRegistry.get(name)
        try:
            instance = cls()
        except Exception:
            logger.warning("Tool %s nicht instanziierbar", name, exc_info=True)
            continue
        if instance.spec.category in wanted:
            tools.append(instance)
    return tools


def _build_agent(
    *,
    model: str,
    tools: list[BaseTool],
    permission_gate: Any,
    permission_loop: Any,
    max_turns: int,
) -> NativeReActAgent:
    """Baut einen NativeReActAgent mit ClaudiProxyEngine + Permission-Gate-faehigem ToolExecutor.

    Der parent-class-Konstruktor erzeugt einen ToolExecutor OHNE Permission-Gate.
    Wir ueberschreiben das ``_executor``-Attribut direkt nach __init__ durch
    unsere Variante. Das ist ein privates Attribut von ``ToolUsingAgent``, aber
    der einzige Weg ohne Upstream-Patches.
    """
    engine = ClaudiProxyEngine()
    agent = NativeReActAgent(
        engine=engine,
        model=model,
        tools=tools,
        max_turns=max_turns,
    )
    agent._executor = ToolExecutor(
        tools,
        permission_gate=permission_gate,
        permission_loop=permission_loop,
    )
    return agent


def build_voice_brain(
    *,
    model: str = "claude-haiku-4-5",
    tools: Optional[list[BaseTool]] = None,
    permission_gate: Any = None,
    permission_loop: Any = None,
    max_turns: int = 6,
) -> ChannelHandler:
    """ChannelHandler-Factory fuer den Voice-Channel.

    Returns a synchronous callback ``handler(msg: ChannelMessage) -> str | None``,
    der die Voice-Eingabe als Query an den Tool-Loop schickt und die finale
    Antwort als String zurueckgibt (oder ``None``, wenn nichts zu sagen ist).

    Parameters
    ----------
    model:
        Claude-Modell (Hint; Proxy nutzt aktuell immer Opus 4.7).
    tools:
        Liste von Tools. Default: ``select_voice_tools()``.
    permission_gate:
        Optional PermissionGate-Instanz.
    permission_loop:
        Optional asyncio-Loop fuer den Permission-Adapter (siehe Stage 3
        Deadlock-Hinweis in docs/architecture/tools_c3po.md).
    max_turns:
        Maximale ReAct-Turns pro Anfrage.
    """
    selected = tools if tools is not None else select_voice_tools()
    agent = _build_agent(
        model=model,
        tools=selected,
        permission_gate=permission_gate,
        permission_loop=permission_loop,
        max_turns=max_turns,
    )

    def _handler(msg: ChannelMessage) -> Optional[str]:
        if not msg.content or not msg.content.strip():
            return None
        try:
            result = agent.run(input=msg.content)
        except Exception:
            logger.exception("voice_brain: Agent run failed")
            return "Entschuldigung, es gab einen Fehler."
        content = result.content if result else ""
        return content or None

    return _handler


__all__ = [
    "DEFAULT_VOICE_TOOL_CATEGORIES",
    "select_voice_tools",
    "build_voice_brain",
    "ChannelHandler",
]
