# Voice-Brain (Stage 4)

**Stand:** 2026-05-10 — Stage 4 fertig auf `feat/stage-4-llm-loop` (Merge steht aus).

## Was Stage 4 liefert

Eine Brueckenkomponente, die den **Voice-Channel** (Stage 1) mit dem
**Tool-Loop** (Stage 3) verdrahtet, vermittelt durch einen LLM (Claude).

```
Mic → Wake-Word → STT (faster-whisper)
                       │
                       ▼
                  ChannelMessage
                       │
                       ▼   (run_in_executor — Deadlock-Schutz)
                  build_voice_brain()
                       │
                       ▼
                  NativeReActAgent (Thought/Action/Observation)
                       │
                       ▼
                  ClaudiProxyEngine → POST gemi.c3po42.de/api/chat/sync
                       │
                       ▼   (Action: tool_name + JSON)
                  ToolExecutor + PermissionGate
                       │
                       ▼   (39 Tools registriert, kuratiert auf ~29 fuer Voice)
                  Tool laeuft
                       │
                       ▼
                  Observation → naechster ReAct-Turn
                       │
                       ▼   (Final Answer)
                  AgentResult.content (deutscher Text)
                       │
                       ▼
                  VoiceLocalChannel.send() → TTS (Charon) → Lautsprecher
```

## Bausteine

| Modul | Verantwortung |
|---|---|
| `src/openjarvis/engine/claudi_proxy.py` | `ClaudiProxyEngine` — `InferenceEngine`-Subklasse. POST gegen `gemi.c3po42.de/api/chat/sync`. Kein API-Key noetig (OAuth ueber VPS-Service). |
| `src/openjarvis/agents/voice_brain.py` | `select_voice_tools()` + `build_voice_brain()`. Kuratiert die 29 Voice-tauglichen Tools (admin per Default raus). |
| `src/openjarvis/channels/voice_local.py` | Stage-1-Komponente, in Stage 4 erweitert um `run_in_executor`-Aufruf des Handlers. |
| `configs/c3po/settings.toml` `[voice_brain]` | `claudi_url`, `claudi_token`, `model`, `max_turns`, `tool_categories`. |
| `scripts/voice_brain_smoke_test.py` | Backend-Cutover-Beweis ohne Mikro. |
| `scripts/voice_smoke_test.py` (erweitert) | End-to-End mit echtem Mikro, optional `C3PO_VOICE_BRAIN=1`. |

## Warum Claudi-Proxy statt direkter Anthropic-API

Andre hat keinen `ANTHROPIC_API_KEY`, dafuer aber eine Claude-Max-Subscription. Der
VPS-Service `claudi-api.service` (Port 8085, Bearer `gemi2026`) wickelt OAuth ueber die
Claude-CLI ab und stellt einen einfachen Text-Completion-Endpoint bereit.

**Vorteile:**
- Kein API-Key in Andre's PC-Env, keine Pro-Call-Kosten.
- Single source of truth fuer Auth — gleiche Subscription wie das Bot Dashboard.

**Nachteile:**
- Latenz ~5-15 Sek pro Turn (VPS-Roundtrip + Opus 4.7 Inferenz). Multi-Turn-Loop kann 30s+ dauern.
- Kein Function-Calling-API — der Proxy liefert nur reinen Text. Wir nutzen **ReAct**
  (text-basiertes Thought/Action/Observation-Format), das genau dafuer designed ist.
- Server ignoriert den `model`-Hint und nutzt immer `claude-opus-4-7`. Der `model="claude-haiku-4-5"`-Default
  ist nur dokumentarisch — sobald der Proxy Modell-Routing kann, greift's automatisch.

## Latenzbudget (gemessen 2026-05-10)

| Schritt | Zeit |
|---|---|
| Wake-Word-Erkennung | <100ms |
| STT (faster-whisper base, CPU/int8) | 1-2s |
| ReAct-Turn 1 (Thought + Action) | 5-10s |
| Tool-Aufruf (z.B. mail.list_unread) | 1-3s |
| ReAct-Turn 2 (Final Answer) | 5-10s |
| TTS (Gemini Charon) | 2-4s |
| **Gesamt** | **~15-30s** |

Der Smoke-Test (Task 7) hat 30.2s gebraucht fuer "Lies meine Mails" → 50 echte
Gmail-Mails formatiert. Bei kuerzeren Queries ("Wie spaet ist es?") deutlich weniger,
sobald das LLM `time.now` zuverlaessig anspringt.

## Deadlock-Falle (von Stage 3 geerbt)

`ToolExecutor` mit `permission_loop=running_loop` deadlockt, wenn `executor.execute()`
synchron aus genau diesem Loop heraus gerufen wird (`run_coroutine_threadsafe` schickt
das Coro an einen Loop, der gerade blockiert).

**Loesung in Stage 4 Task 5:** `VoiceLocalChannel._listen_once` ruft den Handler via
`loop.run_in_executor(None, handler, msg)`. Damit landet `executor.execute()` in einem
**anderen** Thread als der Loop — `run_coroutine_threadsafe` an den `permission_loop`
funktioniert sauber, weil der Loop nicht blockiert ist.

## Bekannte Schwaechen

- **Tool-Calling-Selektion ist nicht 100% zuverlaessig.** Bei kurzen Queries
  ("Wie spaet ist es?") ruft das LLM `time.now` nicht immer auf, sondern erfindet
  eine Standard-Antwort. Bei "lies meine Mails" hat's funktioniert. Vermutlich
  hilft ein praeziserer System-Prompt — Hardening-Task.
- **`unittest.mock.patch` greift nicht im Worker-Thread.** Wenn ein Test den
  Gmail-Connector mockt, der Handler aber via `run_in_executor` laeuft, sieht der
  Worker-Thread das Modul-Symbol unverpatcht. Fuer Smoke-Tests harmlos (echter
  OAuth-Token funktioniert), fuer pytest-Mocks muss man entweder einen
  injizierbaren Connector-Param oder Modul-globale monkeypatches nutzen.
- **`agent._executor`-Ueberschreibung** greift in eine private API von
  `ToolUsingAgent`. Upstream-Merge mit Stanford-OpenJarvis koennte das brechen.
  Upstream-PR fuer `executor=`-kwarg im `__init__` waere die saubere Loesung.

## Stage-4-Cutover (verifiziert 2026-05-10)

- `scripts/voice_brain_smoke_test.py` (Backend): **STAGE-4-CUTOVER OK**
- 50 echte Gmail-Mails per `mail.list_unread`, formatiert als deutsche Liste.
- Latenz: 30.2s ueber den ganzen Multi-Turn-Loop.

**End-to-End-Mic-Test (`scripts/voice_smoke_test.py` mit `C3PO_VOICE_BRAIN=1`):**
manueller Test durch Andre — wird per Memory aktualisiert.

## Naechste Etappe

**Stage 5 (Frontend + Cutover):**
- OpenJarvis Tauri/React-Frontend aktivieren, an Permission-Routen anschliessen
  (Audit-Log, Voice-Status, Permissions-Editor).
- Cockpit-Lite als Fallback wenn Tauri zickt.
- Finale Umstellung von C3PO-legacy auf neuen Stack (Windows-Autostart umbiegen).

Optional vor Stage 5:
- ReAct-System-Prompt deutsch + tool-call-incentive verbessern.
- `select_voice_tools` lernt aus settings.toml `[voice_brain.tool_categories]`.
- Tray-Daemon im Voice-Smoke-Test mitstarten, damit `mail.send` etc. nutzbar werden.
