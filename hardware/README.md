# Hardware Overview

## System block description
Bench Breathe hardware is a USB-powered sensing node with:
- ESP32-C3 controller module
- PM sensor interface (UART/I2C depending on selected module)
- VOC sensor interface (I2C)
- Temperature/humidity sensor interface (I2C)
- User input/status (button + non-color-only indicator)
- USB-C power/data path and programming/debug header

## Selected component baseline

Issue #2 selected exact datasheet-backed parts for the first schematic pass:

- Espressif `ESP32-C3-WROOM-02-N4` controller module
- Sensirion `SPS30` particulate module
- Sensirion `SGP40-D-R4` VOC sensor
- Sensirion `SHT40-AD1B-R2` temperature/humidity sensor
- TI `TPS62162DSGR` 3.3 V buck and `TPS22919DCKR` PM-rail load switch
- GCT `USB4105-GF-A`, TI `TPD4E05U06DQAR`, Bourns `MF-MSMF050-2`, and Diodes Incorporated `SMBJ5.0A-13-F` for the USB input/protection baseline

See [`component-selection.md`](component-selection.md) for pin/electrical/package checks, direct manufacturer documents, the static current budget, sourcing snapshot, and open blockers. Selection does not imply a completed circuit or physical validation.

## Interfaces
- I2C bus for VOC + temp/humidity sensors
- UART or I2C (module-dependent) for PM sensor
- USB serial for bring-up, diagnostics, and fallback data access
- Local network endpoint for companion dashboard

## Power plan
- Input: USB 5V SELV only
- Local regulation and filtering sized for sensor peak current
- Brownout-safe startup and reset behavior required

## Enclosure and assembly concept
- Small desk/workbench enclosure with airflow channels
- Sensor placement strategy that balances intake exposure and heat isolation
- Fastener-based assembly for repairability and sensor replacement

## Safety limits
- No mains/high-voltage circuitry
- No relay or actuator control in MVP
- Advisory trend monitor only; not a certified safety instrument

## Expected KiCad deliverables
- Editable KiCad project: `.kicad_pro`, `.kicad_sch`, `.kicad_pcb` (when PCB begins)
- ERC and DRC outputs with documented exceptions
- Source-of-truth schematic properties for Manufacturer/MPN BOM fields
