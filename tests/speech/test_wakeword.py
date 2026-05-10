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


def test_detector_at_exact_threshold_is_wake():
    """confidence == threshold soll als Wake gelten (>= nicht >)."""
    from openjarvis.speech.wakeword import WakeWordDetector

    fake_model = MagicMock()
    fake_model.predict.return_value = {"hey_jarvis_v0.1": 0.5}

    with patch("openjarvis.speech.wakeword._load_model", return_value=fake_model):
        det = WakeWordDetector(
            model_path="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            threshold=0.5,
        )

    audio_chunk = (b"\x00\x00") * 1280
    is_wake, confidence = det.process(audio_chunk)
    assert is_wake is True
    assert confidence == pytest.approx(0.5)


def test_detector_handles_empty_chunk():
    """Leere Bytes liefern (False, 0.0), kein Crash."""
    from openjarvis.speech.wakeword import WakeWordDetector

    fake_model = MagicMock()
    fake_model.predict.return_value = {"hey_jarvis_v0.1": 0.9}  # sollte nie aufgerufen werden

    with patch("openjarvis.speech.wakeword._load_model", return_value=fake_model):
        det = WakeWordDetector(
            model_path="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            threshold=0.5,
        )

    is_wake, confidence = det.process(b"")
    assert is_wake is False
    assert confidence == 0.0
    fake_model.predict.assert_not_called()


def test_detector_warns_once_on_wrong_chunk_size(caplog):
    """Falsche Chunk-Groesse logt Warning, aber nur einmal."""
    import logging
    from openjarvis.speech.wakeword import WakeWordDetector

    fake_model = MagicMock()
    fake_model.predict.return_value = {"hey_jarvis_v0.1": 0.0}

    with patch("openjarvis.speech.wakeword._load_model", return_value=fake_model):
        det = WakeWordDetector(
            model_path="dummy.onnx",
            wake_name="hey_jarvis_v0.1",
            threshold=0.5,
        )

    # Falsche Groesse: 640 samples = 1280 bytes statt 2560
    bad_chunk = (b"\x00\x00") * 640

    with caplog.at_level(logging.WARNING, logger="openjarvis.speech.wakeword"):
        det.process(bad_chunk)
        det.process(bad_chunk)
        det.process(bad_chunk)

    warnings = [r for r in caplog.records if "chunk has" in r.message]
    assert len(warnings) == 1
