# Device ↔ App Protocol (Draft v0)

## Goals
- Deterministic, versioned, local-first communication between Bench Breathe firmware and companion app.
- Safe degradation when network features are unavailable.

## Transport assumptions
- Primary: local network HTTP + JSON
- Fallback: USB serial command/response bridge for setup and export
- No mandatory internet dependency

## Core resources (draft)
- `GET /api/v1/health` — firmware version, uptime, sensor readiness, storage state
- `GET /api/v1/config` — sampling interval, retention settings, device label
- `PUT /api/v1/config` — validated config updates
- `GET /api/v1/live` — latest sample and quality flags
- `GET /api/v1/history?from=&to=` — range query for time-series data
- `POST /api/v1/events` — user-tagged events (fan_on, window_open, session_start)
- `GET /api/v1/export.csv` / `GET /api/v1/export.json` — explicit local export

## Data quality and status semantics
- Sensor class may report `ready`, `warming`, `fault`, or `unknown`
- Missing/invalid channels are explicit `null` + reason, never silently dropped
- Time source and clock-quality state are included in export metadata

## Security assumptions (MVP)
- Local trusted-network environment by default
- No hardcoded cloud keys
- Document threat model limits for LAN exposure
- Future auth hardening can add optional local credentials without breaking offline mode

## Versioning
- Protocol version embedded in responses
- Breaking changes require `/api/v2/...` path and migration notes
