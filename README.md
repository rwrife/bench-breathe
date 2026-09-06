# Bench Breathe

USB-powered ESP32-C3 workshop air-quality logger that tracks PM2.5 and VOC trends locally to help makers improve ventilation habits without cloud accounts.

## Overview
Bench Breathe is a safe, low-voltage, local-first open-hardware project for hobby workshops and desk labs. It samples particulate and volatile-organic-compound (VOC) indicators, stores trend history locally, and serves a local companion dashboard for setup, calibration prompts, and export.

## Motivation
Makers often rely on smell or guesswork to decide when to open a window or run extraction fans. Bench Breathe provides clear trend visibility and event logging so ventilation decisions are easier and more consistent.

## Target users
- Electronics hobbyists and makers using soldering/flux
- 3D-printing users monitoring enclosure/workbench air trends
- Home workshop users who want local logging without cloud lock-in

## Concrete use cases
- Track PM and VOC trends during soldering sessions
- Compare baseline vs. active-work periods
- Log manual ventilation actions (window open, fan on) and see effect
- Export local data for personal analysis/troubleshooting

## Intended end-to-end workflow
1. Power the device from USB-C (SELV 5V only).
2. Connect from phone/desktop browser on local network or USB fallback.
3. Run first-time setup and baseline capture.
4. Start a work session and optionally mark ventilation events.
5. Review local trend charts and session summaries.
6. Export CSV/JSON snapshots under user control.

## MVP features
- ESP32-C3 firmware with deterministic sample cadence
- PM2.5 + VOC + temperature/humidity sensing pipeline
- Local buffering with bounded retention and explicit data deletion
- Local web companion for status, history, calibration prompts, and export
- Session/event markers (work started, fan enabled, window opened)
- Offline behavior documentation and recovery/reset flow

## Non-goals (MVP)
- No cloud account, cloud sync, or remote telemetry service
- No automatic fan/mains switching or relay control
- No compliance/certified industrial hygiene claims
- No medical, emergency, life-safety, or occupational-limit guarantee

## Privacy, permissions, and data storage
- Local-first by default; no mandatory external service
- Device stores only device telemetry/configuration and user-added event labels
- Companion app stores user data locally and exports only by explicit user action
- No microphone/camera/location requirement in MVP

## Hardware safety limits
- Prototype scope is SELV only (USB 5V)
- No mains wiring, no high-voltage interfaces, no safety-critical control loops
- Advisory trends only; not a certified exposure or safety instrument

## Planned editable source tree
- `hardware/kicad/bench-breathe.kicad_pro`
- `hardware/kicad/bench-breathe.kicad_sch`
- `hardware/kicad/bench-breathe.kicad_pcb` (when custom PCB starts)

> Final validated BOM data belongs in KiCad schematic symbol properties and is exported to `bom/bom.csv`.

## Current status
Scaffold and backlog only. No completed KiCad design, firmware build, app build, ERC/DRC report, or physical test evidence is claimed yet.

## Milestones
1. Requirements + architecture lock
2. Datasheet-backed part selection and KiCad schematic
3. PCB/layout + ERC/DRC + BOM export
4. Firmware + local companion app integration
5. Bring-up docs, assembly docs, and release artifacts

## Development quickstart (documentation phase)
```bash
git clone https://github.com/rwrife/bench-breathe.git
cd bench-breathe
```
Review `PLAN.md` and the issue backlog to execute one vertical slice at a time.
