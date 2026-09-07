#!/usr/bin/env python3
"""Verify the M2 component-selection metadata in the KiCad schematic."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

EXPECTED = {
    "U1": ("Espressif Systems", "ESP32-C3-WROOM-02-N4", "C2934560"),
    "U2": ("Sensirion AG", "SPS30", None),
    "U3": ("Sensirion AG", "SGP40-D-R4", "C2874215"),
    "U4": ("Sensirion AG", "SHT40-AD1B-R2", "C2909890"),
    "U5": ("Texas Instruments", "TPS62162DSGR", "C40256"),
    "U6": ("Texas Instruments", "TPD4E05U06DQAR", "C138714"),
    "U7": ("Texas Instruments", "TPS22919DCKR", "C2149796"),
    "J1": ("GCT", "USB4105-GF-A", "C3020560"),
    "F1": ("Bourns", "MF-MSMF050-2", "C17313"),
    "D1": ("Diodes Incorporated", "SMBJ5.0A-13-F", "C110528"),
}

EXPECTED_SYMBOLS = {
    "D1": ("Device", "D_Zener"),
}

EXPECTED_PACKAGES = {
    "U4": "DFN-4, 1.5 x 1.5 x 0.5 mm, open cavity, no center land",
    "D1": "SMB / DO-214AA",
}


def fields_for(component: ET.Element) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field in component.findall("./fields/field"):
        name = field.get("name")
        if name:
            fields[name] = field.text or ""
    return fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "schematic",
        nargs="?",
        type=Path,
        default=Path("hardware/kicad/bench-breathe.kicad_sch"),
    )
    parser.add_argument(
        "--bom",
        type=Path,
        default=Path("bom/preliminary-bom.csv"),
        help="planning BOM whose selected rows must match the schematic metadata",
    )
    args = parser.parse_args()

    if shutil.which("kicad-cli") is None:
        print("FAIL: kicad-cli is not available", file=sys.stderr)
        return 2
    if not args.schematic.is_file():
        print(f"FAIL: schematic not found: {args.schematic}", file=sys.stderr)
        return 2
    if not args.bom.is_file():
        print(f"FAIL: BOM not found: {args.bom}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="bench-breathe-netlist-") as tmp:
        netlist = Path(tmp) / "selection.xml"
        subprocess.run(
            [
                "kicad-cli",
                "sch",
                "export",
                "netlist",
                str(args.schematic),
                "--format",
                "kicadxml",
                "--output",
                str(netlist),
            ],
            check=True,
        )
        root = ET.parse(netlist).getroot()

    components = {
        component.get("ref", ""): component
        for component in root.findall("./components/comp")
    }
    errors: list[str] = []
    with args.bom.open(newline="", encoding="utf-8") as bom_file:
        selected_bom_rows = {
            row["MPN"]: row
            for row in csv.DictReader(bom_file)
            if row["Planning_Status"] == "SELECTED_M2"
        }

    expected_mpns = {selection[1] for selection in EXPECTED.values()}
    unexpected_bom = sorted(set(selected_bom_rows) - expected_mpns)
    missing_bom = sorted(expected_mpns - set(selected_bom_rows))
    if unexpected_bom:
        errors.append(f"unexpected SELECTED_M2 BOM MPNs: {', '.join(unexpected_bom)}")
    if missing_bom:
        errors.append(f"missing SELECTED_M2 BOM MPNs: {', '.join(missing_bom)}")

    unexpected = sorted(set(components) - set(EXPECTED))
    missing = sorted(set(EXPECTED) - set(components))
    if unexpected:
        errors.append(f"unexpected components: {', '.join(unexpected)}")
    if missing:
        errors.append(f"missing components: {', '.join(missing)}")

    for reference, (manufacturer, mpn, lcsc) in EXPECTED.items():
        component = components.get(reference)
        if component is None:
            continue
        fields = fields_for(component)
        expected_fields: dict[str, str] = {
            "Manufacturer": manufacturer,
            "MPN": mpn,
        }
        if lcsc is not None:
            expected_fields["LCSC"] = lcsc
        elif fields.get("LCSC", "").strip():
            errors.append(
                f"{reference} has an unvalidated LCSC field: {fields['LCSC']!r}"
            )
        for name, expected in expected_fields.items():
            actual = fields.get(name)
            if actual != expected:
                errors.append(
                    f"{reference} {name}: expected {expected!r}, got {actual!r}"
                )
        for required in ("Datasheet", "Package", "BOM Comments"):
            if not fields.get(required, "").strip():
                errors.append(f"{reference} has empty {required}")
        datasheet = fields.get("Datasheet", "")
        if datasheet and not datasheet.startswith("https://"):
            errors.append(f"{reference} Datasheet is not HTTPS: {datasheet}")
        expected_package = EXPECTED_PACKAGES.get(reference)
        if expected_package is not None and fields.get("Package") != expected_package:
            errors.append(
                f"{reference} Package: expected {expected_package!r}, "
                f"got {fields.get('Package')!r}"
            )
        expected_symbol = EXPECTED_SYMBOLS.get(reference)
        if expected_symbol is not None:
            libsource = component.find("libsource")
            actual_symbol = (
                libsource.attrib.get("lib", "") if libsource is not None else "",
                libsource.attrib.get("part", "") if libsource is not None else "",
            )
            if actual_symbol != expected_symbol:
                errors.append(
                    f"{reference} symbol expected {expected_symbol!r}, got {actual_symbol!r}"
                )
        bom_row = selected_bom_rows.get(mpn)
        if bom_row is not None:
            if bom_row["Manufacturer"] != manufacturer:
                errors.append(
                    f"{reference} BOM Manufacturer expected {manufacturer!r}, "
                    f"got {bom_row['Manufacturer']!r}"
                )
            if bom_row["Source_URL"] != datasheet:
                errors.append(
                    f"{reference} BOM Source_URL differs from schematic Datasheet"
                )

    if errors:
        print("COMPONENT_SELECTION_METADATA: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("COMPONENT_SELECTION_METADATA: PASS")
    print(f"components={len(components)}")
    print(f"selected_m2_bom_rows={len(selected_bom_rows)}")
    print("required_fields=Manufacturer,MPN,Datasheet,Package,BOM Comments")
    expected_lcsc_count = sum(1 for _, _, lcsc in EXPECTED.values() if lcsc)
    print(
        f"expected_lcsc_fields={expected_lcsc_count} "
        "(one manufacturer-ambiguous match intentionally omitted)"
    )
    print("electrical_connectivity=not_checked (M2 staging sheet; issue #3)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
