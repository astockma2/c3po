# C3PO Cockpit-Lite (Stage 5)

**Stand:** 2026-05-10, Stage 5 fertig auf `feat/stage-5-cockpit-lite` (Merge steht aus).

## Was Cockpit-Lite leistet

Browserbasierte Visualisierung der Permission-Routen + Voice-Channel-Status. Vanilla-HTML/CSS/JS, kein Build-Schritt, kein npm.

**URL:** `http://localhost:8000/cockpit/`

## Sektionen

| Section | Quelle | Polling |
|---|---|---|
| Offene Permission-Anfragen | `GET /permission/pending` | alle 3s |
| Voice-Status | `GET /voice/status` | alle 3s |
| Audit-Log (letzte 50) | `GET /audit/log?limit=50` | alle 3s |

## Aktionen

- Click "Ja" / "Nein" -> `POST /permission/respond/{prompt_id}` mit `{"response": "yes"|"no"}`
- PIN-Eingabe -> `POST /permission/respond/{prompt_id}` mit `{"response": "<pin>"}`

## Voice-Status-Updates aus dem Channel

`VoiceLocalChannel.connect()` und `.disconnect()` rufen `update_voice_status(connected=...)`. Bei jedem erkannten Wake-Word inkrementiert `_listen_once()` den `wake_count` und setzt `last_wake = time.time()`. Cockpit zeigt das in der Voice-Sektion live.

## Files

| Datei | Verantwortung |
|---|---|
| `src/openjarvis/server/cockpit_static/index.html` | 3 Sektionen + Header mit Online-Indicator |
| `src/openjarvis/server/cockpit_static/cockpit.css` | Dark-Cyan-Theme (`--bg:#0a1929`, `--cyan:#00e5ff`) |
| `src/openjarvis/server/cockpit_static/cockpit.js` | `fetch`-Polling, DOM-Updates, Button-Handler |
| `src/openjarvis/server/app.py` | Mount `/cockpit` mit `html=True`, VOR dem Stanford-SPA-Catch-All |
| `src/openjarvis/server/permission_routes.py` | Neuer Endpoint `GET /permission/pending` (Stage 5) |

**Warum `cockpit_static/` und nicht `static/cockpit/`?** Der `static/`-Ordner ist gitignored (Build-Output des Stanford-Chat-Frontends). Cockpit-Lite ist in Git eingecheckt und braucht einen eigenen Ordner.

## ReAct-Prompt-Override (deutsch)

Andre's Setup nutzt einen deutschen ReAct-System-Prompt:
`~/.openjarvis/agents/native_react/system_prompt.md`.

- **Quelle im Repo:** `configs/c3po/agents/native_react/system_prompt.md`
- **Installer:** `python scripts/install_prompt_override.py`
- **Aenderungen am Prompt -> Voice-Brain neu starten**, damit `load_system_prompt_override` ihn neu liest.

**Wichtig fuer Format-Slots:** Der Prompt wird mit `.format(tool_descriptions=..., skill_examples=...)` befuellt. Literale Curly-Braces (z.B. in JSON-Beispielen) muessen **doppelt** geschrieben werden: `{{"when": "today"}}`. Sonst KeyError beim Laden.

Mit dem deutschen Override:
- "lies meine Mails" -> LLM ruft `mail.list_unread` zuverlaessig
- "wie spaet ist es?" -> LLM ruft `time.now`
- Final Answer ist TTS-tauglich (kurze Saetze, keine Bullet-Listen)

## Bekannte Schwaechen

- **`_voice_status` ist modul-global** in `permission_routes.py`. Parallel laufende Tests koennen den Snapshot stoeren. Im Single-Process-Setup unkritisch; bei Multi-Worker (z.B. `uvicorn --workers 4`) muesste das auf Redis o.ae. ziehen.
- **Polling alle 3s** ist okay fuer Single-User. Bei vielen offenen Tabs / mehreren Usern lieber Server-Sent-Events oder WebSocket nachziehen.
- **CSRF/Auth fehlt komplett.** Cockpit-Endpoints sind nicht geschuetzt — alle Aufrufer mit Netzwerk-Zugriff auf `localhost:8000` koennen Permissions resolven oder den Audit-Log lesen. Bei LAN/WAN-Exposure unbedingt Reverse-Proxy mit Auth davorsetzen.
- **Path-Traversal-Schutz** kommt vom `StaticFiles`-Mount selbst (Starlette macht das korrekt). Das Cockpit selbst hat keine eigene Routing-Logik.
- **CockpitPending greift auf `gate._pending` und `gate._pending_meta` direkt zu** (private Attribute). Wenn das Gate jemals Locking verschaerft, muss ein `gate.snapshot_pending()`-Helper rausgezogen werden.

## Cutover-Beweis (Stage 5)

```powershell
$env:PYTHONPATH = "src"
$env:OPENJARVIS_PERMISSIONS_CONFIG = "configs/c3po/permissions.toml"
$env:OPENJARVIS_ADMIN_WHITELIST = "configs/c3po/admin_whitelist.toml"
./.venv/Scripts/jarvis.exe serve --port 8000
```

Browser auf `http://localhost:8000/cockpit/` -> Drei Sektionen sichtbar, Polling laeuft (DevTools Network-Tab zeigt `/permission/pending`, `/voice/status`, `/audit/log` alle 3s).

Parallel `python scripts/voice_brain_smoke_test.py` starten -> Audit-Log fuellt sich, Voice-Status updated. Wenn ein `confirm`-Tool gerufen wird, erscheint die Pending-Card im Cockpit; Click "Ja" loest sie auf.

## Naechste Etappe (Stage 6, optional)

- **Cutover von C3PO-legacy:** Windows-Autostart auf `jarvis serve + voice_smoke_test --brain` umbiegen. Legacy in Archiv.
- **Auth fuer Cockpit:** PIN-only-Login oder OAuth (falls Andre's Bot Dashboard die Auth schon hat).
- **WebSocket statt Polling:** Wenn das 3s-Polling-Latenz spuerbar wird.
- **Tauri-Frontend** (volles React/Tailwind statt Vanilla) — Andre's Vorhaben aus dem urspruenglichen Stage-5-Brainstorm. Cockpit-Lite ist explizit der Mini-Vorab-Schritt.
