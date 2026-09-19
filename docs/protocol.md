# Device ↔ App Protocol — Contract v1 (FINAL)

Status: **finalized contract** (COM-04). This document is the single
versioned contract for HTTP and USB-serial data shapes, units, limits,
errors, authorization, and compatibility between Bench Breathe firmware
and the companion app. Breaking changes require `/api/v2/...` (HTTP) or a
`protocol: "v2"` serial banner, plus migration notes in a new
`## v1 → v2 migration` section.

Reference implementations of this contract at finalize time:

| Surface | Reference | Evidence class |
|---|---|---|
| Serial NDJSON health line | `firmware/src/core/health_line.cpp` (baseline emits `protocol:"v0"` field; see Known deltas) | simulation (unit-tested) |
| HTTP API + serial commands | `app/dev/stub-server.mjs` (dev device simulator) | contract tests `app/test/contract.test.mjs` |
| Client | `app/public/` companion web app | contract tests |

## Version history

| Version | Date | Change |
|---|---|---|
| v0 (draft) | 2026-09-04 | Initial draft resource list. |
| **v1 (final)** | 2026-09-19 | Finalize HTTP shapes/limits/errors, add authorization (COM-07), time control, history/export/event wire shapes, serial command set. |

### v0 → v1 breaking changes (explicit)

1. **Authorization.** v0 assumed open local access. v1 requires a
   per-device bearer credential on every API resource except the
   documented public subset (COM-07). A v0 client cannot use a v1 device.
2. **Health response split.** v0 `GET /api/v1/health` returned everything.
   v1 splits it: a *public, non-sensitive* health subset (no sensor values,
   no label) and the full status inside `GET /api/v1/live`.
3. **Error shape.** v0 left errors undefined. v1 fixes a single error
   envelope and error-code registry (below).
4. **Null-channel shape.** v0 said "explicit `null` + reason". v1 fixes
   the exact per-channel object: `{"status","value","unit","reason"}`.
   `value` is JSON `null` exactly when `status != "ready"`.
5. **Time control added.** `POST /api/v1/time` (clock-quality semantics
   `unset/estimated/network`). New capability, not a break.
6. **Path prefix.** All resources live under `/api/v1/` (v0 draft already
   used this prefix; now normative).

### Known deltas at finalize time

