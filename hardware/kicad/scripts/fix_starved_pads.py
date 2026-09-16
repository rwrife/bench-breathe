#!/usr/bin/env python3
"""Set ZONE_CONNECTION_FULL on pads that starve thermal relief, then refill.

Usage: python3 fix_starved_pads.py <board.kicad_pcb> "REF:PAD" ["REF:PAD" ...]
"""
import sys

import pcbnew

path = sys.argv[1]
targets = [t.split(":") for t in sys.argv[2:]]
b = pcbnew.LoadBoard(path)
hit = 0
for fp in b.Footprints():
    if fp.GetReference() not in [t[0] for t in targets]:
        continue
    for pad in fp.Pads():
        if fp.GetReference() + ":" + pad.GetPadName() in sys.argv[2:]:
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            hit += 1
pcbnew.ZONE_FILLER(b).Fill(list(b.Zones()))
b.Save(path)
print(f"set FULL on {hit} pads; refilled; saved")
