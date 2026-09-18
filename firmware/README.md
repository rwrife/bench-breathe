# Firmware — ESP32-C3 baseline

Bench Breathe firmware for the A0 hardware (`../hardware/kicad/bench-breathe.kicad_sch`):
ESP32-C3-WROOM-02-N4 + SPS30 (UART/SHDLC) + SGP40 + SHT40 (I2C), USB-C powered,
SELV/USB-only — no mains, no actuator control, advisory trend logging only.

Status: **baseline implemented and verified statically + natively (simulation).
Bench verification on a named prototype has NOT been performed** — no target
board existed on the verification host at implementation time (see
"Verification record" and the open bench items below).

## Layout

- `src/core/` — portable C++ core: no Arduino/ESP includes. CRC codecs,
  datasheet command layers (SHT40/SGP40/SPS30), sampler loop, bounded history,
  event log, button FSM, config validation, USB source-state gating (PWR-03
  matrix), NDJSON health renderer. All unit-testable natively.
- `src/device_hal.h` — thin Arduino/Wire/UART implementations (device env only).
- `src/main.cpp` — device glue: pin map, power gate, tick loop, serial stream.
- `test/test_core/` — datasheet-vector codec tests (SHT4x v6.4 §4.4/§4.6,
  SGP40 v1.2 Tables 9–10, SPS30 v2.0 §5.2/§5.3 example frames).
- `test/test_behavior/` — sampler/power-gate/button/config behavior over
  fake buses (`src/hal/host_sim.h`).

## Pinned toolchain (reproducible build)

Verified with PlatformIO Core 6.1.18 on Linux x86-64, 2026-09-18:

| Pin | Value |
|---|---|
| `platform` | `espressif32@6.10.0` (pinned in `platformio.ini`) |
| Arduino core | 3.20017.241212 (Arduino ESP32 core 2.0.17, installed by the platform pin) |
| `test platform` | `native@1.2.1` |
| C++ standard | `-std=gnu++17` with `build_unflags = -std=gnu++11` (core 2.x default is gnu++11 — the unflag is required) |

Install: `pip install platformio` then from `firmware/`:

```sh
pio test -e native     # host unit tests (19 test cases)
pio run -e esp32c3     # device build (clean rebuild: pio run -e esp32c3 -t clean first)
```

This is the "documented local automation" build path required by the issue;
the repo has no CI workflows, so these commands are the reproducible gate.
Any toolchain pin bump requires re-running BOTH commands and refreshing the
record below.

## Verification record (actual output, 2026-09-18, PlatformIO Core 6.1.18)

`pio test -e native`:

```
================= 19 test cases: 19 succeeded in 00:00:00.757 =================
```

`pio run -e esp32c3` (after `-t clean`):

```
RAM:   [====      ]  40.8% (used 133692 bytes from 327680 bytes)
Flash: [==        ]  22.1% (used 290162 bytes from 1310720 bytes)
========================= [SUCCESS] Took 2.35 seconds =========================
```

Evidence classes (per `hardware/requirements.md` §10): codec vectors and
behavior tests are **simulation-class** (host execution of the real code
paths against datasheet vectors/fake buses); the device build is
**static-class** (compiles + links, fits memory). Neither is a bench claim.

## Flashing, recovery, and update path

Hardware: J1 USB-C into the module's native USB (D+/D- via series R11/R12),
plus J3 debug header carrying 3V3/GND/EN/BOOT(GPIO9)/U0TXD/U0RXD.

**Flash (normal):**
```sh
pio run -e esp32c3 -t upload        # esptool via PlatformIO; uses USB CDC
# or explicitly:
pio run -e esp32c3 -t upload --upload-port /dev/ttyACM0
```

**Download-mode recovery** (firmware bricked / boot loop): pull BOOT (J3
pin 4, net `BOOT_GPIO9`) low while pulsing EN (J3 pin 3) or power-cycling;
the ESP32-C3 ROM bootloader enumerates and `pio run -t upload` works again.
R10 keeps GPIO9 high at normal boot; the header is the manual entry point.

**Full re-flash from scratch (recovery escalation):**
```sh
pio run -t erase                    # blank flash (erases history + config)
pio run -e esp32c3 -t upload
```

**Update/rollback path:** releases are tagged `firmware-vX.Y.Z`; updating is
`git checkout firmware-vX.Y.Z && pio run -e esp32c3 -t upload`. Rollback is
the same command on the previous tag (config schema `Config.schema` is
versioned; incompatible schema values fail `validate_config` and fall back
to defaults rather than reading old-layout garbage). OTA over Wi-Fi is
deliberately NOT in the baseline (issue #7 protocol scope).

> Bench status: none of the three commands above has been executed against a
> physical board yet — no target was attached to the verification host. This
> remains an open acceptance item tracked in issue #8's bring-up checklist.

## What the baseline does

1. **Power gating (PWR-03):** classifies the USB source from CC1/CC2 ADC
   windows (`core/power_source.h`) + CDC enumeration + REG_PG; the PM rail
   enable (U7, GPIO6) and Wi-Fi stay off outside full-sensing mode; repeated
   brownout reboots pin the device to recovery mode.
2. **Acquisition (SNS-02/03/04):** config-bounded interval (2–60 s, invalid
   values rejected not clamped); per tick: SHT40 → SGP40 (humidity-
   compensated, datasheet default words when SHT40 faults) → SPS30 poll.
   Slower channels repeat latest value with retained age; unavailable values
   are explicit nulls with reasons; warm-up windows follow datasheets
   (SPS30 30 s, SGP40 1 h baseline conditioning).
3. **Storage (DAT-01..03):** 24-byte compact records, deterministic
   oldest-first rollover, 5-min aggregate folding (mean-over-valid / max-VOC),
   capacity/used/oldest/newest published in health output. Wall-clock base
   freezes on first sync so corrections never reorder records (SNS-06).
   **Capacity caveat:** DAT-01/02 full windows (43,200 raw / 8,640 agg,
   ~1.04 MB + 0.28 MB) exceed SRAM and need the mmap'd flash partition —
   the baseline runs a 4096-record (~2.3 h @ 2 s) RAM arena and publishes
   honest capacity in the health stream.
4. **Serial fallback (COM-03):** 1 Hz NDJSON health line over USB CDC with
   protocol version, mode, source, storage state, clock quality, and all
   four channels with status+unit+value-or-null.
5. **Button (COM-06/DAT-06 detection):** debounced edge-to-edge hold windows —
   short press, ≥5 s setup-hold, ≥15 s factory-hold (fire on release only).
   Actions are event-marked; the setup/pairing flow itself is issue #7.

## Open bench-gated items (do not confuse with the above evidence)

- Flash/recovery/update commands untested on hardware (no board on host).
- CC advertisement ADC calibration vs the R1/R2 divider + ESP32-C3 ADC
  accuracy (windows are spec-conservative; bench must confirm boundaries).
- SHT40 thermal placement/slow-cadence accuracy, SGP40 baseline quality,
  SPS30 fan-start current overlap with Wi-Fi TX — all need PWR-04 captures.
- Full DAT-01/DAT-02 capacity via mmap flash partition; DAT-04/05/06
  power-loss-atomic persistence needs the flash store + fault injection.
- Wi-Fi/HTTP API, pairing, auth, setup-mode expiry (COM-04..09): issue #7.

## Responsibilities / interfaces (inherited plan)

Initialize sensors and validate readiness states; deterministic sampling +
timestamped records; bounded retention; local protocol endpoints (issue #7);
calibration/baseline workflows surfaced as channel status; button events and
indicator states. Provisioning/update: serial first, versioned config schema,
documented flash/rollback above.
