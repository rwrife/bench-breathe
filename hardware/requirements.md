# Bench Breathe MVP Requirements

Status: **baseline for MVP design**

Scope: USB-powered indoor workshop air-quality trend logger

Evidence state: requirements only; no electrical, firmware, app, or physical validation is implied

Requirement IDs are stable references for schematic, firmware, app, and bring-up work. A later design change may revise a requirement through review, but implementations must not silently diverge from this baseline.

## 1. Product intent and boundaries

Bench Breathe helps a user observe particulate, VOC, temperature, and humidity trends around a hobby workbench and compare those trends with manually recorded ventilation events. It is an advisory logger, not a protective control or calibrated exposure instrument.

### In scope for the MVP

- One desk/workbench device powered from USB 5 V SELV.
- PM2.5, VOC-index/proxy, temperature, and relative-humidity trend channels.
- Local acquisition, bounded storage, viewing, event annotation, and explicit export.
- Local-network access with a USB serial fallback for setup, diagnostics, and export.
- Editable KiCad, firmware, protocol, and web-app sources.
- Reproducible static checks and documented bench bring-up before any release claim.

### Explicitly out of scope

- Mains wiring, mains sensing, relay outputs, fan control, or any actuator control.
- USB Power Delivery negotiation or operation above nominal USB 5 V.
- Medical, diagnostic, emergency, life-safety, or occupational-exposure decisions.
- Certified indoor-air-quality, industrial-hygiene, or regulatory-limit measurements.
- Automatic alarms that imply a safe/unsafe determination.
- Cloud accounts, mandatory internet access, remote telemetry, or unattended remote control.
- Outdoor, wet, condensing, explosive, corrosive, or industrial-process environments.

## 2. Electrical requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| PWR-01 | The only external power input shall be nominal 5 V USB from a SELV source. No circuit shall intentionally connect to mains or hazardous voltage. | Schematic review and connector inspection |
| PWR-02 | Full sensing is supported only when the device detects a USB-C 1.5 A/3 A CC advertisement or a USB 2.0 host completes configuration for a 500 mA load. The user documentation shall additionally require a safety-certified 5 V source rated at least 1 A; that safety certification is an external user constraint, not something the device claims to detect. | Schematic review, user-document review, and source-state matrix test |
| PWR-03 | The device shall use USB-C sink terminations and shall not negotiate USB-PD. Hardware/firmware shall implement the current ceilings and modes in the source-state matrix below, keep the PM sensor and Wi-Fi disabled outside full-sensing mode, report insufficient power over serial when available, and avoid repeated brownout boot loops. | USB power-state and current test for every matrix row |
| PWR-04 | With a supported source, steady-state average input current target is no more than 250 mA and peak input current shall remain at or below 500 mA, including sensor startup and radio transmit. | Logged average plus oscilloscope/current-probe worst-case capture |
| PWR-05 | USB input protection shall include a documented overcurrent strategy and protection against ESD/transient exposure appropriate to a user-accessible USB connector. | Datasheet-backed schematic review and DRC |
| PWR-06 | USB-C sink configuration and any data connection shall follow the selected connector/controller datasheets; unused high-voltage or PD functions shall not be populated. | Pin-by-pin schematic review against manufacturer datasheets |
| PWR-07 | A power fault or brownout shall not leave partially committed configuration or history records presented as valid. | Firmware fault-injection test |
| PWR-08 | All user-accessible signal connectors shall remain within SELV/logic-level domains and shall have documented pinout, voltage, and current limits. | Schematic and bring-up guide review |

### USB source-state matrix

| Detectable state | Allowed mode | Maximum input current | Pass condition |
|---|---|---:|---|
| USB-C CC advertises 1.5 A or 3 A at 5 V | Full sensing | 500 mA peak | PM and Wi-Fi may start; measured peak remains <=500 mA |
| USB 2.0 host, before configuration | Recovery/serial only | 100 mA | PM and Wi-Fi remain off; device enumerates without brownout |
| USB 2.0 host grants configured 500 mA load | Full sensing | 500 mA peak | PM and Wi-Fi may start; measured peak remains <=500 mA |
| USB suspend | Suspended | 2.5 mA | Sensors and radio are off; measured current is <=2.5 mA |
| Default-current/unknown CC with no successful host configuration, charge-only legacy cable, denied configuration, or detected source droop | Recovery/error only | 100 mA | Full sensing never starts; insufficient-power status is available when serial is functional; no reset loop occurs |

