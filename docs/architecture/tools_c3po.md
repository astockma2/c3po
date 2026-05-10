# C3PO Tools — PermissionGate-Verdrahtung im ToolExecutor

**Stage:** 3 (Tools)
**Stand:** 2026-05-10 (Task 1 — Architektur-Entscheidung)
**Code-Referenz:** [src/openjarvis/tools/_stubs.py](../../src/openjarvis/tools/_stubs.py), [src/openjarvis/security/permission_gate.py](../../src/openjarvis/security/permission_gate.py)

## Ziel

39 Tools (time, hello, windows, mail, calendar, browser, messaging, admin) bekommen
**zentral** eine Permission-Pruefung — **eine** Stelle im Code, nicht 39× pro Tool.

## Aufrufer-Kartografie (Step 2)

`ToolExecutor.execute(tool_call: ToolCall) -> ToolResult` ist **synchron**. Alle 16 internen
Aufruf-Stellen rufen sie aus unterschiedlichen Kontexten:

| Aufrufer | Sync/Async | Hinweise |
|---|---|---|
| `agents/deep_research.py:339` | sync | direkt im Step-Loop |
| `agents/monitor_operative.py:289,333` | sync | im observe/act-Loop |
| `agents/morning_digest.py:139,217` | sync | digest_collect + tts |
| `agents/native_openhands.py:346,374,393` | sync | im Tool-Loop |
| `agents/native_react.py:241` | sync | ReAct-Loop |
| `agents/operative.py:182` | sync | Operative-Step |
| `agents/orchestrator.py:145,298,347` | sync, parallel ueber ThreadPool | Orchestrator-Tool-Loop |
| `agents/rlm.py:310` | sync | RLM-Step |
| `learning/intelligence/orchestrator/environment.py:84` | sync | RL-Environment |
| `mcp/server.py:266` | sync | MCP-Server |
| `skills/executor.py:92` | sync | Skill-Step |
| `workflow/engine.py:252` | sync | Workflow-Engine |
| `server/agent_manager_routes.py:721` | **monkey-patched** | DR-Agent-Tracking |

**Befund:** Alle Aufrufer sind synchron. Nur der **VoiceLocalChannel-`_listen_loop`** (Stage 1)
laeuft in einem asyncio-Loop und wuerde indirekt `executor.execute()` aufrufen, wenn der
Voice-Channel-Tool-Loop in Stage 4 verdrahtet wird.

## Permission-Hook im Dispatcher

### Variantenvergleich

**Variante A — Sync bleibt, Loop-Adapter** (gewaehlt)
- `ToolExecutor.execute()` bleibt sync.
- Neuer Adapter `PermissionGateAdapter` kapselt async→sync-Brücke.
- ctor-Param `permission_gate: PermissionGate | None = None` und `permission_loop: AbstractEventLoop | None = None`.
- Wenn `permission_loop` gesetzt: `asyncio.run_coroutine_threadsafe(gate.check(...), loop).result(timeout=…)`
- Wenn nicht: `asyncio.run(gate.check(...))` (frischer Loop pro Aufruf — fuer sync-Agents).
- **Vorteil:** Bestehende 16 Aufrufer brechen NICHT.
- **Nachteil:** Mit asyncio.run() wird pro Tool-Call ein neuer Loop aufgemacht. Das ist
  okay, weil Permission-Checks nicht hot-path sind. Falls hot-path gebraucht: `permission_loop` setzen.

**Variante B — Separater AsyncToolDispatcher**
- Verworfen: 16 Aufrufer muessten umgeschrieben werden, oder beide Klassen koexistieren.

**Variante C — Alles auf async**
- Verworfen: 16+ Files brechen, riesige Test-Suite muss umgestellt werden.

### Entscheidung: Variante A

Begruendung in einer Zeile: minimaler Bestands-Eingriff, Test-isolierbar via Adapter,
asyncio.run() ist okay weil Permission-Checks selten genug sind.

### Hook-Position in `ToolExecutor.execute()`

```
1. Lookup Tool im Registry         (existing)
2. Parse arguments JSON             (existing)
3. Boundary guard                   (existing)
4. RBAC capability check            (existing)
5. Taint check                      (existing)
6. >>> NEU: PermissionGate-Hook <<< (Stage 3)
7. Confirmation check (legacy spec.requires_confirmation)  (existing)
8. Emit start event                 (existing)
9. Execute mit timeout              (existing)
10. Emit end event                  (existing)
```

**Wichtig:** Position 6 — nach Capability/Boundary/Taint, vor dem alten
`spec.requires_confirmation`-Pfad. Der alte Pfad bleibt erhalten als Fallback fuer
Tools, die noch nicht in `permissions.toml` stehen, aber `spec.requires_confirmation = True`
gesetzt haben.

### Channel-Kontext

`ToolCall` bekommt ein optionales Feld `channel: str = ""`. Aufrufer (Voice-Channel,
Engine-Loop, Telegram-Channel) setzen es. Wenn leer und Permission-Gate gesetzt, wird
`channel="unknown"` an `gate.check()` weitergegeben — landet im Audit-Log.

## Permission-Matrix (Stage 3 final)

| Block | Tools | free | confirm | admin |
|---|---|---|---|---|
| Time/Hello | 3 | 3 | 0 | 0 |
| Windows | 6 | 3 | 3 (open_app, close_app, kill_process) | 0 |
| Mail | 4 | 3 | 1 (send) | 0 |
| Calendar | 3 | 3 | 0 | 0 |
| Browser | 8 | 5 | 3 (close_tab, click, fill) | 0 |
| Messaging | 5 | 1 (last_received) | 4 (alle send) | 0 |
| Admin | 10 | 0 | 0 | 10 |
| **Total** | **39** | **18** | **11** | **10** |

Verifiziert durch [tests/tools/c3po/test_permissions_config.py](../../tests/tools/c3po/test_permissions_config.py).

## Test-Strategie

| Test-Klasse | Was testet sie | Mock-Pattern |
|---|---|---|
| `test_dispatcher_permission_gate.py` | Hook in ToolExecutor | MagicMock fuer PermissionGate |
| `tests/tools/c3po/test_*.py` | Pro Tool-Block | Connector-Aufrufe mocken |
| Subprocess-Tools (windows, admin) | NIEMALS echt aufrufen | `subprocess.run`/`Popen` immer gemockt |
| `scripts/tools_smoke_test.py` | E2E mit echten Permissions | manueller Voice-Test, nicht in CI |

## Risiken & Frueh-Erkennung

| ID | Risiko | Frueh erkennbar in |
|---|---|---|
| R-3.1 | sync/async-Bridge leakt Threads | Task 3 (Hook-Tests) |
| R-3.2 | Subprocess-Test fuehrt echten Befehl aus | Task 5/10 — Test-Reviewer pruefen |
| R-3.3 | Permission-Eintrag fehlt fuer ein Tool | Task 12 — alle 39 in permissions.toml |
| R-3.4 | LLM-Tool-Loop ruft mehr als max_tool_calls | Task 13 (Live-Test) |
