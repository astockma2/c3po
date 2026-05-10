"""Tests fuer WakeWordDetector."""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


def test_detector_returns_confidence_above_threshold():
    """Detector sollte True liefern wenn Modell-Confidence > threshold."""
    from openjarvis.speech.wakeword import WakeWordDetector

    fake_model = MagicMock()
    fake_model.predict.return_value = {"hey_jarvis_v0.1": 0.7}

    with patch("openjarvis.speech.wakeword._load_model", return_value=fake_model):
        det = WakeWordDetector(
            model_path="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            threshold=0.5,
        )

    audio_chunk = np.zeros(1280, dtype=np.int16).tobytes()
    is_wake, confidence = det.process(audio_chunk)
    assert is_wake is True
    assert confidence == pytest.approx(0.7)


def test_detector_below_threshold_returns_false():
    from openjarvis.speech.wakeword import WakeWordDetector

    fake_model = MagicMock()
    fake_model.predict.return_value = {"hey_jarvis_v0.1": 0.3}

    with patch("openjarvis.speech.wakeword._load_model", return_value=fake_model):
        det = WakeWordDetector(
            model_path="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            threshold=0.5,
        )

    audio_chunk = np.zeros(1280, dtype=np.int16).tobytes()
    is_wake, confidence = det.process(audio_chunk)
    assert is_wake is False
    assert confidence == pytest.approx(0.3)


def test_detector_unknown_wake_name_returns_zero():
    """Wenn das Modell den wake_name nicht kennt, confidence=0."""
    from openjarvis.speech.wakeword import WakeWordDetector

    fake_model = MagicMock()
    fake_model.predict.return_value = {"alexa_v0.1": 0.9}

    with patch("openjarvis.speech.wakeword._load_model", return_value=fake_model):
        det = WakeWordDetector(
            model_path="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            threshold=0.5,
        )

    audio_chunk = np.zeros(1280, dtype=np.int16).tobytes()
    is_wake, confidence = det.process(audio_chunk)
    assert is_wake is False
    assert confidence == 0.0
