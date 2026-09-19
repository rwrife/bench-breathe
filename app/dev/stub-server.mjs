// Bench Breathe dev stub device — implements docs/protocol.md contract v1.
//
// Purpose: run the companion app end-to-end on a dev machine without a
// physical board (issue #7). This is a *simulator*, not the firmware: real
// devices speak the same wire shapes (v1) but are reached over Wi-Fi HTTP
// served by the device itself (COM-05) once provisioning lands.
//
// Zero external dependencies (node >= 20 stdlib only).
//   node app/dev/stub-server.mjs [--port 8123]
//
// Pairing demo: hold the stub's "button" via POST /__dev/button (simulated
// physical action) to arm pairing and print a code, then pair from the app.

import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, "..", "public");

const PROTOCOL = "v1";
const FW = "0.1.0-stub";
const INTERVAL_MIN = 2000, INTERVAL_MAX = 60000, DEFAULT_INTERVAL = 2000;
const LABEL_MAX = 31;
const RAW_CAP = 4096, AGG_CAP = 288;

// ---------------------------------------------------------------- state ----
const state = {
  startedMonoMs: Date.now(),
  config: { schema: 1, interval_ms: DEFAULT_INTERVAL, label: "bench-breathe" },
  wallUs: 0,                      // 0 = unset
  clock: "unset",                 // unset|estimated|network
  seq: 0,
  raw: [],                        // retained history records
  events: [],
  eventSeq: 0,
  pairing: null,                  // {code, expiresAtMs} when armed
  token: null,                    // active API credential once paired
  armedUntilMs: 0,                // serial mutation arm window
};

function uptimeS() { return Math.floor((Date.now() - state.startedMonoMs) / 1000); }
function wallUsNow() { return state.wallUs === 0 ? 0 : Date.now() * 1000 + (state.wallUs - state.startedMonoMs * 1000); }

// Simulated sensor physics: gentle random-walk PM2.5, warming ramps at boot.
const sim = { pm: 8.5, voc: 120, t: 24.5, rh: 45, bootMs: Date.now() };
function chan(status, value, unit, reason) {
  return { status, value: status === "ready" ? value : null, unit, reason };
}
function tickSensors() {
  sim.pm = Math.max(0.5, sim.pm + (Math.random() - 0.5) * 1.2);
  sim.voc = Math.max(20, sim.voc + (Math.random() - 0.5) * 14);
  sim.t += (Math.random() - 0.5) * 0.1;
  sim.rh = Math.min(90, Math.max(10, sim.rh + (Math.random() - 0.5) * 0.8));
  const booted_s = (Date.now() - sim.bootMs) / 1000;
  const pmReady = booted_s >= 8;      // SPS30 pump warm-up (datasheet ~4s fast, longer stable)
  const vocReady = booted_s >= 4;     // SGP40 baseline settling
  const rec = {
    seq: ++state.seq,
    wall_us: wallUsNow(),
    clock: state.clock,
    channels: {
      pm25: pmReady ? chan("ready", round2(sim.pm), "ug_m3", "none")
                    : chan("warming", null, "ug_m3", "warming"),
      voc_raw: vocReady ? chan("ready", Math.round(sim.voc), "ticks", "none")
                        : chan("warming", null, "ticks", "warming"),
      temperature_c: chan("ready", round2(sim.t), "c", "none"),
      humidity_pct: chan("ready", round2(sim.rh), "pct", "none"),
    },
  };
  state.raw.push(rec);
  if (state.raw.length > RAW_CAP) state.raw.splice(0, state.raw.length - RAW_CAP);
  return rec;
}
function round2(v) { return Math.round(v * 100) / 100; }

// Acquisition tick at configured interval.
let sampleTimer = null;
function restartSampling() {
  if (sampleTimer) clearInterval(sampleTimer);
  sampleTimer = setInterval(tickSensors, state.config.interval_ms);
}
tickSensors(); restartSampling();

// ---------------------------------------------------------------- shapes ---
function storageBlock() {
  return {
    raw_used: state.raw.length, raw_capacity: RAW_CAP,
    agg_used: 0, agg_capacity: AGG_CAP,
    oldest_seq: state.raw.length ? state.raw[0].seq : 0,
    newest_seq: state.seq,
  };
}
function sourceState() { return "default_cc"; }
function deviceMode() { return "full"; }

