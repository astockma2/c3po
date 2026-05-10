"""Mic-Aufnahme + VAD-basiertes Schneiden bis Stille.

Wird vom voice_local-Channel genutzt, aber bewusst hardware-isoliert
um Tests gegen reine Audio-Bytes laufen zu lassen.
"""
from __future__ import annotations

import logging
from typing import Iterator

import webrtcvad

logger = logging.getLogger(__name__)


def _mic_frame_iter(
    sample_rate: int,
    chunk_ms: int,
    device: str = "",
) -> Iterator[bytes]:
    """Endlos-Generator der Mic-Frames als bytes liefert.

    Wird in Tests gemockt, damit kein echtes Mikro noetig ist.
    """
    import sounddevice as sd

    chunk_samples = int(sample_rate * chunk_ms / 1000)
    kwargs: dict = {
        "channels": 1,
        "samplerate": sample_rate,
        "dtype": "int16",
        "blocksize": chunk_samples,
    }
    if device:
        kwargs["device"] = device

    with sd.RawInputStream(**kwargs) as stream:
        while True:
            data, overflow = stream.read(chunk_samples)
            if overflow:
                logger.warning("Mic-Overflow; Frames verloren")
            yield bytes(data)


def record_until_silence(
    *,
    sample_rate: int = 16000,
    chunk_ms: int = 30,
    silence_ms: int = 800,
    vad_aggressiveness: int = 2,
    max_seconds: int = 10,
    device: str = "",
) -> bytes:
    """Nimmt Audio auf bis silence_ms ununterbrochene Stille folgt.

    Returns
    -------
    bytes
        16kHz mono int16 PCM-Audio-Bytes.
    """
    if chunk_ms not in (10, 20, 30):
        raise ValueError(f"chunk_ms muss 10/20/30 sein, war {chunk_ms}")

    vad = webrtcvad.Vad(vad_aggressiveness)
    silence_chunks_needed = silence_ms // chunk_ms
    max_chunks = (max_seconds * 1000) // chunk_ms

    frames: list[bytes] = []
    silence_run = 0
    voice_seen = False

    frame_iter = _mic_frame_iter(sample_rate, chunk_ms, device)
    for chunk_idx, frame in enumerate(frame_iter):
        frames.append(frame)
        is_voice = vad.is_speech(frame, sample_rate)

        if is_voice:
            voice_seen = True
            silence_run = 0
        else:
            silence_run += 1

        if voice_seen and silence_run >= silence_chunks_needed:
            break
        if chunk_idx + 1 >= max_chunks:
            break

    return b"".join(frames)


__all__ = ["record_until_silence"]
