# Bench Breathe — Integration and Bring-Up Guide (A0)

Target revision: **A0** (`hardware/kicad/bench-breathe.kicad_pcb`, board
65 × 75 mm, 2 copper layers) with firmware `0.1.0-baseline`
(`firmware/`) and companion app contract v1 (`docs/protocol.md`).

**Evidence-class legend (used throughout — see `hardware/requirements.md` §10
and risk R-12):**

| Class | Means |
|---|---|
| static | geometry/compile/metadata checks reproducible from committed sources |
| simulation | host-executed code paths / device simulator, never a real board |
| bench | physical measurement on a named prototype revision |
| field | optional representative observation; never calibration/certification |

> **This guide is a bench procedure with pre-registered pass/fail limits. As
> of writing, NO section marked "bench" has been executed — no A0 prototype
> exists.** Completing a bench step means recording: date, board revision,
> instrument (model + calibration status), and raw reading, then filing the
> result under this issue's evidence. Static/simulation results may never be
> written into a bench cell.

## 0. Safety boundaries (read first)

- **USB 5 V SELV only.** No mains wiring or control, no relays/actuators,
  no USB-PD sourcing. Power the board only from a reputable 5 V USB supply
  or a current-limited bench supply set ≤ 5.5 V / ≤ 1 A.
- The device is an **advisory trend logger**. It does not determine whether
  air is safe; it is not a medical, emergency, or occupational instrument.
- If current draw exceeds the limits in Step 3, **unplug** — the PPTC F1 is
  a slow fault device, not a precision current limiter.
- J3 is 3.3 V logic only. Never inject 5 V into it; SPS30 5 V appears only
  on J2 pin 1 when the PM rail gate (U7) is enabled by firmware.

## 1. What you need

| Item | Ref | Notes |
|---|---|---|
| A0 board, stuffed | — | BOM: `bom/bom.csv` (26 lines / 37 refs; source of truth = schematic properties). No DNP lines on A0. |
| SPS30 PM module + harness cable | U2, J2 | Cable: JST ZHR-5 crimp → SPS30. See §2.3 for harness pinout; verify continuity before first power-up. |
| USB-C data-capable cable | NS-004 (bom/non-schematic-items.csv) | Known-good data cable required (charging-only cables hide the console). |
| 5 V USB supply or bench supply | NS-007 | ≥ 1 A recommended for headroom above the ~430 mA static worst-case budget. |
| Multimeter (+ shunt/µA meter or current probe for Step 3) | — | |
| USB-UART adapter (optional) | NS-006 | Only if you prefer the U0TXD/U0RXD console on J3 over native USB CDC. |
| Enclosure with airflow path (Step 7 only) | NS-003 | Vented; SPS30 intake unobstructed; SHT40 away from heat. |

**Fab/assembly note (static-class blocker carried from A0):** the committed
board has 15 open ratsnest stubs documented in
`hardware/pcb-notes.md` §Residuals and `hardware/kicad/reports/`.
**A0 is an evidence board for placement/DRC/geometry validation, not a fab
release.** Fabricate only after the A1 stub closure lands; until then, this
guide applies to whatever board revision is named in the bench record.
[PLACEHOLDER: assembly photo — replace with real photo of stuffed A0]

## 2. Wiring and pinouts

All tables below are extracted from the editable sources (schematic net
assignments + PCB pad nets + `firmware/src/main.cpp` / `device_hal.h`), not
re-typed from memory. If you change one source, regenerate the others.

### 2.1 J1 — USB-C receptacle (input power + native USB)

| Pin | Net | Function |
|---|---|---|
| A4/A8/A9/B4/B8/B9 | VBUS | 5 V in (internally bonded) |
| A5 / B5 | CC1_SENSE / CC2_SENSE | 5.1 kΩ Rd to GND (R1/R2); also ADC source-classify sense |
| A6/B6 + A7/B7 | USB_CONN_DP / USB_CONN_DM | through ESD array U6, then 0 Ω R12/R11 → USB_DP/USB_DM at the module |
| A1/A12/B1/B12, S1 | GND | shell/ground (pour-connected) |

