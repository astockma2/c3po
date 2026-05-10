"""HTTP-Routen fuer Stage 2: Permission-Gate-Antworten + Audit-Log + Voice-Status.

Wird in `create_app` ueber `app.include_router(create_permission_router(...))`
eingebunden, mit den Singleton-Instanzen von `PermissionGate` und `AuditLogger`
aus `app.state`.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openjarvis.security.audit import AuditLogger
from openjarvis.security.permission_gate import PermissionGate


# Pydantic-Schema fuer den POST-Body
class RespondBody(BaseModel):
    response: str


# In-Memory-Snapshot fuer den /voice/status-Endpoint.
# voice_local-Channel kann das spaeter (Task 12+) aktualisieren via
# `update_voice_status(connected=True, wake_count=n, last_wake=ts)`.
_voice_status: Dict[str, Any] = {
    "connected": False,
    "wake_count": 0,
    "last_wake": 0.0,
}


def get_voice_status_snapshot() -> Dict[str, Any]:
    """Liefert das aktuelle Voice-Status-Dict."""
    return dict(_voice_status)


def update_voice_status(**kwargs: Any) -> None:
    """Wird vom voice_local-Channel gerufen wenn sich Status aendert."""
    _voice_status.update(kwargs)


def create_permission_router(
    *,
    gate: PermissionGate,
    audit: AuditLogger,
) -> APIRouter:
    """Erzeugt einen APIRouter mit /permission/respond, /audit/log, /voice/status."""
    router = APIRouter()

    @router.post("/permission/respond/{prompt_id}")
    async def post_respond(prompt_id: str, body: RespondBody) -> Dict[str, Any]:
        # Wir muessen schauen ob die prompt_id ueberhaupt bekannt ist.
        # gate.confirm() returnt False sowohl bei "unbekannt" als auch bei
        # "ablehnung" - fuer das HTTP-API differenzieren wir 404 vs 200.
        if prompt_id not in gate._pending:
            raise HTTPException(status_code=404, detail="prompt_id unbekannt oder bereits aufgeloest")
        granted = await gate.confirm(prompt_id, body.response)
        return {"granted": granted, "prompt_id": prompt_id}

    @router.get("/permission/pending")
    def get_pending() -> Dict[str, List[Dict[str, Any]]]:
        """Liefert die aktuell offenen Permission-Prompts (Stage 5 Cockpit)."""
        pending_list: List[Dict[str, Any]] = []
        for prompt_id, (_fut, kind) in gate._pending.items():
            meta = gate._pending_meta.get(prompt_id, {})
            pending_list.append(
                {
                    "prompt_id": prompt_id,
                    "kind": kind,
                    "tool": meta.get("tool", ""),
                    "channel": meta.get("channel", ""),
                    "args": meta.get("args", {}),
                }
            )
        return {"pending": pending_list}

    @router.get("/audit/log")
    def get_audit_log(limit: int = 100, event_type: str | None = None) -> Dict[str, List[Dict[str, Any]]]:
        events = audit.query(event_type=event_type, limit=limit)
        out: List[Dict[str, Any]] = []
        for ev in events:
            preview_payload: Any = ev.content_preview
            try:
                preview_payload = json.loads(ev.content_preview)
            except (ValueError, TypeError):
                pass
            out.append(
                {
                    "timestamp": ev.timestamp,
                    "event_type": ev.event_type.value,
                    "action_taken": ev.action_taken,
                    "preview": preview_payload,
                }
            )
        return {"events": out}

    @router.get("/voice/status")
    def get_voice_status() -> Dict[str, Any]:
        return get_voice_status_snapshot()

    return router


__all__ = [
    "create_permission_router",
    "get_voice_status_snapshot",
    "update_voice_status",
]