## 3. Sensing requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| SNS-01 | The device shall expose PM2.5, VOC index/proxy, temperature, and relative-humidity channels with units and validity state. | Protocol contract tests |
| SNS-02 | The default acquisition tick shall be 2 s. A channel with a slower datasheet-qualified cadence may repeat its latest value but shall retain its own sample age and validity. | Firmware timing test and datasheet review |
| SNS-03 | The configurable acquisition interval shall be bounded to 2–60 s; invalid values shall be rejected rather than silently clamped. | Firmware unit/contract tests |
| SNS-04 | Each channel state shall be one of `ready`, `warming`, `fault`, or `unknown`; unavailable values shall be explicit nulls with a reason. | Protocol contract tests |
| SNS-05 | Sensor warm-up, conditioning, baseline, and compensation behavior shall follow the selected manufacturer datasheets and be surfaced to the user. | Datasheet review and bench bring-up record |
| SNS-06 | Samples shall carry monotonic ordering plus wall-clock time and clock-quality metadata when wall-clock time is available. Clock correction shall not reorder stored samples. | Firmware rollover/time-correction tests |
| SNS-07 | Every MVP surface shall describe readings as trends or sensor proxies. A stronger accuracy, exposure, health, or safe/unsafe claim is prohibited in the MVP and requires a separately reviewed post-MVP requirements and validation program. | Documentation and UI copy review |

## 4. Storage and data ownership

| ID | Requirement | Acceptance evidence |
|---|---|---|
| DAT-01 | The device shall retain at least 24 h of 2 s trend records (43,200 acquisition ticks) under the final record format. | Storage-capacity calculation and rollover test |
| DAT-02 | The device shall retain at least 30 days of 5 min aggregates (8,640 intervals) or an equivalent documented bounded summary. | Storage-capacity calculation and rollover test |
| DAT-03 | Retention shall use deterministic oldest-first rollover and shall publish capacity, used space, oldest timestamp, and newest timestamp. | Firmware storage tests and API contract test |
| DAT-04 | Configuration writes and history metadata updates shall be atomic or recoverable after reset/power loss. | Fault-injection and reboot recovery tests |
| DAT-05 | A `clear history` action shall delete all raw samples, aggregates, and event labels while retaining device configuration. It shall require an authenticated local session plus explicit app confirmation; completion metadata shall be committed atomically so interrupted erasure cannot make deleted records queryable or exportable after reboot. | Firmware/app deletion and power-interruption tests |
| DAT-06 | Factory reset shall remove user configuration, pairing credentials, event labels, raw samples, and aggregates. It shall require a sustained physical-button action; the app may guide but shall not remotely complete the reset. | Firmware/app reset and reboot tests |
| DAT-07 | CSV and JSON export shall occur only after an explicit authenticated local user action and shall include schema/protocol version, units, channel validity, and clock-quality metadata. | Export fixture and authorization tests |
| DAT-08 | No microphone, camera, location, contact, or cloud-account data shall be requested or stored by the MVP. | App permission/static review |
| DAT-09 | Event labels are user-controlled local text; implementations shall define a bounded length and escape them safely in UI and exports. | App/firmware input-boundary tests |

## 5. Connectivity and protocol requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| COM-01 | Normal operation shall not require internet access. Loss of LAN access shall not stop sampling or retention. | Offline integration test |
| COM-02 | The primary app transport shall be versioned HTTP/JSON on the local network. | Protocol contract tests |
| COM-03 | USB serial shall provide a documented fallback for setup, health/status, configuration recovery, and data export. | Serial integration test |
| COM-04 | Before firmware/app integration, the current `docs/protocol.md` Draft v0 shall be finalized as the single versioned contract for HTTP and serial data shapes, units, limits, errors, authorization, and compatibility. Breaking changes require a new major API version or documented migration. | Protocol issue acceptance plus cross-project contract tests |
| COM-05 | The compiled companion app shall be served by the device so setup and normal use require no internet-hosted assets or separately installed server. API requests shall be same-origin; wildcard CORS is prohibited. | Offline browser test and firmware/app build inspection |
| COM-06 | Setup mode shall begin only after a physical-button action, be visibly indicated, expire within 10 min, and exit after successful pairing/provisioning. Factory reset returns the device to unprovisioned state but shall not start setup mode until another physical-button action. | Firmware/app setup, timeout, and reset integration tests |
| COM-07 | Static app assets and a minimal non-sensitive health response may be fetched without authentication. After a sustained physical-button action, USB serial shall reveal a single-use pairing code with at least 128 bits of cryptographically secure random entropy for at most 10 min. During that window only, an unauthenticated same-origin pairing endpoint may exchange the code for the per-device API credential; the first successful exchange consumes the code and closes the endpoint. Factory reset replaces all pairing material. Every other API resource requires the credential; state-changing requests also use same-origin request protections, and USB-serial mutation commands require a separate recent physical-button confirmation. | Entropy/source review plus bootstrap race, authorization, cross-origin, expiry, reset, and serial-mutation tests |
| COM-08 | The device shall not create outbound cloud connections in the MVP. Network listeners shall be limited to documented local services. | Firmware static review and network capture |
| COM-09 | MVP HTTP traffic is not confidential against an attacker already on the trusted private LAN. This residual risk and the prohibition on internet exposure/port forwarding shall be visible in setup documentation; the UI shall not describe the device as internet-safe. | Threat-model/documentation review and network capture |