### 2.2 J3 — debug/program header (1×6, 2.54 mm, 3.3 V only)

| Pin | Net | ESP32-C3 GPIO | Use |
|---|---|---|---|
| 1 | +3V3 | — | 3.3 V reference/monitor only — not a 500 mA rail tap |
| 2 | GND | — | |
| 3 | EN | EN | pulse low→high to reset; hold low + BOOT for download mode |
| 4 | BOOT_GPIO9 | GPIO9 | pull low during EN pulse → ROM bootloader (firmware recovery) |
| 5 | PM_UART_RX | GPIO20 (U0RXD) | console RX (module native USB is CDC; this is the secondary path) |
| 6 | PM_UART_TX | GPIO21 (U0TXD) | console TX |

### 2.3 J2 — SPS30 harness (JST PH 1×5, board side)

| Pin | Net | Mates to (SPS30 ZHR-5 cable) |
|---|---|---|
| 1 | PM_5V | red — 5 V, gated by U7 (off until firmware enables) |
| 2 | PM_UART_RX | white/blue — SPS30 TX (module RXD ← board) |
| 3 | PM_UART_TX | SPS30 RX |
| 4 | (SEL, floating via NC) | SPS30 SEL — floating selects UART mode |
| 5 | GND | black |

Verify harness continuity **unpowered** before mating to the SPS30: pin-to-pin
on both ends, and no short 1↔5.

### 2.4 Test points (19, one pad each)

TP1 VBUS · TP2 VBUS_FUSED · TP3 +3V3 · TP4 GND · TP5 PM_5V · TP6 REG_PG ·
TP7 EN · TP8 BOOT_GPIO9 · TP9 I2C_SDA · TP10 I2C_SCL · TP11 USB_DP ·
TP12 USB_DM · TP13 CC1_SENSE · TP14 CC2_SENSE · TP15 PM_ENABLE ·
TP16 USER_BUTTON_N · TP17 PM_UART_RX · TP18 PM_UART_TX · TP19 SGP_VDD

TP11/TP12 are on the **module side** of the 0 Ω links — lifting R11/R12
isolates the host-side pair.

### 2.5 Firmware GPIO map (from `firmware/src/main.cpp` / `device_hal.h`)

| GPIO | Net | Direction | Note |
|---|---|---|---|
| 0 / 1 | CC1_SENSE / CC2_SENSE | ADC | source classification (PWR-03) |
| 3 | REG_PG | input | buck power-good presence gate |
| 4 / 5 | I2C_SDA / I2C_SCL | I²C 100 kHz | SHT40 @0x44, SGP40 @0x59 |
| 6 | PM_ENABLE | output | U7 gate; LOW = PM rail off |
| 7 | STATUS_LED_K | output | active-low |
| 9 | BOOT_GPIO9 | strap | R10 10 kΩ pull-up |
| 10 | USER_BUTTON_N | input | active-low (R8 pull-up populated) |
| 20 / 21 | PM_UART_TX / PM_UART_RX | UART1 115200 8N1 | SPS30 (SHDLC) |

## 3. First power-up (bench) — smoke and rails

Pre-registered pass/fail. Stop at the first FAIL; troubleshooting matrix is §7.

| # | Step | Expected (pre-registered) | Class | Result |
|---|---|---|---|---|
| 3.1 | Visual: orientation of D1/D2/U5/U7/J1/J2, solder bridges, J2 unconnected | no bridge at U5 WSON-8 / U6 USON-10 | bench | ☐ |
| 3.2 | USB-C cable only to host port (or supply ≤1 A limit), meter in series | **< 100 mA** (RecoveryOnly — PM rail off, Wi-Fi off) | bench | ☐ |
| 3.3 | TP3↔TP4 | 3.30 V ±5 %, ripple not visible on DMM | bench | ☐ |
| 3.4 | TP1↔TP4 / TP2↔TP4 | both ≈ 5.0 V (within cable drop) | bench | ☐ |
| 3.5 | TP6 (REG_PG) | HIGH (≈ 3.3 V via R3 pull-up) | bench | ☐ |
| 3.6 | TP5 (PM_5V) | **≈ 0 V** (U7 gated off at boot) | bench | ☐ |
| 3.7 | TP13/TP14 (CC sense) with plain host port | ≈ 0.2–0.4 V default-USB window (firmware windows 200–380 mV; **bench must confirm window edges vs ADC accuracy** — open item in firmware README) | bench | ☐ |

