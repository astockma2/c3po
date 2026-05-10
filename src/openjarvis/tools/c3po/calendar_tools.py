"""C3PO Calendar-Tools (Stage 3 Sub-Stufe 3.4, alle ``free``).

3 Tools:
- ``calendar.upcoming(when='today'|'tomorrow'|'14:00')`` — naechste Termine
- ``calendar.list(date='2026-05-10')`` — Termine an einem konkreten Tag
- ``calendar.search(query='...')`` — Volltext-Suche

Backend: ``GCalendarConnector``. ``thunderbird_calendar`` ist die zweite
Quelle, wird hier aber nicht verdrahtet — nur Gmail-Stack zuerst (analog
zu Mail-Tools). Spaeter erweitern.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from typing import Any, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _get_gcal_connector() -> Any:
    """Liefert eine GCalendarConnector-Instanz. Tests patchen das."""
    from openjarvis.connectors.gcalendar import GCalendarConnector

    return GCalendarConnector()


def _read_gcal_token(connector: Any) -> Optional[str]:
    from openjarvis.connectors.google_auth import load_tokens

    tokens = load_tokens(connector._credentials_path)
    if not tokens:
        return None
    return tokens.get("token") or tokens.get("access_token")


def _today_window() -> tuple[str, str]:
    """RFC3339-Strings fuer den heutigen Tag (00:00 → 23:59) lokal."""
    now = datetime.now()
    start = datetime.combine(now.date(), time(0, 0)).isoformat() + "Z"
    end = datetime.combine(now.date(), time(23, 59)).isoformat() + "Z"
    return start, end


def _list_events_for_window(
    token: str,
    *,
    time_min: str,
    time_max: Optional[str] = None,
    max_events: int = 20,
) -> list[dict]:
    """Holt Events ueber den gcalendar-API-Helper, optional nach time_max gefiltert."""
    from openjarvis.connectors.gcalendar import _gcal_api_events_list

    resp = _gcal_api_events_list(
        token, "primary", time_min=time_min
    )
    items = resp.get("items", [])
    if time_max is not None:
        items = [
            e
            for e in items
            if (
                e.get("end", {}).get("dateTime", "")
                or e.get("end", {}).get("date", "")
            )
            <= time_max
        ]
    return items[:max_events]


def _summarize_event(event: dict) -> dict:
    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", ""),
        "start": event.get("start", {}).get("dateTime")
        or event.get("start", {}).get("date", ""),
        "end": event.get("end", {}).get("dateTime")
        or event.get("end", {}).get("date", ""),
        "location": event.get("location", ""),
    }


# ---------------------------------------------------------------------------
# calendar.upcoming
# ---------------------------------------------------------------------------


@ToolRegistry.register("calendar.upcoming")
class CalendarUpcomingTool(BaseTool):
    """Naechste Termine — Default: heute."""

    tool_id = "calendar.upcoming"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="calendar.upcoming",
            description=(
                "Liefert die naechsten Kalendertermine. Default: heute. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "when": {
                        "type": "string",
                        "description": (
                            "'today' (Default), 'tomorrow', oder ein "
                            "Zeitpunkt 'HH:MM' der den Start-Filter setzt."
                        ),
                    },
                    "max_events": {"type": "integer"},
                },
            },
            category="calendar",
        )

    def execute(self, **params: Any) -> ToolResult:
        when = (params.get("when") or "today").strip().lower()
        max_events = int(params.get("max_events") or 10)
        try:
            connector = _get_gcal_connector()
            token = _read_gcal_token(connector)
            if not token:
                return ToolResult(
                    tool_name="calendar.upcoming",
                    content="Kalender nicht verbunden.",
                    success=False,
                )
            now = datetime.now()
            if when == "today":
                tmin, tmax = _today_window()
            elif when == "tomorrow":
                tmrw = (now + timedelta(days=1)).date()
                tmin = datetime.combine(tmrw, time(0, 0)).isoformat() + "Z"
                tmax = datetime.combine(tmrw, time(23, 59)).isoformat() + "Z"
            elif ":" in when and len(when) == 5:
                # 'HH:MM' — Start ab heute zu dieser Uhrzeit
                hh, mm = when.split(":")
                anchor = datetime.combine(now.date(), time(int(hh), int(mm)))
                tmin = anchor.isoformat() + "Z"
                tmax = None
            else:
                tmin = now.isoformat() + "Z"
                tmax = None
            events = _list_events_for_window(
                token, time_min=tmin, time_max=tmax, max_events=max_events
            )
            return ToolResult(
                tool_name="calendar.upcoming",
                content=json.dumps(
                    [_summarize_event(e) for e in events],
                    ensure_ascii=False,
                ),
                success=True,
                metadata={"count": len(events), "when": when},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="calendar.upcoming",
                content=f"Fehler: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# calendar.list
# ---------------------------------------------------------------------------


@ToolRegistry.register("calendar.list")
class CalendarListTool(BaseTool):
    """Alle Termine an einem konkreten Datum."""

    tool_id = "calendar.list"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="calendar.list",
            description=(
                "Listet alle Kalendertermine an einem konkreten Datum. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "ISO-Datum YYYY-MM-DD.",
                    },
                },
                "required": ["date"],
            },
            category="calendar",
        )

    def execute(self, **params: Any) -> ToolResult:
        date_str = (params.get("date") or "").strip()
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return ToolResult(
                tool_name="calendar.list",
                content=f"Ungueltiges Datum '{date_str}', erwartet YYYY-MM-DD.",
                success=False,
            )
        try:
            connector = _get_gcal_connector()
            token = _read_gcal_token(connector)
            if not token:
                return ToolResult(
                    tool_name="calendar.list",
                    content="Kalender nicht verbunden.",
                    success=False,
                )
            tmin = datetime.combine(day, time(0, 0)).isoformat() + "Z"
            tmax = datetime.combine(day, time(23, 59)).isoformat() + "Z"
            events = _list_events_for_window(
                token, time_min=tmin, time_max=tmax, max_events=50
            )
            return ToolResult(
                tool_name="calendar.list",
                content=json.dumps(
                    [_summarize_event(e) for e in events],
                    ensure_ascii=False,
                ),
                success=True,
                metadata={"count": len(events), "date": date_str},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="calendar.list",
                content=f"Fehler: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# calendar.search
# ---------------------------------------------------------------------------


@ToolRegistry.register("calendar.search")
class CalendarSearchTool(BaseTool):
    """Volltext-Suche in Termin-Titeln und -Beschreibungen."""

    tool_id = "calendar.search"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="calendar.search",
            description=(
                "Sucht Kalendertermine per Volltext. "
                "Permission: free."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_events": {"type": "integer"},
                },
                "required": ["query"],
            },
            category="calendar",
        )

    def execute(self, **params: Any) -> ToolResult:
        query = (params.get("query") or "").strip()
        if not query:
            return ToolResult(
                tool_name="calendar.search",
                content="Keine Query angegeben.",
                success=False,
            )
        max_events = int(params.get("max_events") or 20)
        q_lower = query.lower()
        try:
            connector = _get_gcal_connector()
            token = _read_gcal_token(connector)
            if not token:
                return ToolResult(
                    tool_name="calendar.search",
                    content="Kalender nicht verbunden.",
                    success=False,
                )
            # Wir holen Events der naechsten 90 Tage und filtern lokal —
            # die Calendar-API hat kein natives Volltext-Endpoint fuer
            # einzelne Kalender (q-Parameter ist Beta).
            tmin = datetime.now().isoformat() + "Z"
            events = _list_events_for_window(
                token, time_min=tmin, max_events=500
            )
            filtered: List[dict] = []
            for e in events:
                blob = " ".join(
                    [
                        e.get("summary", ""),
                        e.get("description", ""),
                        e.get("location", ""),
                    ]
                ).lower()
                if q_lower in blob:
                    filtered.append(_summarize_event(e))
                if len(filtered) >= max_events:
                    break
            return ToolResult(
                tool_name="calendar.search",
                content=json.dumps(filtered, ensure_ascii=False),
                success=True,
                metadata={"count": len(filtered), "query": query},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="calendar.search",
                content=f"Fehler: {exc}",
                success=False,
            )


__all__ = [
    "CalendarUpcomingTool",
    "CalendarListTool",
    "CalendarSearchTool",
]