- Firmware baseline (`0.1.0-baseline`) streams serial NDJSON health lines
  with `"protocol":"v0"` and no `reason` field on null channels. The wire
  *field names and enum strings* are unchanged in v1; firmware adoption of
  `"protocol":"v1"` + `reason` + the serial command set is a firmware
  follow-up (bench-gated, tracked for #8 bring-up). The app tolerates
  both by treating a missing `reason` on a null channel as
  `"not_yet_measured"`.
- The device does not yet serve HTTP itself (Wi-Fi provisioning + flash
  partition work); the app therefore runs against the dev stub today.

## Goals
- Deterministic, versioned, local-first communication.
- Safe degradation when network features are unavailable (USB-serial
  fallback covers setup, health, config recovery, export — COM-03).
- No mandatory internet dependency; no outbound cloud connections (COM-08).

## Transport
- **Primary:** HTTP/1.1 + JSON on the local network. The device serves the
  compiled app itself; all API requests are **same-origin**; wildcard CORS
  is prohibited (COM-05).
- **Fallback:** USB serial (CDC, 115200 baud), line-oriented commands and
  NDJSON responses (below).
- MVP HTTP traffic is **not confidential** against an attacker already on
  the trusted private LAN (COM-09). The device must never be port-forwarded
  or internet-exposed, and the UI must not describe it as internet-safe.

## Authorization (COM-06 / COM-07)

- After a sustained physical-button action, USB serial prints a
  **single-use pairing code** (≥128 bits CSPRNG entropy, valid ≤10 min):
  `PAIR <code>`.
- During that window, `POST /api/v1/pair` (unauthenticated, same-origin)
  exchanges the code for the per-device API credential. The first
  successful exchange consumes the code and closes the pairing endpoint.
- All protected requests carry `X-BB-Auth: <token>`.
- State-changing HTTP requests additionally require
  `X-BB-Req: bb` (same-origin request protection — a custom header forces
  a CORS preflight, which same-origin usage never triggers).
- USB-serial mutation commands (`SET`, `TIME`, `PAIR`, `RESET`) require a
  fresh physical-button confirmation: valid for 30 s after a button hold,
  signalled on the serial stream as `ARM 30`.
- Factory reset replaces all pairing material and returns the device to the
  unprovisioned state.

**Public (unauthenticated) subset:**
`GET /api/v1/health`, `POST /api/v1/pair`, and static app assets.
Everything else under `/api/v1/` requires the credential.

## Common shapes

### Error envelope (every non-2xx HTTP response)
```json
{"error": {"code": "string", "message": "string", "details": {}}}
```
Error-code registry (stable strings):

| code | HTTP | Meaning |
|---|---|---|
| `unauthorized` | 401 | missing/invalid `X-BB-Auth` |
| `pairing_closed` | 409 | pairing endpoint not armed (no button action / expired) |
| `pairing_invalid` | 403 | wrong or already-consumed code |
| `interval_out_of_range` | 422 | `interval_ms` outside 2000–60000 (rejected, never clamped — SNS-03) |
| `label_too_long` | 422 | label > 31 UTF-8 bytes |
| `time_invalid` | 422 | `wall_us` not a non-negative integer |
| `event_tag_invalid` | 422 | event tag shape violation |
| `unknown_path` | 404 | not a known resource |
| `device_error` | 500 | internal failure |

### Channel object (SNS-01/SNS-04)
```json
{"status": "ready|warming|fault|unknown",
 "value":  12.3,            // JSON null unless status == "ready"
 "unit":   "ug_m3|ticks|c|pct",
 "reason": "none|warming|sensor_fault|power_gated|not_yet_measured|stale_beyond_limit"}
```
Missing/invalid channels are explicit `null` + `reason`, never silently
dropped and never zeros-as-data. Units are fixed per channel id:
`pm25` µg/m³, `voc_raw` SGP40 SRAW_VOC ticks (raw proxy, not index),
`temperature_c` °C, `humidity_pct` %RH.

### Clock quality (SNS-06)
`"clock": "unset" | "estimated" | "network"` — no wall source / set once,
never validated (e.g. serial or HTTP time) / network-synced. Records with
`"clock":"unset"` carry `wall_us = 0`; clients order them by `seq`.

## HTTP resources (all under `/api/v1/`)

### `GET /health` — public health subset (COM-07)
Non-sensitive only; no sensor values, no device label.
```json
{"protocol":"v1","fw":"0.1.0-baseline","uptime_s":123,
 "mode":"full|recovery|suspended|error","source":"no_vbus|default_cc|cc_1a5|cc_3a|unknown_cc",
 "clock":"unset|estimated|network","paired":false,
 "storage":{"raw_used":0,"raw_capacity":0,"agg_used":0,"agg_capacity":0}}
```

### `POST /pair` — body `{"code":"<pairing code>"}` → `200 {"token":"...","schema":1}`
`409 pairing_closed` when unarmed, `403 pairing_invalid` on wrong/consumed
code. Response sets no cookies; the client stores the token.

### `GET /config` / `PUT /config`
```json
{"schema":1,"interval_ms":2000,"label":"bench-breathe"}
```
PUT is validated (`interval_out_of_range`, `label_too_long`) and applied
atomically; the response is the committed config.

### `POST /time` — body `{"wall_us": 1767225600000000}`
Sets wall clock; resulting quality is `estimated`. → `200` health-like
echo `{"clock":"estimated","wall_us":...}`.

### `GET /live` — latest sample + full status
```json
{"protocol":"v1","seq":1234,"wall_us":1767225600000000,"clock":"estimated",
 "uptime_s":123,"mode":"full","source":"default_cc",
 "storage":{"raw_used":100,"raw_capacity":4096,"agg_used":10,"agg_capacity":288,
            "oldest_seq":1,"newest_seq":1234},
 "channels":{"pm25":{...channel},"voc_raw":{...},"temperature_c":{...},"humidity_pct":{...}}}
```

### `GET /history?from=<wall_us>&to=<wall_us>` — bounded range query
Omitting both returns the retained window. Response:
```json
{"protocol":"v1","from":0,"to":0,"clock":"estimated","count":2,
 "records":[{"seq":1,"wall_us":0,"clock":"unset",
             "channels":{"pm25":{...},"voc_raw":{...},"temperature_c":{...},"humidity_pct":{...}}}]}
```
Records are ordered by ascending `seq`. `from`/`to` filter on `wall_us`
when `clock != "unset"` (records with unset wall clock are included only
when both bounds are omitted).

### `POST /events` — body `{"tag":"fan_on","note":"optional ≤200 bytes"}`
Tag must match `[a-z][a-z0-9_]{0,31}`; `session_start`, `window_open`,
`fan_on` are the reserved MVP tags but any valid tag is accepted.
→ `201 {"protocol":"v1","event_id":3,"mono_us":987654,"tag":"fan_on","note":""}`.
`GET /events` returns `{"protocol":"v1","count":n,"events":[same shape]}`.

### `GET /export.csv` and `GET /export.json` — explicit user export only
Both carry full retained history + events; the app downloads them verbatim.

CSV: first line is a metadata comment line, then a header row:
```
# bench-breathe export protocol=v1 clock=estimated fw=0.1.0-baseline exported_wall_us=1767225600000000 count=2
seq,wall_us,clock,pm25_ug_m3,voc_raw_ticks,temperature_c,humidity_pct
1,,unset,,,,
2,1767225600000000,estimated,12.30,214,25.40,48.10
```
Unset channel values are empty CSV fields. JSON:
```json
{"protocol":"v1","exported_wall_us":1767225600000000,"clock":"estimated",
 "fw":"0.1.0-baseline","count":2,
 "records":[{...history record shape...}],
 "events":[{...event shape...}]}
```

## USB-serial fallback (COM-03)

Line protocol over USB CDC @115200. One command per line (CRLF);
responses are NDJSON lines, terminated for commands by a status line
`OK` or `ERR <code>`. The device also free-runs one health NDJSON line
per second (the baseline line, field-compatible with `GET /live` minus
`seq`/`channels` nesting unchanged).

Commands (mutations require fresh button-arm, `ARM 30`):

| Command | Response |
|---|---|
| `GET health` | full serial health NDJSON line, `OK` |
| `GET config` | config NDJSON, `OK` |
| `SET config interval_ms=<n> [label=<s>]` | committed config NDJSON, `OK`, or `ERR interval_out_of_range` / `ERR label_too_long` / `ERR not_armed` |
| `TIME <wall_us>` | `{"clock":"estimated",...}`, `OK` |
| `PAIR` | `PAIR <code>` (arms pairing endpoint ≤10 min), requires arm |
| `GET history` | one NDJSON history record per line, then `OK` |
| `EXPORT csv` | CSV lines exactly as `GET /export.csv`, then `OK` |
| `RESET` | `{"reset":true}`, `OK`, requires arm |

`not_armed` serial error string mirrors the HTTP registry style.

## Data quality and status semantics (normative)
- Sensor class reports `ready`, `warming`, `fault`, or `unknown`.
- `value` non-null ⇔ `status:"ready"`; every non-ready channel carries a
  non-`none` `reason`.
- Time source and clock-quality state are included in export metadata.
- Exports are explicit user actions only; the app never uploads anything.

## Data ownership and privacy
- The user owns all captured data. No cloud, no telemetry, no analytics
  (in-app or device-side). All state (device URL, token) stays in browser
  `localStorage` on the user's machine; history stays on the device until
  the user exports it. Forgetting a device (Forget button) clears local
  state; factory reset on the device clears device-side data.
- Threat model: trusted private LAN only; MVP traffic is not encrypted —
  do not port-forward (COM-09).

## Compatibility rules
- Additive fields may appear at any time; clients must ignore unknown
  fields.
- Enum strings are stable wire values and never renumbered/reused; new
  enum values are minor changes, clients must degrade to `unknown`.
- Removal/renaming of fields, enum semantics changes, or auth changes are
  breaking → `/api/v2` (HTTP) or `protocol:"v2"` (serial) + this document
  gaining a migration section.
- `schema` in config responses allows config-shape evolution without an
  API version bump.
