"""Tests fuer c3po/time_tools.py — Stage 3 Sub-Stufe 3.1."""

from __future__ import annotations

import datetime as _dt
from unittest.mock import patch

import pytest

from openjarvis.tools.c3po.time_tools import (
    TimeDateTool,
    TimeNowTool,
)


class TestTimeNowTool:
    def test_spec_name(self):
        assert TimeNowTool().spec.name == "time.now"

    def test_spec_category(self):
        assert TimeNowTool().spec.category == "time"

    def test_execute_returns_german_string(self):
        fixed = _dt.datetime(2026, 5, 10, 14, 23, 0)
        with patch("openjarvis.tools.c3po.time_tools._now", return_value=fixed):
            result = TimeNowTool().execute()
        assert result.success is True
        assert "14:23" in result.content
        # Wochentag ist deutsch — pruefe auf einen festen Anker.
        assert "2026" in result.content

    def test_execute_locale_independent(self):
        """Auch wenn das System-Locale englisch ist, soll der Output deutsch sein."""
        fixed = _dt.datetime(2026, 1, 1, 9, 5, 0)
        with patch("openjarvis.tools.c3po.time_tools._now", return_value=fixed):
            result = TimeNowTool().execute()
        # Deutscher Monatsname / Wochentag
        assert "Januar" in result.content
        assert "Donnerstag" in result.content


class TestTimeDateTool:
    def test_spec_name(self):
        assert TimeDateTool().spec.name == "time.date"

    def test_execute_returns_iso_date(self):
        fixed = _dt.datetime(2026, 5, 10, 14, 23, 0)
        with patch("openjarvis.tools.c3po.time_tools._now", return_value=fixed):
            result = TimeDateTool().execute()
        assert result.success is True
        assert result.content == "2026-05-10"

    def test_execute_no_args(self):
        result = TimeDateTool().execute()
        assert result.success is True
        # ISO-Format YYYY-MM-DD
        assert len(result.content.split("-")) == 3