## 4. Firmware flash + console (bench)

```sh
cd firmware && pio run -e esp32c3 -t upload        # or --upload-port /dev/ttyACM0
picocom -b 115200 /dev/ttyACM0                     # USB CDC console
```

Expected (pre-registered):

| Check | Pass criterion |
|---|---|
| Upload succeeds | esptool erase+write+verify OK |
| Console output | one NDJSON health line per second; `"protocol":"v0"` and `"fw":"0.1.0-baseline"` (baseline known delta — v1 `reason` field + serial commands are pending firmware adoption, tracked in `docs/protocol.md` Known deltas) |
| `mode` field | `"recovery"` before pairing/full-source state, `"full"` once source permits — PM stays off until then |
| Recovery path | hold BOOT (J3-4) low, pulse EN (J3-3): chip re-enumerates, upload works again |
| Full re-flash | `pio run -t erase` then upload; device returns to defaults |

## 5. Sensor interface checks (bench)

With the source in a state that permits full sensing (per §4 health line
`mode:"full"`, then `TP15` HIGH and `TP5` ≈ 5 V):

| # | Check | Expected | Class | Result |
|---|---|---|---|---|
| 5.1 | I²C scan (ESP32 I2CScanner or `GET` via serial once command set lands) | exactly **0x44** (SHT40) and **0x59** (SGP40) | bench | ☐ |
| 5.2 | TP19 (SGP_VDD) | ≈ 3.27 V (3.3 V minus ~10 Ω×≤3 mA drop) | bench | ☐ |
| 5.3 | SHT40 channel in health line | `temperature_c`/`humidity_pct` reach `"status":"ready"` within ~2 ticks (2 s default), plausible room values (e.g. 18–30 °C, 30–70 %RH) | bench | ☐ |
| 5.4 | SPS30 startup on PM enable | fan audible; `pm25` stays `"warming"` ≥ 30 s (datasheet spin-up), then `"ready"` with non-null value; TP17/TP18 show SHDLC traffic (0x7E-framed) on scope/analyser | bench | ☐ |
| 5.5 | SGP40 conditioning | `voc_raw` present (ticks, not index); treat first **1 h** as baseline-conditioning (datasheet) — values advisory until conditioned; this is the **calibration/baseline procedure**: run the device for ≥ 1 h in the target environment with clean-ish air before interpreting VOC trends. SHT40/SPS30 need **no** user calibration; SGP40 has no user offset — its baseline drifts with contamination and is advisory only | bench | ☐ |
| 5.6 | PM off again (recovery mode) | PM_5V falls to < 0.1 V within a tick of mode change; U7 QOD discharge visible on TP5 | bench | ☐ |

## 6. Power/performance checks (bench) — R-03 evidence

| # | Check | Pass limit (pre-registered from static budget, `hardware/component-selection.md`) | Class | Result |
|---|---|---|---|---|
| 6.1 | Average input current, full sensing steady state | ≤ **250 mA** @ 5 V (project ceiling) | bench | ☐ |
| 6.2 | Peak input current during concurrent Wi-Fi TX + SPS30 fan start | ≤ **500 mA**; waveform captured (instrument + probe named) — static estimate ≈ 430 mA, only ~72 mA headroom | bench | ☐ |
| 6.3 | SHT40 heater (if exercised) never concurrent with fan start/TX | no overlap event in capture | bench | ☐ |
| 6.4 | Brownout-loop guard: force droop (current-limited supply at 4.4 V) | repeated brownouts ≥ 3 pin device to RecoveryOnly, no flash loop | bench | ☐ |
| 6.5 | 3.3 V rail under 6.2 peak | no EN dip (TP7 ≥ 3.0 V), TP3 stays in spec | bench | ☐ |