## 6. User interface and accessibility requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| UX-01 | Device state shall not be communicated by color alone; the app shall provide textual state and the device shall provide a documented non-color-only pattern or behavior. | UI review and bring-up test |
| UX-02 | The app shall distinguish sensor warming/fault/unknown states from healthy measurements and shall not graph invalid null values as zero. | App tests |
| UX-03 | Trend displays shall show units, time range, freshness, and data gaps. | App tests and manual accessibility review |
| UX-04 | Destructive reset/delete actions and configuration changes shall require explicit confirmation and report partial failure. | App integration tests |
| UX-05 | Advisory copy shall avoid safe/unsafe, healthy/unhealthy, medical, emergency, or certified-exposure claims. | Documentation/UI copy review |

## 7. Mechanical and environmental requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| MEC-01 | The assembled enclosure target shall not exceed 120 mm × 120 mm × 80 mm. | CAD/enclosure measurement |
| MEC-02 | The enclosure shall open non-destructively and permit sensor/PCB replacement using ordinary hand tools. | Assembly trial |
| MEC-03 | USB cable strain relief and board mounting shall prevent connector load from being carried only by solder joints. | Mechanical inspection |
| MEC-04 | Airflow openings shall expose the sensing path while discouraging direct touch, debris entry, and recirculation of MCU/regulator heat. | Enclosure review and thermal/response comparison |
| ENV-01 | MVP use is indoor, dry, non-condensing operation only. Design target is 10–35 °C and 20–80% RH, bounded further by the selected component datasheets. | Datasheet audit and chamber/controlled-environment check if available |
| ENV-02 | Outdoor/weather exposure, condensation, solvent-rich atmospheres, and explosive dust/gas environments are prohibited. | Product labeling/documentation review |

## 8. Cost, serviceability, and source requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| CST-01 | Prototype BOM target is USD 35–60 and ceiling is USD 75, excluding host device, tools, shipping, tax, and optional debug accessories. | Dated BOM sourcing report |
| SRC-01 | Manufacturer and MPN shall live in KiCad schematic symbol properties as the BOM source of truth; `bom/bom.csv` shall be generated from that source. | BOM export diff/check |
| SRC-02 | Pinouts, absolute limits, recommended operating conditions, and required external components shall be checked against manufacturer datasheets before schematic approval. | Datasheet-backed design review |
| SRC-03 | Hardware deliverables shall remain editable KiCad sources; firmware and app sources shall include repeatable build instructions. | Release artifact review |
| SRC-04 | No release may claim ERC, DRC, firmware build, app build, simulation, bench, or field success without the corresponding captured evidence. | Release checklist review |

## 9. Safety boundaries and required wording

Bench Breathe is a **non-certified advisory trend logger**. It may help a user notice changes and decide to investigate ventilation, but it does not determine whether air is safe, whether exposure is acceptable, or whether protective equipment is required.

- Use only a reputable/certified 5 V USB SELV power source and a known-good cable.
- Do not connect any Bench Breathe input or output to mains, a relay, machinery, ventilation equipment, or a safety interlock.
- Do not use the product as a smoke, fire, gas, carbon-monoxide, medical, or emergency alarm.
- Sensor faults, contamination, placement, airflow, warm-up, drift, and power/network loss can produce missing or misleading readings.
- When a workshop activity may create harmful exposure, follow the material/tool manufacturer guidance and applicable professional safety practice independently of this device.

## 10. Verification classes

Later milestones shall label evidence using these classes so static checks are not confused with physical validation:

1. **Static:** review, lint, ERC, DRC, source inspection, or datasheet comparison.
2. **Simulation:** modeled electrical/thermal behavior with assumptions recorded.
3. **Bench:** measured on a named prototype revision with equipment and conditions recorded.
4. **Field:** observed in representative use over a stated duration; not certification.

Passing one class does not imply another. In particular, ERC/DRC does not prove physical performance, and a bench trend comparison does not establish exposure accuracy or safety fitness.
