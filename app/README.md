# Companion App (Local Web) — MVP

A zero-dependency, no-build-step web app that talks to a Bench Breathe
device over the versioned local protocol in [`docs/protocol.md`](../docs/protocol.md)
(contract v1). The compiled assets (`public/`) are plain static files: a real
device serves them itself, so setup and normal use need no internet-hosted
assets and no separately installed server (COM-05).

## Run locally (dev)

Requires Node.js ≥ 20 (nothing else — no `npm install`).

```sh
cd app
npm run dev        # starts the dev stub device on http://127.0.0.1:8123
# open http://127.0.0.1:8123 in a browser
```

The stub simulates a device (sensor physics, history ring, pairing) so the
whole app flow is exercised without a board. It is a **simulator**, not
firmware — real devices serve the same API once Wi-Fi provisioning lands.

First-run pairing demo:

1. In the app, enter device URL `http://127.0.0.1:8123` → **Check device**.
2. Simulate the physical button hold (stand-in for the real button + serial
   code printout): `curl -X POST http://127.0.0.1:8123/__dev/button`
   — prints the pairing code (real devices print it on the USB serial
   console, valid ≤10 min).
3. Enter the code → **Pair**. Live view, history, exports, and settings
   unlock.

## Tests

```sh
cd app
npm test           # node --test test/contract.test.mjs — 13 contract tests
```

`test/contract.test.mjs` asserts the wire shapes, limits, error codes, and
auth rules of `docs/protocol.md` v1 against the stub. It is the cross-project
contract test required by COM-04: when the device's real HTTP server exists,
the same suite runs against it unchanged.

## What the MVP covers

- **Setup flow**: device URL entry, health probe, button-armed pairing with
  single-use code, token storage, Forget-device recovery (COM-06/COM-07 UI).
- **Live view**: per-channel values with explicit data-quality states
  (`ready`/`warming`/`fault`/`unknown`, null + reason), device mode/power
  source/clock quality/uptime/storage, live PM2.5 trend chart.
- **History**: retained-window or wall-clock-range view with null-density
  summary; ordering falls back to `seq` while the device clock is unset.
- **Event tagging**: `session_start` / `window_open` / `fan_on` / custom.
- **Export**: CSV and JSON download via the device's export endpoints
  (`Content-Disposition: attachment`), never automatic.
- **Settings**: sampling-interval and label editing with reject-don't-clamp
  validation feedback (SNS-03), one-click clock sync (quality becomes
  `estimated`, honestly labelled).

## Data ownership & privacy

- The user owns all captured data. No cloud, no telemetry, no analytics.
- Device URL + API token live only in this browser's `localStorage`;
  **Forget device** clears them. History lives on the device until the user
  exports it.
- MVP traffic is plain HTTP on your trusted LAN — **not** confidential
  against a LAN attacker (COM-09). Never port-forward or internet-expose
  the device; the app never describes the device as internet-safe.

## Protocol boundary

- The app is a client of `docs/protocol.md` — no hidden device endpoints,
  no cloud-only paths. All API requests are same-origin (wildcard CORS is
  prohibited and contract-tested).
- Schema changes require an explicit protocol version bump and migration
  notes in `docs/protocol.md`.
