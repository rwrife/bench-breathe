#!/usr/bin/env python3
"""Export bom/bom.csv from the editable KiCad schematic.

Workflow (issue #4): the schematic symbol properties are the BOM source of
truth. This script drives `kicad-cli sch export bom` (ungrouped, one row per
reference, including the per-reference `BOM Comments` field) and then merges
identical-part rows in-script — grouping on the tuple
(Value, Footprint, Package, Manufacturer, MPN, LCSC, DNP), collapsing
references into ranges, and joining per-reference notes with their reference
prefix so no per-ref note is lost. (kicad-cli 9.0.9 `--group-by` silently
fails to collapse rows for multi-field group keys, so the merge lives here.)

It then appends supplier and pricing columns:

- `Supplier_Source` is the LCSC part number only when the schematic carries a
  manufacturer-validated LCSC property; otherwise `TBD - no validated source`.
- `Estimated_Unit_Cost_USD` / `Price_Basis` carry the dated LCSC catalog
  snapshot recorded in `hardware/component-selection.md` for exactly those
  validated parts. Every other row is `TBD`. Prices are volatile planning
  evidence, not quotes; nothing here is fabricated or live-scraped.

Usage (from the repository root):

    python3 bom/export_bom.py [--schematic hardware/kicad/bench-breathe.kicad_sch]
                              [--output bom/bom.csv]

Exit code is non-zero if the export cannot be produced or if a schematic row
is dropped, so this is safe to wire into CI later.
"""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCH = REPO_ROOT / "hardware" / "kicad" / "bench-breathe.kicad_sch"
DEFAULT_OUT = REPO_ROOT / "bom" / "bom.csv"

# Dated one-unit pricing snapshot from hardware/component-selection.md
# ("Availability and lifecycle snapshot", LCSC catalog snapshot 2026-09-05,
# manufacturer-validated matches only). NOT a purchase quote.
PRICE_SNAPSHOT_USD: dict[str, float] = {
    "ESP32-C3-WROOM-02-N4": 3.2912,
    "SGP40-D-R4": 6.8654,
    "SHT40-AD1B-R2": 2.0288,
    "TPS62162DSGR": 0.9697,
    "TPD4E05U06DQAR": 0.0819,
    "TPS22919DCKR": 0.1378,
    "USB4105-GF-A": 1.0624,
    "MF-MSMF050-2": 0.0690,
    "SMBJ5.0A-13-F": 0.1019,
}
PRICE_SNAPSHOT_DATE = "LCSC catalog snapshot 2026-09-05 (see hardware/component-selection.md)"

OUTPUT_HEADER = [
    "Refs", "Qty", "Value", "Description", "Footprint", "Package",
    "Manufacturer", "MPN", "Supplier_Source", "Estimated_Unit_Cost_USD",
    "Price_Basis", "DNP", "Notes",
]

# Short functional descriptions keyed by reference prefix/role so the CSV is
# readable without opening the schematic. Derived from the schematic nets and
# hardware/component-selection.md functions.
DESCRIPTION_BY_VALUE = {
    "USB4105-GF-A": "USB Type-C 5V sink receptacle with CC1/CC2 Rd sensing",
    "SPS30 HARNESS": "Board-side JST PH harness header for off-board SPS30 PM module",
    "DEBUG / PROGRAM 3V3": "6-pin 3.3V debug/program header (EN, BOOT, U0TXD/RXD)",
    "SPS30": "Sensirion SPS30 particulate matter sensor (off-board, UART)",
    "SGP40-D-R4": "Sensirion SGP40 VOC index sensor (I2C 0x59)",
    "SHT40-AD1B-R2": "Sensirion SHT40 temperature/humidity sensor (I2C 0x44)",
    "TPS62162DSGR": "TI fixed 3.3V 1A synchronous buck regulator",
    "TPD4E05U06DQAR": "TI 4-channel low-capacitance USB/CC ESD protection",
    "TPS22919DCKR": "TI load switch for gated SPS30 5V rail",
    "USB-C 5V sink + USB2 data": "USB Type-C receptacle",
    "MF-MSMF050-2": "Bourns resettable PTC input fault protection",
    "SMBJ5.0A-13-F": "Diodes Inc. unidirectional TVS clamp on fused VBUS",
    "GREEN STATUS": "Green status LED (blink patterns, not color-only state)",
    "SETUP / EVENT / RESET": "Tactile button for event marking, setup hold, reset hold",
    "ESP32-C3-WROOM-02-N4": "Espressif ESP32-C3 Wi-Fi + native-USB MCU module",
    "2.2uH 1.3A": "Buck power inductor (TPS62162 recommended value)",
    "0.50A hold / 1.00A trip": "Resettable fuse, USB input protection",
}


