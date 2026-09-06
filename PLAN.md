# Bench Breathe — Implementation Plan

## Scope and architecture
Bench Breathe is a low-voltage open-hardware system with three layers:
1. **Device firmware (ESP32-C3):** sensor sampling, local buffering, protocol endpoint, configuration persistence.
2. **Hardware platform:** USB power, sensor interfaces, protection, debug/programming access, test points, and enclosure-ready layout.
3. **Companion app (local web):** setup flow, live status, trend views, event tagging, calibration guidance, export/backup.

## Technology choices and rationale
- **Controller:** ESP32-C3 module family (low cost, Wi-Fi + BLE support, strong ecosystem).
- **Firmware:** C/C++ with PlatformIO + ESP-IDF or Arduino core (repeatable builds, broad hardware support).
- **Sensors:** PM sensor + VOC sensor + temp/humidity sensor to provide actionable trend context.
- **Companion app:** TypeScript + Vite local web app for phone/desktop browser access without app-store friction.
- **Data format:** JSON config/state + CSV/JSON export for portable analysis.
- **Hardware CAD:** KiCad editable source files as system of record.

## Milestones and dependency order
1. **M1 — Requirements + risk review**
   - Lock measurable requirements and constraints.
2. **M2 — Component selection + datasheet validation**
   - Populate Manufacturer/MPN in schematic properties with source evidence.
3. **M3 — KiCad project + schematic**
   - Build complete schematic and run ERC with documented exceptions.
4. **M4 — BOM source-of-truth export**
   - Export and maintain `bom/bom.csv` from schematic properties.
5. **M5 — PCB layout**
   - Route board, enforce keepouts/clearances, run DRC and document outcomes.
6. **M6 — Firmware baseline**
   - Build/flash path, sample loop, protocol endpoint, retention policy.
7. **M7 — Companion app baseline**
   - Local setup/status/history/export flow bound to protocol contract.
8. **M8 — Integration + bring-up docs**
   - Assembly, test procedure, expected readings, troubleshooting guidance.
9. **M9 — Release/fabrication bundle**
   - Gerbers/drill/CPL (if needed), BOM export, docs, license checks.

## Testing strategy
- Unit tests for firmware data handling/calibration math where practical.
- Protocol contract tests between firmware and app.
- Hardware checks: ERC/DRC, continuity/power-rail bring-up checklist.
- Integration tests: known air-event scenarios with expected trend signatures.
- Documentation verification: assembly and calibration steps reproducible by a second person.

## Packaging/distribution plan
- Firmware release binaries + source + flashing instructions.
- Companion app static build served locally or from device-hosted endpoint.
- Hardware release package includes editable KiCad sources and fabrication outputs when mature.

## Risks
- Sensor warm-up drift and environmental noise can cause false confidence.
- PM/VOC sensor selection may affect cost and enclosure airflow constraints.
- Wi-Fi onboarding complexity can delay usability; USB fallback must remain first-class.
- Overstating health/safety meaning of readings is a product and documentation risk.

## Explicit non-goals
- Automatic mains fan control or actuator switching.
- Industrial hygiene certification claims.
- Medical/diagnostic or emergency alerting functionality.
- Cloud-dependent operation in MVP.
