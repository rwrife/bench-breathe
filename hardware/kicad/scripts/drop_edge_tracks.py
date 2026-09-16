#!/usr/bin/env python3
"""Remove tracks closer to the board outline than the edge-clearance rule.

Usage: python3 drop_edge_tracks.py <board.kicad_pcb> <edge_limit_mm>
KiCad coords; rectangular outline assumed (this board's outline is exactly
rectangular). Router debris pressed against the edge is removed; the ratsnest
for the affected nets re-opens and is adjudicated by the next DRC.
"""
import sys

import pcbnew

path = sys.argv[1]
limit = float(sys.argv[2])
NM = 1_000_000
b = pcbnew.LoadBoard(path)
exs, eys = [], []
for d in b.GetDrawings():
    if "Edge" in d.GetLayerName():
        bb = d.GetBoundingBox()
        exs += [bb.GetX() / NM, bb.GetRight() / NM]
        eys += [bb.GetY() / NM, bb.GetBottom() / NM]
x1, x2, y1, y2 = min(exs), max(exs), min(eys), max(eys)
removed = 0
for t in list(b.GetTracks()):
    ok = True
    for pt in (t.GetStart(), t.GetEnd()):
        px, py = pt.x / NM, pt.y / NM
        if (px - x1 < limit) or (x2 - px < limit) or (py - y1 < limit) or (y2 - py < limit):
            ok = False
    if not ok:
        b.Remove(t)
        removed += 1
print(f"removed {removed} edge-violating tracks; outline=({x1},{y1})..({x2},{y2}) limit={limit}")
b.Save(path)