function healthPublic() {
  return {
    protocol: PROTOCOL, fw: FW, uptime_s: uptimeS(),
    mode: deviceMode(), source: sourceState(), clock: state.clock,
    paired: state.token !== null,
    storage: (({ raw_used, raw_capacity, agg_used, agg_capacity }) =>
      ({ raw_used, raw_capacity, agg_used, agg_capacity }))(storageBlock()),
  };
}
function live() {
  const newest = state.raw[state.raw.length - 1];
  return {
    protocol: PROTOCOL, seq: newest ? newest.seq : 0,
    wall_us: newest ? newest.wall_us : 0, clock: state.clock,
    uptime_s: uptimeS(), mode: deviceMode(), source: sourceState(),
    storage: storageBlock(),
    channels: newest ? newest.channels
      : { pm25: chan("unknown", null, "ug_m3", "not_yet_measured"),
          voc_raw: chan("unknown", null, "ticks", "not_yet_measured"),
          temperature_c: chan("unknown", null, "c", "not_yet_measured"),
          humidity_pct: chan("unknown", null, "pct", "not_yet_measured") },
  };
}

// ----------------------------------------------------------------- CSV ----
function csvLine(rec) {
  const c = rec.channels;
  const f = (ch) => ch.status === "ready" ? ch.value.toFixed(2) : "";
  return `${rec.seq},${rec.wall_us || ""},${rec.clock},${f(c.pm25)},${f(c.voc_raw)},${f(c.temperature_c)},${f(c.humidity_pct)}`;
}
function exportCsv() {
  const meta = `# bench-breathe export protocol=${PROTOCOL} clock=${state.clock} fw=${FW} exported_wall_us=${wallUsNow() || ""} count=${state.raw.length}`;
  return meta + "\nseq,wall_us,clock,pm25_ug_m3,voc_raw_ticks,temperature_c,humidity_pct\n"
    + state.raw.map(csvLine).join("\n") + "\n";
}
function exportJson() {
  return JSON.stringify({
    protocol: PROTOCOL, exported_wall_us: wallUsNow(), clock: state.clock,
    fw: FW, count: state.raw.length, records: state.raw, events: state.events,
  }, null, 1) + "\n";
}

// ------------------------------------------------------------- helpers -----
function err(res, httpCode, code, message, details = {}) {
  res.writeHead(httpCode, { "content-type": "application/json" });
  res.end(JSON.stringify({ error: { code, message, details } }));
}
function json(res, httpCode, obj) {
  res.writeHead(httpCode, { "content-type": "application/json" });
  res.end(JSON.stringify(obj));
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (c) => { data += c; if (data.length > 65536) { reject(new Error("body_too_large")); req.destroy(); } });
    req.on("end", () => { try { resolve(data ? JSON.parse(data) : {}); } catch { reject(new Error("bad_json")); } });
    req.on("error", reject);
  });
}
function authed(req) {
  return state.token !== null && req.headers["x-bb-auth"] === state.token;
}
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".json": "application/json" };
function serveStatic(req, res, urlPath) {
  let rel = urlPath === "/" ? "/index.html" : urlPath;
  const file = path.normalize(path.join(PUBLIC_DIR, rel));
  if (!file.startsWith(PUBLIC_DIR)) return err(res, 404, "unknown_path", "not found");
  fs.readFile(file, (e, buf) => {
    if (e) return err(res, 404, "unknown_path", "not found");
    res.writeHead(200, { "content-type": MIME[path.extname(file)] || "application/octet-stream" });
    res.end(buf);
  });
}

