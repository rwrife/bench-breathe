// Bench Breathe companion app client — protocol contract v1 (docs/protocol.md).
// No build step, no dependencies, no CDN: the device serves these files
// itself (COM-05). All state (URL + token) stays in browser localStorage.
"use strict";

const LS_URL = "bb.deviceUrl";
const LS_TOKEN = "bb.token";

const $ = (id) => document.getElementById(id);

const store = {
  url: localStorage.getItem(LS_URL) || "",
  token: localStorage.getItem(LS_TOKEN) || "",
  set(url, token) {
    this.url = url; this.token = token;
    if (url) localStorage.setItem(LS_URL, url); else localStorage.removeItem(LS_URL);
    if (token) localStorage.setItem(LS_TOKEN, token); else localStorage.removeItem(LS_TOKEN);
  },
  clear() { this.set("", ""); },
};

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (store.token) headers["X-BB-Auth"] = store.token;
  if (opts.method && opts.method !== "GET") headers["X-BB-Req"] = "bb";
  let res;
  try {
    res = await fetch(store.url.replace(/\/$/, "") + path, { ...opts, headers });
  } catch (e) {
    throw new ApiError(0, "network", `device unreachable: ${e.message}`);
  }
  let body = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) { try { body = await res.json(); } catch { /* keep null */ } }
  if (!res.ok) {
    const e = (body && body.error) || {};
    throw new ApiError(res.status, e.code || "device_error", e.message || res.statusText);
  }
  return body;
}
class ApiError extends Error {
  constructor(status, code, message) { super(message); this.status = status; this.code = code; }
}

// ------------------------------------------------------------- setup flow --
let health = null;

function setBadge(text, cls) {
  const b = $("conn-badge"); b.textContent = text; b.className = `badge ${cls}`;
}
function msg(elId, text, isError = false) {
  const el = $(elId);
  if (text === null) { el.hidden = true; el.textContent = ""; return; }
  el.hidden = false; el.textContent = text;
  el.classList.toggle("error", isError);
}

async function checkDevice(showPairing = false) {
  if (!store.url) { msg("setup-msg", "Enter the device URL first.", true); return false; }
  msg("setup-msg", null);
  try {
    health = await api("/api/v1/health");
    setBadge(`connected · fw ${health.fw} · ${health.mode}`, "on");
    $("pair-box").hidden = !(health.paired === false || showPairing);
    $("btn-pair").hidden = !(health.paired === false || showPairing);
    if (health.paired && store.token) showApp();
    else if (!health.paired) msg("setup-msg", "Device reachable but not paired. Hold the device button, read the code from the serial console, and pair.");
    else msg("setup-msg", "Device reachable but this browser is not paired. Re-pair (hold button, read code).", true);
    return true;
  } catch (e) {
    setBadge("not connected", "off");
    msg("setup-msg", `${e.code}: ${e.message}`, true);
    return false;
  }
}

async function pair() {
  const code = $("pair-code").value.trim();
  if (!code) { msg("setup-msg", "Enter the pairing code.", true); return; }
  try {
    const r = await api("/api/v1/pair", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ code }) });
    store.set(store.url, r.token);
    msg("setup-msg", "Paired.");
    await checkDevice();
  } catch (e) {
    msg("setup-msg", `pairing failed — ${e.code}: ${e.message}`, true);
  }
}

function showApp() {
  $("status").hidden = $("history").hidden = $("settings").hidden = false;
  startPolling();
  refreshHistory().catch(() => {});
}

// ------------------------------------------------------------- live view ---
let pollTimer = null;
let liveHistory = [];  // [{t_wall, pm25, voc, temp, rh}] for trend chart

function fmtChannel(ch, unitLabel) {
  const icon = { ready: "●", warming: "◐", fault: "✕", unknown: "?" }[ch.status] || "?";
  const v = ch.value === null ? "—" : `${ch.value} ${unitLabel}`;
  const why = ch.value === null && ch.reason && ch.reason !== "none" ? ` (${ch.reason.replace(/_/g, " ")})` : "";
  return { icon, text: `${v}${why}`, status: ch.status };
}

function renderLive(l) {
  $("health-line").textContent =
    `mode ${l.mode} · power ${l.source.replace(/_/g, " ")} · clock ${l.clock} · uptime ${fmtUptime(l.uptime_s)}` +
    ` · storage ${l.storage.raw_used}/${l.storage.raw_capacity} raw (seq ${l.storage.oldest_seq}–${l.storage.newest_seq})`;
  const defs = [["pm25", "PM2.5", "µg/m³"], ["voc_raw", "VOC proxy", "ticks"], ["temperature_c", "Temp", "°C"], ["humidity_pct", "Humidity", "%RH"]];
  const grid = $("channels"); grid.innerHTML = "";
  for (const [key, name, unit] of defs) {
    const ch = l.channels[key] || { status: "unknown", value: null, reason: "not_yet_measured" };
    const f = fmtChannel(ch, unit);
    const div = document.createElement("div");
    div.className = `chan ${f.status}`;
    div.innerHTML = `<div class="chan-name">${name}</div><div class="chan-val">${f.icon} ${f.text}</div>`;
    grid.appendChild(div);
  }
  if (l.channels && l.channels.pm25 && l.channels.pm25.value !== null) {
    liveHistory.push({ t: l.wall_us || Date.now() * 1000, pm25: l.channels.pm25.value });
    if (liveHistory.length > 300) liveHistory.shift();
    drawChart();
  }
  $("clock-state").textContent = `device clock: ${l.clock}`;
}

