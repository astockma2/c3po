"""Piper TTS Backend — lokales ONNX-basiertes TTS.

Voices werden ueber model_dir/<voice_id>.onnx + <voice_id>.onnx.json gefunden.
Andre's Modelle: de_DE-thorsten_emotional-medium, de_DE-pavoque-low.
"""
from __future__ import annotations

import io
import logging
import wave
from pathlib import Path
from typing import List

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

logger = logging.getLogger(__name__)

_DEFAULT_VOICE = "de_DE-thorsten_emotional-medium"


def _load_voice(model_path: Path):
    """Wrapper damit Tests gemockt werden koennen.

    Returns
    -------
    (PiperVoice, sample_rate)
    """
    from piper import PiperVoice

    voice = PiperVoice.load(str(model_path))
    sample_rate = voice.config.sample_rate
    return voice, sample_rate


def _synth_to_wav_bytes(voice, text: str, sample_rate: int) -> bytes:
    """Synthetisiert text mit voice und gibt WAV-Bytes (in-memory) zurueck.

    piper-tts >= 1.4.2: API ist `synthesize_wav(text, wav_file)`, das Format wird
    intern gesetzt. Die alte `synthesize(text, wav_writer)`-Signatur existiert
    nicht mehr (die liefert jetzt einen AudioChunk-Iterator).
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_writer:
        # synthesize_wav setzt nchannels/sampwidth/framerate selbst
        # (set_wav_format=True per Default).
        voice.synthesize_wav(text, wav_writer)
    return buf.getvalue()


@TTSRegistry.register("piper")
class PiperTTSBackend(TTSBackend):
    """Lokales ONNX-TTS via piper-tts.

    Modelle liegen in model_dir/<voice>.onnx + <voice>.onnx.json
    """

    backend_id = "piper"

    def __init__(self, *, model_dir: str = "piper-models") -> None:
        self._model_dir = Path(model_dir)

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "wav",
    ) -> TTSResult:
        if output_format != "wav":
            raise ValueError(
                f"PiperTTS unterstuetzt nur 'wav', nicht '{output_format}'"
            )
        voice_id = voice_id or _DEFAULT_VOICE
        model_path = self._model_dir / f"{voice_id}.onnx"
        if not model_path.exists():
            raise FileNotFoundError(f"Piper-Modell nicht gefunden: {model_path}")

        voice, sample_rate = _load_voice(model_path)
        wav_bytes = _synth_to_wav_bytes(voice, text, sample_rate)

        return TTSResult(
            audio=wav_bytes,
            format="wav",
            sample_rate=sample_rate,
            voice_id=voice_id,
        )

    def available_voices(self) -> List[str]:
        if not self._model_dir.exists():
            return []
        voices = []
        for onnx_file in self._model_dir.glob("*.onnx"):
            cfg = onnx_file.with_suffix(".onnx.json")
            if cfg.exists():
                voices.append(onnx_file.stem)
        return sorted(voices)

    def health(self) -> bool:
        return bool(self.available_voices())


__all__ = ["PiperTTSBackend"]
