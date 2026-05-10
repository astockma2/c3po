"""Voice-Brain Hilfsfunktionen fuer den Voice-Channel (Stage 4).

Aktuell nur Tool-Selektion. ``build_voice_brain`` (ChannelHandler-Factory)
kommt in einem nachfolgenden Commit.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools._stubs import BaseTool

logger = logging.getLogger(__name__)

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


__all__ = ["DEFAULT_VOICE_TOOL_CATEGORIES", "select_voice_tools"]
