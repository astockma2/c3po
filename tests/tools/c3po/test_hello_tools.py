"""Tests fuer c3po/time_tools.py::HelloGreetTool — Stage 3 Sub-Stufe 3.1."""

from __future__ import annotations

from openjarvis.tools.c3po.time_tools import HelloGreetTool


class TestHelloGreetTool:
    def test_spec_name(self):
        assert HelloGreetTool().spec.name == "hello.greet"

    def test_default_name_is_andre(self):
        result = HelloGreetTool().execute()
        assert result.success is True
        assert "Andre" in result.content

    def test_custom_name(self):
        result = HelloGreetTool().execute(name="Nicole")
        assert result.success is True
        assert "Nicole" in result.content

    def test_german_greeting(self):
        result = HelloGreetTool().execute()
        # Pruefe dass es deutsch ist
        assert "Hallo" in result.content or "hallo" in result.content.lower()
