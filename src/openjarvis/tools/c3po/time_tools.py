"""C3PO time + hello tools (Stage 3 Sub-Stufe 3.1, alle ``free``).

Quelle: ``C3PO-legacy/tools/time_tool.py`` + ``hello_tool.py`` als BaseTool-Klassen.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _now() -> _dt.datetime:
    """Indirekter Time-Accessor — Tests koennen das patchen."""
    return _dt.datetime.now()


# Deutsche Wochentage + Monatsnamen — wir benutzen NICHT setlocale,
# weil das auf manchen Windows-Systemen "Deutsch_Deutschland" verlangt
# und auf Linux-CI fehlt.
_WOCHENTAGE = (
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
)
_MONATE = (
    "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


def _format_german(now: _dt.datetime) -> str:
    """`Es ist 14:23 Uhr am Sonntag, dem 10. Mai 2026.`"""
    return (
        f"Es ist {now.hour:02d}:{now.minute:02d} Uhr am "
        f"{_WOCHENTAGE[now.weekday()]}, dem "
        f"{now.day}. {_MONATE[now.month - 1]} {now.year}."
    )


@ToolRegistry.register("time.now")
class TimeNowTool(BaseTool):
    """Aktuelle Uhrzeit + Datum auf Deutsch."""

    tool_id = "time.now"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="time.now",
            description="Liefert aktuelle Uhrzeit und Datum als deutscher Satz.",
            parameters={"type": "object", "properties": {}},
            category="time",
        )

    def execute(self, **params: Any) -> ToolResult:
        return ToolResult(
            tool_name="time.now",
            content=_format_german(_now()),
            success=True,
        )


@ToolRegistry.register("time.date")
class TimeDateTool(BaseTool):
    """Aktuelles Datum als ISO-String YYYY-MM-DD."""

    tool_id = "time.date"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="time.date",
            description="Liefert das aktuelle Datum im Format YYYY-MM-DD.",
            parameters={"type": "object", "properties": {}},
            category="time",
        )

    def execute(self, **params: Any) -> ToolResult:
        return ToolResult(
            tool_name="time.date",
            content=_now().strftime("%Y-%m-%d"),
            success=True,
        )


@ToolRegistry.register("hello.greet")
class HelloGreetTool(BaseTool):
    """Freundliche deutsche Begruessung."""

    tool_id = "hello.greet"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="hello.greet",
            description="Liefert eine freundliche deutsche Begruessung.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name der Person (Default: Andre).",
                    },
                },
            },
            category="social",
        )

    def execute(self, **params: Any) -> ToolResult:
        name = params.get("name") or "Andre"
        return ToolResult(
            tool_name="hello.greet",
            content=f"Hallo {name}, schoen dich zu hoeren.",
            success=True,
        )


__all__ = ["TimeNowTool", "TimeDateTool", "HelloGreetTool"]
