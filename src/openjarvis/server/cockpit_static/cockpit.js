"use strict";

const POLL_INTERVAL_MS = 3000;
const AUDIT_LIMIT = 50;

const $ = (sel) => document.querySelector(sel);

function fmtTimestamp(ts) {
    if (!ts) return "—";
    const d = new Date(ts * 1000);
    return d.toLocaleString("de-DE", {
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        day: "2-digit", month: "2-digit",
    });
}

function eventTypeClass(type) {
    if (!type) return "";
    if (type.includes("granted")) return "event-granted";
    if (type.includes("denied")) return "event-denied";
    if (type.includes("requested")) return "event-requested";
    return "";
}

async function fetchJson(url) {
    try {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) return null;
        return await r.json();
    } catch (e) {
        return null;
    }
}

async function postJson(url, body) {
    try {
        const r = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        return r.ok ? await r.json() : null;
    } catch (e) {
        return null;
    }
}

function renderPending(data) {
    const list = $("#pending-list");
    const pending = (data && data.pending) || [];
    if (pending.length === 0) {
        list.innerHTML = '<p class="empty">Keine offenen Anfragen.</p>';
        return;
    }
    list.innerHTML = "";
    pending.forEach((p) => {
        const card = document.createElement("div");
        card.className = "prompt-card kind-" + p.kind;

        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = (p.kind === "pin" ? "Admin (PIN)" : "Bestaetigung") +
            " · Kanal: " + (p.channel || "?");
        card.appendChild(meta);

        const toolLine = document.createElement("div");
        const tool = document.createElement("span");
        tool.className = "tool";
        tool.textContent = p.tool;
        toolLine.appendChild(tool);
        card.appendChild(toolLine);

        const args = document.createElement("pre");
        args.className = "args";
        args.textContent = JSON.stringify(p.args || {}, null, 2);
        card.appendChild(args);

        const actions = document.createElement("div");
        actions.className = "actions";

        if (p.kind === "pin") {
            const input = document.createElement("input");
            input.type = "password";
            input.placeholder = "PIN";
            input.autocomplete = "off";
            actions.appendChild(input);
            const ok = document.createElement("button");
            ok.className = "confirm";
            ok.textContent = "PIN absenden";
            ok.onclick = () => respond(p.prompt_id, input.value);
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") respond(p.prompt_id, input.value);
            });
            actions.appendChild(ok);
        } else {
            const yes = document.createElement("button");
            yes.className = "confirm";
            yes.textContent = "Ja";
            yes.onclick = () => respond(p.prompt_id, "yes");
            actions.appendChild(yes);
            const no = document.createElement("button");
            no.className = "decline";
            no.textContent = "Nein";
            no.onclick = () => respond(p.prompt_id, "no");
            actions.appendChild(no);
        }
        card.appendChild(actions);
        list.appendChild(card);
    });
}

async function respond(promptId, response) {
    const result = await postJson("/permission/respond/" + promptId, { response });
    if (!result) {
        alert("Fehler beim Senden der Antwort. Pruefe Server-Logs.");
        return;
    }
    refresh();
}

function renderVoiceStatus(data) {
    if (!data) return;
    $("#voice-connected").textContent = data.connected ? "verbunden" : "getrennt";
    $("#voice-wake-count").textContent = data.wake_count || 0;
    $("#voice-last-wake").textContent = data.last_wake
        ? fmtTimestamp(data.last_wake)
        : "noch nichts gehoert";
}

function renderAudit(data) {
    const tbody = $("#audit-rows");
    const events = (data && data.events) || [];
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty">Keine Events.</td></tr>';
        return;
    }
    tbody.innerHTML = "";
    events.forEach((ev) => {
        const tr = document.createElement("tr");

        const tdTime = document.createElement("td");
        tdTime.textContent = fmtTimestamp(ev.timestamp);
        tr.appendChild(tdTime);

        const tdType = document.createElement("td");
        tdType.className = eventTypeClass(ev.event_type);
        tdType.textContent = ev.event_type;
        tr.appendChild(tdType);

        const tdAction = document.createElement("td");
        tdAction.textContent = ev.action_taken || "";
        tr.appendChild(tdAction);

        const tdDetails = document.createElement("td");
        tdDetails.className = "details";
        const detailsStr = typeof ev.preview === "string"
            ? ev.preview
            : JSON.stringify(ev.preview || {});
        tdDetails.textContent = detailsStr;
        tdDetails.title = detailsStr;
        tr.appendChild(tdDetails);

        tbody.appendChild(tr);
    });
}

function setOnline(online) {
    const indicator = $("#conn-indicator");
    const text = $("#conn-text");
    indicator.classList.toggle("offline", !online);
    if (online) {
        indicator.title = "Server erreichbar";
        text.textContent = "verbunden";
    } else {
        indicator.title = "Server nicht erreichbar";
        text.textContent = "getrennt";
    }
}

async function refresh() {
    const [pending, voice, audit] = await Promise.all([
        fetchJson("/permission/pending"),
        fetchJson("/voice/status"),
        fetchJson("/audit/log?limit=" + AUDIT_LIMIT),
    ]);
    const online = pending !== null && voice !== null && audit !== null;
    setOnline(online);
    renderPending(pending);
    renderVoiceStatus(voice);
    renderAudit(audit);
}

window.addEventListener("DOMContentLoaded", () => {
    refresh();
    setInterval(refresh, POLL_INTERVAL_MS);
});
