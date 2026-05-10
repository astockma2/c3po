"""Test: deutscher REACT_SYSTEM_PROMPT-Override wird geladen (Stage 5)."""
from __future__ import annotations

from pathlib import Path

import pytest

from openjarvis.agents.prompt_loader import load_system_prompt_override


class TestPromptOverride:
    def test_override_returns_german_prompt(self, tmp_path, monkeypatch):
        home = tmp_path / "openjarvis"
        agents_dir = home / "agents" / "native_react"
        agents_dir.mkdir(parents=True)
        (agents_dir / "system_prompt.md").write_text(
            "Du bist ein ReAct-Agent fuer C3PO.\n{tool_descriptions}",
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENJARVIS_HOME", str(home))
        result = load_system_prompt_override("native_react")
        assert result is not None
        assert "ReAct-Agent fuer C3PO" in result

    def test_override_returns_none_when_missing(self, tmp_path, monkeypatch):
        home = tmp_path / "openjarvis_empty"
        monkeypatch.setenv("OPENJARVIS_HOME", str(home))
        assert load_system_prompt_override("native_react") is None


class TestRepoTemplate:
    def test_template_exists(self):
        """Der mitgelieferte deutsche Prompt-Override existiert im Repo."""
        repo_template = (
            Path(__file__).resolve().parents[2]
            / "configs"
            / "c3po"
            / "agents"
            / "native_react"
            / "system_prompt.md"
        )
        assert repo_template.exists(), f"Template fehlt: {repo_template}"

    def test_template_has_required_format_slots(self):
        repo_template = (
            Path(__file__).resolve().parents[2]
            / "configs"
            / "c3po"
            / "agents"
            / "native_react"
            / "system_prompt.md"
        )
        content = repo_template.read_text(encoding="utf-8")
        assert "Du bist ein ReAct-Agent" in content
        # Beide Format-Slots muessen drin sein damit
        # NativeReActAgent.run().format() durchlaeuft
        assert "{tool_descriptions}" in content
        assert "{skill_examples}" in content

    def test_template_mentions_time_now_example(self):
        repo_template = (
            Path(__file__).resolve().parents[2]
            / "configs"
            / "c3po"
            / "agents"
            / "native_react"
            / "system_prompt.md"
        )
        content = repo_template.read_text(encoding="utf-8")
        assert "time.now" in content, (
            "Prompt sollte time.now als Beispiel nennen "
            "fuer das Tool-Calling-Hardening"
        )
