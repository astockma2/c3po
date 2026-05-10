"""Stage 3 Cutover-Smoke-Test: minimaler Tool-Loop mit PermissionGate.

Was dieser Script verifiziert:
- ToolExecutor mit PermissionGate baut sich ohne Fehler auf.
- Alle 39 Stage-3-Tools sind in der Registry.
- ``mail.list_unread`` als ``free``-Tool laeuft durch den Gate
  (im Mock-Modus mit gemocktem Gmail-Connector).
- ``mail.send`` als ``confirm``-Tool wartet auf eine Future, die wir hier
  programmatisch via ``gate.confirm(prompt_id, "yes")`` aufloesen.

Das ist KEIN Voice-Test — fuer "Andre spricht und C3PO antwortet" siehe
``scripts/voice_smoke_test.py`` (Stage 1). Hier geht's nur um den
Tool-Loop mit Permissions, ohne Mikro/TTS/STT/LLM.

Live-Modus:
    $env:C3PO_SMOKE_LIVE = "1"
    python scripts/tools_smoke_test.py

Mock-Modus (Default, ohne Gmail-Setup):
    python scripts/tools_smoke_test.py

Cutover-Kriterium aus Design-Dokument: "Voice-Test 'sag mir die Mails'
liefert echte Liste". Dieses Skript liefert die Liste, der Voice-Layer
ist in Stage 4 dran.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Pfade
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
CONFIG_DIR = REPO_ROOT / "configs" / "c3po"

# Erst nach sys.path-Setup importieren:
import openjarvis.tools.c3po  # noqa: F401 — triggert Tool-Registrierung
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolCall
from openjarvis.security.permission_gate import PermissionGate
from openjarvis.tools._stubs import ToolExecutor


def header(s: str) -> None:
    print(f"\n=== {s} ===")


def green(s: str) -> str:
    return f"\033[32m{s}\033[0m" if sys.stdout.isatty() else s


def red(s: str) -> str:
    return f"\033[31m{s}\033[0m" if sys.stdout.isatty() else s


def step(label: str, ok: bool, detail: str = "") -> None:
    icon = green("OK") if ok else red("FAIL")
    print(f"  [{icon}] {label}" + (f" — {detail}" if detail else ""))


async def _async_main(live: bool) -> int:
    failures = 0

    header("1. Tool-Registry-Inventur")
    keys = set(ToolRegistry.keys())
    expected_count = 39
    c3po_tools = [
        k for k in keys
        if k.split(".")[0] in {
            "time", "hello", "windows", "mail", "calendar",
            "browser", "telegram", "whatsapp", "signal", "slack",
            "messaging", "admin",
        }
    ]
    ok_count = len(c3po_tools) == expected_count
    step(
        f"Erwartet {expected_count} Stage-3-Tools",
        ok_count,
        f"gefunden: {len(c3po_tools)}",
    )
    if not ok_count:
        failures += 1

    header("2. PermissionGate-Setup")
    gate = PermissionGate(
        config_path=CONFIG_DIR / "permissions.toml",
        admin_whitelist_path=CONFIG_DIR / "admin_whitelist.toml",
    )
    step("permissions.toml + admin_whitelist.toml geladen", True)

    header("3. ToolExecutor mit Gate")
    # Wir nehmen nur die Tools die wir testen — sonst muss alles instanziierbar sein.
    mail_list = ToolRegistry.get("mail.list_unread")()
    mail_send = ToolRegistry.get("mail.send")()
    time_now = ToolRegistry.get("time.now")()

    executor = ToolExecutor(
        [mail_list, mail_send, time_now],
        permission_gate=gate,
        permission_loop=asyncio.get_running_loop(),
    )
    step("Executor mit PermissionGate + permission_loop", True)

    header("4. Free-Tool: time.now (im Worker-Thread, run_coroutine_threadsafe-Pfad)")
    # Wichtig: ``executor.execute()`` blockiert auf dem Permission-Check.
    # Wenn wir direkt im Haupt-Loop laufen, deadlockt run_coroutine_threadsafe
    # (es schickt Coros an genau diesen Loop, der schon blockiert).
    # Deshalb verlagern wir den Tool-Aufruf in einen Worker-Thread.
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        executor.execute,
        ToolCall(id="t1", name="time.now", arguments="{}", channel="smoke_test"),
    )
    step(
        "time.now success", result.success, f"output: {result.content[:80]}"
    )
    if not result.success:
        failures += 1

    header("5. Free-Tool durch Gate: mail.list_unread")
    if live:
        result = await loop.run_in_executor(
            None,
            executor.execute,
            ToolCall(
                id="t2",
                name="mail.list_unread",
                arguments='{"max_results": 5}',
                channel="smoke_test",
            ),
        )
        step(
            "mail.list_unread live", result.success,
            f"count: {(result.metadata or {}).get('count')}",
        )
    else:
        fake_connector = MagicMock()
        fake_connector.is_connected.return_value = True
        fake_connector.sync.return_value = iter([
            SimpleNamespace(
                doc_id="gmail:fake1",
                author="Andre <andre@astockma.de>",
                title="Stage 3 Test-Mail",
                content="Smoke-Test fuer Stage 3.",
                timestamp=datetime(2026, 5, 10, 14, 0),
                metadata={"labels": ["UNREAD", "INBOX"]},
            ),
            SimpleNamespace(
                doc_id="gmail:fake2",
                author="Nicole <nicole@example.com>",
                title="Zweite Test-Mail",
                content="Auch noch zu lesen.",
                timestamp=datetime(2026, 5, 10, 14, 5),
                metadata={"labels": ["UNREAD"]},
            ),
        ])

        def _run_list():
            with patch(
                "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
                return_value=fake_connector,
            ):
                return executor.execute(
                    ToolCall(
                        id="t2",
                        name="mail.list_unread",
                        arguments="{}",
                        channel="smoke_test",
                    )
                )

        result = await loop.run_in_executor(None, _run_list)
        step("mail.list_unread mock", result.success)
        if result.success:
            mails = json.loads(result.content)
            print(f"     -> {len(mails)} ungelesene Mails:")
            for m in mails:
                print(f"        - {m['from']}: {m['subject']}")
    if not result.success:
        failures += 1

    header("6. Confirm-Tool: mail.send (Tray-Dialog simuliert)")
    # Wir schiessen das Tool ab, dann resolve manuell mit "yes".
    send_args = json.dumps({
        "to": "andre@astockma.de",
        "subject": "Stage 3 Cutover",
        "body": "Stage 3 ist durchgelaufen.",
    })

    async def _confirm_when_pending():
        # Warte bis Gate ein pending hat, dann resolve
        for _ in range(100):
            if gate._pending:
                prompt_id = next(iter(gate._pending))
                await gate.confirm(prompt_id, "yes")
                return prompt_id
            await asyncio.sleep(0.05)
        return None

    # Den eigentlichen Tool-Call in einem Thread laufen lassen, damit der
    # confirm-Resolver in unserem Loop greifen kann.
    import functools

    def _run_send():
        # Wir wissen: mail.send ruft den Gmail-API-Pfad. Im Mock-Modus
        # patchen wir das Token + den API-Call weg, damit der Tool-Code
        # NACH dem Permission-OK durchlaeuft.
        with patch(
            "openjarvis.tools.c3po.mail_tools._read_gmail_token",
            return_value="fake-tok",
        ), patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.mail_tools._gmail_api_send_message",
            return_value={"id": "fake-send-id"},
        ):
            return executor.execute(
                ToolCall(
                    id="t3",
                    name="mail.send",
                    arguments=send_args,
                    channel="smoke_test",
                )
            )

    loop = asyncio.get_running_loop()
    send_task = loop.run_in_executor(None, _run_send)
    confirm_task = asyncio.create_task(_confirm_when_pending())
    send_result, prompt_id = await asyncio.gather(send_task, confirm_task)

    step(
        f"Gate stellte prompt_id={prompt_id}",
        prompt_id is not None,
    )
    step(
        "mail.send nach 'yes' erfolgreich",
        send_result.success,
        f"detail: {send_result.content[:100]}",
    )
    if not send_result.success:
        failures += 1

    header("7. Confirm-Tool denied: gleicher Aufruf, diesmal 'no'")
    async def _decline_when_pending():
        for _ in range(100):
            if gate._pending:
                prompt_id = next(iter(gate._pending))
                await gate.confirm(prompt_id, "no")
                return prompt_id
            await asyncio.sleep(0.05)
        return None

    def _run_send_again():
        with patch(
            "openjarvis.tools.c3po.mail_tools._read_gmail_token",
            return_value="fake-tok",
        ), patch(
            "openjarvis.tools.c3po.mail_tools._get_gmail_connector",
            return_value=MagicMock(),
        ), patch(
            "openjarvis.tools.c3po.mail_tools._gmail_api_send_message",
            return_value={"id": "should-not-be-called"},
        ) as send_mock:
            r = executor.execute(
                ToolCall(
                    id="t4",
                    name="mail.send",
                    arguments=send_args,
                    channel="smoke_test",
                )
            )
            return r, send_mock.called

    send_task2 = loop.run_in_executor(None, _run_send_again)
    decline_task = asyncio.create_task(_decline_when_pending())
    (decline_result, send_called), _ = await asyncio.gather(send_task2, decline_task)

    step(
        "mail.send nach 'no' blockiert",
        decline_result.success is False and not send_called,
        f"content: {decline_result.content[:80]}",
    )
    if decline_result.success or send_called:
        failures += 1

    return failures


def main() -> int:
    live = os.environ.get("C3PO_SMOKE_LIVE", "0").lower() in ("1", "true", "yes")
    print(f"Modus: {'LIVE' if live else 'MOCK'}")
    failures = asyncio.run(_async_main(live))
    print()
    if failures == 0:
        print(green("STAGE-3-CUTOVER OK"))
        return 0
    print(red(f"STAGE-3-CUTOVER FAIL ({failures} Issues)"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
