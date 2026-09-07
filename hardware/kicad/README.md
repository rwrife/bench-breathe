# KiCad hardware sources

`bench-breathe.kicad_sch` is the editable M2 component-selection carrier. It stores exact Manufacturer/MPN/LCSC/Datasheet/Package/BOM Comments fields for the selected controller, sensors, regulator, and USB protection parts.

It is intentionally **not an electrically complete schematic**: every staging pin is marked no-connect and several parts use generic pin-count symbols. This keeps issue #2 metadata editable without implying that application circuits, pin mappings, footprints, or electrical behavior have passed design review.

Issue #3 must:

1. replace generic symbols with functional symbols verified against manufacturer pin tables;
2. assign and verify footprints pad-by-pad;
3. wire USB power/data/CC, regulation, controller, sensors, debug, status/input, and test points;
4. run design ERC and analyzers on that electrically complete revision.

The zero-violation M2 ERC only proves that the staging sheet is internally well-formed with intentional no-connects. It is not evidence that the future circuit works.

Re-run the metadata gate from the repository root with:

```bash
python3 hardware/scripts/verify_component_selection.py
```
