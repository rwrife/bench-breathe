#!/usr/bin/env python3
"""Generate the editable Bench Breathe first-pass schematic.

Manufacturer documents cited in hardware/component-selection.md are the
pinout/electrical ground truth. The generated KiCad schematic remains editable;
this script makes the initial capture reproducible.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

RES_DS = "https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_16.pdf"
CAP_DS = "https://www.murata.com/en-global/products/capacitor/mlcc/overview/lineup"


def find_symbol_dir(explicit: str | None) -> Path:
    for candidate in (explicit, os.environ.get("KICAD_SYMBOL_DIR"), "/usr/share/kicad/symbols"):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    raise SystemExit("KiCad symbol libraries not found; pass --symbol-dir")


def q(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def custom_symbol(name: str, ref: str, footprint: str, datasheet: str,
                  description: str, pins: list[tuple[str, str, str, str]]) -> str:
    sides = {side: [pin for pin in pins if pin[3] == side] for side in "LRTB"}
    rows = max(len(sides["L"]), len(sides["R"]), 4)
    half_h = max(7.62, (rows + 1) * 1.27)
    half_w = 15.24
    output = [
        f'  (symbol "{q(name)}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
        f'    (property "Reference" "{q(ref)}" (at {-half_w} {half_h + 2.54} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))',
        f'    (property "Value" "{q(name)}" (at {half_w} {-half_h - 2.54} 0) (effects (font (size 1.27 1.27)) (justify right top)))',
        f'    (property "Footprint" "{q(footprint)}" (at 0 {-half_h - 5.08} 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (property "Datasheet" "{q(datasheet)}" (at 0 {-half_h - 7.62} 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (property "ki_description" "{q(description)}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (symbol "{q(name)}_0_1" (rectangle (start {-half_w} {half_h}) (end {half_w} {-half_h}) (stroke (width 0.254) (type default)) (fill (type background))))',
        f'    (symbol "{q(name)}_1_1"',
    ]

    def pin_line(pin: tuple[str, str, str, str], index: int, count: int) -> str:
        number, pin_name, pin_type, side = pin
        if side == "L":
            x, y, angle = -half_w - 5.08, (count - 1 - 2 * index) * 1.27, 0
        elif side == "R":
            x, y, angle = half_w + 5.08, (count - 1 - 2 * index) * 1.27, 180
        elif side == "T":
            x, y, angle = (index - count // 2) * 2.54, half_h + 5.08, 270
        else:
            x, y, angle = (index - count // 2) * 2.54, -half_h - 5.08, 90
        return (
            f'      (pin {pin_type} line (at {x:.3f} {y:.3f} {angle}) (length 5.08) '
            f'(name "{q(pin_name)}" (effects (font (size 1.016 1.016)))) '
            f'(number "{q(number)}" (effects (font (size 1.016 1.016)))))'
        )

    for side in "LRTB":
        for index, pin in enumerate(sides[side]):
            output.append(pin_line(pin, index, len(sides[side])))
    output += ["    )", "  )"]
    return "\n".join(output)


def write_project_library(here: Path) -> None:
    lib = here / "lib"
    pretty = lib / "bench-breathe.pretty"
    pretty.mkdir(parents=True, exist_ok=True)
    symbols = [
        custom_symbol(
            "USB4105-GF-A", "J", "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
            "https://media.digikey.com/pdf/Data%20Sheets/GCT%20PDFs/USB4105_Spec.pdf",
            "GCT USB4105 USB 2.0 Type-C receptacle; USB Type-C contact identifiers",
            [("A4","VBUS","passive","R"), ("A9","VBUS","passive","R"),
             ("B4","VBUS","passive","R"), ("B9","VBUS","passive","R"),
             ("A5","CC1","bidirectional","R"), ("B5","CC2","bidirectional","R"),
             ("A6","D+","bidirectional","R"), ("B6","D+","bidirectional","R"),
             ("A7","D-","bidirectional","R"), ("B7","D-","bidirectional","R"),
             ("A8","SBU1","passive","R"), ("B8","SBU2","passive","R"),
             ("A1","GND","power_in","B"), ("A12","GND","power_in","B"),
             ("B1","GND","power_in","B"), ("B12","GND","power_in","B"),
             ("S1","SHIELD","passive","B")],
        ),
        custom_symbol(
            "ESP32-C3-WROOM-02-N4", "U", "RF_Module:ESP32-C3-WROOM-02",
            "https://documentation.espressif.com/esp32-c3-wroom-02_datasheet_en.pdf",
            "Espressif ESP32-C3-WROOM-02-N4 module; pin map from datasheet v1.7 Table 3-1",
            [("1","3V3","power_in","T"), ("2","EN","input","L"),
             ("3","GPIO4","bidirectional","L"), ("4","GPIO5","bidirectional","L"),
             ("5","GPIO6","bidirectional","L"), ("6","GPIO7","bidirectional","L"),
             ("7","GPIO8","bidirectional","L"), ("8","GPIO9","bidirectional","L"),
             ("10","GPIO10","bidirectional","L"), ("11","GPIO20_U0RXD","bidirectional","R"),
             ("12","GPIO21_U0TXD","bidirectional","R"), ("13","GPIO18_USB_D-","bidirectional","R"),
             ("14","GPIO19_USB_D+","bidirectional","R"), ("15","GPIO3","bidirectional","R"),
             ("16","GPIO2","bidirectional","R"), ("17","GPIO1","bidirectional","R"),
             ("18","GPIO0","bidirectional","R"), ("9","GND","power_in","B"),
             ("19","GND","power_in","B")],
        ),
        custom_symbol(
            "SPS30", "U", "", "https://sensirion.com/media/documents/8600FF88/64A3B8D6/Sensirion_PM_Sensors_Datasheet_SPS30.pdf",
            "Sensirion SPS30 off-board particulate module; Table 4 connector map",
            [("1","VDD","power_in","T"), ("2","RX_SDA","bidirectional","L"),
             ("3","TX_SCL","bidirectional","L"), ("4","SEL","input","L"),
             ("5","GND","power_in","B")],
        ),
        custom_symbol(
            "SGP40-D-R4", "U", "bench-breathe:Sensirion_DFN-6-1EP_2.44x2.44mm_P0.8mm",
            "https://sensirion.com/media/documents/296373BB/6203C5DF/Sensirion_Gas_Sensors_Datasheet_SGP40.pdf",
            "Sensirion SGP40 VOC sensor; Table 6 transparent-top pin map",
            [("1","VDD","power_in","T"), ("2","VSS","power_in","B"),
             ("3","SDA","bidirectional","L"), ("4","GND","power_in","B"),
             ("5","VDDH","power_in","T"), ("6","SCL","bidirectional","L"),
             ("7","EP_GND","power_in","B")],
        ),
        custom_symbol(
            "SHT40-AD1B-R2", "U", "Sensor_Humidity:Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad",
            "https://sensirion.com/media/documents/33FD6951/6555C40E/Sensirion_Datasheet_SHT4x.pdf",
            "Sensirion SHT40 temperature/humidity sensor; Figure 18 pin map",
            [("1","SDA","bidirectional","L"), ("2","SCL","bidirectional","L"),
             ("3","VDD","power_in","T"), ("4","VSS","power_in","B")],
        ),
        custom_symbol(
            "TPS62162DSGR", "U", "Package_SON:WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm_ThermalVias",
            "https://www.ti.com/lit/ds/symlink/tps62160.pdf",
            "TI fixed 3.3 V 1 A buck; DSG WSON-8 pin map including exposed pad",
            [("1","PGND","power_in","B"), ("2","VIN","power_in","L"),
             ("3","EN","input","L"), ("4","AGND","power_in","B"),
             ("5","FB","input","L"), ("6","VOS","input","R"),
             ("7","SW","power_out","R"), ("8","PG","open_collector","R"),
             ("9","EP_GND","power_in","B")],
        ),
        custom_symbol(
            "TPD4E05U06DQAR", "U", "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
            "https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf",
            "TI four-channel low-capacitance ESD protector; DQA Table 4-2 pin map",
            [("1","D1+","passive","L"), ("2","D1-","passive","L"),
             ("3","GND","power_in","B"), ("4","D2+","passive","L"),
             ("5","D2-","passive","L"), ("6","NC","passive","R"),
             ("7","NC","passive","R"), ("8","GND","power_in","B"),
             ("9","NC","passive","R"), ("10","NC","passive","R")],
        ),
        custom_symbol(
            "TPS22919DCKR", "U", "Package_TO_SOT_SMD:SOT-363_SC-70-6",
            "https://www.ti.com/lit/ds/symlink/tps22919.pdf",
            "TI TPS22919 active-high 1.5 A load switch; DCK Table 5 pin map",
            [("1","IN","power_in","L"), ("2","GND","power_in","B"),
             ("3","ON","input","L"), ("4","NC","passive","R"),
             ("5","QOD","passive","R"), ("6","VOUT","power_out","R")],
        ),
    ]
    (lib / "bench-breathe.kicad_sym").write_text(
        "(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n"
        + "\n".join(symbols) + "\n)\n", encoding="utf-8")

    # Sensirion Figure 14 dimensions, independently cross-checked against
    # KiCad upstream footprint MR 2511.
    footprint = '''(footprint "Sensirion_DFN-6-1EP_2.44x2.44mm_P0.8mm" (version 20240108) (generator pcbnew)
  (layer "F.Cu")
  (descr "Sensirion SGP40 DFN-6 EP; manufacturer Figure 14 land pattern")
  (tags "SGP40 Sensirion VOC DFN-6")
  (attr smd)
  (fp_text reference "REF**" (at 0 -2.5 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
  (fp_text value "Sensirion_DFN-6-1EP_2.44x2.44mm_P0.8mm" (at 0 2.5 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
  (fp_rect (start -1.6 -1.6) (end 1.6 1.6) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
  (fp_rect (start -1.22 -1.22) (end 1.22 1.22) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
  (fp_circle (center 0.3 0.3) (end 0.7 0.3) (stroke (width 0.05) (type default)) (fill none) (layer "Dwgs.User"))
  (pad "1" smd rect (at -1.15 -0.8) (size 0.55 0.4) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "2" smd rect (at -1.15 0) (size 0.55 0.4) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "3" smd rect (at -1.15 0.8) (size 0.55 0.4) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "4" smd rect (at 1.15 0.8) (size 0.55 0.4) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "5" smd rect (at 1.15 0) (size 0.55 0.4) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "6" smd rect (at 1.15 -0.8) (size 0.55 0.4) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "7" smd custom (at 0 0) (size 0.55 0.4) (layers "F.Cu" "F.Paste" "F.Mask")
    (solder_paste_margin -0.1) (zone_connect 0)
    (options (clearance outline) (anchor rect))
    (primitives (gr_poly (pts (xy 0.625 0.85) (xy -0.625 0.85) (xy -0.625 -0.55) (xy -0.325 -0.85) (xy 0.625 -0.85)) (width 0.01) (fill yes))))
)'''
    (pretty / "Sensirion_DFN-6-1EP_2.44x2.44mm_P0.8mm.kicad_mod").write_text(footprint + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol-dir")
    parser.add_argument("--output", default=str(Path(__file__).with_name("bench-breathe.kicad_sch")))
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    write_project_library(here)
    symbol_dir = find_symbol_dir(args.symbol_dir)
    os.environ["KICAD_SYMBOL_DIR"] = str(symbol_dir)

    from kicad_sch_api import create_schematic, get_symbol_cache
    cache = get_symbol_cache()
    cache.discover_libraries([str(symbol_dir)])
    if not cache.add_library_path(str(here / "lib" / "bench-breathe.kicad_sym")):
        raise SystemExit("Could not load project symbol library")

    schematic = create_schematic("Bench Breathe M3 schematic")
    schematic.set_paper_size("A3")
    schematic.set_title_block(
        title="Bench Breathe USB/SELV air-quality trend logger",
        date="2026-09-08", rev="A0 schematic",
        company="Open hardware design — rwrife/bench-breathe",
        comments={
            1: "USB 5 V SELV only; no mains, relays, actuators, or USB-PD",
            2: "Non-certified advisory trend logger; not medical, emergency, or life-safety equipment",
            3: "Static schematic/ERC evidence only; PCB, simulation, assembly, bench, and field validation pending",
        },
    )
    components: dict[str, object] = {}
    labels: set[tuple[float, float, str]] = set()
    no_connects: set[tuple[float, float]] = set()

    def add(lib_id: str, ref: str, value: str, pos: tuple[float, float], footprint: str,
            manufacturer: str, mpn: str, datasheet: str, package: str, notes: str,
            *, lcsc: str = "", in_bom: bool = True):
        component = schematic.components.add(lib_id, ref, value, position=pos, footprint=footprint)
        properties = {"Manufacturer": manufacturer, "MPN": mpn, "Datasheet": datasheet,
                      "Package": package, "BOM Comments": notes}
        if lcsc:
            properties["LCSC"] = lcsc
        for key, value_ in properties.items():
            component.set_property(key, value_)
        component.in_bom = in_bom
        components[ref] = component
        return component

    def point(ref: str, pin: str):
        from kicad_sch_api.core.types import Point
        component = components[ref]
        definition = component.get_pin(str(pin))
        if definition is None:
            raise ValueError(f"{ref} pin {pin} missing")
        return Point(component.position.x + definition.position.x,
                     component.position.y - definition.position.y)

    def connect(ref: str, pin: str, net: str) -> None:
        pin_point = point(ref, pin)
        key = (round(pin_point.x, 6), round(pin_point.y, 6), net)
        if key not in labels:
            schematic.labels.add(net, (pin_point.x, pin_point.y))
            labels.add(key)

    def nc(ref: str, pin: str) -> None:
        pin_point = point(ref, pin)
        key = (round(pin_point.x, 6), round(pin_point.y, 6))
        if key not in no_connects:
            schematic.no_connects.add((pin_point.x, pin_point.y))
            no_connects.add(key)

    def resistor(ref: str, value: str, pos: tuple[float, float], mpn: str, notes: str):
        return add("Device:R", ref, value, pos, "Resistor_SMD:R_0603_1608Metric",
                   "Yageo", mpn, RES_DS, "0603 (1608 metric)", notes)

    def capacitor(ref: str, value: str, pos: tuple[float, float], mpn: str, notes: str,
                  footprint: str = "Capacitor_SMD:C_0603_1608Metric"):
        return add("Device:C", ref, value, pos, footprint, "Murata", mpn, CAP_DS,
                   footprint.split(":")[-1], notes)

    # USB-C entry, sink advertisement, fault protection, and four-line ESD.
    add("bench-breathe:USB4105-GF-A", "J1", "USB4105-GF-A", (35, 48),
        "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
        "GCT", "USB4105-GF-A", "https://media.digikey.com/pdf/Data%20Sheets/GCT%20PDFs/USB4105_Spec.pdf",
        "USB Type-C receptacle, right-angle top-mount hybrid SMT/THT",
        "USB 2.0 5 V sink only. CC1/CC2 each use 5.1 kΩ Rd and feed ADC source-current sensing. No USB-PD.", lcsc="C3020560")
    resistor("R1", "5.1k 1%", (64, 31), "RC0603FR-075K1L", "USB-C CC1 Rd; also forms CC1 ADC sense voltage.")
    resistor("R2", "5.1k 1%", (78, 31), "RC0603FR-075K1L", "USB-C CC2 Rd; also forms CC2 ADC sense voltage.")
    resistor("R11", "0R 1%", (54, 101), "RC0603FR-070RL", "USB D- configuration link; 0 Ω follows Espressif Figure 9-1 and permits later SI tuning.")
    resistor("R12", "0R 1%", (75, 101), "RC0603FR-070RL", "USB D+ configuration link; 0 Ω follows Espressif Figure 9-1 and permits later SI tuning.")
    add("Device:Polyfuse", "F1", "0.50A hold / 1.00A trip", (82, 48), "Fuse:Fuse_1812_4532Metric",
        "Bourns", "MF-MSMF050-2", "https://bourns.com/docs/product-datasheets/mf-msmf.pdf", "1812 (4532 metric)",
        "Resettable input fault protection; not a precision USB current limiter.", lcsc="C17313")
    add("Device:D_Zener", "D1", "SMBJ5.0A-13-F", (101, 64), "Diode_SMD:D_SMB",
        "Diodes Incorporated", "SMBJ5.0A-13-F", "https://www.diodes.com/assets/Datasheets/ds19002.pdf", "SMB / DO-214AA",
        "Unidirectional TVS: pin 1 cathode to VBUS_FUSED, pin 2 anode to GND.", lcsc="C110528")
    add("bench-breathe:TPD4E05U06DQAR", "U6", "TPD4E05U06DQAR", (64, 83), "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
        "Texas Instruments", "TPD4E05U06DQAR", "https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf", "USON-10 (DQA), 2.5 x 1.0 mm",
        "Four low-capacitance ESD channels on USB D+/D-/CC1/CC2; place at J1 with short GND return.", lcsc="C138714")

    # Fixed 3.3 V buck, values from TPS6216x Tables 2–4.
    add("bench-breathe:TPS62162DSGR", "U5", "TPS62162DSGR", (132, 49), "Package_SON:WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm_ThermalVias",
        "Texas Instruments", "TPS62162DSGR", "https://www.ti.com/lit/ds/symlink/tps62160.pdf", "WSON-8 exposed pad (DSG), 2.0 x 2.0 mm",
        "Fixed 3.3 V buck: FB and EP to AGND; 2.2 µH/22 µF output; tight switch loop required.", lcsc="C40256")
    add("Device:L", "L1", "2.2uH 1.3A", (164, 49), "Inductor_SMD:L_1008_2520Metric",
        "TDK", "VLS252012T-2R2M1R3", "https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=VLS252012T-2R2M1R3", "2.5 x 2.0 mm SMD",
        "TPS6216x recommended inductor; 1.3 A current rating, verify saturation margin in layout/bench review.")
    capacitor("C1", "10uF 10V X5R", (113, 69), "GRM31CR61A106KA01L", "Buck input capacitor; close to VIN/PGND.", "Capacitor_SMD:C_1206_3216Metric")
    capacitor("C2", "22uF 16V X5R", (180, 65), "GRM31CR61C226ME15L", "Buck output capacitor; 22 µF nominal per TI recommended combination.", "Capacitor_SMD:C_1206_3216Metric")
    resistor("R3", "100k 1%", (150, 69), "RC0603FR-07100KL", "TPS62162 open-drain PG pull-up.")

    # Controller, reset delay, boot/debug, source-state sensing.
    add("bench-breathe:ESP32-C3-WROOM-02-N4", "U1", "ESP32-C3-WROOM-02-N4", (235, 61), "RF_Module:ESP32-C3-WROOM-02",
        "Espressif Systems", "ESP32-C3-WROOM-02-N4", "https://documentation.espressif.com/esp32-c3-wroom-02_datasheet_en.pdf",
        "ESP32-C3-WROOM-02 module, 18.0 x 20.0 x 3.2 mm",
        "Native USB on pins 13/14; CC ADC sensing on GPIO0/1; antenna keepout required; GPIO2/8/9 strapping reviewed.", lcsc="C2934560")
    capacitor("C3", "10uF 10V X5R", (209, 27), "GRM31CR61A106KA01L", "ESP32 local 3.3 V bulk capacitor.", "Capacitor_SMD:C_1206_3216Metric")
    capacitor("C4", "100nF 50V X7R", (222, 27), "GRM188R71H104KA93D", "ESP32 high-frequency supply bypass.")
    resistor("R4", "10k 1%", (236, 27), "RC0603FR-0710KL", "ESP32 EN pull-up; EN must not float.")
    capacitor("C5", "1uF 16V X7R", (249, 27), "GRM188R71C105KA12D", "ESP32 EN power-on delay per module datasheet Figure 9-1.")
    resistor("R10", "10k 1%", (263, 27), "RC0603FR-0710KL", "GPIO9 boot-strap pull-up; debug header may pull low for download mode.")
    add("Connector_Generic:Conn_01x06", "J3", "DEBUG / PROGRAM 3V3", (318, 45), "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
        "Samtec", "TSW-106-07-G-S", "https://suddendocs.samtec.com/prints/tsw-1xx-xx-xxx-x-xx-xx-mkt.pdf", "1x6 2.54 mm header",
        "3.3 V only: pin 1=3V3, 2=GND, 3=EN, 4=BOOT/GPIO9, 5=U0TXD, 6=U0RXD.")

    # PM rail switch and keyed SPS30 cable interface.
    add("bench-breathe:TPS22919DCKR", "U7", "TPS22919DCKR", (66, 139), "Package_TO_SOT_SMD:SOT-363_SC-70-6",
        "Texas Instruments", "TPS22919DCKR", "https://www.ti.com/lit/ds/symlink/tps22919.pdf", "SC-70-6 (DCK), 2.1 x 2.0 mm",
        "Active-high PM rail switch. Internal ON pulldown defaults SPS30 off; QOD tied to output for discharge.", lcsc="C2149796")
    capacitor("C10", "10uF 10V X5R", (66, 160), "GRM31CR61A106KA01L", "Local switched PM rail bulk; controlled rise limits inrush.", "Capacitor_SMD:C_1206_3216Metric")
    add("Connector_Generic:Conn_01x05", "J2", "SPS30 HARNESS", (29, 139), "Connector_JST:JST_PH_S5B-PH-K_1x05_P2.00mm_Horizontal",
        "JST", "S5B-PH-K-S(LF)(SN)", "https://www.jst-mfg.com/product/pdf/eng/ePH.pdf", "JST PH 1x5 2.00 mm side-entry",
        "Board-side keyed harness header: 1=PM_5V, 2=RX, 3=TX, 4=SEL/floating, 5=GND. Verify assembled cable continuity.")
    add("bench-breathe:SPS30", "U2", "SPS30", (105, 139), "",
        "Sensirion AG", "SPS30", "https://sensirion.com/media/documents/8600FF88/64A3B8D6/Sensirion_PM_Sensors_Datasheet_SPS30.pdf",
        "Module with JST ZHR-5 mating connector",
        "Off-board PM module. UART selected by leaving SEL floating; housing is internally tied to signal GND.")

    # Shared I2C sensors and required local decoupling.
    resistor("R5", "4.7k 1%", (143, 116), "RC0603FR-074K7L", "Single board-owned I2C SDA pull-up to 3.3 V.")
    resistor("R6", "4.7k 1%", (157, 116), "RC0603FR-074K7L", "Single board-owned I2C SCL pull-up to 3.3 V.")
    resistor("R7", "10R 1%", (165, 139), "RC0603FR-0710RL", "SGP40 VDD RC decoupling series element per Figure 5.")
    add("bench-breathe:SGP40-D-R4", "U3", "SGP40-D-R4", (202, 142), "bench-breathe:Sensirion_DFN-6-1EP_2.44x2.44mm_P0.8mm",
        "Sensirion AG", "SGP40-D-R4", "https://sensirion.com/media/documents/296373BB/6203C5DF/Sensirion_Gas_Sensors_Datasheet_SGP40.pdf",
        "DFN-6, 2.44 x 2.44 x 0.85 mm, center pad",
        "I2C 0x59. VDD uses 10 Ω/100 nF RC, VDDH uses 1 µF; EP and pin 4 to GND; no board wash.", lcsc="C2874215")
    capacitor("C6", "100nF 50V X7R", (181, 164), "GRM188R71H104KA93D", "SGP40 filtered VDD decoupling after 10 Ω series resistor.")
    capacitor("C7", "1uF 16V X7R", (195, 164), "GRM188R71C105KA12D", "SGP40 VDDH hotplate supply decoupling.")
    add("bench-breathe:SHT40-AD1B-R2", "U4", "SHT40-AD1B-R2", (258, 142), "Sensor_Humidity:Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad",
        "Sensirion AG", "SHT40-AD1B-R2", "https://sensirion.com/media/documents/33FD6951/6555C40E/Sensirion_Datasheet_SHT4x.pdf",
        "DFN-4, 1.5 x 1.5 x 0.5 mm, open cavity, no center land",
        "I2C 0x44. Open-cavity sensor requires airflow, no copper under cavity, and separation from heat.", lcsc="C2909890")
    capacitor("C8", "100nF 50V X7R", (258, 164), "GRM188R71H104KA93D", "SHT40 local VDD bypass.")

    # Local status and sustained-action button.
    add("Switch:SW_Push", "SW1", "SETUP / EVENT / RESET", (315, 137), "Button_Switch_SMD:SW_SPST_PTS810",
        "C&K", "PTS810SJM250SMTRLFS", "https://www.ckswitches.com/media/1476/pts810.pdf", "SMD tactile switch",
        "Active-low local button. Firmware distinguishes event, setup hold, and factory-reset hold with explicit confirmation.")
    resistor("R8", "10k 1%", (292, 119), "RC0603FR-0710KL", "User-button pull-up to 3.3 V.")
    capacitor("C9", "100nF 50V X7R", (330, 137), "GRM188R71H104KA93D", "Button hardware debounce; firmware still applies bounded debounce.")
    add("Device:LED", "D2", "GREEN STATUS", (366, 137), "LED_SMD:LED_0603_1608Metric",
        "Lite-On", "LTST-C190KGKT", "https://optoelectronics.liteon.com/upload/download/DS22-2000-095/LTST-C190KGKT.pdf", "0603 green LED",
        "Active-low status LED. Firmware must use documented blink patterns so state is not conveyed by color alone.")
    resistor("R9", "1k 1%", (346, 137), "RC0603FR-071KL", "Status LED current limit; approximately 1–2 mA at 3.3 V.")

    # Connectivity: direct pin labels keep every net explicit and compact.
    for pin in ("A4","A9","B4","B9"): connect("J1", pin, "VBUS")
    for pin in ("A1","A12","B1","B12","S1"): connect("J1", pin, "GND")
    connect("J1","A5","CC1_SENSE"); connect("J1","B5","CC2_SENSE")
    for pin in ("A6","B6"): connect("J1",pin,"USB_CONN_DP")
    for pin in ("A7","B7"): connect("J1",pin,"USB_CONN_DM")
    for pin in ("A8","B8"): nc("J1",pin)
    connect("R1","1","CC1_SENSE"); connect("R1","2","GND")
    connect("R2","1","CC2_SENSE"); connect("R2","2","GND")
    connect("F1","1","VBUS"); connect("F1","2","VBUS_FUSED")
    connect("D1","1","VBUS_FUSED"); connect("D1","2","GND")
    for pin, net in {"1":"USB_CONN_DM","2":"USB_CONN_DP","3":"GND","4":"CC1_SENSE","5":"CC2_SENSE","8":"GND"}.items(): connect("U6",pin,net)
    for pin in ("6","7","9","10"): nc("U6",pin)
    connect("R11","1","USB_CONN_DM"); connect("R11","2","USB_DM")
    connect("R12","1","USB_CONN_DP"); connect("R12","2","USB_DP")

    for pin, net in {"1":"GND","2":"VBUS_FUSED","3":"VBUS_FUSED","4":"GND","5":"GND","6":"+3V3","7":"SW_NODE","8":"REG_PG","9":"GND"}.items(): connect("U5",pin,net)
    connect("L1","1","SW_NODE"); connect("L1","2","+3V3")
    connect("C1","1","VBUS_FUSED"); connect("C1","2","GND")
    connect("C2","1","+3V3"); connect("C2","2","GND")
    connect("R3","1","+3V3"); connect("R3","2","REG_PG")

    controller_nets = {"1":"+3V3","2":"EN","3":"I2C_SDA","4":"I2C_SCL","5":"PM_ENABLE",
                       "6":"STATUS_LED_K","8":"BOOT_GPIO9","9":"GND","10":"USER_BUTTON_N",
                       "11":"PM_UART_TX","12":"PM_UART_RX","13":"USB_DM","14":"USB_DP","15":"REG_PG",
                       "17":"CC2_SENSE","18":"CC1_SENSE","19":"GND"}
    for pin, net in controller_nets.items(): connect("U1",pin,net)
    for pin in ("7","16"): nc("U1",pin)
    for ref in ("C3","C4"): connect(ref,"1","+3V3"); connect(ref,"2","GND")
    connect("R4","1","+3V3"); connect("R4","2","EN")
    connect("C5","1","EN"); connect("C5","2","GND")
    connect("R10","1","+3V3"); connect("R10","2","BOOT_GPIO9")
    for pin, net in {"1":"+3V3","2":"GND","3":"EN","4":"BOOT_GPIO9","5":"PM_UART_RX","6":"PM_UART_TX"}.items(): connect("J3",pin,net)

    for pin, net in {"1":"VBUS_FUSED","2":"GND","3":"PM_ENABLE","5":"PM_5V","6":"PM_5V"}.items(): connect("U7",pin,net)
    nc("U7","4")
    connect("C10","1","PM_5V"); connect("C10","2","GND")
    for ref in ("J2","U2"):
        for pin, net in {"1":"PM_5V","2":"PM_UART_RX","3":"PM_UART_TX","5":"GND"}.items(): connect(ref,pin,net)
        nc(ref,"4")

    connect("R5","1","+3V3"); connect("R5","2","I2C_SDA")
    connect("R6","1","+3V3"); connect("R6","2","I2C_SCL")
    connect("R7","1","+3V3"); connect("R7","2","SGP_VDD")
    for pin, net in {"1":"SGP_VDD","2":"GND","3":"I2C_SDA","4":"GND","5":"+3V3","6":"I2C_SCL","7":"GND"}.items(): connect("U3",pin,net)
    connect("C6","1","SGP_VDD"); connect("C6","2","GND")
    connect("C7","1","+3V3"); connect("C7","2","GND")
    for pin, net in {"1":"I2C_SDA","2":"I2C_SCL","3":"+3V3","4":"GND"}.items(): connect("U4",pin,net)
    connect("C8","1","+3V3"); connect("C8","2","GND")

    connect("R8","1","+3V3"); connect("R8","2","USER_BUTTON_N")
    connect("SW1","1","USER_BUTTON_N"); connect("SW1","2","GND")
    connect("C9","1","USER_BUTTON_N"); connect("C9","2","GND")
    connect("R9","1","+3V3"); connect("R9","2","STATUS_LED_A")
    connect("D2","2","STATUS_LED_A"); connect("D2","1","STATUS_LED_K")

    # ERC source declarations and named test access.
    for index, (net, pos) in enumerate((("VBUS",(105,88)),("VBUS_FUSED",(125,88)),("+3V3",(145,88)),("SGP_VDD",(165,88)),("GND",(185,88))), 1):
        ref = f"#FLG0{index}"
        add("power:PWR_FLAG", ref, "PWR_FLAG", pos, "", "N/A", "PCB_NET_FLAG", "~", "ERC-only",
            "ERC source declaration; not a purchased component.", in_bom=False)
        connect(ref,"1",net)
    test_nets = ["VBUS","VBUS_FUSED","+3V3","GND","PM_5V","REG_PG","EN","BOOT_GPIO9","I2C_SDA","I2C_SCL","USB_DP","USB_DM","CC1_SENSE","CC2_SENSE","PM_ENABLE","USER_BUTTON_N","PM_UART_RX","PM_UART_TX","SGP_VDD"]
    for index, net in enumerate(test_nets, 1):
        ref = f"TP{index}"
        add("Connector:TestPoint", ref, net, (25 + ((index - 1) % 10) * 37, 215 + ((index - 1) // 10) * 15),
            "TestPoint:TestPoint_Pad_D1.5mm", "N/A", "PCB_TEST_PAD", "~", "Unpopulated PCB pad",
            "Unpopulated labeled test pad; probe limits follow connected rail/signal.", in_bom=False)
        connect(ref,"1",net)

    schematic.add_text("USB-C 5 V SELV / CC SOURCE SENSE / PPTC / TVS / ESD", (20, 16), size=1.7, bold=True)
    schematic.add_text("TPS62162 FIXED 3.3 V BUCK / ESP32-C3-WROOM-02 / DEBUG", (105, 16), size=1.7, bold=True)
    schematic.add_text("SWITCHED SPS30 / SGP40 + SHT40 SHARED I2C", (20, 108), size=1.7, bold=True)
    schematic.add_text("LOCAL STATUS + SUSTAINED-ACTION BUTTON", (278, 108), size=1.7, bold=True)
    schematic.add_text("STATIC SCHEMATIC/ERC EVIDENCE ONLY — PCB, SIMULATION, ASSEMBLY, BENCH AND FIELD VALIDATION REMAIN PENDING", (20, 254), size=1.0, bold=True)

    issues = schematic.validate()
    errors = [issue for issue in issues if getattr(issue, "severity", "") == "error"]
    if errors:
        raise SystemExit("Schematic API validation failed: " + "; ".join(map(str, errors)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    schematic.save_as(output)
    print(f"generated {output} with {len(components)} symbols; api_validation_issues={len(issues)} errors=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
