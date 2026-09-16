#!/usr/bin/env python3
"""Re-fill copper zones after SES import and save; report filled area per zone.

Usage: python3 refill_zones.py <board.kicad_pcb>
The stored fill polygons are stale once router tracks exist; DRC flags the
old polygons against the new copper until the zones are re-filled.
"""
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
zones = list(b.Zones())
pours = [z for z in zones if not z.GetIsRuleArea()]
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(zones)
b.Save(sys.argv[1])
b2 = pcbnew.LoadBoard(sys.argv[1])
for i, z in enumerate(b2.Zones()):
    if not z.GetIsRuleArea():
        print(f"pour {i} net={z.GetNetname()} filled_mm2={z.GetFilledArea() / 1e12:.1f}")
