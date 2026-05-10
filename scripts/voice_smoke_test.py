"""Manueller Voice-Smoke-Test fuer Stufe 1.

Voraussetzungen:
- pip install -e ".[c3po-voice]" (im aktivierten venv)
- piper-models/de_DE-thorsten_emotional-medium.onnx + .json
- piper-models/openwakeword/hey_jarvis_v0.1.onnx
- Mikrofon + Lautsprecher aktiv

Ablauf:
1. Skript starten -> "lausche..." erscheint
2. "Hey Jarvis" sagen
3. Etwas hinterher sprechen (z.B. "Hallo Andre")
4. Erwartet: Konsole zeigt erkannten Text, Lautsprecher echot zurueck
5. Ctrl+C beendet
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from openjarvis.channels._stubs import ChannelMessage
from openjarvis.channels.voice_local import VoiceLocalChannel

# Imports triggern Registry-Anmeldung der Backends:
import openjarvis.speech.piper_tts  # noqa: F401
import openjarvis.speech.faster_whisper  # noqa: F401
import openjarvis.speech.gemini_tts  # noqa: F401


# Windows: stdout ist per Default cp1252 - Umlaute aus deutscher Spracherkennung
# (z.B. "fuer" -> "fuer"/"fuer" mit Sonderzeichen) crashen sonst mit UnicodeEncodeError.
# UTF-8 erzwingen, errors="replace" als Sicherheitsnetz.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def print_flush(*args, **kwargs) -> None:
    """print() mit zwingendem Flush - im Hintergrund-Subprocess landen
    sonst nur logger.info-Lines im Output, prints bleiben im Buffer."""
    kwargs.setdefault("flush", True)
    print(*args, **kwargs)


WAKEWORD_MODEL = "piper-models/openwakeword/hey_jarvis_v0.1.onnx"
TTS_MODEL_DIR = "piper-models"
TTS_VOICE = "de_DE-thorsten_emotional-medium"


def _check_files() -> bool:
    """Pre-flight: alle benoetigten Dateien da, openwakeword-Hilfsmodelle ggf. nachladen."""
    missing = []
    for path in (
        WAKEWORD_MODEL,
        f"{TTS_MODEL_DIR}/{TTS_VOICE}.onnx",
        f"{TTS_MODEL_DIR}/{TTS_VOICE}.onnx.json",
    ):
        if not Path(path).exists():
            missing.append(path)
    if missing:
        print_flush("FEHLER: folgende Dateien fehlen:")
        for p in missing:
            print_flush(f"  - {p}")
        return False

    # openwakeword braucht melspectrogram.onnx + embedding_model.onnx
    # unter <site-packages>/openwakeword/resources/models/. Erste-Run-Auto-Download.
    import openwakeword
    oww_models_dir = (
        Path(openwakeword.__file__).parent / "resources" / "models"
    )
    if not (oww_models_dir / "melspectrogram.onnx").exists():
        print_flush("Lade openwakeword-Hilfsmodelle (einmalig, ~17 MB)...")
        from openwakeword.utils import download_models
        download_models(model_names=[])
        print_flush("Hilfsmodelle geladen.")
    return True


def echo_handler(msg: ChannelMessage) -> str:
    print_flush(f"\n>> Verstanden: {msg.content!r} (lang={msg.metadata.get('language')})")
    return f"Du hast gesagt: {msg.content}"


def _build_brain_handler(loop: asyncio.AbstractEventLoop):
    """Stage-4-Handler: build_voice_brain mit Claudi-Proxy + PermissionGate.

    Wird nur gebaut wenn ``$env:C3PO_VOICE_BRAIN = "1"``. Sonst nutzt der
    Smoke-Test den simplen echo_handler (Stage-1-Verhalten).
    """
    from pathlib import Path

    from openjarvis.agents.voice_brain import build_voice_brain
    from openjarvis.security.permission_gate import PermissionGate

    # Tools registrieren
    import openjarvis.tools.c3po  # noqa: F401

    config_dir = Path(__file__).resolve().parents[1] / "configs" / "c3po"
    gate = PermissionGate(
        config_path=config_dir / "permissions.toml",
        admin_whitelist_path=config_dir / "admin_whitelist.toml",
    )
    brain = build_voice_brain(
        model="claude-haiku-4-5",
        permission_gate=gate,
        permission_loop=loop,
        max_turns=4,
    )

    def _wrapped(msg: ChannelMessage) -> str:
        print_flush(
            f"\n>> Verstanden: {msg.content!r} "
            f"(lang={msg.metadata.get('language')})"
        )
        print_flush("   -> denke nach (Claudi-Proxy)...")
        response = brain(msg)
        if not response:
            response = "Ich habe keine Antwort."
        print_flush(f"<< {response[:200]}{'...' if len(response) > 200 else ''}")
        return response

    return _wrapped


async def main() -> int:
    if not _check_files():
        return 1

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    print_flush("Lade Modelle (faster-whisper laedt beim ersten Wake-Word ~150 MB)...")
    ch = VoiceLocalChannel(
        wakeword_model=WAKEWORD_MODEL,
        wake_name="hey_jarvis_v0.1",
        tts_model_dir=TTS_MODEL_DIR,
        tts_voice="Charon",
        tts_backend_name="gemini_tts",
        # CPU + int8: laeuft ohne CUDA-DLLs, schnell genug fuer Smoke-Test.
        stt_device="cpu",
        stt_compute_type="int8",
        # Sprache fest setzen - ohne das halluziniert Whisper-base
        # bei kurzem Sprechen gerne englischen Quatsch.
        stt_language="de",
    )

    # Stage-4-Brain optional: nur wenn C3PO_VOICE_BRAIN=1 gesetzt ist.
    # Sonst Stage-1-Echo, damit der alte Smoke-Test funktional bleibt.
    use_brain = os.environ.get("C3PO_VOICE_BRAIN", "0").lower() in ("1", "true", "yes")
    if use_brain:
        loop = asyncio.get_running_loop()
        handler = _build_brain_handler(loop)
        print_flush("[Stage 4] Voice-Brain aktiv (Claudi-Proxy + PermissionGate).")
    else:
        handler = echo_handler
        print_flush("[Stage 1] Echo-Handler aktiv. Fuer Voice-Brain: $env:C3PO_VOICE_BRAIN = '1'")
    ch.on_message(handler)
    ch.connect()
    print_flush("\nlausche... sag 'Hey Jarvis' und dann etwas. Ctrl+C zum Beenden.")

    try:
        # _listen_loop ist async, aber _listen_once enthaelt blocking
        # sounddevice-Reads. Wir lassen es einfach laufen - Ctrl+C
        # schickt KeyboardInterrupt, der die innere for-Schleife verlaesst.
        await ch._listen_loop()
    except KeyboardInterrupt:
        print_flush("\nBeende auf Wunsch.")
    finally:
        ch.disconnect()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
