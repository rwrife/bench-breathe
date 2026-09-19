// Contract tests for docs/protocol.md v1 — run the wire shapes, limits,
// errors, and auth rules in the contract against the dev stub device.
// When the device's real HTTP server lands, point BB_BASE_URL at it and the
// same suite applies (COM-04 cross-project contract tests).
//
//   node --test app/test/     (or: cd app && npm test)
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";

const PORT = 8199;
const BASE = `http://127.0.0.1:${PORT}`;
let proc;
let token = null;

async function req(path, opts = {}, tok = token) {
  const headers = { ...(opts.headers || {}) };
  if (tok && !("X-BB-Auth" in headers)) headers["X-BB-Auth"] = tok;
  const res = await fetch(BASE + path, { ...opts, headers });
  let body = null;
  const text = await res.text();
  try { body = JSON.parse(text); } catch { body = text; }
  return { status: res.status, body, headers: res.headers };
}
const jpost = (path, obj, tok) => req(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(obj) }, tok);
const jput = (path, obj, tok) => req(path, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(obj) }, tok);
// mutating request with token + same-origin protection header
const mut = (path, method, obj) => req(path, { method, headers: { "content-type": "application/json", "X-BB-Req": "bb" }, body: JSON.stringify(obj) });
async function button() { // simulated physical action -> arms pairing, prints code
  const r = await req("/__dev/button", { method: "POST" }, null);
  assert.equal(r.status, 200);
  return r.body.code;
}
before(async () => {
  proc = spawn(process.execPath, ["dev/stub-server.mjs", "--port", String(PORT), "--quiet"], {
    cwd: new URL("..", import.meta.url).pathname, stdio: "ignore",
  });
  for (let i = 0; i < 50; i++) {
    try { const r = await req("/api/v1/health", {}, null); if (r.status === 200) return; } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("stub device did not start");
});
after(() => proc.kill());

// ------------------------------------------------- public health subset ----
test("health is public, non-sensitive, protocol-tagged", async () => {
  const r = await req("/api/v1/health", {}, null);
  assert.equal(r.status, 200);
  assert.equal(r.body.protocol, "v1");
  for (const k of ["fw", "uptime_s", "mode", "source", "clock", "paired", "storage"])
    assert.ok(k in r.body, `missing ${k}`);
  // COM-07: no sensor values, no label in the public subset
  assert.ok(!("channels" in r.body));
  assert.ok(!("label" in r.body));
  assert.ok(!("config" in r.body));
  assert.ok(!("raw_capacity" in r.body)); // storage present but bounded keys
});

test("protected resources demand the credential (401 unauthorized)", async () => {
  for (const p of ["/api/v1/live", "/api/v1/config", "/api/v1/history", "/api/v1/events", "/api/v1/export.csv", "/api/v1/export.json"]) {
    const r = await req(p, {}, null);
    assert.equal(r.status, 401, p);
    assert.equal(r.body.error.code, "unauthorized", p);
  }
});

// ------------------------------------------------------------ pairing ------
test("pairing: closed when unarmed; wrong code invalid; success yields token", async () => {
  let r = await jpost("/api/v1/pair", { code: "nope" }, null);
  assert.equal(r.status, 409); assert.equal(r.body.error.code, "pairing_closed");

  const code = await button();
  assert.equal(typeof code, "string");
  assert.ok(code.length >= 20, "pairing code must carry >=128 bits of entropy");

  r = await jpost("/api/v1/pair", { code: "wrong" }, null);
  assert.equal(r.status, 403); assert.equal(r.body.error.code, "pairing_invalid");

  r = await jpost("/api/v1/pair", { code }, null);
  assert.equal(r.status, 200);
  assert.ok(typeof r.body.token === "string" && r.body.token.length >= 32);
  assert.equal(r.body.schema, 1);
  token = r.body.token;

  // first exchange consumed the code and closed the endpoint
  r = await jpost("/api/v1/pair", { code }, null);
  assert.equal(r.status, 409); assert.equal(r.body.error.code, "pairing_closed");
});

test("mutating requests need the same-origin protection header", async () => {
  const r = await jpost("/api/v1/events", { tag: "fan_on" }); // token but no X-BB-Req
  assert.equal(r.status, 401);
});

// ------------------------------------------------------------ live/shapes --
test("live follows channel object shape and null semantics (SNS-04)", async () => {
  const r = await req("/api/v1/live");
  assert.equal(r.status, 200);
  const { channels, seq, clock, storage } = r.body;
  assert.ok(Number.isInteger(seq));
  assert.ok(["unset", "estimated", "network"].includes(clock));
  for (const k of ["pm25", "voc_raw", "temperature_c", "humidity_pct"]) {
    const ch = channels[k];
    assert.ok(ch, `missing channel ${k}`);
    assert.ok(["ready", "warming", "fault", "unknown"].includes(ch.status), k);
    if (ch.status === "ready") {
      assert.equal(typeof ch.value, "number", `${k} ready must carry number`);
      assert.equal(ch.reason, "none", k);
    } else {
      assert.equal(ch.value, null, `${k} non-ready must be explicit null`);
      assert.ok(ch.reason && ch.reason !== "none", `${k} null needs reason`);
    }
  }
  assert.equal(channels.pm25.unit, "ug_m3");
  assert.equal(channels.voc_raw.unit, "ticks");
  for (const k of ["raw_used", "raw_capacity", "agg_used", "agg_capacity", "oldest_seq", "newest_seq"])
    assert.ok(k in storage);
});

// ------------------------------------------------------------ config -------
test("config round-trip; out-of-range and over-long labels rejected not clamped (SNS-03)", async () => {
  let r = await req("/api/v1/config");
  assert.equal(r.status, 200);
  assert.equal(r.body.schema, 1);
  assert.ok(r.body.interval_ms >= 2000 && r.body.interval_ms <= 60000);

  r = await mut("/api/v1/config", "PUT", { interval_ms: 5000 });
  assert.equal(r.status, 200); assert.equal(r.body.interval_ms, 5000);

  r = await mut("/api/v1/config", "PUT", { interval_ms: 1000 });
  assert.equal(r.status, 422); assert.equal(r.body.error.code, "interval_out_of_range");
  r = await req("/api/v1/config"); assert.equal(r.body.interval_ms, 5000, "rejected write must not mutate");

  r = await mut("/api/v1/config", "PUT", { label: "x".repeat(32) });
  assert.equal(r.status, 422); assert.equal(r.body.error.code, "label_too_long");

  r = await mut("/api/v1/config", "PUT", { interval_ms: 3000, label: "bench-breathe" });
  assert.equal(r.status, 200); assert.equal(r.body.interval_ms, 3000);
});

// ------------------------------------------------------------ time ---------
test("time set -> clock quality becomes estimated; invalid rejected", async () => {
  let r = await mut("/api/v1/time", "POST", { wall_us: 1767225600000000 });
  assert.equal(r.status, 200); assert.equal(r.body.clock, "estimated");
  r = await mut("/api/v1/time", "POST", { wall_us: "soon" });
  assert.equal(r.status, 422); assert.equal(r.body.error.code, "time_invalid");
});

// ------------------------------------------------------------ events -------
test("events: tag grammar enforced, reserved tags accepted, GET lists them", async () => {
  for (const bad of ["Fan_On", "1fan", "", "x".repeat(40)]) {
    const r = await mut("/api/v1/events", "POST", { tag: bad });
    assert.equal(r.status, 422, bad); assert.equal(r.body.error.code, "event_tag_invalid");
  }
  for (const tag of ["fan_on", "window_open", "session_start"]) {
    const r = await mut("/api/v1/events", "POST", { tag, note: "contract test" });
    assert.equal(r.status, 201, tag);
    assert.ok(Number.isInteger(r.body.event_id));
  }
  const r = await req("/api/v1/events");
  assert.equal(r.status, 200); assert.equal(r.body.count, 3);
});

// ------------------------------------------------------------ history ------
test("history records ordered by seq with per-record channels", async () => {
  const r = await req("/api/v1/history");
  assert.equal(r.status, 200);
  assert.equal(r.body.count, r.body.records.length);
  let prev = -1;
  for (const rec of r.body.records) {
    assert.ok(rec.seq > prev, "seq must strictly increase"); prev = rec.seq;
    assert.ok(["unset", "estimated", "network"].includes(rec.clock));
    assert.ok("channels" in rec);
  }
});

// ------------------------------------------------------------ exports ------
test("CSV export: metadata line, header, numeric/null fields", async () => {
  const r = await req("/api/v1/export.csv");
  assert.equal(r.status, 200);
  const lines = r.body.trim().split("\n");
  assert.match(lines[0], /^# bench-breathe export protocol=v1 clock=.* count=\d+$/);
  assert.equal(lines[1], "seq,wall_us,clock,pm25_ug_m3,voc_raw_ticks,temperature_c,humidity_pct");
  assert.equal(lines.length - 2, Number(/count=(\d+)$/.exec(lines[0])[1]));
  const cols = lines[lines.length - 1].split(",");
  assert.equal(cols.length, 7);
  assert.ok(r.headers.get("content-disposition").includes("attachment"));
});

test("JSON export: envelope metadata + records + events", async () => {
  const r = await req("/api/v1/export.json");
  assert.equal(r.status, 200);
  for (const k of ["protocol", "exported_wall_us", "clock", "fw", "count", "records", "events"])
    assert.ok(k in r.body, k);
  assert.equal(r.body.count, r.body.records.length);
  assert.equal(r.body.records.length >= 1, true);
});

// ------------------------------------------------------------ errors -------
test("unknown authenticated path -> 404 unknown_path envelope", async () => {
  const r = await req("/api/v1/nonexistent");
  assert.equal(r.status, 404);
  assert.equal(r.body.error.code, "unknown_path");
  assert.equal(typeof r.body.error.message, "string");
});

test("no wildcard CORS headers anywhere (COM-05)", async () => {
  const r = await req("/api/v1/health", {}, null);
  assert.notEqual(r.headers.get("access-control-allow-origin"), "*");
});
