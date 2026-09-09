# BOM workflow

The **editable KiCad schematic** (`hardware/kicad/bench-breathe.kicad_sch`) is
the single source of truth for this BOM. Sourcing data lives in schematic
symbol properties (`Manufacturer`, `MPN`, `LCSC`, `Package`, `Datasheet`,
`BOM Comments`) and is exported — never hand-maintained — into:

| File | Role |
|------|------|
| `bom.csv` | Generated stuffed-BOM export from the schematic (this is the committed artifact). |
| `export_bom.py` | Reproducible exporter: `kicad-cli sch export bom` (ungrouped) + in-script merge of identical parts, supplier/pricing annotation. |
| `verify_bom.py` | Gate script: proves `bom.csv` is exactly the in-BOM symbol set of the schematic with no fabricated prices. |
| `preliminary-bom.csv` | Historical issue-#2 candidate list, now annotated with `Schematic_Refs` and `Reconciliation` columns. |
| `non-schematic-items.csv` | PCB fab, enclosure, cables, fasteners, adapter, power supply — items not on any schematic symbol, each with explicit planning status. |

## Regenerate

From the repository root (requires `kicad-cli` on PATH, tested with KiCad 9.0.9):

```bash
python3 bom/export_bom.py          # rewrites bom/bom.csv
python3 bom/verify_bom.py          # fails non-zero on any inconsistency
```

## Sourcing and pricing policy (no fabricated claims)

- `Supplier_Source` contains an LCSC part number **only** where the schematic
  carries a manufacturer-validated `LCSC` property (see
  `hardware/component-selection.md`); every other row is
  `TBD - no validated source`.
- `Estimated_Unit_Cost_USD` is populated only for those validated parts, from
  the dated LCSC catalog snapshot (2026-09-05) recorded in
  `hardware/component-selection.md`. The `Price_Basis` column names that
  source on every priced row. All other rows are `TBD`.
- These are volatile planning figures, **not purchase quotes**. Re-run
  authorized-channel stock, pricing, and lifecycle checks at order time.
- Stock quantities are intentionally absent from this export; they go stale
  and must be re-queried live before ordering.

## Scope boundaries

The board is a SELV/USB-only device (5 V USB-C input, no mains control, no
medical/life-safety claims). Non-schematic support items (enclosure, cables,
fasteners, wall adapter, debug adapter) are tracked with explicit
`UNRESOLVED - live sourcing required` status rather than guessed parts.
