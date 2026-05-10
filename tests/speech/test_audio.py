"""Tests fuer den Mic-Helper."""
from __future__ import annotations
import numpy as np
import pytest
from unittest.mock import patch


def _silence_frame(duration_ms: int = 30, sample_rate: int = 16000) -> bytes:
    """16kHz mono int16 silence."""
    n = int(duration_ms * sample_rate / 1000)
    return (np.zeros(n, dtype=np.int16)).tobytes()


def _voice_frame(duration_ms: int = 30, sample_rate: int = 16000) -> bytes:
    """16kHz mono int16 mit Sinus-Ton (Voice-aehnlich)."""
    n = int(duration_ms * sample_rate / 1000)
    t = np.arange(n) / sample_rate
    audio = (np.sin(2 * np.pi * 440 * t) * 30000).astype(np.int16)
    return audio.tobytes()


def test_record_until_silence_stops_after_silence_window():
    """Recording stoppt nachdem 800ms Stille folgt."""
    from openjarvis.speech._audio import record_until_silence

    fake_frames = [_voice_frame() for _ in range(5)] + [_silence_frame() for _ in range(30)]
    fake_iter = iter(fake_frames)

    with patch("openjarvis.speech._audio._mic_frame_iter", return_value=fake_iter):
        audio_bytes = record_until_silence(
            sample_rate=16000, chunk_ms=30, silence_ms=800,
            vad_aggressiveness=2, max_seconds=10,
        )

    voice_chunk_size = len(_voice_frame())
    # webrtcvad klassifiziert die ersten ~3 Stille-Frames nach Sprache noch als
    # voice (interner Hangover), daher: 8 voice-erkannte Frames + 26 silence
    # zum Ausloesen des Breaks (silence_ms=800 / chunk_ms=30 = 26).
    expected_chunks = 8 + 26
    expected_bytes = expected_chunks * voice_chunk_size
    assert len(audio_bytes) == expected_bytes, (
        f"expected {expected_bytes} bytes (={expected_chunks} chunks), got {len(audio_bytes)}"
    )


def test_record_until_silence_respects_max_seconds():
    """Wenn nie Stille kommt, stoppt nach max_seconds."""
    from openjarvis.speech._audio import record_until_silence

    voice_chunk = _voice_frame()
    def endless():
        while True:
            yield voice_chunk

    with patch("openjarvis.speech._audio._mic_frame_iter", return_value=endless()):
        audio_bytes = record_until_silence(
            sample_rate=16000, chunk_ms=30, silence_ms=800,
            vad_aggressiveness=2, max_seconds=1,
        )

    assert 30000 <= len(audio_bytes) <= 35000


def test_record_until_silence_rejects_invalid_chunk_ms():
    """webrtcvad braucht 10/20/30ms-Frames."""
    from openjarvis.speech._audio import record_until_silence

    with pytest.raises(ValueError, match="chunk_ms muss 10/20/30 sein"):
        record_until_silence(
            sample_rate=16000, chunk_ms=25, silence_ms=800,
            vad_aggressiveness=2, max_seconds=1,
        )


def test_record_until_silence_rejects_invalid_sample_rate():
    """webrtcvad braucht 8000/16000/32000/48000 Hz."""
    from openjarvis.speech._audio import record_until_silence

    with pytest.raises(ValueError, match="sample_rate muss 8000/16000/32000/48000 sein"):
        record_until_silence(
            sample_rate=44100, chunk_ms=30, silence_ms=800,
            vad_aggressiveness=2, max_seconds=1,
        )