def run_kicad_bom(sch: Path, fields: str, labels: str, group_by: str,
                  extra: list[str]) -> list[dict[str, str]]:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        "kicad-cli", "sch", "export", "bom", str(sch),
        "--output", str(tmp_path),
        "--fields", fields,
        "--labels", labels,
        "--sort-field", "Reference",
    ] + extra
    if group_by:
        cmd += ["--group-by", group_by]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp_path.exists():
        sys.exit(f"kicad-cli BOM export failed ({proc.returncode}): {proc.stderr}")
    rows = list(csv.DictReader(io.StringIO(tmp_path.read_text())))
    tmp_path.unlink(missing_ok=True)
    return rows


def ref_ranges(refs: list[str]) -> str:
    """Collapse refs like ['R4','R8','R10','C1'] into 'C1,R4,R8,R10' with
    contiguous same-prefix runs rendered as ranges (e.g. 'R4-R8')."""
    def key(ref: str):
        prefix = "".join(c for c in ref if not c.isdigit())
        digits = "".join(c for c in ref if c.isdigit())
        return (prefix, int(digits) if digits else 0)
    ordered = sorted(refs, key=key)
    chunks: list[list[str]] = []  # each chunk is a contiguous run
    for ref in ordered:
        prefix, num = key(ref)
        if chunks:
            last = chunks[-1]
            lp, ln = key(last[-1])
            if prefix == lp and num == ln + 1:
                last.append(ref)
                continue
        chunks.append([ref])
    parts = []
    for chunk in chunks:
        if len(chunk) >= 3:
            p, first = key(chunk[0])
            _, last_num = key(chunk[-1])
            parts.append(f"{p}{first}-{last_num}")
        else:
            parts.extend(chunk)
    return ",".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--schematic", default=str(DEFAULT_SCH))
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    sch = Path(args.schematic)
    out = Path(args.output)
    if not sch.exists():
        sys.exit(f"schematic not found: {sch}")

    rows = run_kicad_bom(
        sch,
        "Reference,Value,Footprint,Package,Manufacturer,MPN,LCSC,DNP,BOM Comments",
        "Refs,Value,Footprint,Package,Manufacturer,MPN,LCSC,DNP,Notes",
        "", [],
    )

    # Merge identical parts, preserving first-seen order.
    merged: dict[tuple, dict] = {}
    for row in rows:
        ref = row["Refs"].strip()
        if not ref:
            sys.exit("ungrouped export returned an empty reference — aborting")
        identity = (
            row["Value"], row.get("Footprint", ""), row.get("Package", ""),
            row.get("Manufacturer", ""), (row.get("MPN") or "").strip(),
            (row.get("LCSC") or "").strip(), (row.get("DNP") or "").strip(),
        )
        entry = merged.setdefault(identity, {"refs": [], "notes": []})
        entry["refs"].append(ref)
        note = (row.get("Notes") or "").strip()
        if note:
            entry["notes"].append(note)

    total_refs = sum(len(e["refs"]) for e in merged.values())
    out_rows = []
    for (value, footprint, package, manufacturer, mpn, lcsc, dnp), entry in merged.items():
        if mpn in PRICE_SNAPSHOT_USD and lcsc:
            price = f"{PRICE_SNAPSHOT_USD[mpn]:.4f}"
            basis = PRICE_SNAPSHOT_DATE
        else:
            price = "TBD"
            basis = "TBD - live sourcing required at order time"
        supplier = f"LCSC {lcsc}" if lcsc else "TBD - no validated source"
        out_rows.append({
            "Refs": ref_ranges(entry["refs"]),
            "Qty": len(entry["refs"]),
            "Value": value,
            "Description": DESCRIPTION_BY_VALUE.get(value, ""),
            "Footprint": footprint,
            "Package": package,
            "Manufacturer": manufacturer,
            "MPN": mpn,
            "Supplier_Source": supplier,
            "Estimated_Unit_Cost_USD": price,
            "Price_Basis": basis,
            "DNP": dnp,
            "Notes": " | ".join(entry["notes"]),
        })

    # Sanity gate: every grouped row must still have refs and a manufacturer.
    missing = [r["Refs"] for r in out_rows if not r["Refs"] or not r["Manufacturer"]]
    if missing:
        sys.exit(f"rows missing refs/manufacturer (schematic properties incomplete): {missing}")

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_HEADER)
        writer.writeheader()
        writer.writerows(out_rows)

    priced = [r for r in out_rows if r["Estimated_Unit_Cost_USD"] != "TBD"]
    print(f"Wrote {out} ({len(out_rows)} grouped lines, {total_refs} schematic references)")
    print(f"Priced rows (dated snapshot): {len(priced)}; TBD-price rows: {len(out_rows) - len(priced)}")


if __name__ == "__main__":
    main()
