"""Tests for the digest_collect tool."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from openjarvis.connectors._stubs import Document
from openjarvis.core.registry import ConnectorRegistry, ToolRegistry


def test_digest_collect_registered():
    from openjarvis.tools.digest_collect import DigestCollectTool

    ToolRegistry.register_value("digest_collect", DigestCollectTool)
    assert ToolRegistry.contains("digest_collect")


def test_digest_collect_executes():
    from openjarvis.tools.digest_collect import DigestCollectTool

    tool = DigestCollectTool()

    mock_docs = [
        Document(
            doc_id="test-1",
            source="gmail",
            doc_type="email",
            content="Meeting at 3pm",
            title="Team standup",
            author="alice@example.com",
            timestamp=datetime(2026, 4, 1, 10, 0),
        )
    ]

    mock_connector = MagicMock()
    mock_connector.return_value.is_connected.return_value = True
    mock_connector.return_value.sync.return_value = mock_docs

    with patch.object(ConnectorRegistry, "contains", return_value=True):
        with patch.object(ConnectorRegistry, "get", return_value=mock_connector):
            result = tool.execute(sources=["gmail"], hours_back=24)

    assert result.success is True
    assert "=== MESSAGES ===" in result.content
    assert "[gmail] From: alice@example.com" in result.content
    assert "Team standup" in result.content
    assert result.metadata["total_items"] == 1


def test_digest_collect_missing_connector():
    from openjarvis.tools.digest_collect import DigestCollectTool

    tool = DigestCollectTool()

    with patch.object(ConnectorRegistry, "contains", return_value=False):
        result = tool.execute(sources=["nonexistent"])

    assert result.success is True  # Partial success
    assert "not available" in result.content


def test_digest_collect_formats_local_mail_and_calendar():
    from openjarvis.tools.digest_collect import DigestCollectTool

    tool = DigestCollectTool()
    docs_by_source = {
        "strato_mail": [
            Document(
                doc_id="mail-1",
                source="strato_mail",
                doc_type="email",
                content="Bitte Rueckruf.",
                title="Patientenakte",
                author="Praxis <praxis@example.com>",
                timestamp=datetime(2026, 4, 1, 10, 0),
            )
        ],
        "thunderbird_calendar": [
            Document(
                doc_id="cal-1",
                source="thunderbird_calendar",
                doc_type="calendar_event",
                content="When: 2026-04-01T15:00:00 - 2026-04-01T16:00:00",
                title="Dr. Termin",
                timestamp=datetime(2026, 4, 1, 15, 0),
                metadata={
                    "end": "2026-04-01T16:00:00",
                    "calendar_name": "Privat",
                },
            )
        ],
    }

    def connector_for(source):
        connector = MagicMock()
        connector.return_value.is_connected.return_value = True
        connector.return_value.sync.return_value = docs_by_source[source]
        return connector

    with patch.object(ConnectorRegistry, "contains", return_value=True):
        with patch.object(ConnectorRegistry, "get", side_effect=connector_for):
            result = tool.execute(
                sources=["strato_mail", "thunderbird_calendar"],
                hours_back=24,
            )

    assert result.success is True
    assert "=== MESSAGES ===" in result.content
    assert "[strato_mail] From: Praxis" in result.content
    assert "=== CALENDAR ===" in result.content
    assert "[thunderbird_calendar]" in result.content
    assert "Dr. Termin" in result.content
