"""Tests fuer c3po/calendar_tools.py — Stage 3 Sub-Stufe 3.4."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.tools.c3po.calendar_tools import (
    CalendarListTool,
    CalendarSearchTool,
    CalendarUpcomingTool,
    _summarize_event,
)


def _ev(eid: str, summary: str, *, start: str, end: str = "", desc: str = "", loc: str = "") -> dict:
    return {
        "id": eid,
        "summary": summary,
        "description": desc,
        "location": loc,
        "start": {"dateTime": start},
        "end": {"dateTime": end or start},
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestSummarizeEvent:
    def test_extracts_main_fields(self):
        e = _ev("e1", "Meeting", start="2026-05-10T14:00:00Z", loc="Buero")
        s = _summarize_event(e)
        assert s["id"] == "e1"
        assert s["summary"] == "Meeting"
        assert s["start"] == "2026-05-10T14:00:00Z"
        assert s["location"] == "Buero"


# ---------------------------------------------------------------------------
# calendar.upcoming
# ---------------------------------------------------------------------------


class TestCalendarUpcoming:
    def test_spec(self):
        assert CalendarUpcomingTool().spec.name == "calendar.upcoming"

    def test_no_token_fails(self):
        with patch(
            "openjarvis.tools.c3po.calendar_tools._get_gcal_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._read_gcal_token",
            return_value=None,
        ):
            r = CalendarUpcomingTool().execute()
        assert r.success is False

    def test_today_default(self):
        events = [
            _ev("e1", "Standup", start="2026-05-10T09:00:00Z"),
            _ev("e2", "Lunch", start="2026-05-10T12:00:00Z"),
        ]
        with patch(
            "openjarvis.tools.c3po.calendar_tools._get_gcal_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._read_gcal_token",
            return_value="tok",
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._list_events_for_window",
            return_value=events,
        ) as fetch:
            r = CalendarUpcomingTool().execute()
        assert r.success is True
        data = json.loads(r.content)
        assert len(data) == 2
        # Default 'today' setzt sowohl time_min als auch time_max
        kw = fetch.call_args.kwargs
        assert kw.get("time_min")
        assert kw.get("time_max")

    def test_tomorrow_keyword(self):
        with patch(
            "openjarvis.tools.c3po.calendar_tools._get_gcal_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._read_gcal_token",
            return_value="tok",
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._list_events_for_window",
            return_value=[],
        ) as fetch:
            CalendarUpcomingTool().execute(when="tomorrow")
        kw = fetch.call_args.kwargs
        # tmrw fenster sollte gesetzt sein
        assert kw.get("time_min") and kw.get("time_max")

    def test_hhmm_anchor(self):
        with patch(
            "openjarvis.tools.c3po.calendar_tools._get_gcal_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._read_gcal_token",
            return_value="tok",
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._list_events_for_window",
            return_value=[],
        ) as fetch:
            CalendarUpcomingTool().execute(when="14:00")
        kw = fetch.call_args.kwargs
        assert "T14:00" in (kw.get("time_min") or "")
        assert kw.get("time_max") is None


# ---------------------------------------------------------------------------
# calendar.list
# ---------------------------------------------------------------------------


class TestCalendarList:
    def test_spec(self):
        assert CalendarListTool().spec.name == "calendar.list"

    def test_invalid_date_fails(self):
        r = CalendarListTool().execute(date="nope")
        assert r.success is False
        assert "YYYY-MM-DD" in r.content

    def test_valid_date_calls_api(self):
        with patch(
            "openjarvis.tools.c3po.calendar_tools._get_gcal_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._read_gcal_token",
            return_value="tok",
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._list_events_for_window",
            return_value=[_ev("e1", "Meet", start="2026-05-10T10:00:00Z")],
        ) as fetch:
            r = CalendarListTool().execute(date="2026-05-10")
        assert r.success is True
        kw = fetch.call_args.kwargs
        assert "2026-05-10T00:00" in kw["time_min"]
        assert "2026-05-10T23:59" in kw["time_max"]


# ---------------------------------------------------------------------------
# calendar.search
# ---------------------------------------------------------------------------


class TestCalendarSearch:
    def test_empty_query_fails(self):
        r = CalendarSearchTool().execute(query="")
        assert r.success is False

    def test_filters_by_query_locally(self):
        events = [
            _ev("e1", "Standup", start="2026-05-10T09:00:00Z"),
            _ev("e2", "Lunch with Alice", start="2026-05-10T12:00:00Z"),
            _ev("e3", "Review", start="2026-05-11T15:00:00Z", desc="Alice und Bob"),
        ]
        with patch(
            "openjarvis.tools.c3po.calendar_tools._get_gcal_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._read_gcal_token",
            return_value="tok",
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._list_events_for_window",
            return_value=events,
        ):
            r = CalendarSearchTool().execute(query="alice")
        assert r.success is True
        data = json.loads(r.content)
        # Beide alice-Events sollen matchen
        ids = {d["id"] for d in data}
        assert ids == {"e2", "e3"}

    def test_case_insensitive(self):
        events = [_ev("e1", "MEETING", start="2026-05-10T09:00:00Z")]
        with patch(
            "openjarvis.tools.c3po.calendar_tools._get_gcal_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._read_gcal_token",
            return_value="tok",
        ), patch(
            "openjarvis.tools.c3po.calendar_tools._list_events_for_window",
            return_value=events,
        ):
            r = CalendarSearchTool().execute(query="meeting")
        data = json.loads(r.content)
        assert len(data) == 1
