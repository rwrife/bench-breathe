# Bench Breathe

USB-powered ESP32-C3 workshop air-quality logger that tracks PM2.5 and VOC trends locally to help makers improve ventilation habits without cloud accounts.

## Overview

Bench Breathe is a low-voltage, local-first open-hardware project for hobby workshops and desk labs. It samples particulate and VOC indicators with temperature/humidity context, stores bounded trend history locally, and provides a local companion dashboard for setup, quality states, event notes, and explicit export.

**Bench Breathe is a non-certified advisory trend logger.** It does not determine whether air is safe and is not a medical, emergency, life-safety, or occupational-exposure instrument.

## Intended users and use cases

- Electronics hobbyists comparing trends during soldering or rework.
- 3D-printing users comparing baseline and active-print periods.
- Home workshop users recording manual actions such as opening a window or enabling an independently controlled extractor.
- Makers exporting their own local CSV/JSON data for troubleshooting and analysis.

## MVP workflow

1. Power the device from a reputable 5 V USB SELV source.
2. Connect from a phone/desktop browser on the local network or use USB serial fallback.
3. Complete time-bounded setup and baseline/warm-up prompts.
4. Record a work session and optional ventilation event labels.
5. Review local trends, freshness, quality states, and data gaps.
6. Export or delete local data through an explicit user action.

## Frozen MVP baseline

The normative baseline is in [`hardware/requirements.md`](hardware/requirements.md), with subsystem ownership, dependencies, evidence gates, and the risk register in [`PLAN.md`](PLAN.md).

Key constraints:

- USB 5 V SELV only; <=250 mA steady-state target and <=500 mA peak.
- PM2.5, VOC proxy/index, temperature, and humidity trend channels.
- Default 2 s acquisition, bounded local retention, and deterministic rollover.
- Local HTTP/JSON app interface with USB serial setup/recovery/export fallback.
- Offline sampling without mandatory internet, cloud account, or outbound telemetry.
- Editable KiCad hardware sources and schematic-owned Manufacturer/MPN BOM data.
- Advisory trend language only; static, simulation, bench, and field evidence remain distinct.

## Explicit non-goals and safety limits

- **No mains wiring or control.** No relays, fan switching, actuators, machinery control, or safety interlocks.
- **No hazardous-voltage or USB-PD operation.** The project is nominal 5 V USB SELV only.
- **No medical, emergency, fire/smoke/gas-alarm, life-safety, or occupational-limit function.**
- **No certified accuracy or safe/unsafe determination.** Placement, warm-up, drift, contamination, airflow, and faults can produce misleading data.
- **No mandatory cloud service or internet access.**
- Indoor, dry, non-condensing hobby-workshop use only; not for outdoor, explosive, or industrial-process environments.

Users must follow tool/material manufacturer guidance and appropriate ventilation and PPE practice independently of this device.

## Architecture at a glance

- **Hardware:** USB input/protection/regulation, ESP32-C3, PM/VOC/temp-humidity interfaces, status/input, debug/test access, PCB, and enclosure interface.
- **Firmware:** deterministic acquisition, validity states, bounded retention, atomic configuration, versioned local API, and serial recovery.
- **Companion web app:** setup, status/history, event notes, configuration, explicit export/delete, and accessible advisory messaging.
- **Shared protocol:** [`docs/protocol.md`](docs/protocol.md) is finalized contract v1 (HTTP + USB-serial shapes, units, limits, errors, authorization). The firmware baseline still streams the v0-compatible serial line; adoption is tracked in `docs/release-checklist.md` (T-1).

The device remains authoritative for sensor state, timestamps, configuration limits, and retained records. The app presents that contract and must not turn null/invalid values into apparently valid measurements. For the MVP, compiled app assets are served by the device for offline same-origin use. A physical, time-bounded setup action issues the per-device local credential; this reduces casual LAN access but does not make cleartext HTTP confidential or safe for internet exposure.

## Source tree

- `hardware/requirements.md` — normative MVP requirements and safety boundaries
- `hardware/kicad/bench-breathe.kicad_pro` — editable KiCad project container
- `hardware/kicad/bench-breathe.kicad_sch` — editable A0 electrical schematic and schematic-owned BOM-property source
- `hardware/kicad/bench-breathe.kicad_pcb` — planned editable PCB
- `hardware/component-selection.md` — exact M2 parts, manufacturer-datasheet checks, static power budget, and dated availability snapshot
- `firmware/` — device firmware and verification
- `app/` — local companion web app
- `docs/protocol.md` — device/app contract (v1)
- `docs/bring-up.md` — integration bring-up procedure, wiring/pinouts, calibration, troubleshooting matrix, and evidence ledger
- `docs/release-checklist.md` — fabrication/release artifact gates and open tracked items
- `bom/bom.csv` — generated stuffed-BOM export from schematic properties (regenerate with `python3 bom/export_bom.py`, gate with `python3 bom/verify_bom.py`)
- `bom/README.md` — BOM workflow, sourcing/pricing policy, and file roles
- `bom/non-schematic-items.csv` — enclosure, cables, fasteners, adapter, power supply, and PCB fab with explicit planning status

The current `bom/preliminary-bom.csv` is the issue-#2 planning list reconciled against the schematic (`Schematic_Refs`/`Reconciliation` columns). It is not a fabrication-ready BOM; `bom/bom.csv` is the export artifact.

## Project status

| Milestone | Status |
|---|---|
| M1 — Requirements, architecture, safety, and risk baseline | Baseline documented |
| M2 — Datasheet-backed component selection | Static selection complete; physical validation not started |
| M3 — Editable KiCad schematic and ERC | Complete: clean KiCad 9 ERC plus static validation and PDF review export |
| M4 — Schematic-source BOM export | Complete: `bom/bom.csv` generated from schematic properties with reproducibility + no-fabricated-price gate (`bom/verify_bom.py`) |
| M5 — PCB layout and DRC | A0 evidence board complete: 0 DRC violations with 15 documented unrouted stubs — **not fab release** (see `hardware/pcb-notes.md` §Residuals and `docs/release-checklist.md`) |
| M6 — Firmware baseline | Baseline implemented + natively verified (19 unit tests, pinned device build). Bench flash/flash-recovery and power gating on hardware not performed |
| M7 — Companion app baseline | App MVP + contract v1 complete; 13/13 contract tests against the dev simulator only — never run against a real device |
| M8 — Integration and bench bring-up | Bring-up procedure, wiring/pinouts, and troubleshooting published (`docs/bring-up.md`); all bench steps unexecuted — no prototype exists |
| M9 — Mature fabrication/release bundle | Gate checklist published (`docs/release-checklist.md`); fab artifacts blocked on A1 stub closure |

The editable A0 schematic and its static ERC/analyzer evidence are complete,
as is the A0 evidence PCB (0 DRC violations, 15 documented unrouted stubs —
not fab release), the natively verified firmware baseline, and the
contract-tested companion app (simulator-evidence only). PCB fab export,
simulation, firmware/app builds on hardware, assembly, bench measurement,
field results, and certification are not claimed. See
`docs/bring-up.md` (bench procedure and evidence ledger) and
`docs/release-checklist.md` (release gates and open tracked items).

## Development start

```bash
git clone https://github.com/rwrife/bench-breathe.git
cd bench-breathe
```

Review `hardware/requirements.md`, `PLAN.md`, and the issue backlog before implementing a subsystem. Work should proceed in dependency order and attach the evidence named by the relevant milestone; documentation alone does not satisfy a hardware or physical-test gate.
