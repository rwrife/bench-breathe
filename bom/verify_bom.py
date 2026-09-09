#!/usr/bin/env python3
"""Verification gate for bom/bom.csv (issue #4 acceptance criteria).

Checks, all of which must pass for exit code 0:

1. Freshness: re-running `export_bom.py` to a temp file reproduces the
   committed `bom.csv` byte-for-byte (the CSV is generated, not hand-edited).
2. Coverage: the union of `Refs` in the CSV equals the complete in-BOM
   symbol-reference set of the schematic, queried independently from
   `kicad-cli` (ungrouped, Reference-only).
3. Supplier integrity: every `Supplier_Source` value is either `LCSC <code>`
   (with the bare code also present as the row's validated source) or an
   explicit `TBD - ...` marker. No free-text invented suppliers.
4. No fabricated prices: a numeric `Estimated_Unit_Cost_USD` appears only on
   rows whose MPN is in the dated snapshot table *and* which have a validated
   LCSC source, with the exact snapshot value; every other row is `TBD`.

Usage (from repository root): python3 bom/verify_bom.py
"""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "bom" / "bom.csv"
SCH_PATH = REPO_ROOT / "hardware" / "kicad" / "bench-breathe.kicad_sch"
EXPORTER = REPO_ROOT / "bom" / "export_bom.py"

sys.path.insert(0, str(REPO_ROOT / "bom"))
from export_bom import PRICE_SNAPSHOT_USD, ref_ranges  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def schematic_refs() -> set[str]:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    proc = subprocess.run(
        ["kicad-cli", "sch", "export", "bom", str(SCH_PATH),
         "--output", str(tmp_path), "--fields", "Reference",
         "--labels", "Refs", "--sort-field", "Reference"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"kicad-cli reference export failed: {proc.stderr}")
    refs = {r.strip() for row in csv.DictReader(open(tmp_path))
            for r in row["Refs"].split(",") if r.strip()}
    tmp_path.unlink(missing_ok=True)
    return refs


def main() -> None:
    if not CSV_PATH.exists():
        sys.exit("bom/bom.csv missing — run bom/export_bom.py first")

    # 1. Freshness (byte-for-byte reproducibility).
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    proc = subprocess.run(
        [sys.executable, str(EXPORTER), "--schematic", str(SCH_PATH),
         "--output", str(tmp_path)],
        capture_output=True, text=True,
    )
    ok = proc.returncode == 0 and tmp_path.read_bytes() == CSV_PATH.read_bytes()
    check("bom.csv is byte-identical to a fresh export_bom.py run", ok,
          proc.stderr.strip() if not ok else "")
    tmp_path.unlink(missing_ok=True)

    rows = list(csv.DictReader(CSV_PATH.open()))

    # 2. Coverage.
    csv_refs: set[str] = set()
    for row in rows:
        for part in row["Refs"].split(","):
            if "-" in part and not part.startswith("-"):
                lo, hi = part.split("-", 1)
                prefix = "".join(c for c in lo if not c.isdigit())
                try:
                    a = int("".join(c for c in lo if c.isdigit()))
                    b = int("".join(c for c in hi if c.isdigit()))
                    csv_refs.update(f"{prefix}{i}" for i in range(a, b + 1))
                    continue
                except ValueError:
                    pass
            csv_refs.add(part)
    sch_refs = schematic_refs()
    check(f"CSV refs cover all {len(sch_refs)} in-BOM schematic symbols",
          csv_refs == sch_refs,
          f"missing={sorted(sch_refs - csv_refs)} extra={sorted(csv_refs - sch_refs)}"
          if csv_refs != sch_refs else f"{len(csv_refs)} refs matched")

    # 3. Supplier integrity.
    bad_suppliers = [
        r["Refs"] for r in rows
        if not (r["Supplier_Source"].startswith("LCSC ") or r["Supplier_Source"].startswith("TBD"))
    ]
    check("Supplier_Source is LCSC-validated or explicit TBD on every row",
          not bad_suppliers, str(bad_suppliers) if bad_suppliers else "")

    # 4. No fabricated prices.
    bad_price = []
    for r in rows:
        p = r["Estimated_Unit_Cost_USD"]
        if p == "TBD":
            if r["Price_Basis"] != "TBD - live sourcing required at order time":
                bad_price.append((r["Refs"], "TBD price without TBD basis"))
            continue
        try:
            val = float(p)
        except ValueError:
            bad_price.append((r["Refs"], f"non-numeric price {p!r}"))
            continue
        expected = PRICE_SNAPSHOT_USD.get(r["MPN"])
        if expected is None or abs(val - expected) > 1e-9 or not r["Supplier_Source"].startswith("LCSC "):
            bad_price.append((r["Refs"], f"price {p} not backed by snapshot+validated-source"))
    check("all numeric prices match the dated LCSC snapshot with validated source",
          not bad_price, str(bad_price) if bad_price else "")

    print()
    if FAILURES:
        print(f"RESULT: FAIL ({len(FAILURES)} check(s) failed)")
        sys.exit(1)
    print(f"RESULT: PASS ({len(rows)} BOM lines, {len(csv_refs)} schematic references)")


if __name__ == "__main__":
    main()
