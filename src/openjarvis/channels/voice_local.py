"""Voice-Local Channel - lokaler Mic+Speaker-Input/Output.

Architektur (vollstaendig erst nach Task 16):
- listen()-Loop laeuft als Hintergrund-Task wenn connect() gerufen wurde.
- Loop hoert Mic per WakeWordDetector ab.
- Bei Wake-Word: record_until_silence aus _audio.py.
- STT (faster-whisper) transkribiert.
- ChannelHandler-Callback wird mit ChannelMessage gerufen.
- Handler-Returnwert (string) wird per send() durch TTS gesprochen.

In Task 15 ist der Loop noch ein Stub - dieser Commit liefert nur
das BaseChannel-Interface plus den TTS-Output-Pfad in send().
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from openjarvis.channels._stubs import (
    BaseChannel,
    ChannelHandler,
    ChannelMessage,
    ChannelStatus,
)
from openjarvis.core.registry import ChannelRegistry, SpeechRegistry, TTSRegistry
from openjarvis.speech._audio import record_until_silence
from openjarvis.speech.text_normalizer import normalize_for_tts
from openjarvis.speech.wakeword import WakeWordDetector

logger = logging.getLogger(__name__)


def _get_tts_backend(name: str = "piper", *, model_dir: str = "piper-models"):
    """Wrapper damit Tests gemockt werden koennen.

    Konstruktor-Argumente sind backend-spezifisch:
    - "piper" braucht model_dir
    - "gemini" liest GOOGLE_API_KEY/GEMINI_API_KEY aus ENV
    - andere: zero-arg
    """
    cls = TTSRegistry.get(name)
    if cls is None:
        raise RuntimeError(f"TTS-Backend '{name}' nicht registriert")
    if name == "piper":
        return cls(model_dir=model_dir)
    return cls()  # gemini_tts und andere: ENV-basierte Auth, zero-arg


def _pcm_to_wav(pcm: bytes, *, sample_rate: int = 16000) -> bytes:
    """Wrap rohe int16-mono-PCM-Bytes in einen WAV-Container.

    record_until_silence liefert rohes PCM, faster-whisper/av braucht
    aber einen kompletten Container - sonst InvalidDataError.
    """
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _get_stt_backend(
    name: str = "faster-whisper",
    *,
    model_size: str = "base",
    device: str = "auto",
    compute_type: str = "float16",
):
    """Wrapper fuer SpeechRegistry-Lookup, mockbar.

    Registry-Key ist mit Bindestrich (`faster-whisper`) registriert,
    nicht Underscore.

    device="auto" waehlt CUDA wenn verfuegbar - auf reinen CPU-Maschinen
    waere "cpu" + compute_type="int8" die robuste Wahl.
    """
    cls = SpeechRegistry.get(name)
    if cls is None:
        raise RuntimeError(f"STT-Backend '{name}' nicht registriert")
    return cls(model_size=model_size, device=device, compute_type=compute_type)


def _mic_chunk_iter(*, sample_rate: int = 16000, chunk_samples: int = 1280):
    """Endloser Generator fuer Wake-Word-Chunks (1280 samples = 80 ms @ 16k).

    In Tests gemockt.
    """
    import sounddevice as sd

    with sd.RawInputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=chunk_samples,
    ) as stream:
        while True:
            data, _ = stream.read(chunk_samples)
            yield bytes(data)


def _play_audio(audio_bytes: bytes, sample_rate: int) -> None:
    """Spielt WAV-Bytes ueber die Default-Audio-Out-Karte.

    Resampelt linear auf die native Rate des Default-Output-Geraets,
    weil viele Realtek-Treiber 22050 Hz nicht sauber hochrechnen
    (Symptom: zerrt/abgehackt). Fuer Tests gemockt.
    """
    import io
    import wave

    import numpy as np
    import sounddevice as sd

    with wave.open(io.BytesIO(audio_bytes), "rb") as w:
        frames = w.readframes(w.getnframes())
        src_rate = w.getframerate()

    audio_np = np.frombuffer(frames, dtype=np.int16)

    try:
        device_rate = int(sd.query_devices(kind="output")["default_samplerate"])
    except Exception:
        device_rate = src_rate

    if device_rate != src_rate and len(audio_np) > 1:
        ratio = device_rate / src_rate
        new_len = int(len(audio_np) * ratio)
        old_x = np.linspace(0.0, 1.0, num=len(audio_np), endpoint=False)
        new_x = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
        audio_np = np.interp(new_x, old_x, audio_np.astype(np.float32)).astype(np.int16)
        play_rate = device_rate
    else:
        play_rate = src_rate

    sd.play(audio_np, samplerate=play_rate, blocking=True)


@ChannelRegistry.register("voice_local")
class VoiceLocalChannel(BaseChannel):
    """Lokaler Voice-Channel - Mic in, Speaker out."""

    channel_id = "voice_local"

    def __init__(
        self,
        *,
        wakeword_model: str = "",
        wake_name: str = "hey_jarvis_v0.1",
        tts_model_dir: str = "piper-models",
        tts_voice: str = "de_DE-thorsten_emotional-medium",
        tts_backend_name: str = "piper",
        stt_model_size: str = "base",
        stt_device: str = "auto",
        stt_compute_type: str = "float16",
        stt_language: str = "",
    ) -> None:
        self._wakeword_model = wakeword_model
        self._wake_name = wake_name
        self._tts_model_dir = tts_model_dir
        self._tts_voice = tts_voice
        self._tts_backend_name = tts_backend_name
        self._stt_model_size = stt_model_size
        self._stt_device = stt_device
        self._stt_compute_type = stt_compute_type
        self._stt_language = stt_language
        self._status = ChannelStatus.DISCONNECTED
        self._message_handler: Optional[ChannelHandler] = None
        self._listen_task: Optional[asyncio.Task] = None

    def connect(self) -> None:
        if not self._wakeword_model:
            logger.warning("voice_local: kein wakeword_model konfiguriert")
            self._status = ChannelStatus.ERROR
            return
        self._status = ChannelStatus.CONNECTED
        logger.info("voice_local connected (mic-loop noch nicht aktiv)")

    def disconnect(self) -> None:
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
        self._status = ChannelStatus.DISCONNECTED

    def send(
        self,
        channel: str,
        content: str,
        *,
        conversation_id: str = "",
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        try:
            normalized = normalize_for_tts(content)
            tts = _get_tts_backend(
                self._tts_backend_name,
                model_dir=self._tts_model_dir,
            )
            result = tts.synthesize(normalized, voice_id=self._tts_voice)
            _play_audio(result.audio, result.sample_rate)
            return True
        except Exception:
            logger.exception("TTS-Ausgabe fehlgeschlagen")
            return False

    def status(self) -> ChannelStatus:
        return self._status

    def list_channels(self) -> List[str]:
        return ["voice_local"]

    def on_message(self, handler: ChannelHandler) -> None:
        self._message_handler = handler

    async def _listen_once(self) -> None:
        """Eine Wake-Word-Runde: chunks lesen bis Wake oder Generator leer.

        Bei Wake: record_until_silence -> STT -> handler -> ggf. send().
        """
        detector = WakeWordDetector(
            model_path=self._wakeword_model,
            wake_name=self._wake_name,
            threshold=0.5,
        )
        chunks = _mic_chunk_iter(sample_rate=16000, chunk_samples=1280)
        for chunk in chunks:
            is_wake, _conf = detector.process(chunk)
            if not is_wake:
                continue

            pcm = record_until_silence(
                sample_rate=16000,
                chunk_ms=30,
                silence_ms=800,
                vad_aggressiveness=2,
                max_seconds=10,
            )
            wav = _pcm_to_wav(pcm, sample_rate=16000)
            stt = _get_stt_backend(
                model_size=self._stt_model_size,
                device=self._stt_device,
                compute_type=self._stt_compute_type,
            )
            stt_kwargs = {"format": "wav"}
            if self._stt_language:
                stt_kwargs["language"] = self._stt_language
            result = stt.transcribe(wav, **stt_kwargs)

            if self._message_handler is None:
                return

            msg = ChannelMessage(
                channel="voice_local",
                sender="local_mic",
                content=result.text,
                metadata={"language": result.language},
            )
            response = self._message_handler(msg)
            if response:
                self.send(channel="voice_local", content=response)
            return

    async def _listen_loop(self) -> None:
        """Endlos-Loop. Wird beim connect() als Background-Task gestartet."""
        while self._status == ChannelStatus.CONNECTED:
            try:
                await self._listen_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Fehler im voice_local-Loop, Restart in 1s")
                await asyncio.sleep(1)


__all__ = ["VoiceLocalChannel"]
