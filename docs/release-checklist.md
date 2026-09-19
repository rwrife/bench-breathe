# Fabrication / Release Artifact Checklist

Purpose: define what a **mature release bundle** must contain per subsystem,
track the status of each artifact honestly (generated ≠ verified-on-bench),
and give the exact regeneration commands so any artifact is reproducible from
committed sources (packaging policy: `PLAN.md` §Packaging and release policy).

Status vocabulary: **done** (artifact committed + regeneration proven) ·
**blocked** (named blocker) · **not started** · **bench-gated** (artifact
cannot be honestly completed without a named prototype).

## 1. Hardware

| Artifact | Path | Status | Regeneration |
|---|---|---|---|
| Editable KiCad project | `hardware/kicad/bench-breathe.kicad_pro/.kicad_sch/.kicad_pcb` | done | schematic via `generate_schematic.py`; PCB via `hardware/kicad/scripts/` chain (`hardware/kicad/README.md`, `hardware/pcb-notes.md`) |
| Schematic PDF | `hardware/kicad/exports/bench-breathe-schematic.pdf` | done | `kicad-cli sch export pdf …` |
| ERC report | `hardware/kicad/reports/erc.json` | done — 0 violations (re-run 2026-09-19) | `kicad-cli sch erc …` |
| DRC report | `hardware/kicad/reports/pcb-drc-final.json` (+ `pcb-drc-issue8-recheck.json`) | done as **static evidence** — 0 violations / 15 stubs | `kicad-cli pcb drc …` |
| **Gerbers + drill + board paste (CPL)** | `hardware/kicad/fab/` | **BLOCKED — not exported** | After the 15 stubs close (A1). `pcb-notes.md` §Residuals is explicit: A0 is *not* fab release. Export then via `kicad-cli pcb export gerbers/drill/pos-files`. Exporting Gerbers for an unrouted board would violate R-12 honesty. |
| Fabrication quote / fab parameter check | `docs/` note | not started | requires Gerbers → JLCPCB/PCBWay design-rule check (jlcpcb/pcbway workflow) |
| Assembly drawing / pick-place review | — | not started | after fab export gate |
| Board renders (STEP/photos) | — | not started — placeholder: no render committed | STEP: `kicad-cli pcb export step`; photos are bench-gated |
| Antenna/RF, thermal | — | bench-gated | `pcb-notes.md`: static checks cannot evaluate |

**Gate to unblock hardware fab artifacts:** close the 15 documented stubs
(A1 nudge/manual fanout per `pcb-notes.md` fix table), re-run DRC to 0/0,
then export fab files and record fab-house design-rule confirmation.

## 2. BOM

| Artifact | Path | Status | Regeneration |
|---|---|---|---|
| Stuffed BOM export | `bom/bom.csv` | done — regenerate+gate pass 2026-09-19 (26 lines / 37 refs) | `python3 bom/export_bom.py && python3 bom/verify_bom.py` |
| Non-schematic items | `bom/non-schematic-items.csv` | done (planning-status rows, sourcing TBD) | manual curation (policy: bom/README.md) |
| Order-time stock/price refresh | — | not started (order-time only; policy forbids stale live-scraped numbers in-repo) | distributor skills at order time |
| JLCPCB-format BOM/CPL translation | `bom/` | blocked by fab gate (needs CPL) | `bom` skill `translate_bom_pnp.py` after fab export |

## 3. Firmware

| Artifact | Status | Evidence / gate |
|---|---|---|
| Source + pinned PlatformIO env (`platformio.ini`) | done | build SUCCESS re-run 2026-09-19 |
| Unit/behavior tests | done — 19/19 (simulation class) | `pio test -e native` |
| Reproducible binary | not started — no tag; binaries only when reproduced from a tag (policy) | after tag `firmware-v0.1.0` once bench Step 4 passes |
| Flashing/recovery instructions | done (documented, bench-gated execution) | `firmware/README.md` §Flashing + `docs/bring-up.md` §4 |
| Protocol v1 serial adoption (`protocol:"v1"`, `reason`, serial command set) | not started — known delta in `docs/protocol.md` | tracked below (Open tracked items T-1) |
| Full DAT-01 mmap flash partition | not started | firmware README open item (T-2) |
| Release notes with evidence classes | not started — first release notes must name prototype + evidence classes | at first tag |

## 4. Companion app

| Artifact | Status | Evidence / gate |
|---|---|---|
| Static assets (`app/public/`) | done | zero-dep, no build step (COM-05) |
| Contract tests | done — 13/13 (simulation class) | `cd app && npm test` |
| Dev simulator | done — `app/dev/stub-server.mjs` (explicitly a simulator) | — |
| Device-side HTTP serving + Wi-Fi provisioning | not started | app runs against stub today (T-3) |
| Release bundle / notes | not started | blocked on device HTTP + bench |

## 5. Integration / docs

| Artifact | Status |
|---|---|
| Protocol contract v1 | done — `docs/protocol.md` (final, v0→v1 breaking list + known deltas) |
| Bring-up guide + wiring/pinouts + calibration + troubleshooting | done (this PR) — `docs/bring-up.md`; bench cells deliberately unexecuted |
| Bench evidence records | bench-gated — attach to `docs/bring-up.md` §9 ledger |
| Field observations | optional; never claimed |

## 6. Release gate (all must read done or explicitly waived in writing)

- [x] Editable KiCad sources
- [x] Clean ERC + static validator
- [ ] DRC 0 violations **and 0 unresolved stubs** ← current blocker
- [ ] Gerbers/drill/CPL exported + fab-rule checked
- [ ] `bom/bom.csv` gate pass (done at HEAD; re-check at release)
- [ ] Firmware tag + reproduced binary + bench Step 4 pass
- [ ] Protocol v1 serial adoption in firmware (T-1)
- [ ] Device HTTP serving + app paired against real device (T-3)
- [ ] Bring-up bench record for a named revision (Steps 3–6, 8)
- [ ] Release notes stating completed evidence classes only (R-12)

## Open tracked items (absorbed from issue #8 body — each needs its own issue/PR)

| ID | Item | Owner track |
|---|---|---|
| T-1 | Firmware serial protocol-v1 adoption: `"protocol":"v1"`, per-channel `reason`, serial command set (GET/SET/TIME/PAIR/EXPORT/RESET, `ARM 30`) | firmware |
| T-2 | DAT-01 full-capacity mmap flash partition + power-loss atomicity fault injection | firmware |
| T-3 | Device-side HTTP serving + Wi-Fi provisioning/setup mode | firmware/app |
| T-4 | A1 stub closure (15 documented, fixes pre-registered in `pcb-notes.md`) → fab export gate | hardware |
| T-5 | CC ADC window calibration vs divider + ESP32-C3 ADC accuracy (bring-up Step 3.7) | bench |
| T-6 | Bench record of Steps 3–6/8 on a named prototype (R-03/R-12 evidence) | bench |

## Placeholder media (explicitly marked until replaced)

- Assembly photo — `docs/bring-up.md` §1
- Bench captures (current waveform, I²C scan, console) — `docs/bring-up.md` §9
- Board renders/STEP — no image committed anywhere in the repo; renders will
  live beside fab files once exported
