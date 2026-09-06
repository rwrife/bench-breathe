# Hardware Overview

## System block description
Bench Breathe hardware is a USB-powered sensing node with:
- ESP32-C3 controller module
- PM sensor interface (UART/I2C depending on selected module)
- VOC sensor interface (I2C)
- Temperature/humidity sensor interface (I2C)
- User input/status (button + non-color-only indicator)
- USB-C power/data path and programming/debug header

## Controller choice
**ESP32-C3 module family** is the baseline due to low cost, Wi-Fi support, and mature toolchain support for local web workflows.

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
