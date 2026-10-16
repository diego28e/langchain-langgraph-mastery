// The Orbita Cloud support desk UI (Lesson 12.09): start runs, stream them, survive a reload, stop them.
// Same origin as the API, no framework, no third-party code (the server sends a strict CSP).
"use strict";
const $ = (id) => document.getElementById(id);
const store = sessionStorage;          // per tab; cleared when the tab closes
const state = JSON.parse(store.getItem("desk") || "{}");   // {thread, run, last, log: [[cls, text]]}
const save = () => store.setItem("desk", JSON.stringify(state));
let key = store.getItem("desk-key") || "";
let controller = null;

function line(cls, text) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;              // textContent, never innerHTML: answers are untrusted text
  $("log").appendChild(div);
  return div;
}

function render() {
  $("log").textContent = "";
  for (const [cls, text] of state.log || []) line(cls, text);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Authorization": "Bearer " + key, "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (response.status === 401) { signOut("Your key was not accepted."); throw new Error("401"); }
  return response;
}

function busy(on) {
  $("send").disabled = on;
  $("cancel").disabled = !on;
}

// Read the SSE stream with fetch (EventSource can't send an Authorization header).
async function follow() {
  controller = new AbortController();
  busy(true);
  const headers = state.last != null ? { "Last-Event-ID": String(state.last) } : {};
  let answer = null;
  try {
    const response = await api(`/runs/${state.run}/stream`, { headers, signal: controller.signal });
    if (!response.ok) throw new Error(`stream: HTTP ${response.status}`);
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        const event = { event: "message", data: "", id: null };
        for (const raw of block.split("\n")) {
          if (raw.startsWith(":")) continue;                     // keep-alive comment
          const i = raw.indexOf(":");
          const field = raw.slice(0, i), text = raw.slice(i + 1).replace(/^ /, "");
          if (field === "data") event.data += text;
          else if (field in event) event[field] = text;
        }
        if (event.id !== null) { state.last = Number(event.id); save(); }
        const data = event.data ? JSON.parse(event.data) : {};
        if (event.event === "token") {
          answer = answer || line("agent", "");
          answer.textContent += data.text;
        } else if (event.event === "interrupt") {
          showApproval(data.interrupts);
        } else if (event.event === "end") {
          const text = data.status === "success" ? data.answer : `(${data.status})`;
          if (answer) answer.remove();
          state.log.push(["agent", text]); line("agent", text);
        } else if (event.event === "error") {
          state.log.push(["error", data.message]); line("error", data.message);
        }
      }
    }
    state.run = null; state.last = null; save();
  } catch (err) {
    if (err.name !== "AbortError") $("status").textContent = "Connection lost; reload to resume. " + err.message;
  } finally {
    busy(false);
    controller = null;
  }
}

function showApproval(interrupts) {
  const ask = (interrupts && interrupts[0]) || {};
  $("approval").hidden = false;
  $("approval-text").textContent = `Refund ${ask.invoice_id || ""} for $${ask.amount ?? "?"} needs a billing manager. (Only a manager key can answer.)`;
}

async function send(message) {
  if (!state.thread) {
    const created = await (await api("/threads", { method: "POST" })).json();
    state.thread = created.thread_id;
  }
  const response = await api(`/threads/${state.thread}/runs`, {
    method: "POST", body: JSON.stringify(message),
    headers: { "Idempotency-Key": crypto.randomUUID() },     // a double click doesn't start two runs
  });
  const body = await response.json();
  if (!response.ok) { line("error", `${response.status}: ${body.detail}`); return; }
  state.run = body.run_id; state.last = null; save();
  await follow();
}

function signOut(why) {
  store.removeItem("desk-key"); key = "";
  $("chat").hidden = true; $("login").hidden = false;
  if (why) $("status").textContent = why;
}

$("signin").onclick = () => {
  key = $("key").value.trim();
  if (!key) return;
  store.setItem("desk-key", key);
  start();
};

$("ask").onsubmit = async (e) => {
  e.preventDefault();
  const text = $("message").value.trim();
  if (!text) return;
  $("message").value = "";
  state.log = state.log || [];
  state.log.push(["user", text]); line("user", text); save();
  await send({ message: text });
};

$("cancel").onclick = async () => { if (state.run) await api(`/runs/${state.run}/cancel`, { method: "POST" }); };
$("approve").onclick = async () => { $("approval").hidden = true; await send({ resume: "approve" }); };
$("reject").onclick = async () => { $("approval").hidden = true; await send({ resume: { action: "reject", feedback: "not approved" } }); };
$("new").onclick = () => { if (controller) controller.abort(); for (const k of Object.keys(state)) delete state[k]; save(); render(); };

async function start() {
  $("login").hidden = true; $("chat").hidden = false;
  render();
  if (state.run) { $("status").textContent = "Resuming your last answer…"; await follow(); $("status").textContent = ""; }
}

fetch("/version").then((r) => r.json()).then((v) => { $("version").textContent = `release ${v.release} · ${v.mode}`; });
if (key) start();
