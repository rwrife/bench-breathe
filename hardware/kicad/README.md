# KiCad hardware sources

`bench-breathe.kicad_sch` is the editable A0 electrical schematic. It stores exact Manufacturer/MPN/LCSC/Datasheet/Package/BOM Comments fields and implements USB power/data/CC sensing, the fixed 3.3 V regulator, controller, sensors, programming/debug, local status/button, and named test points.

Project-local functional symbols and the SGP40 land pattern live under `lib/`; `generate_schematic.py` regenerates the editable source, and `validate_schematic.py` checks critical datasheet pin maps, net assignments, BOM properties, ERC JSON, and the PDF export.

Reproduce the static evidence from the repository root:

```bash
python3 -m venv /tmp/bench-breathe-ksa-env
/tmp/bench-breathe-ksa-env/bin/pip install -r hardware/kicad/requirements.txt
KICAD_SYMBOL_DIR=/usr/share/kicad/symbols /tmp/bench-breathe-ksa-env/bin/python hardware/kicad/generate_schematic.py
kicad-cli sch erc hardware/kicad/bench-breathe.kicad_sch --format json --output hardware/kicad/reports/erc.json --exit-code-violations
kicad-cli sch export pdf hardware/kicad/bench-breathe.kicad_sch --output hardware/kicad/exports/bench-breathe-schematic.pdf
KICAD_SYMBOL_DIR=/usr/share/kicad/symbols /tmp/bench-breathe-ksa-env/bin/python hardware/kicad/validate_schematic.py --erc hardware/kicad/reports/erc.json --footprint-dir /usr/share/kicad/footprints
```

The zero-violation ERC and validator are **static schematic evidence only**. They do not prove PCB routing, signal integrity, radio performance, power transients, assembly, sensor accuracy, or physical operation.

Re-run the metadata gate from the repository root with:

```bash
python3 hardware/scripts/verify_component_selection.py
```
