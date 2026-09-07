# Datasheet-backed component selection

Status: **M2 static component selection complete; electrical design and physical validation not started**

Snapshot date: **2026-09-07 UTC**

This document records the exact parts selected for the first schematic pass. Manufacturer datasheets are the electrical ground truth. The editable staging sheet at [`kicad/bench-breathe.kicad_sch`](kicad/bench-breathe.kicad_sch) carries `Manufacturer`, `MPN`, `Datasheet`, `Package`, and `BOM Comments` properties plus `LCSC` only for manufacturer-validated matches. It intentionally has no electrical connectivity; issue #3 owns functional symbols, wiring, footprints, ERC, and the complete application circuits.

## Selected parts

| Ref | Function | Manufacturer / MPN | Package or interface | Why selected |
|---|---|---|---|---|
| U1 | Controller and Wi-Fi | Espressif Systems `ESP32-C3-WROOM-02-N4` | 19-pad 18.0 x 20.0 x 3.2 mm module, PCB antenna | Native USB D-/D+ on module pins 13/14, 4 MB flash, 15 GPIOs, local Wi-Fi, documented antenna keepout |
| U2 | PM1/PM2.5/PM4/PM10 channel | Sensirion `SPS30` | Module; JST ZHR-5 mating connector; UART or I2C | Manufacturer-supported particulate module, 1 s sampling, documented warm-up/lifetime and 3.3 V-compatible interface levels |
| U3 | VOC proxy/index channel | Sensirion `SGP40-D-R4` | DFN-6, 2.44 x 2.44 x 0.85 mm, center pad | Dedicated VOC raw signal and Sensirion VOC Index algorithm; accepts humidity/temperature compensation |
| U4 | Temperature/humidity context | Sensirion `SHT40-AD1B-R2` | DFN-4, 1.5 x 1.5 x 0.5 mm, open cavity | 0x44 I2C device, low measurement current, supplies compensation inputs for U3 |
| U5 | 5 V to 3.3 V conversion | Texas Instruments `TPS62162DSGR` | WSON-8 exposed pad (DSG), 2.0 x 2.0 mm | Fixed 3.3 V, 1 A synchronous buck; 3–17 V input withstands the selected VBUS TVS clamp |
| U6 | USB signal/CC ESD | Texas Instruments `TPD4E05U06DQAR` | USON-10 (DQA), 2.5 x 1.0 mm | Four 0.5 pF-class channels for D+, D-, CC1, and CC2; IEC 61000-4-2 system-level rating |
| U7 | Switched 5 V PM rail | Texas Instruments `TPS22919DCKR` | SC-70-6 (DCK), 2.1 x 2.0 mm | MCU-controlled PM power removal, controlled rise time, output discharge, and 1.5 A capacity |
| J1 | USB-C USB 2.0 receptacle | GCT `USB4105-GF-A` | Right-angle top-mount hybrid SMT/THT | USB 2.0 data contacts, mechanically staked shell, 5 A aggregate VBUS contact test margin; no PD controller |
| F1 | Input overcurrent fault protection | Bourns `MF-MSMF050-2` | 1812 | 0.50 A hold / 1.00 A trip PPTC for fault protection |
| D1 | VBUS transient clamp | Diodes Incorporated `SMBJ5.0A-13-F` | SMB / DO-214AA, unidirectional | 5.0 V working standoff and 9.2 V maximum rated-pulse clamp, below U5's 17 V recommended maximum |

## Manufacturer-datasheet checks

### U1 — ESP32-C3-WROOM-02-N4

