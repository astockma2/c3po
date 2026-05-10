# Permission Gate

Stage-2-Komponente fuer kanal-aware Tool-Call-Permissions im C3PO-Voice-Agent.
Vor jedem sensiblen Tool-Call laeuft eine 3-Stufen-Pruefung:

| Stufe     | Verhalten                                                  |
|-----------|------------------------------------------------------------|
| `free`    | Sofort `granted`, ohne Rueckfrage. Z.B. `calendar.upcoming`. |
| `confirm` | Tray-Dialog mit Ja/Nein-Klick. Z.B. `mail.send`.            |
| `admin`   | Tray-Dialog mit PIN-Eingabe (Windows Credential Manager).   |
| `denied`  | Sofort abgelehnt mit Grund.                                 |

Tools, die nicht in `permissions.toml` stehen, werden default-deny abgelehnt.

## Architektur

```
+---------------+       +-----------------+       +---------------+
| Channel       |       | PermissionGate  |       | Tray-Daemon   |
| (voice_local, |       | (Server)        |       | (Win Process) |
|  telegram, …) |       |                 |       |               |
+-------+-------+       +--------+--------+       +-------+-------+
        |                        |                        |
        | check(tool, args, ch)  |                        |
        +----------------------->+                        |
        |                        | bus.publish(           |
        |                        |   PERMISSION_*_REQUESTED|
        |                        |   prompt_id, tool, args,|
        |                        |   channel)              |
        |                        +----------------------->+
        | <--needs_confirm/pin   |                        | confirm/pin_dialog.show
        |    (prompt_id)         |                        |
        |                        |                        | user clicks
        |                        |                        |
        |                        | POST /permission/      | <--+
        |                        |  respond/{prompt_id}   |
        |                        | <----------------------+
        |                        | gate.confirm(pid, resp)|
        |                        | -> Future-resolve      |
        |                        | bus.publish(           |
        |                        |   PERMISSION_RESOLVED) |
        | <----awaits future-----+                        |
        |   granted=True/False   |                        |
        |                        |                        |
   tool laeuft                   |                        |
   (oder nicht)                  | audit.log(             |
                                 |   PERMISSION_GRANTED)  |
                                 v                        |
                            +----+-----+                  |
                            | Audit-DB |                  |
                            | (Hash-   |                  |
                            |  Chain)  |                  |
                            +----------+                  |
```

## Klassen

### `PermissionGate`

```python
class PermissionGate:
    def __init__(
        self,
        *,
        config_path: Path,                    # permissions.toml
        admin_whitelist_path: Path | None = None,
        pin_check: Callable[[str], bool] | None = None,
        bus: EventBus | None = None,
        audit: AuditLogger | None = None,
        default_timeout: float = 30.0,
    ): ...

    async def check(
        self, tool_name: str, args: dict, *, channel: str
    ) -> PermissionResult: ...

    async def confirm(self, prompt_id: str, response: str) -> bool: ...
```

`PermissionResult` ist ein frozen Dataclass mit den States `granted`,
`denied`, `needs_confirm`, `needs_pin` und Properties `is_granted` /
`is_pending`.

### Race-Schutz

`PermissionGate._pending` ist ein `dict[str, (Future, kind)]`, geschuetzt
durch `self._lock` (asyncio.Lock). Jeder neue `check()`-Call mit Confirm/Admin
erzeugt eine UUID4 prompt_id und legt das Future unter Lock ab. `confirm()`
und der `_auto_decline()`-Watcher poppen unter Lock und pruefen ob das
Future schon `done()` ist - so kann immer nur einer "gewinnen".

### Auto-Decline

Pro pending Anfrage wird `_auto_decline(prompt_id)` als Background-Task
gestartet. Nach `default_timeout` Sekunden (default 30) popt der Watcher
unter Lock und resolved das Future zu `False`, falls noch nicht resolved.
Das schreibt einen `PERMISSION_DENIED`-Audit-Eintrag mit `reason="timeout"`.

## Konfiguration

### `permissions.toml`

```toml
[tools]
# Free - kein Dialog
"calendar.upcoming" = "free"
"time.now"          = "free"
"hello.greet"       = "free"

# Confirm - Tray-Dialog mit Ja/Nein
"mail.send"         = "confirm"
"messaging.send"    = "confirm"
"shell.exec"        = "confirm"
"browser.click"     = "confirm"

# Admin - PIN-Pflicht (zusaetzlich admin_whitelist.toml)
"admin.reboot"      = "admin"
"admin.shutdown"    = "admin"
"admin.cleanup"     = "admin"

# Denied - explizit verboten
"shell.format_disk" = "denied"
```

