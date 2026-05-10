"""openWakeWord-Wrapper fuer C3PO.

Laedt ONNX-Modell, vergleicht eingehende Audio-Chunks gegen ein
Wake-Word und liefert (is_wake, confidence). Mic-Loop wird vom
Aufrufer organisiert (siehe channels/voice_local).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)


def _load_model(model_path: str):
    """Wrapper damit Tests den Modell-Loader mocken koennen."""
    from openwakeword.model import Model
    return Model(
        wakeword_models=[model_path],
        inference_framework="onnx",
    )


class WakeWordDetector:
    """Wrappt openWakeWord fuer kontinuierliche Inference auf Mic-Chunks.

    Parameters
    ----------
    model_path : str
        Pfad zur Wake-Word-ONNX (z.B. piper-models/openwakeword/hey_jarvis_v0.1.onnx)
    wake_name : str
        Schluesselname im predict()-Output (z.B. "hey_jarvis_v0.1")
    threshold : float
        Confidence-Schwelle fuer is_wake=True. Default 0.5.
    """

    def __init__(self, *, model_path: str, wake_name: str, threshold: float = 0.5) -> None:
        if not Path(model_path).exists() and not model_path.startswith("dummy"):
            logger.warning("Wake-Word-Modell nicht gefunden: %s", model_path)
        self._model = _load_model(model_path)
        self._wake_name = wake_name
        self._threshold = threshold
        self._expected_chunk_bytes = 1280 * 2  # 1280 samples × int16
        self._size_warned = False

    def process(self, audio_chunk: bytes) -> Tuple[bool, float]:
        """Gibt (is_wake, confidence) fuer einen 16kHz int16 chunk zurueck.

        openWakeWord erwartet typischerweise 1280-sample chunks (80ms @ 16kHz).
        """
        if len(audio_chunk) == 0:
            return (False, 0.0)
        if len(audio_chunk) != self._expected_chunk_bytes and not self._size_warned:
            logger.warning(
                "WakeWordDetector: chunk has %d bytes (expected %d). "
                "openWakeWord internal buffers may produce garbage. "
                "Verify your mic loop yields 1280-sample chunks at 16kHz.",
                len(audio_chunk),
                self._expected_chunk_bytes,
            )
            self._size_warned = True
        audio_np = np.frombuffer(audio_chunk, dtype=np.int16)
        result = self._model.predict(audio_np)
        confidence = float(result.get(self._wake_name, 0.0))
        return (confidence >= self._threshold, confidence)


__all__ = ["WakeWordDetector"]
