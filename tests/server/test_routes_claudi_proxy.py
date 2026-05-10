"""Stage 7: claudi_proxy-Modelle landen im /v1/models und werden NICHT
ueber stream_cloud oder stream_local geroutet (generisch ueber is_c3po_custom).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_claudi():
    """Minimal-App mit echter ClaudiProxyEngine im app.state.engine."""
    from openjarvis.engine.claudi_proxy import ClaudiProxyEngine
    from openjarvis.server.app import create_app

    eng = ClaudiProxyEngine()
    app = create_app(engine=eng, model="claude-opus-4-7")
    yield app, eng
    eng.close()


class TestClaudiModelsInList:
    def test_v1_models_includes_claude_opus(self, app_with_claudi):
        app, _ = app_with_claudi
        client = TestClient(app)
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()["data"]]
        assert "claude-opus-4-7" in ids


class TestC3poCustomEngineHelper:
    def test_helper_returns_true_for_claudi_proxy(self, app_with_claudi):
        """Echte ClaudiProxyEngine -> _is_c3po_custom_engine = True."""
        from openjarvis.server.routes import _is_c3po_custom_engine

        _, eng = app_with_claudi
        assert _is_c3po_custom_engine(eng, "claude-opus-4-7") is True

    def test_helper_returns_false_for_engine_without_flag(self):
        """Engine ohne is_c3po_custom-Attribut -> Default False."""
        from openjarvis.server.routes import _is_c3po_custom_engine

        # MagicMock liefert auch ohne explizites Attribut "etwas" zurueck.
        # Wir patchen _engine_for_model auf ein Mock ohne is_c3po_custom.
        class _NoFlagEngine:
            pass

        mock_engine = _NoFlagEngine()
        with patch(
            "openjarvis.server.routes._engine_for_model",
            return_value=mock_engine,
        ):
            assert _is_c3po_custom_engine(mock_engine, "anything") is False

    def test_helper_returns_false_for_explicit_false_flag(self):
        from openjarvis.server.routes import _is_c3po_custom_engine

        class _StanfordEngine:
            is_c3po_custom = False

        mock_engine = _StanfordEngine()
        with patch(
            "openjarvis.server.routes._engine_for_model",
            return_value=mock_engine,
        ):
            assert _is_c3po_custom_engine(mock_engine, "model") is False
