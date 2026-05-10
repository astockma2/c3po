"""Tests fuer PiperTTSBackend."""
from __future__ import annotations

import io
import wave
import pytest
from unittest.mock import MagicMock, patch


def _fake_wav_bytes() -> bytes:
    """Erzeugt eine 0.1-Sek-WAV bei 22050Hz mono."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 2205)
    return buf.getvalue()


def test_synthesize_returns_wav_bytes(tmp_path):
    from openjarvis.speech.piper_tts import PiperTTSBackend

    # Modell-File anlegen damit der existence-check passiert
    voice_id = "de_DE-thorsten_emotional-medium"
    (tmp_path / f"{voice_id}.onnx").touch()
    (tmp_path / f"{voice_id}.onnx.json").touch()

    with patch(
        "openjarvis.speech.piper_tts._load_voice",
        return_value=(MagicMock(), 22050),
    ), patch(
        "openjarvis.speech.piper_tts._synth_to_wav_bytes",
        return_value=_fake_wav_bytes(),
    ):
        backend = PiperTTSBackend(model_dir=str(tmp_path))
        result = backend.synthesize("Hallo Welt", voice_id=voice_id)

    assert result.audio.startswith(b"RIFF")
    assert result.format == "wav"
    assert result.sample_rate == 22050


def test_synthesize_uses_default_voice_when_voice_id_empty(tmp_path):
    from openjarvis.speech.piper_tts import PiperTTSBackend

    default_voice = "de_DE-thorsten_emotional-medium"
    (tmp_path / f"{default_voice}.onnx").touch()
    (tmp_path / f"{default_voice}.onnx.json").touch()

    with patch(
        "openjarvis.speech.piper_tts._load_voice",
        return_value=(MagicMock(), 22050),
    ), patch(
        "openjarvis.speech.piper_tts._synth_to_wav_bytes",
        return_value=_fake_wav_bytes(),
    ):
        backend = PiperTTSBackend(model_dir=str(tmp_path))
        result = backend.synthesize("Test")

    assert result.voice_id == default_voice


def test_synthesize_rejects_non_wav_format(tmp_path):
    from openjarvis.speech.piper_tts import PiperTTSBackend
    backend = PiperTTSBackend(model_dir=str(tmp_path))
    with pytest.raises(ValueError, match="unterstuetzt nur 'wav'"):
        backend.synthesize("hi", output_format="mp3")


def test_synthesize_raises_on_missing_model(tmp_path):
    from openjarvis.speech.piper_tts import PiperTTSBackend
    backend = PiperTTSBackend(model_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="Piper-Modell nicht gefunden"):
        backend.synthesize("hi", voice_id="nonexistent_voice")


def test_available_voices_lists_onnx_files(tmp_path):
    from openjarvis.speech.piper_tts import PiperTTSBackend

    (tmp_path / "de_DE-thorsten_emotional-medium.onnx").touch()
    (tmp_path / "de_DE-thorsten_emotional-medium.onnx.json").touch()
    (tmp_path / "de_DE-pavoque-low.onnx").touch()
    (tmp_path / "de_DE-pavoque-low.onnx.json").touch()

    backend = PiperTTSBackend(model_dir=str(tmp_path))
    voices = backend.available_voices()
    assert "de_DE-thorsten_emotional-medium" in voices
    assert "de_DE-pavoque-low" in voices


def test_available_voices_skips_onnx_without_config(tmp_path):
    from openjarvis.speech.piper_tts import PiperTTSBackend

    # nur ONNX, keine config -> sollte nicht gelistet werden
    (tmp_path / "broken.onnx").touch()

    backend = PiperTTSBackend(model_dir=str(tmp_path))
    assert backend.available_voices() == []


def test_health_returns_true_when_voices_available(tmp_path):
    from openjarvis.speech.piper_tts import PiperTTSBackend

    (tmp_path / "de_DE-thorsten_emotional-medium.onnx").touch()
    (tmp_path / "de_DE-thorsten_emotional-medium.onnx.json").touch()

    backend = PiperTTSBackend(model_dir=str(tmp_path))
    assert backend.health() is True


def test_health_false_for_missing_dir():
    from openjarvis.speech.piper_tts import PiperTTSBackend

    backend = PiperTTSBackend(model_dir="/does/not/exist")
    assert backend.health() is False