// --------------------------------------------------------------- server ----
const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, "http://stub");
  const p = u.pathname;

  // Dev-only: simulate the physical button (arms pairing + serial mutations).
  if (p === "/__dev/button" && req.method === "POST") {
    const code = crypto.randomBytes(16).toString("base64url"); // 128 bits
    state.pairing = { code, expiresAtMs: Date.now() + 10 * 60 * 1000 };
    state.armedUntilMs = Date.now() + 30 * 1000;
    console.log(`PAIR ${code}`);
    return json(res, 200, { armed: true, code, note: "printed on 'serial' — pair within 10 min" });
  }

  if (p === "/api/v1/health" && req.method === "GET") return json(res, 200, healthPublic());

  if (p === "/api/v1/pair" && req.method === "POST") {
    if (!state.pairing || Date.now() > state.pairing.expiresAtMs)
      return err(res, 409, "pairing_closed", "pairing endpoint not armed or expired");
    let body; try { body = await readBody(req); } catch { return err(res, 422, "bad_json", "invalid JSON body"); }
    if (typeof body.code !== "string" || body.code !== state.pairing.code)
      return err(res, 403, "pairing_invalid", "wrong or already-consumed code");
    // first successful exchange consumes the code and closes the endpoint
    state.pairing = null;
    state.token = crypto.randomBytes(32).toString("base64url");
    return json(res, 200, { token: state.token, schema: state.config.schema });
  }

  if (p.startsWith("/api/v1/")) {
    if (!authed(req)) return err(res, 401, "unauthorized", "missing or invalid X-BB-Auth");
    const mutating = req.method !== "GET";
    if (mutating && req.headers["x-bb-req"] !== "bb")
      return err(res, 401, "unauthorized", "missing same-origin request protection header X-BB-Req: bb");

    if (p === "/api/v1/config" && req.method === "GET") return json(res, 200, state.config);
    if (p === "/api/v1/config" && req.method === "PUT") {
      let body; try { body = await readBody(req); } catch { return err(res, 422, "bad_json", "invalid JSON body"); }
      const cand = { ...state.config };
      if (body.interval_ms !== undefined) cand.interval_ms = body.interval_ms;
      if (body.label !== undefined) cand.label = body.label;
      if (!Number.isInteger(cand.interval_ms) || cand.interval_ms < INTERVAL_MIN || cand.interval_ms > INTERVAL_MAX)
        return err(res, 422, "interval_out_of_range", `interval_ms must be an integer in [${INTERVAL_MIN},${INTERVAL_MAX}]`, { min: INTERVAL_MIN, max: INTERVAL_MAX });
      if (typeof cand.label !== "string" || Buffer.byteLength(cand.label, "utf8") > LABEL_MAX)
        return err(res, 422, "label_too_long", `label must be <= ${LABEL_MAX} UTF-8 bytes`, { max_bytes: LABEL_MAX });
      state.config = cand;              // atomic commit only after full validation
      restartSampling();
      return json(res, 200, state.config);
    }
    if (p === "/api/v1/time" && req.method === "POST") {
      let body; try { body = await readBody(req); } catch { return err(res, 422, "bad_json", "invalid JSON body"); }
      if (!Number.isInteger(body.wall_us) || body.wall_us < 0)
        return err(res, 422, "time_invalid", "wall_us must be a non-negative integer (µs)");
      state.wallUs = body.wall_us; state.clock = "estimated"; state.startedMonoMs = Date.now();
      return json(res, 200, { clock: state.clock, wall_us: wallUsNow() });
    }
    if (p === "/api/v1/live" && req.method === "GET") return json(res, 200, live());
    if (p === "/api/v1/history" && req.method === "GET") {
      const from = u.searchParams.has("from") ? Number(u.searchParams.get("from")) : null;
      const to = u.searchParams.has("to") ? Number(u.searchParams.get("to")) : null;
      let recs = state.raw;
      if (from !== null || to !== null)
        recs = recs.filter((r) => r.clock !== "unset" && (from === null || r.wall_us >= from) && (to === null || r.wall_us <= to));
      return json(res, 200, { protocol: PROTOCOL, from: from ?? 0, to: to ?? 0, clock: state.clock, count: recs.length, records: recs });
    }
    if (p === "/api/v1/events" && req.method === "GET")
      return json(res, 200, { protocol: PROTOCOL, count: state.events.length, events: state.events });
    if (p === "/api/v1/events" && req.method === "POST") {
      let body; try { body = await readBody(req); } catch { return err(res, 422, "bad_json", "invalid JSON body"); }
      if (typeof body.tag !== "string" || !/^[a-z][a-z0-9_]{0,31}$/.test(body.tag))
        return err(res, 422, "event_tag_invalid", "tag must match [a-z][a-z0-9_]{0,31}");
      const note = body.note === undefined ? "" : String(body.note);
      if (Buffer.byteLength(note, "utf8") > 200)
        return err(res, 422, "event_tag_invalid", "note must be <= 200 UTF-8 bytes");
      const ev = { protocol: PROTOCOL, event_id: ++state.eventSeq, mono_us: uptimeS() * 1e6, tag: body.tag, note };
      state.events.push(ev);
      return json(res, 201, ev);
    }
    if (p === "/api/v1/export.csv" && req.method === "GET") {
      res.writeHead(200, { "content-type": "text/csv", "content-disposition": `attachment; filename="bench-breathe-export-${Date.now()}.csv"` });
      return res.end(exportCsv());
    }
    if (p === "/api/v1/export.json" && req.method === "GET") {
      res.writeHead(200, { "content-type": "application/json", "content-disposition": `attachment; filename="bench-breathe-export-${Date.now()}.json"` });
      return res.end(exportJson());
    }
    return err(res, 404, "unknown_path", `no resource at ${req.method} ${p}`);
  }

  if (req.method !== "GET") return err(res, 404, "unknown_path", "not found");
  return serveStatic(req, res, p);
});

const portArg = process.argv.indexOf("--port");
const PORT = portArg >= 0 ? Number(process.argv[portArg + 1]) : 8123;
const QUIET = process.argv.indexOf("--quiet") >= 0;
server.listen(PORT, "127.0.0.1", () => {
  if (QUIET) return;
  console.log(`bench-breathe stub device (protocol ${PROTOCOL}) on http://127.0.0.1:${PORT}`);
  console.log(`simulate button+pairing code:  curl -X POST http://127.0.0.1:${PORT}/__dev/button`);
});
export { server, state };
