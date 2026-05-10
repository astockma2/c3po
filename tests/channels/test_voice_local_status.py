"""Stage 5: VoiceLocalChannel aktualisiert den Cockpit-Voice-Status.

Hinweis: ``permission_routes._voice_status`` ist modul-global. Diese Tests
laufen NICHT parallel-sicher. Die ``_reset_voice_status``-Fixture stellt
einen sauberen Ausgangszustand her.
"""
from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.channels.voice_local import VoiceLocalChannel
from openjarvis.server import permission_routes


@pytest.fixture(autouse=True)
def _reset_voice_status():
    """Modul-global den Voice-Status zuruecksetzen vor und nach jedem Test."""
    permission_routes._voice_status.update(
        {"connected": False, "wake_count": 0, "last_wake": 0.0}
    )
    yield
    permission_routes._voice_status.update(
        {"connected": False, "wake_count": 0, "last_wake": 0.0}
    )


class TestConnectDisconnectStatus:
    def test_connect_sets_connected_true(self):
        ch = VoiceLocalChannel(wakeword_model="dummy.onnx")
        ch.connect()
        assert permission_routes.get_voice_status_snapshot()["connected"] is True

    def test_connect_without_model_does_not_set_connected(self):
        ch = VoiceLocalChannel(wakeword_model="")  # leer -> Status=ERROR
        ch.connect()
        assert permission_routes.get_voice_status_snapshot()["connected"] is False

    def test_disconnect_sets_connected_false(self):
        ch = VoiceLocalChannel(wakeword_model="dummy.onnx")
        ch.connect()
        assert permission_routes.get_voice_status_snapshot()["connected"] is True
        ch.disconnect()
        assert permission_routes.get_voice_status_snapshot()["connected"] is False


class TestWakeEventCounter:
    @pytest.mark.asyncio
    async def test_wake_increments_counter(self):
        """Wenn Wake-Word erkannt wird, wake_count steigt + last_wake gesetzt."""
        ch = VoiceLocalChannel(wakeword_model="dummy.onnx")

        # Voll-Mock-Pfad damit kein echtes Mic angesprochen wird
        fake_detector = MagicMock()
        fake_detector.process.return_value = (True, 0.9)
        fake_stt = MagicMock()
        fake_stt.transcribe.return_value = MagicMock(text="x", language="de")

        with patch(
            "openjarvis.channels.voice_local.WakeWordDetector",
            return_value=fake_detector,
        ), patch(
            "openjarvis.channels.voice_local._mic_chunk_iter",
            return_value=iter([b"\x00" * 2560]),
        ), patch(
            "openjarvis.channels.voice_local.record_until_silence",
            return_value=b"\x00" * 1600,
        ), patch(
            "openjarvis.channels.voice_local._get_stt_backend",
            return_value=fake_stt,
        ):
            before = permission_routes.get_voice_status_snapshot()["wake_count"]
            await ch._listen_once()
            after = permission_routes.get_voice_status_snapshot()
        assert after["wake_count"] == before + 1
        assert after["last_wake"] > 0
