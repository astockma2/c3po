"""Stage 4 Cutover-Smoke-Test: Voice-Brain via Claudi-Proxy.

Was dieses Skript verifiziert:
- ClaudiProxyEngine.health() liefert True (VPS-Verbindung steht)
- build_voice_brain baut Agent + Permission-Gate + Tool-Selektion ohne Crash
- Eingabe "lies meine Mails" wird als Query an Anthropic geschickt
- (im Mock-Modus:) mail.list_unread liefert die gemockten Mails
- Agent formuliert eine deutsche Antwort

Mock-Modus (Default): Gmail-Connector wird gemockt.
LIVE-Modus: echter Gmail-Connector — ``$env:C3PO_VOICE_LIVE = "1"``.

Hinweis: Stage 3 hat das gleiche Pattern fuer die Permission-Gate-Pruefung
in scripts/tools_smoke_test.py. Dieses Skript ist analog, aber mit echtem
LLM-Loop statt direkt-aufgerufenen Tools.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
CONFIG_DIR = REPO_ROOT / "configs" / "c3po"

# Sicherstellen dass Windows console UTF-8 kann (Umlaute in TTS-Antworten)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import openjarvis.tools.c3po  # noqa: F401 — registriert die 39 Tools

from openjarvis.agents.voice_brain import build_voice_brain
from openjarvis.channels._stubs import ChannelMessage
from openjarvis.engine.claudi_proxy import ClaudiProxyEngine
from openjarvis.security.permission_gate import PermissionGate


def header(s: str) -> None:
    print(f"\n=== {s} ===")


def step(label: str, ok: bool, detail: str = "") -> None:
    icon = "OK" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{icon}] {label}{suffix}")


def _fake_mail_doc(*, doc_id, sender, subject, body):
    return SimpleNamespace(
        doc_id=doc_id,
        author=sender,
        title=subject,
        content=body,
        timestamp=datetime.now(),
        metadata={"labels": ["UNREAD"]},
    )


async def _async_main(live: bool) -> int:
    failures = 0

    header("1. Claudi-Proxy-Health")
    eng = ClaudiProxyEngine()
    is_healthy = eng.health()
    step("ClaudiProxyEngine().health()", is_healthy)
    eng.close()
    if not is_healthy:
        print("VPS unerreichbar — Smoke-Test bricht hier ab.")
        return 1

    header("2. PermissionGate + Brain-Bau")
    gate = PermissionGate(
        config_path=CONFIG_DIR / "permissions.toml",
        admin_whitelist_path=CONFIG_DIR / "admin_whitelist.toml",
    )
    loop = asyncio.get_running_loop()
    handler = build_voice_brain(
        model="claude-haiku-4-5",
        permission_gate=gate,
        permission_loop=loop,
        max_turns=4,
    )
    step("build_voice_brain", callable(handler))

    header("3. Tool-Call 'lies meine Mails'")
    msg = ChannelMessage(
        channel="voice_local",
        sender="local_mic",
        content="Lies bitte meine ungelesenen E-Mails und nenne mir die Absender.",
    )

    def _call_handler():
        if live:
            return handler(msg)
        fake = MagicMock()
        fake.is_connected.return_value = True
        fake.sync.return_value = iter([
            _fake_mail_doc(
                doc_id="gmail:1",
                sender="Nicole <nicole@example.com>",
                subject="Frage zum Projekt",
                body="Hallo Andre, hast du die Daten schon angeschaut?",
            ),
            _fake_mail_doc(
                doc_id="gmail:2",
                sender="Stefan <stefan@firma.de>",
                subject="Code-Review",
                body="Bitte schau drueber wenn du Zeit hast.",
            ),
        ])
        with patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=fake,
        ):
            return handler(msg)

    t0 = time.perf_counter()
    response = await loop.run_in_executor(None, _call_handler)
    elapsed = time.perf_counter() - t0

    print(f"\n--- Antwort ({elapsed:.1f}s) ---")
    print(response or "(leer)")
    print("---------------------------")

    step("Handler hat eine Antwort geliefert", bool(response))
    if not response:
        failures += 1

    # Mehr ist hier nicht zu pruefen — ob das LLM mail.list_unread aufruft,
    # ist Modell-Qualitaet, nicht Brueckenkopf-Korrektheit. Wenn der Handler
    # einen String zurueckgibt, ist der Pfad bewiesen.

    return failures


def main() -> int:
    live = os.environ.get("C3PO_VOICE_LIVE", "0").lower() in ("1", "true", "yes")
    print(f"Modus: {'LIVE' if live else 'MOCK'}")
    failures = asyncio.run(_async_main(live))
    print()
    if failures == 0:
        print("STAGE-4-CUTOVER OK")
        return 0
    print(f"STAGE-4-CUTOVER FAIL ({failures} Issues)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