function fmtUptime(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : m ? `${m}m ${s % 60}s` : `${s}s`;
}

function drawChart() {
  const cv = $("chart"), ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, cv.width, cv.height);
  const pts = liveHistory;
  if (pts.length < 2) { $("chart-legend").textContent = "collecting samples…"; return; }
  const vals = pts.map((p) => p.pm25);
  const lo = Math.min(...vals), hi = Math.max(...vals), span = (hi - lo) || 1;
  ctx.strokeStyle = "#4a90d9"; ctx.lineWidth = 2; ctx.beginPath();
  pts.forEach((p, i) => {
    const x = (i / (pts.length - 1)) * (cv.width - 8) + 4;
    const y = cv.height - 8 - ((p.pm25 - lo) / span) * (cv.height - 16);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
  $("chart-legend").textContent = `PM2.5 trend (µg/m³) — last ${pts.length} live samples, range ${lo.toFixed(1)}–${hi.toFixed(1)}`;
}

async function poll() {
  try {
    const l = await api("/api/v1/live");
    renderLive(l);
    setBadge(`connected · seq ${l.seq}`, "on");
  } catch (e) {
    if (e.code === "unauthorized") {
      setBadge("token invalid — re-pair", "warn");
      $("status").hidden = $("history").hidden = $("settings").hidden = true;
      msg("setup-msg", "Device rejected the stored token (factory reset?). Re-pair.", true);
    } else setBadge("connection lost", "warn");
  }
}
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  poll();
  pollTimer = setInterval(poll, 2000);
  api("/api/v1/config").then((c) => {
    $("cfg-interval").value = c.interval_ms; $("cfg-label").value = c.label;
  }).catch(() => {});
}

// -------------------------------------------------------------- history ----
async function refreshHistory() {
  const sel = $("hist-range").value;
  let path = "/api/v1/history";
  if (sel !== "all") {
    const nowUs = Date.now() * 1000;
    path += `?from=${nowUs - Number(sel) * 1000000}&to=${nowUs}`;
  }
  const h = await api(path);
  let nullCount = 0, total = 0;
  for (const r of h.records) for (const k of Object.keys(r.channels || {})) { total++; if (r.channels[k].value === null) nullCount++; }
  $("hist-summary").textContent =
    `${h.count} records (${h.clock === "unset" ? "device clock unset — ordered by seq" : `wall-clock filtered`}) · ` +
    `${total ? Math.round((nullCount / total) * 100) : 0}% of channel slots null/incomplete`;
}

async function downloadExport(kind) {
  const res = await fetch(store.url.replace(/\/$/, "") + `/api/v1/export.${kind}`, {
    headers: { "X-BB-Auth": store.token },
  });
  if (!res.ok) { msg("cfg-msg", `export failed (${res.status})`, true); return; }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `bench-breathe-export-${Date.now()}.${kind}`;
  document.body.appendChild(a); a.click(); a.remove();
  msg("cfg-msg", `exported ${kind.toUpperCase()} — file saved locally by your browser (nothing uploaded anywhere).`);
}

// -------------------------------------------------------------- settings ---
async function saveConfig() {
  const body = { interval_ms: Number($("cfg-interval").value), label: $("cfg-label").value };
  try {
    const c = await api("/api/v1/config", { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    msg("cfg-msg", `saved: interval ${c.interval_ms} ms, label "${c.label}"`);
  } catch (e) { msg("cfg-msg", `rejected — ${e.code}: ${e.message}`, true); }
}

async function syncTime() {
  try {
    const r = await api("/api/v1/time", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ wall_us: Date.now() * 1000 }) });
    msg("cfg-msg", `device clock set from this computer → quality: ${r.clock} (one-time estimate, never network-validated)`);
  } catch (e) { msg("cfg-msg", `time set failed — ${e.code}: ${e.message}`, true); }
}

async function addEvent() {
  let tag = $("event-tag").value;
  if (tag === "custom") tag = "user_tag";
  try {
    const ev = await api("/api/v1/events", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ tag, note: $("event-note").value }) });
    msg("cfg-msg", `event #${ev.event_id} "${ev.tag}" recorded on device`);
    $("event-note").value = "";
  } catch (e) { msg("cfg-msg", `event failed — ${e.code}: ${e.message}`, true); }
}

// ---------------------------------------------------------------- wiring ---
$("btn-connect").addEventListener("click", () => {
  store.set($("device-url").value.trim(), store.token);
  checkDevice();
});
$("btn-pair").addEventListener("click", pair);
$("btn-forget").addEventListener("click", () => {
  store.clear();
  if (pollTimer) clearInterval(pollTimer); pollTimer = null; liveHistory = [];
  $("status").hidden = $("history").hidden = $("settings").hidden = true;
  setBadge("not connected", "off");
  msg("setup-msg", "Device forgotten — URL and token cleared from this browser.");
});
$("btn-refresh").addEventListener("click", () => refreshHistory().catch((e) => msg("cfg-msg", e.message, true)));
$("hist-range").addEventListener("change", () => refreshHistory().catch(() => {}));
$("btn-export-csv").addEventListener("click", () => downloadExport("csv"));
$("btn-export-json").addEventListener("click", () => downloadExport("json"));
$("btn-save-cfg").addEventListener("click", saveConfig);
$("btn-sync-time").addEventListener("click", syncTime);
$("btn-event").addEventListener("click", addEvent);

// Auto-resume a previously paired device.
if (store.url) { $("device-url").value = store.url; checkDevice(); }