## 7. Troubleshooting matrix

| Symptom | First checks | Likely cause class |
|---|---|---|
| No console, LED dead, 0 current | Cable (data-capable?), TP1 VBUS, TP2 after F1, D1 orientation | assembly/cable |
| VBUS present, no 3V3 (TP3=0) | TP6 REG_PG, U5 solder (WSON-8), L1, FB/EP to GND | assembly |
| 3V3 OK, no enumeration | TP11/TP12 vs TP (host side): lift R11/R12 to isolate; try J3-5/6 console | USB path / cable |
| Enumerates, health line `mode:"recovery"` forever | CC windows on TP13/14 (3.7) — check R1/R2 5.1 k, divider; try known 1.5 A adapter | source classify (bench item 3.7) |
| `pm25` stuck `"warming"`/`"fault"` | J2 harness continuity (§2.3), TP5=5 V after PM enable, fan sound, TP17/18 frames | harness first — most probable assembly defect |
| I²C scan finds neither/one sensor | TP9/10 ~3.3 V idle (R5/R6), U3/U4 solder (DFN), short list in §5.1 | assembly |
| SHT40 temp reads high | proximity to U5/U1 (heat) — static design places sensors on quiet island; re-check placement revision + enclosure airflow | design/bench |
| Boot after erase behaves oddly | config schema fallback to defaults is expected (validate_config), not corruption | firmware behavior (documented) |
| Device pairs but API 401s | stale token → Forget + re-pair; `ARM 30` needed for serial mutations | protocol (docs/protocol.md) |

## 8. Companion app bench acceptance

Real-device acceptance once the device serves HTTP (tracked open item —
firmware baseline does not; app currently runs against the dev simulator,
**simulation class**):

1. Serve `app/public/` from the device (COM-05) — open in phone browser.
2. Hold button ≥ 5 s → serial prints `PAIR <code>`; pair from app ≤ 10 min.
3. Live/history/export views show only `ready` values; null channels render
   as gaps, never zeros (contract v1 §Common shapes).
4. `window_open` event tag appears in history overlay and in both exports.
5. USB-serial fallback (§4) still works with Wi-Fi disabled.

## 9. Evidence ledger for this guide

| Gate | Status at writing | Evidence |
|---|---|---|
| ERC clean | static — **pass** (re-run 2026-09-19) | `hardware/kicad/reports/erc.json` (0 violations, KiCad 9.0.9) + `validate_schematic.py` PASS (34 pin-net maps, 61 components) |
| PCB DRC | static — **0 violations, 15 stubs documented, NOT fab release** | `reports/pcb-drc-final.json` + fresh re-verification `reports/pcb-drc-issue8-recheck.json` (2026-09-19: same 15 stubs / 1 zone-pseudo-rat; one stub cites a different F.Cu track pair — same electrical stub), `pcb-notes.md` §Residuals |
| BOM gates | static — **pass** (2026-09-19) | `bom/verify_bom.py` PASS (26 lines/37 refs, no fabricated price), `verify_component_selection.py` PASS |
| Firmware tests/build | simulation + static — **pass** (2026-09-19) | `pio test -e native` 19/19; `pio run -e esp32c3` SUCCESS |
| App contract tests | simulation — **pass** (2026-09-19) | `npm test` 13/13 (Node v22.23.1) |
| Steps 3–6, 8 | bench — **NOT PERFORMED — no prototype** | this guide, awaiting first A1/prototype |
| Field observation | field — none claimed | — |

[PLACEHOLDER: bench capture screenshots (current waveform, I²C scan, health-line console) — to be attached to the first bench record naming the prototype revision]
