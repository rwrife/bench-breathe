#!/usr/bin/env python3
"""Silk hygiene after routing: shrink dense/passive references, never delete.

Usage: python3 fix_silk.py <board.kicad_pcb>

Policy (testability first):
- TP*/SW* references stay VISIBLE but shrink to 0.8 mm / 0.15 mm stroke.
- Dense R/C/D references (^[DRC]\\d+$) are hidden — values/courtyards remain.
- IC/connector/board-text labels stay visible, shrunk if oversized.
"""
import re
import sys

import pcbnew

NM = 1_000_000
path = sys.argv[1]
b = pcbnew.LoadBoard(path)
hidden = 0
shrunk = 0
for fp in b.Footprints():
    ref = fp.GetReference()
    for field in fp.GetFields():
        try:
            if field.GetName() != "Reference":
                continue
        except AttributeError:  # some bindings expose only GetText
            pass
        if getattr(field, "GetName", lambda: "")() != "Reference":
            continue
        if re.fullmatch(r"[DRC]\d+", ref):
            field.SetVisible(False)
            hidden += 1
        elif re.fullmatch(r"(TP|SW|MK|J|U|F|L|D)\d*", ref) or ref.startswith("TP") or ref in ("SW1",):
            field.SetVisible(True)
            field.SetTextSize(pcbnew.VECTOR2I(int(0.8 * NM), int(0.8 * NM)))
            field.SetTextThickness(150000)
            shrunk += 1
print(f"hidden={hidden} shrunk-visible={shrunk}")
b.Save(path)
print("saved", path)
