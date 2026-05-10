"""Test: VoiceLocalChannel ruft handler im Worker-Thread auf, nicht direkt im asyncio-Loop.

Verhindert die Permission-Gate-Deadlock-Falle aus
docs/architecture/tools_c3po.md.
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.channels.voice_local import VoiceLocalChannel


@pytest.fixture(autouse=True)
def _register_voice_local():
    """conftest leert ChannelRegistry — re-register manually fuer diese Tests."""
    from openjarvis.core.registry import ChannelRegistry
    if not ChannelRegistry.contains("voice_local"):
        ChannelRegistry.register_value("voice_local", VoiceLocalChannel)
    yield


@pytest.mark.asyncio
async def test_handler_runs_in_executor_not_in_loop_thread():
    """Wenn _listen_once den handler ruft, laeuft handler in einem ANDEREN
    Thread als der asyncio-Loop selbst (sonst Deadlock-Risiko)."""
    handler_thread_box: dict = {}
    loop_thread_id = threading.get_ident()

    def handler(msg):
        handler_thread_box["tid"] = threading.get_ident()
        return "ok"

    ch = VoiceLocalChannel()
    ch.on_message(handler)

    fake_stt = MagicMock()
    fake_stt.transcribe.return_value = MagicMock(text="hallo", language="de")

    fake_detector = MagicMock()
    fake_detector.process.return_value = (True, 0.9)

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
    ), patch.object(ch, "send", return_value=True):
        await ch._listen_once()

    assert "tid" in handler_thread_box, "handler wurde nie aufgerufen"
    assert handler_thread_box["tid"] != loop_thread_id, (
        f"handler lief im SELBEN Thread wie der Loop (Deadlock-Falle!) "
        f"tid={handler_thread_box['tid']}"
    )


@pytest.mark.asyncio
async def test_handler_response_is_sent_back():
    """Wenn handler einen non-empty String zurueckgibt, wird send() aufgerufen."""
    sent: dict = {}

    def handler(msg):
        return "Es ist 14 Uhr."

    ch = VoiceLocalChannel()
    ch.on_message(handler)

    fake_stt = MagicMock()
    fake_stt.transcribe.return_value = MagicMock(text="wie spaet", language="de")
    fake_detector = MagicMock()
    fake_detector.process.return_value = (True, 0.9)

    def fake_send(*args, **kwargs):
        sent["content"] = kwargs.get("content") or (args[1] if len(args) > 1 else "")
        return True

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
    ), patch.object(ch, "send", side_effect=fake_send):
        await ch._listen_once()

    assert sent.get("content") == "Es ist 14 Uhr."


@pytest.mark.asyncio
async def test_no_handler_means_silent_return():
    """Ohne on_message-Handler darf _listen_once nicht crashen."""
    ch = VoiceLocalChannel()
    # KEIN on_message-Call

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
        # Darf einfach nichts tun, kein Exception
        await ch._listen_once()
