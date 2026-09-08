# Bench Breathe A0 schematic notes

## Scope and safety boundary

This is a **static schematic capture** for a nominal 5 V USB SELV, non-certified advisory trend logger. It contains no mains, relays, actuators, USB-PD controller, or hazardous-voltage interface. ERC and analyzer results do not prove PCB layout, assembly, radio performance, sensor accuracy, power transients, or physical operation.

## Datasheet-backed interfaces

- **J1 / U1 native USB:** USB4105 receptacle A6/B6 and A7/B7 are joined as `USB_CONN_DP`/`USB_CONN_DM`, protected by TPD4E05U06, then pass through 0 Ω configuration links to `USB_DP`/`USB_DM` at ESP32-C3-WROOM-02 pins 14/13. The 0 Ω values follow Espressif Figure 9-1 and preserve a layout/bench tuning point; the analyzer's generic 22 Ω suggestion is not substituted for the module-vendor reference circuit. USB routing and ESD placement remain issue #5 layout work.
- **USB-C source advertisement:** CC1 and CC2 each have 5.1 kΩ Rd to GND and also reach ADC-capable ESP32 GPIO0/GPIO1 as `CC1_SENSE`/`CC2_SENSE`. Firmware must distinguish default, 1.5 A, and 3 A advertisement voltages and separately honor USB configuration/suspend states. The schematic does not claim that firmware behavior or current limits have been bench-tested.
- **3.3 V regulator:** TPS62162 fixed 3.3 V uses 10 µF input, 2.2 µH output inductor, 22 µF output capacitor, 100 kΩ PG pull-up, FB-to-GND, VOS-to-3V3, and exposed-pad/AGND/PGND ground connections from TI tables 2–4 and pin table 6.
- **ESP32-C3 module:** 3.3 V has local 10 µF + 100 nF. EN has 10 kΩ/1 µF delay per Espressif Figure 9-1. GPIO9 is pulled up for normal boot and exposed with EN/UART on the 3.3 V-only debug header.
- **SPS30:** TPS22919 defaults the PM 5 V rail off via its internal ON pulldown. QOD is tied to VOUT for discharge. J2/U2 pin order is VDD, RX, TX, SEL, GND; SEL is left floating to select UART, which Sensirion recommends for cables longer than 20 cm. UART avoids back-powering an unpowered SPS30 from the always-pulled-up sensor I²C bus. ESP32 UART0 is shared with the optional debug header, so an external UART adapter must not drive it while SPS30 is active. Native USB remains the normal recovery/serial path. The SPS30 housing is internally tied to signal GND and must not gain an independent chassis-current path.
- **SGP40:** project symbol follows Sensirion Table 6. VDD uses 10 Ω + 100 nF RC decoupling, VDDH uses 1 µF, and pin 4 plus exposed pad are grounded. The project footprint follows Sensirion Figure 14 and was cross-checked against KiCad upstream footprint MR 2511.
- **SHT40:** project symbol follows Sensirion Figure 18. The open-cavity package needs airflow, no copper under the sensing cavity, contamination controls, and thermal separation in issue #5.

## GPIO allocation

| ESP32 module pin | GPIO/function | Net / use |
|---|---|---|
| 3 | GPIO4 | `I2C_SDA` |
| 4 | GPIO5 | `I2C_SCL` |
| 5 | GPIO6 | `PM_ENABLE` |
| 6 | GPIO7 | `STATUS_LED_K` |
| 8 | GPIO9 | `BOOT_GPIO9` |
| 10 | GPIO10 | `USER_BUTTON_N` |
| 11 | GPIO20/U0RXD | `PM_UART_TX` (sensor TX to MCU RX) |
| 12 | GPIO21/U0TXD | `PM_UART_RX` (MCU TX to sensor RX) |
| 13 | GPIO18/USB_D- | `USB_DM` |
| 14 | GPIO19/USB_D+ | `USB_DP` |
| 15 | GPIO3 | `REG_PG` |
| 17 | GPIO1/ADC | `CC2_SENSE` |
| 18 | GPIO0/ADC | `CC1_SENSE` |

GPIO2 and GPIO8 are intentionally no-connect on A0. GPIO9 is a boot strap and is externally pulled high.

## Native ERC result

KiCad 9.0.9 `sch erc --format json --exit-code-violations` reports **0 violations** in `hardware/kicad/reports/erc.json`. There are no warning exceptions to justify.

## Analyzer triage and intentional exceptions

- `PP-001` reports that SGP40 U3.1 lacks a DC path because its generic graph rule accepts only series resistors ≤1 Ω. Sensirion Figure 5 explicitly requires an RC element on VDD; A0 uses 10 Ω and 100 nF, which provides a DC path (about 30 mV drop at the documented 3 mA maximum). This finding is a rule-threshold false positive, not an open circuit.
- `UC-001`/`UC-002` look only at J1's pre-fuse `VBUS` net. A0 deliberately places the 10 µF buck input capacitor and SMBJ5.0A TVS on `VBUS_FUSED`, immediately after F1, so a sustained TVS fault is current-limited and the TPS62162 input sees its manufacturer-recommended 10 µF. Placement close to J1/F1 and USB inrush behavior remain PCB/bench gates.
- J2 is an internal keyed SPS30 harness boundary and J3 is an internal 3.3 V debug header. Their lack of dedicated connector ESD is accepted for A0's enclosed dry indoor product boundary; external-access and cable-route assumptions must be rechecked during enclosure/layout review.
- `PU-001` assumes SPS30 SEL must have a pull-down. Sensirion Table 4 explicitly defines SEL floating as UART mode and SEL low as I²C mode; A0 intentionally leaves U2.4 and J2.4 no-connect to select UART.

## Evidence classes

- **Static:** performed — manufacturer PDF pin/application checks, generated editable KiCad source, critical pin/net validator, metadata gate, native ERC, schematic analyzer, and PDF export.
- **Simulation:** not performed in issue #3.
- **PCB/DRC:** not applicable yet; issue #5 owns PCB layout.
- **Bench:** not performed; no assembled prototype exists.
- **Field:** not performed.
