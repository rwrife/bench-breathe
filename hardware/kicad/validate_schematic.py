#!/usr/bin/env python3
"""Validate issue #3 schematic acceptance criteria and ERC evidence."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCH = ROOT / "hardware/kicad/bench-breathe.kicad_sch"
PRO = ROOT / "hardware/kicad/bench-breathe.kicad_pro"
LIB = ROOT / "hardware/kicad/lib/bench-breathe.kicad_sym"
FP = ROOT / "hardware/kicad/lib/bench-breathe.pretty/Sensirion_DFN-6-1EP_2.44x2.44mm_P0.8mm.kicad_mod"
NOTES = ROOT / "hardware/schematic-notes.md"
PDF = ROOT / "hardware/kicad/exports/bench-breathe-schematic.pdf"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def prop(component, name: str) -> str:
    value = component.get_property(name)
    if isinstance(value, dict):
        value = value.get("value")
    return "" if value is None else str(value)


def rounded(x: float, y: float) -> tuple[float, float]:
    return round(float(x), 3), round(float(y), 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--erc", type=Path, required=True)
    parser.add_argument(
        "--footprint-dir", type=Path,
        default=Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")),
        help="KiCad .pretty library root used to resolve assigned footprints",
    )
    args = parser.parse_args()
    for path in (SCH, PRO, LIB, FP, NOTES, PDF, args.erc):
        if not path.is_file():
            fail(f"missing required file: {path}")

    os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
    from kicad_sch_api import get_symbol_cache, load_schematic
    cache = get_symbol_cache()
    symbol_dir = Path(os.environ["KICAD_SYMBOL_DIR"])
    if symbol_dir.is_dir():
        cache.discover_libraries([str(symbol_dir)])
    if not cache.add_library_path(str(LIB)):
        fail("could not load project symbol library")
    schematic = load_schematic(SCH)
    components = {c.reference: c for c in schematic.components.all()}
    definitions = {ref: cache.get_symbol(c.lib_id) for ref, c in components.items()}
    if missing := sorted(ref for ref, definition in definitions.items() if definition is None):
        fail(f"symbol definitions did not resolve: {missing}")

    required_refs = {"J1", "J2", "J3", "F1", "D1", "D2", "U1", "U2", "U3", "U4", "U5", "U6", "U7", "L1", "SW1"}
    if missing := sorted(required_refs - set(components)):
        fail(f"missing required functional blocks: {missing}")
    purchased = [c for c in components.values() if c.in_bom and not c.reference.startswith("#")]
    footprint_count = 0
    for component in purchased:
        if component.reference != "U2" and not component.footprint:
            fail(f"{component.reference} has no footprint")
        if component.footprint:
            footprint_count += 1
            library, name = component.footprint.split(":", 1)
            if library == "bench-breathe":
                footprint_path = ROOT / "hardware/kicad/lib/bench-breathe.pretty" / f"{name}.kicad_mod"
            else:
                footprint_path = args.footprint_dir / f"{library}.pretty" / f"{name}.kicad_mod"
            if not footprint_path.is_file():
                fail(f"{component.reference} footprint not found: {component.footprint} ({footprint_path})")
            pad_tokens = re.findall(r'\(pad\s+(?:"([^"]+)"|([^\s()]+))', footprint_path.read_text(encoding="utf-8"))
            pad_numbers = {quoted or bare for quoted, bare in pad_tokens if quoted or bare}
            symbol_pin_numbers = {str(pin.number) for pin in definitions[component.reference].pins}
            if missing_pads := sorted(symbol_pin_numbers - pad_numbers):
                fail(
                    f"{component.reference} symbol pins have no footprint pads in {component.footprint}: "
                    f"{missing_pads}"
                )
        for field in ("Manufacturer", "MPN", "Datasheet", "BOM Comments"):
            if not prop(component, field).strip():
                fail(f"{component.reference} missing {field}")

    expected_pins = {
        "U1": {"1":"3V3", "2":"EN", "9":"GND", "13":"GPIO18_USB_D-", "14":"GPIO19_USB_D+", "17":"GPIO1", "18":"GPIO0", "19":"GND"},
        "U2": {"1":"VDD", "2":"RX_SDA", "3":"TX_SCL", "4":"SEL", "5":"GND"},
        "U3": {"1":"VDD", "2":"VSS", "3":"SDA", "4":"GND", "5":"VDDH", "6":"SCL", "7":"EP_GND"},
        "U4": {"1":"SDA", "2":"SCL", "3":"VDD", "4":"VSS"},
        "U5": {"1":"PGND", "2":"VIN", "3":"EN", "4":"AGND", "5":"FB", "6":"VOS", "7":"SW", "8":"PG", "9":"EP_GND"},
        "U6": {"1":"D1+", "2":"D1-", "3":"GND", "4":"D2+", "5":"D2-", "8":"GND"},
        "U7": {"1":"IN", "2":"GND", "3":"ON", "4":"NC", "5":"QOD", "6":"VOUT"},
    }
    for ref, pin_map in expected_pins.items():
        for number, name in pin_map.items():
            pin = definitions[ref].get_pin(number)
            if pin is None or pin.name != name:
                fail(f"{ref}.{number}: expected {name!r}, got {getattr(pin, 'name', None)!r}")

    text = SCH.read_text(encoding="utf-8")
    label_pattern = re.compile(r'\(label\s+"([^"]+)"\s*\n\s*\(at\s+([-0-9.]+)\s+([-0-9.]+)')
    labels_at: dict[tuple[float, float], set[str]] = defaultdict(set)
    for net, x, y in label_pattern.findall(text):
        labels_at[rounded(float(x), float(y))].add(net)
    for point, nets in labels_at.items():
        if len(nets) > 1:
            fail(f"conflicting labels at {point}: {sorted(nets)}")

    def pin_point(ref: str, number: str) -> tuple[float, float]:
        c = components[ref]
        pin = definitions[ref].get_pin(number)
        if pin is None:
            fail(f"{ref} missing pin {number}")
        return rounded(c.position.x + pin.position.x, c.position.y - pin.position.y)

    expectations = {
        ("J1","A4"):"VBUS", ("J1","A5"):"CC1_SENSE", ("J1","B5"):"CC2_SENSE", ("J1","S1"):"GND",
        ("J1","A6"):"USB_CONN_DP", ("J1","A7"):"USB_CONN_DM",
        ("U1","13"):"USB_DM", ("U1","14"):"USB_DP", ("U1","18"):"CC1_SENSE", ("U1","17"):"CC2_SENSE",
        ("U1","3"):"I2C_SDA", ("U1","4"):"I2C_SCL", ("U1","5"):"PM_ENABLE", ("U1","10"):"USER_BUTTON_N",
        ("U5","2"):"VBUS_FUSED", ("U5","6"):"+3V3", ("U5","7"):"SW_NODE", ("U5","8"):"REG_PG",
        ("U7","1"):"VBUS_FUSED", ("U7","3"):"PM_ENABLE", ("U7","6"):"PM_5V",
        ("U2","1"):"PM_5V", ("U2","2"):"PM_UART_RX", ("U2","3"):"PM_UART_TX",
        ("U3","1"):"SGP_VDD", ("U3","3"):"I2C_SDA", ("U3","5"):"+3V3", ("U3","6"):"I2C_SCL",
        ("U4","1"):"I2C_SDA", ("U4","2"):"I2C_SCL", ("J3","3"):"EN", ("J3","4"):"BOOT_GPIO9",
        ("J3","5"):"PM_UART_RX", ("J3","6"):"PM_UART_TX",
    }
    for (ref, pin), net in expectations.items():
        actual = labels_at.get(pin_point(ref, pin), set())
        if net not in actual:
            fail(f"{ref}.{pin}: expected {net}, got {sorted(actual)}")

    required_nets = {"VBUS", "VBUS_FUSED", "+3V3", "GND", "PM_5V", "SW_NODE", "REG_PG", "EN", "BOOT_GPIO9", "I2C_SDA", "I2C_SCL", "USB_CONN_DP", "USB_CONN_DM", "USB_DP", "USB_DM", "CC1_SENSE", "CC2_SENSE", "PM_ENABLE", "USER_BUTTON_N", "STATUS_LED_K", "PM_UART_RX", "PM_UART_TX", "SGP_VDD"}
    observed = {net for nets in labels_at.values() for net in nets}
    if missing := sorted(required_nets - observed):
        fail(f"missing required nets: {missing}")

    erc = json.loads(args.erc.read_text(encoding="utf-8"))
    violations = [v for sheet in erc.get("sheets", []) for v in sheet.get("violations", [])]
    if violations:
        fail(f"native ERC has {len(violations)} violation(s)")
    if PDF.stat().st_size < 1000:
        fail("schematic PDF is unexpectedly small")
    if "static" not in NOTES.read_text(encoding="utf-8").lower():
        fail("schematic notes omit evidence boundary")

    print(f"PASS: native ERC violations={len(violations)} kicad={erc.get('kicad_version')}")
    print(f"PASS: components={len(components)} purchased={len(purchased)} resolved_footprints={footprint_count} required_functional_blocks={len(required_refs)}")
    print(f"PASS: critical_pin_net_mappings={len(expectations)} named_nets={len(required_nets)}")
    print(f"PASS: schematic_pdf_bytes={PDF.stat().st_size}")
    print("PASS: evidence_class=static_schematic; pcb=not_run simulation=not_run bench=not_run field=not_run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
