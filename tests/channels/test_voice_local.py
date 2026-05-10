"""Integration-Tests fuer VoiceLocalChannel."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openjarvis.channels._stubs import ChannelMessage, ChannelStatus
from openjarvis.channels.voice_local import VoiceLocalChannel
from openjarvis.core.registry import ChannelRegistry


@pytest.fixture(autouse=True)
def _register_voice_local():
    """Re-register after any registry clear (Channel-Tests-Konvention)."""
    if not ChannelRegistry.contains("voice_local"):
        ChannelRegistry.register_value("voice_local", VoiceLocalChannel)


def test_channel_id_is_voice_local():
    from openjarvis.channels.voice_local import VoiceLocalChannel
    ch = VoiceLocalChannel(
        wakeword_model="dummy.onnx",
        wake_name="hey_jarvis_v0.1",
        tts_model_dir="piper-models",
    )
    assert ch.channel_id == "voice_local"


def test_status_starts_disconnected():
    from openjarvis.channels.voice_local import VoiceLocalChannel
    ch = VoiceLocalChannel(
        wakeword_model="dummy.onnx",
        wake_name="hey_jarvis_v0.1",
        tts_model_dir="piper-models",
    )
    assert ch.status() == ChannelStatus.DISCONNECTED


def test_send_writes_audio_via_tts():
    """send(content=...) ruft TTS-Backend, _play_audio bekommt die Bytes."""
    from openjarvis.channels.voice_local import VoiceLocalChannel

    fake_tts_result = MagicMock()
    fake_tts_result.audio = b"FAKEWAV"
    fake_tts_result.sample_rate = 22050

    with patch(
        "openjarvis.channels.voice_local._get_tts_backend"
    ) as mock_get_tts, patch(
        "openjarvis.channels.voice_local._play_audio"
    ) as mock_play:
        mock_get_tts.return_value.synthesize.return_value = fake_tts_result

        ch = VoiceLocalChannel(
            wakeword_model="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            tts_model_dir="piper-models",
        )
        ok = ch.send(channel="voice_local", content="Hallo Welt")

    assert ok is True
    mock_get_tts.return_value.synthesize.assert_called_once()
    mock_play.assert_called_once()
    args, _ = mock_play.call_args
    assert args[0] == b"FAKEWAV"


def test_text_normalizer_runs_before_tts():
    """Markdown-Text wird vor TTS normalisiert (z.B. **fett** -> fett)."""
    from openjarvis.channels.voice_local import VoiceLocalChannel

    captured = {}

    def fake_synth(text, **kw):
        captured["text"] = text
        m = MagicMock()
        m.audio = b"x"
        m.sample_rate = 22050
        return m

    with patch(
        "openjarvis.channels.voice_local._get_tts_backend"
    ) as mock_get_tts, patch(
        "openjarvis.channels.voice_local._play_audio"
    ):
        mock_get_tts.return_value.synthesize.side_effect = fake_synth

        ch = VoiceLocalChannel(
            wakeword_model="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            tts_model_dir="piper-models",
        )
        ch.send(channel="voice_local", content="Hallo **Welt**.")

    assert "**" not in captured["text"]
    assert "Welt" in captured["text"]


def test_send_returns_false_on_tts_error():
    """Wenn TTS-Backend wirft, send() returnt False statt zu crashen."""
    from openjarvis.channels.voice_local import VoiceLocalChannel

    with patch(
        "openjarvis.channels.voice_local._get_tts_backend"
    ) as mock_get_tts, patch(
        "openjarvis.channels.voice_local._play_audio"
    ) as mock_play:
        mock_get_tts.return_value.synthesize.side_effect = RuntimeError("boom")

        ch = VoiceLocalChannel(
            wakeword_model="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            tts_model_dir="piper-models",
        )
        ok = ch.send(channel="voice_local", content="egal")

    assert ok is False
    mock_play.assert_not_called()


def test_list_channels_returns_voice_local_only():
    from openjarvis.channels.voice_local import VoiceLocalChannel
    ch = VoiceLocalChannel(
        wakeword_model="dummy.onnx",
        wake_name="hey_jarvis_v0.1",
        tts_model_dir="piper-models",
    )
    assert ch.list_channels() == ["voice_local"]


def test_on_message_registers_handler():
    from openjarvis.channels.voice_local import VoiceLocalChannel
    ch = VoiceLocalChannel(
        wakeword_model="dummy.onnx",
        wake_name="hey_jarvis_v0.1",
        tts_model_dir="piper-models",
    )
    handler = MagicMock()
    ch.on_message(handler)
    assert ch._message_handler is handler


def test_disconnect_sets_status():
    from openjarvis.channels.voice_local import VoiceLocalChannel
    ch = VoiceLocalChannel(
        wakeword_model="dummy.onnx",
        wake_name="hey_jarvis_v0.1",
        tts_model_dir="piper-models",
    )
    ch.connect()
    assert ch.status() == ChannelStatus.CONNECTED
    ch.disconnect()
    assert ch.status() == ChannelStatus.DISCONNECTED


def test_registry_has_voice_local():
    """Decorator registriert die Klasse in ChannelRegistry."""
    import openjarvis.channels.voice_local  # noqa: F401  (Trigger Registry)
    from openjarvis.core.registry import ChannelRegistry

    cls = ChannelRegistry.get("voice_local")
    assert cls.__name__ == "VoiceLocalChannel"


def test_zero_arg_construction_for_contract():
    """Contract: VoiceLocalChannel() ohne Args muss konstruierbar sein."""
    ch = VoiceLocalChannel()
    assert ch.status() == ChannelStatus.DISCONNECTED


def test_connect_without_wakeword_model_sets_error():
    """Ohne wakeword_model bleibt Channel im ERROR-Status (graceful)."""
    ch = VoiceLocalChannel()
    ch.connect()
    assert ch.status() == ChannelStatus.ERROR


@pytest.mark.asyncio
async def test_listen_once_calls_handler_on_wake():
    """Wenn WakeWord triggert, soll record_until_silence + STT laufen, dann handler."""
    fake_handler = MagicMock(return_value="Antwort an User")

    fake_detector = MagicMock()
    fake_detector.process.side_effect = [
        (False, 0.1),
        (False, 0.2),
        (True, 0.8),
        (False, 0.0),
    ]

    fake_stt = MagicMock()
    fake_stt.transcribe.return_value = MagicMock(
        text="hallo jarvis",
        language="de",
    )

    chunks_iter = iter([b"\x00\x00" * 1280] * 4)

    with patch(
        "openjarvis.channels.voice_local.WakeWordDetector",
        return_value=fake_detector,
    ), patch(
        "openjarvis.channels.voice_local._mic_chunk_iter",
        return_value=chunks_iter,
    ), patch(
        "openjarvis.channels.voice_local.record_until_silence",
        return_value=b"\x00\x00" * 16000,
    ), patch(
        "openjarvis.channels.voice_local._get_stt_backend",
        return_value=fake_stt,
    ), patch(
        "openjarvis.channels.voice_local._get_tts_backend"
    ) as mock_tts, patch(
        "openjarvis.channels.voice_local._play_audio"
    ):
        mock_tts.return_value.synthesize.return_value = MagicMock(
            audio=b"x", sample_rate=22050
        )
        ch = VoiceLocalChannel(
            wakeword_model="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            tts_model_dir="piper-models",
        )
        ch.on_message(fake_handler)
        await ch._listen_once()

    fake_handler.assert_called_once()
    msg = fake_handler.call_args[0][0]
    assert isinstance(msg, ChannelMessage)
    assert msg.content == "hallo jarvis"
    assert msg.channel == "voice_local"
    assert msg.metadata.get("language") == "de"
    fake_stt.transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_listen_once_without_wake_returns_silently():
    """Wenn kein Wake-Word triggert (Generator erschoepft), kein Handler-Call."""
    fake_handler = MagicMock()
    fake_detector = MagicMock()
    fake_detector.process.return_value = (False, 0.1)

    chunks_iter = iter([b"\x00\x00" * 1280] * 3)

    with patch(
        "openjarvis.channels.voice_local.WakeWordDetector",
        return_value=fake_detector,
    ), patch(
        "openjarvis.channels.voice_local._mic_chunk_iter",
        return_value=chunks_iter,
    ):
        ch = VoiceLocalChannel(
            wakeword_model="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            tts_model_dir="piper-models",
        )
        ch.on_message(fake_handler)
        await ch._listen_once()

    fake_handler.assert_not_called()


@pytest.mark.asyncio
async def test_listen_once_skips_send_when_handler_returns_none():
    """Handler kann None zurueckgeben - dann KEIN TTS-Output."""
    fake_handler = MagicMock(return_value=None)
    fake_detector = MagicMock()
    fake_detector.process.side_effect = [(True, 0.9)]
    fake_stt = MagicMock()
    fake_stt.transcribe.return_value = MagicMock(text="ok", language="de")

    with patch(
        "openjarvis.channels.voice_local.WakeWordDetector",
        return_value=fake_detector,
    ), patch(
        "openjarvis.channels.voice_local._mic_chunk_iter",
        return_value=iter([b"\x00\x00" * 1280]),
    ), patch(
        "openjarvis.channels.voice_local.record_until_silence",
        return_value=b"\x00\x00" * 16000,
    ), patch(
        "openjarvis.channels.voice_local._get_stt_backend",
        return_value=fake_stt,
    ), patch(
        "openjarvis.channels.voice_local._play_audio"
    ) as mock_play:
        ch = VoiceLocalChannel(
            wakeword_model="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            tts_model_dir="piper-models",
        )
        ch.on_message(fake_handler)
        await ch._listen_once()

    fake_handler.assert_called_once()
    mock_play.assert_not_called()