### `admin_whitelist.toml`

```toml
[admin]
tools = [
    "admin.reboot",
    "admin.shutdown",
    "admin.cleanup",
]
```

Tools, die `level = "admin"` haben aber NICHT in der Whitelist stehen,
werden sofort abgelehnt - keine PIN-Anfrage. Dadurch kann man die
Permission-Stufe pro Tool dynamisch wechseln, aber Whitelist als zweiten
Schutzwall behalten.

### Server-Konfig per ENV

```bash
export OPENJARVIS_PERMISSIONS_CONFIG=/etc/c3po/permissions.toml
export OPENJARVIS_ADMIN_WHITELIST=/etc/c3po/admin_whitelist.toml
```

`create_app()` liest diese ENV-Variablen, baut den PermissionGate-Singleton
in `app.state.permission_gate` und mountet die Permission-Routen. Ohne
ENV bleibt der Gate `None` und nichts aendert sich am Server-Verhalten -
backwards-compatible.

## HTTP-API

### `POST /permission/respond/{prompt_id}`

Body: `{"response": "yes"}` (Confirm) oder `{"response": "1234"}` (PIN).

```json
HTTP 200
{"granted": true, "prompt_id": "abc-..."}
```

`HTTP 404` wenn die `prompt_id` unbekannt oder schon aufgeloest ist.

### `GET /audit/log?limit=100&event_type=permission_granted`

```json
HTTP 200
{
  "events": [
    {
      "timestamp": 1747830352.341,
      "event_type": "permission_granted",
      "action_taken": "granted",
      "preview": {
        "tool": "mail.send",
        "channel": "voice_local",
        "args": {"to": "x@y"},
        "prompt_id": "abc-..."
      }
    },
    ...
  ]
}
```

### `GET /voice/status`

```json
HTTP 200
{"connected": false, "wake_count": 0, "last_wake": 0.0}
```

Wird vom voice_local-Channel via `update_voice_status(...)` gepflegt.

## Tray-Daemon

`desktop/main.py` (eigener Prozess, gestartet beim Windows-Login):

- `EventRouter` dispatched Server-Events nach Type:
  `permission_confirm_requested` -> `confirm_dialog.confirm_dialog(tool, args)`
  `permission_pin_requested`     -> `pin_dialog.pin_dialog(tool, args)`
- `ServerClient.respond(prompt_id, response)` POSTet an `/permission/respond/{id}`
- Eigentliche GUI in `desktop/tray.py` (PyQt6) und `desktop/{confirm,pin}_dialog.py`
  (tkinter)
- PIN ist im Windows Credential Manager (Service `c3po-admin`,
  Username `admin-pin`); `desktop/keyring_helper.py` verwaltet
  set/get/verify.

## Audit-Hash-Chain

Permission-Events werden in der bestehenden `security/audit.py`-SQLite-DB
mit Merkle-Hash-Chain gespeichert (drei neue `SecurityEventType`-Werte:
`PERMISSION_REQUESTED`, `PERMISSION_GRANTED`, `PERMISSION_DENIED`).

`AuditLogger.verify_chain()` prueft die Kette nach Manipulationen.
`content_preview` ist JSON mit `{tool, channel, args, prompt_id, reason?}`.

## Cutover-Smoke-Test

`scripts/permission_smoke_test.py` spielt den Backend-Pfad in-process
durch:

```
$ ./.venv/Scripts/python.exe scripts/permission_smoke_test.py
[1/4] Tempfiles + PermissionGate ...
    OK gate ready, audit ready
[2/4] check() simuliert Voice-Tool-Call ...
    OK needs_confirm, prompt_id=...
[3/4] simulierter Tray-Klick 'Ja' via gate.confirm() ...
    OK granted=True
[4/4] Audit-Log Verifikation ...
    OK 2 Permission-Events, Hash-Chain intakt
        - permission_granted action='granted'
        - permission_requested action='awaiting_confirm'

STAGE-2-CUTOVER OK: PermissionGate-Pipeline funktioniert end-to-end.
```
