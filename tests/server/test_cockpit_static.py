"""Test: GET /cockpit/ liefert das Cockpit-HTML + CSS + JS (Stage 5)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from openjarvis.server.app import create_app


@pytest.fixture
def client(monkeypatch):
    from unittest.mock import MagicMock

    # Permission-Routes sind optional — Cockpit-Static ist davon unabhaengig.
    monkeypatch.delenv("OPENJARVIS_PERMISSIONS_CONFIG", raising=False)
    monkeypatch.delenv("OPENJARVIS_ADMIN_WHITELIST", raising=False)
    app = create_app(engine=MagicMock(), model="test-model")
    return TestClient(app)


class TestCockpitStatic:
    def test_cockpit_index_returns_html(self, client):
        resp = client.get("/cockpit/")
        assert resp.status_code == 200
        assert "C3PO Cockpit" in resp.text
        assert 'id="pending-section"' in resp.text

    def test_cockpit_css_loads(self, client):
        resp = client.get("/cockpit/cockpit.css")
        assert resp.status_code == 200
        assert "--cyan" in resp.text
        assert resp.headers["content-type"].startswith("text/css")

    def test_cockpit_js_loads(self, client):
        resp = client.get("/cockpit/cockpit.js")
        assert resp.status_code == 200
        assert "POLL_INTERVAL_MS" in resp.text
        # JS-MIME-Type kann je nach Server-Config variieren
        ct = resp.headers["content-type"]
        assert "javascript" in ct or "text" in ct

    def test_cockpit_no_cache_headers(self, client):
        """Cockpit muss no-cache-Header haben damit Polling-Updates greifen."""
        resp = client.get("/cockpit/")
        cache_control = resp.headers.get("cache-control", "").lower()
        assert "no-cache" in cache_control or "no-store" in cache_control