Source: [ESP32-C3-WROOM-02 datasheet v1.7](https://documentation.espressif.com/esp32-c3-wroom-02_datasheet_en.pdf).

- Table 1-1 (p. 3) identifies the N4 variant as 4 MB Quad-SPI flash, -40 to 85 °C, and 18.0 x 20.0 x 3.2 mm.
- Table 3-1 (pp. 10–11) maps module pin 13 to GPIO18/USB_D- and pin 14 to GPIO19/USB_D+; pins 1, 9, and 19 are 3V3/GND.
- Table 6-2 (p. 22) requires 3.0–3.6 V and an external supply capable of at least 0.5 A.
- Table 6-4 (p. 23) reports 345 mA peak for 802.11b TX at 20.5 dBm and 84 mA peak RX for HT40.
- Layout must enforce the datasheet antenna keepout. USB D+/D- and boot strapping on GPIO2/8/9 require explicit issue-#3 review.

### U2 — SPS30

Source: [SPS30 datasheet v2.0 D1](https://sensirion.com/media/documents/8600FF88/64A3B8D6/Sensirion_PM_Sensors_Datasheet_SPS30.pdf).

- Table 2 (p. 3): 4.5–5.5 V supply, 55 mA typical/65 mA maximum in measurement mode, 80 mA maximum during the first 200 ms of fan start.
- Table 4 (p. 4): pin 1 VDD, pin 2 RX/SDA, pin 3 TX/SCL, pin 4 SEL, pin 5 GND. The interface accepts 3.3 V LVTTL levels.
- The corresponding cable-side connector is JST ZHR-5. Pull SEL low for I2C or leave it floating for UART.
- Table 1 (p. 2): 1 s sampling interval, typical stable-output start-up of 8–30 s depending on concentration, and calculated lifetime over 10 years at 24 h/day.
- The housing/shield is internally tied to signal GND; do not create a second unintended chassis-current path.

### U3 — SGP40-D-R4

Source: [SGP40 datasheet v1.2](https://sensirion.com/media/documents/296373BB/6203C5DF/Sensirion_Gas_Sensors_Datasheet_SGP40.pdf).

- Table 2 (p. 4): VDD/VDDH 1.7–3.6 V; at 3.3 V continuous operation is 2.6 mA typical/3.0 mA maximum.
- Table 6 and Figure 5 (p. 7): pin 1 VDD, 2 VSS, 3 SDA, 4 GND, 5 VDDH, 6 SCL; VDD needs RC decoupling and VDDH needs a recommended 1 µF capacitor. The center pad is GND.
- Section 4.2 (p. 11): I2C address `0x59`, standard/fast mode up to 400 kHz.
- Section 3 (pp. 9–10): provide current RH/T values for compensation and feed the 1 s raw signal into Sensirion's Gas Index Algorithm. Warm-up/baseline quality must be surfaced; the output remains a VOC proxy/index, not a safety measurement.
- Table 18 (p. 17) identifies orderable `SGP40-D-R4`, product number 3.000.384.

### U4 — SHT40-AD1B-R2

Source: [SHT4x datasheet v6.4](https://sensirion.com/media/documents/33FD6951/6555C40E/Sensirion_Datasheet_SHT4x.pdf).

- Table 4 (p. 8): 1.08–3.6 V supply; 500 µA maximum measurement current with heater off; 2.2 µA average at one high-repeatability measurement per second.
- Table 6 (p. 10): -40 to 125 °C operating absolute limit. Bench Breathe remains constrained to 10–35 °C and 20–80% RH by `ENV-01`.
- Figure 18 (p. 16): pin 1 SDA, 2 SCL, 3 VDD, 4 VSS. The `A` nomenclature fixes I2C address `0x44`.
- The open-cavity package requires airflow exposure, no copper under the sensor except pads, and separation from MCU/regulator heat. The 200 mW heater can draw 100 mA maximum and is not a normal continuous operating mode.

### U5 — TPS62162DSGR

Source: [TPS6216x datasheet rev. E](https://www.ti.com/lit/ds/symlink/tps62160.pdf).

- Table 5 (p. 4) identifies TPS62162 as fixed 3.3 V in WSON-8.
- Section 7.3 (p. 5): 3–17 V recommended input; family supports up to 1 A continuous output.
- Table 6 (p. 4): pins 1 PGND, 2 VIN, 3 EN, 4 AGND, 5 FB, 6 VOS, 7 SW, 8 PG; exposed pad must be soldered to AGND. TI recommends grounding FB on fixed-output versions.
- Issue #3 must copy the typical application values and tight switch-loop layout from the current datasheet, then verify inductor saturation/current rating and capacitor derating.

### U6/U7/J1/F1/D1 — input and interface protection

- [TPD4E05U06 datasheet rev. 2024](https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf), pp. 1, 4, 6: four protected channels, approximately 0.5 pF loading, 5.5 V working voltage, ±12 kV contact/±15 kV air IEC 61000-4-2 rating. Place at J1; DQA pins 1/2/4/5 are channels and pins 3/8 are GND.
- [TPS22919 datasheet rev. B](https://www.ti.com/lit/ds/symlink/tps22919.pdf), pp. 1, 3–4: 1.6–5.5 V, 1.5 A continuous, active-high ON, controlled rise time, short/thermal self-protection. Pin map is 1 IN, 2 GND, 3 ON, 4 NC, 5 QOD, 6 VOUT.
- [USB4105 product specification rev. A3](https://media.digikey.com/pdf/Data%20Sheets/GCT%20PDFs/USB4105_Spec.pdf), pp. 2–4: USB 2.0 Type-C receptacle, -40 to 85 °C, 5 A aggregate VBUS current test, and 20,000-cycle durability. This project is nevertheless limited to 5 V and 500 mA peak.
- [MF-MSMF datasheet](https://bourns.com/docs/product-datasheets/mf-msmf.pdf), electrical table p. 1: MF-MSMF050 has 15 V maximum, 0.50 A hold, 1.00 A trip, and -40 to 85 °C operation. It is a slow resettable fault device, **not** a precise USB current-limit switch.
- [Diodes Incorporated SMBJ datasheet DS19002 rev. 20](https://www.diodes.com/assets/Datasheets/ds19002.pdf), pp. 1–3: orderable `SMBJ5.0A-13-F` is the unidirectional tape-and-reel variant with 5.0 V working standoff, 6.4–7.23 V breakdown, 9.2 V maximum clamp at the rated pulse, and 600 W peak pulse power. KiCad uses `Device:D_Zener`; pin 1 is K/cathode for VBUS and pin 2 is A/anode for GND.

## Static power budget

This is a conservative arithmetic check, not simulation or a bench measurement.

| Case | Inputs | Estimated USB input |
|---|---|---:|
| Normal measurement/RX envelope | U1 84 mA at 3.3 V; U3 2.6 mA; U4 2.2 µA average; U2 65 mA maximum; assume only 85% buck efficiency | about 132 mA plus LEDs/logic |
| Concurrent worst listed loads | U1 345 mA TX + U3 3 mA + U4 100 mA maximum heater at 3.3 V; U2 80 mA fan start at 5 V; assume 85% buck efficiency | about 428 mA plus LEDs/logic |

The 1 A U5 output rating covers the listed 448 mA 3.3 V aggregate. The peak estimate leaves only about 72 mA before the 500 mA project ceiling, so firmware must not run the SHT40 high-power heater during PM fan start/high-power Wi-Fi activity. Issue #3 must complete the passive/load budget; issue #6 must implement source-state gating; named-revision bench measurements must confirm average and peak current. F1 does not enforce this ceiling.

## Availability and lifecycle snapshot

Queries were run on 2026-09-07 UTC. LCSC fields below come from the component catalog snapshot dated 2026-09-05; DigiKey observations come from exact manufacturer/MPN product listings returned by search on 2026-09-07. Quantities and prices are volatile planning evidence, not purchase quotes. An LCSC number is written into KiCad only when both MPN **and manufacturer** match.

| MPN | Manufacturer-validated source | Snapshot | Reported status/stock and unit field | Disposition |
|---|---|---|---|---|
| ESP32-C3-WROOM-02-N4 | LCSC C2934560 | 2026-09-05 | Active; 3,702; USD 3.2912 | Accepted; exact Espressif match |
| SPS30 | [Sensirion current product catalog](https://sensirion.com/products/catalog/SPS30) and [DigiKey exact Sensirion listing](https://www.digikey.com/en/products/detail/sensirion-ag/SPS30/9598990) | 2026-09-07 | Current manufacturer catalog and buy/ship listing present; numeric stock/price not captured | LCSC C5900567 was **not** assigned because its catalog manufacturer is blank; formal PCN/EOL review remains an order-time check |
| SGP40-D-R4 | LCSC C2874215 | 2026-09-05 | Active; 2,499; USD 6.8654 | Accepted; exact Sensirion match |
| SHT40-AD1B-R2 | LCSC C2909890 | 2026-09-05 | Active; 20,692; USD 2.0288 | Accepted; exact Sensirion match |
| TPS62162DSGR | LCSC C40256 | 2026-09-05 | Active; 439; USD 0.9697 | Accepted; exact TI match |
| TPD4E05U06DQAR | LCSC C138714, [TI product/buy page](https://www.ti.com/product/TPD4E05U06/part-details/TPD4E05U06DQAR), and [DigiKey exact TI listing](https://www.digikey.com/en/products/detail/texas-instruments/TPD4E05U06DQAR/3996774) | 2026-09-05 / 2026-09-07 | Active; 94,387; USD 0.0819; current TI ordering page and exact distributor listing present | Accepted; exact TI match. Candidate C22390021 was rejected because it resolves to DOWO, not TI; formal PCN/EOL review remains an order-time check |
| TPS22919DCKR | LCSC C2149796 | 2026-09-05 | Active; 35,367; USD 0.1378 | Accepted; exact TI match |
| USB4105-GF-A | LCSC C3020560 | 2026-09-05 | Active; 11,505; USD 1.0624 | Accepted; exact Global Connector Technology match |
| MF-MSMF050-2 | LCSC C17313 | 2026-09-05 | Active; 19,184; USD 0.0690 | Accepted; exact Bourns match |
| SMBJ5.0A-13-F | LCSC C110528 and [DigiKey exact Diodes Incorporated listing](https://www.digikey.com/en/products/detail/diodes-incorporated/SMBJ5-0A-13-F/725039) | 2026-09-05 / 2026-09-07 | Active; 6,839; USD 0.1019; exact distributor buy/ship listing present | Accepted; exact Diodes Incorporated match and unique orderable suffix |

Catalog/API source: `https://jlcsearch.tscircuit.com/api/search?q=<MPN>&limit=10&full=true`, cross-checked with exact-code resolver records before writing LCSC properties. Manufacturer names and electrical/package claims come from manufacturer documents, not distributor descriptions. The nine manufacturer-validated LCSC one-unit fields total **$14.61**, excluding SPS30, passives, PCB, cable, enclosure, and accessories; therefore no complete BOM-cost claim is made. Re-run authorized-channel stock, pricing, and PCN/EOL/NRND checks immediately before ordering. No long-term supply guarantee is claimed.

## Explicit open blockers for issue #3 and later

1. U1, U2, U3, U6, U7, and J1 use generic pin-count symbols in the M2 staging sheet. Functional symbols and physical footprints must be created or selected and checked pin-by-pin/pad-by-pad against the cited datasheets before wiring.
2. USB-C CC advertisement sensing, USB 2.0 configuration state, the 100 mA recovery ceiling, the 2.5 mA suspend ceiling, and brownout behavior are not implemented by component selection alone.
3. U5 magnetics/capacitors and all ESD/TVS placement/routing remain schematic/layout work. The SMBJ part is physically large; issue #3/#5 may substitute an exact lower-capacitance/smaller VBUS TVS only after equivalent standoff/clamp/energy checks and an MPN update.
4. U3/U4 are small exposed-sensor DFNs with contamination, soldering, copper, and thermal-placement constraints. A module alternative remains acceptable only through a reviewed requirements/MPN change.
5. The SPS30 cable/mating connector is a required non-IC BOM item and must not be omitted from issue #4.
6. Static power arithmetic does not satisfy simulation, bench, or field evidence. No prototype has been built or measured.

## Evidence classification

- **Static performed:** manufacturer-PDF review, exact-MPN metadata population, live availability query, staging-sheet ERC.
- **Simulation:** not performed; no complete circuit exists.
- **Bench:** not performed; no prototype exists.
- **Field:** not performed.
