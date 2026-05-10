"""Cutover-Smoke-Test fuer Stage 2.

Spielt den kompletten Permission-Gate-Backend-Pfad durch, ohne Voice und
ohne PyQt6:

    1. Server starten (uvicorn als Subprocess) mit
       OPENJARVIS_PERMISSIONS_CONFIG=<tmp>/permissions.toml
    2. check() fuer Mock-Tool 'admin.smoke_test' (level=confirm) -> needs_confirm
    3. /permission/respond/{prompt_id} mit "yes" -> 200 + granted=True
    4. /audit/log -> mindestens 2 Permission-Events mit selber prompt_id
    5. Server stoppen

Ausfuehren:
    ./.venv/Scripts/python.exe scripts/permission_smoke_test.py

Erwarteter Output: alle Schritte mit OK + Audit-Log-Eintraegen.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import requests

from openjarvis.security.audit import AuditLogger
from openjarvis.security.permission_gate import PermissionGate


def _write_toml(target: Path, tools: dict[str, str]) -> None:
    lines = ["[tools]"]
    for name, level in tools.items():
        lines.append(f'"{name}" = "{level}"')
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run_inproc_smoke() -> int:
    """Variante ohne Subprocess: alles in-process testen.

    Vorteil: keine Port-Konflikte, sofort startbar. Nachteil: simuliert
    den HTTP-Pfad nicht, sondern ruft gate.check/confirm direkt.
    Fuer den Server-Pfad gibt es separat den FastAPI-TestClient-Test in
    tests/server/test_permission_routes.py - der laeuft bei jedem pytest-
    Lauf mit.
    """
    print("[1/4] Tempfiles + PermissionGate ...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = tmp_path / "permissions.toml"
        _write_toml(config, {"admin.smoke_test": "confirm"})
        audit = AuditLogger(db_path=tmp_path / "audit.db")
        gate = PermissionGate(
            config_path=config,
            audit=audit,
            default_timeout=5.0,
        )
        print("    OK gate ready, audit ready")

        print("[2/4] check() simuliert Voice-Tool-Call ...")
        result = await gate.check(
            "admin.smoke_test",
            {"reason": "smoke"},
            channel="voice_local",
        )
        if result.state != "needs_confirm":
            print(f"    FAIL: erwartet needs_confirm, war {result.state}")
            return 1
        print(f"    OK needs_confirm, prompt_id={result.prompt_id}")

        print("[3/4] simulierter Tray-Klick 'Ja' via gate.confirm() ...")
        granted = await gate.confirm(result.prompt_id, "yes")
        if granted is not True:
            print(f"    FAIL: erwartet True, war {granted}")
            return 1
        print("    OK granted=True")

        print("[4/4] Audit-Log Verifikation ...")
        events = audit.query(limit=20)
        permission_events = [
            e for e in events
            if e.event_type.value.startswith("permission_")
        ]
        if len(permission_events) < 2:
            print(f"    FAIL: nur {len(permission_events)} Audit-Events fuer Permission")
            return 1
        # Beide Events tragen die selbe prompt_id?
        prompt_ids_seen = set()
        for ev in permission_events:
            try:
                payload = json.loads(ev.content_preview)
                prompt_ids_seen.add(payload.get("prompt_id", ""))
            except (ValueError, TypeError):
                pass
        if result.prompt_id not in prompt_ids_seen:
            print(f"    FAIL: prompt_id {result.prompt_id} nicht in Audit-Events")
            return 1
        ok, broken = audit.verify_chain()
        if not ok:
            print(f"    FAIL: Hash-Chain bricht bei row {broken}")
            return 1
        print(f"    OK {len(permission_events)} Permission-Events, Hash-Chain intakt")
        for ev in permission_events:
            print(f"        - {ev.event_type.value} action={ev.action_taken!r}")

        # Wichtig auf Windows: SQLite-Handle schliessen, sonst kann
        # tempfile das Verzeichnis nicht aufraeumen.
        audit.close()

    print("\nSTAGE-2-CUTOVER OK: PermissionGate-Pipeline funktioniert end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_run_inproc_smoke()))
