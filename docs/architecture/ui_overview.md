# C3PO UI-Overview

**Stand:** 2026-05-10. Stage 7 abgeschlossen.

C3PO hat zwei Web-Oberflaechen, beide auf demselben FastAPI-Server (Port 8000):

## 1. Stanford-Chat-UI (`/`)

**URL:** http://localhost:8000/

React/TypeScript-Frontend von Stanford-OpenJarvis. Voller Chat mit:
- Chat-History pro Modell
- Cost-Comparison (lokal vs. Cloud)
- System-Panel (Power/Energy/Tokens)
- Dashboard, Data Sources, Agents, Logs, Settings

**Modell-Auswahl:** ``claude-opus-4-7`` und ``claude-haiku-4-5`` (via Claudi-Proxy, kein API-Key noetig).

**Voraussetzungen:** `frontend/`-Build (Vite -> `src/openjarvis/server/static/`). Mit `./scripts/start_c3po.ps1` wird der Build automatisch gemacht wenn er fehlt.

**Wann nutzen:** Allgemeines Chatten, Modell-Vergleich, Settings-UI, Energie-Statistiken.

## 2. Cockpit-Lite (`/cockpit/`)

**URL:** http://localhost:8000/cockpit/

Vanilla-HTML/CSS/JS (Stage 5). Spezifisch fuer:
- Offene Permission-Anfragen (Ja/Nein/PIN)
- Voice-Status (Wake-Count, letzter Wake)
- Audit-Log (letzte 50 Events)

**Voraussetzungen:** Keine. Liegt in `src/openjarvis/server/cockpit_static/`, immer eingecheckt.

**Wann nutzen:** Wenn der Voice-Agent laeuft (`./scripts/start_c3po.ps1`) und du Permission-Prompts beantworten oder das Audit-Log einsehen willst.

## Wann welche?

| Use-Case | UI |
|---|---|
| "Schreib mir eine Mail" | Chat-UI (`/`) |
| "Hey Jarvis, lies meine Mails" (Voice) | Cockpit-Lite (`/cockpit/`) zeigt was passiert |
| Modell wechseln | Chat-UI |
| `mail.send`-Prompt beantworten | Cockpit-Lite |
| Token-Verbrauch ueber Zeit | Chat-UI -> Dashboard |
| Audit-Trail durchsuchen | Cockpit-Lite |

## Setup

```powershell
# Erststart oder nach git pull:
.\scripts\start_c3po.ps1
# Pre-Flight baut Frontend wenn noetig (~1-2 Min kalter Cache), dann Server + Voice-Brain.

# Manueller Frontend-Build (z.B. nach Frontend-Code-Aenderung):
.\scripts\setup_frontend.ps1

# Frontend-Build ueberspringen (z.B. wenn nur Voice-Backend gebraucht wird):
$env:C3PO_SKIP_FRONTEND = "1"
.\scripts\start_c3po.ps1
```

## Engine-Routing

Stanford-OpenJarvis trennt zwei Modell-Kategorien:
- **lokal** (Ollama, vLLM): erscheinen im Modell-Dropdown
- **cloud** (Anthropic-API, OpenAI): brauchen API-Keys in Settings -> Cloud Models

C3PO hat eine **dritte Kategorie**: Claudi-Proxy. Technisch eine Cloud-Engine (Claude-Modelle ueber VPS-OAuth), aber ohne API-Key-Setup. Damit das funktioniert, ist `ClaudiProxyEngine.is_c3po_custom = True` gesetzt, und `server/routes.py` umgeht den Stanford-Cloud-Routing-Pfad fuer solche Engines (siehe `_is_c3po_custom_engine()`).

**Wenn du eine andere C3PO-Custom-Engine bauen willst** (z.B. einen lokalen LLM-Tunnel): setz `is_c3po_custom = True` als Klassen-Attribut auf der `InferenceEngine`-Subklasse, und alle Routing-Sonderegeln greifen automatisch:

1. `GET /v1/models` filtert sie nicht als "cloud" raus
2. Streaming-Pfad nimmt `engine.stream()` statt `stream_cloud()` (kein API-Key noetig)
3. Streaming-Pfad nimmt auch nicht den `stream_local()`-Fallback (Ollama-hartkodiert)

## Bekannte Schwaechen

- **Stanford-Frontend kann das Cockpit-Lite-Voice-Status-Panel nicht anzeigen.** Wenn du Voice-Status sehen willst, oeffne `/cockpit/` separat.
- **Service-Worker cached aggressiv.** Nach Frontend-Code-Aenderung Ctrl+Shift+R im Browser (Hard-Refresh).
- **"Share Your Savings"-Maske kommt beim ersten Besuch.** Stanford-Telemetrie ("Mac Mini gewinnen"). "No Thanks" klicken.
- **PWA-Caching kann das alte Bundle bevorzugen.** Wenn UI nach Build nicht aktuell ist: in DevTools (F12) -> Application -> Service Workers -> Unregister, dann Hard-Refresh.

## Sicherheits-Hinweise

- **Kein Auth.** Server bindet per Default auf 127.0.0.1 (nicht von aussen erreichbar). Wenn du `--host 0.0.0.0` nutzt: vorher Auth ergaenzen oder Reverse-Proxy mit Basic-Auth davor.
- **Audit-Log ist offen.** Jeder mit Zugriff auf `localhost:8000` kann den Audit-Log lesen. Auf Single-User-Dev-PC unkritisch.
- **Permission-Prompts sind offen.** Wer im Cockpit "Ja" klickt, autorisiert Tools. PIN-Tools sind durch `admin_whitelist.toml` zusaetzlich geschuetzt, aber kein 2FA.
