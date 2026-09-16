#!/usr/bin/env python3
"""Delete tracks that DRC reports as track_dangling.

Usage: python3 drop_dangling.py <board.kicad_pcb> <drc.json>
Matches by net + exact segment endpoints (mm) from the DRC item descriptions.
"""
import json
import math
import sys

import pcbnew

NM = 1_000_000
path, drc_path = sys.argv[1], sys.argv[2]
drc = json.load(open(drc_path))
b = pcbnew.LoadBoard(path)
want = []  # (net, layer_sub, length_mm)
for v in drc.get("violations", []):
    if v.get("type") != "track_dangling":
        continue
    for it in v.get("items", []):
        d = it.get("description", "")
        if d.startswith("Track ["):
            net = d.split("[", 1)[1].split("]", 1)[0]
            lay = d.split(" on ")[1].split(",")[0].strip()
            ln = float(d.split("length ")[1].split(" mm")[0])
            want.append((net, lay, ln))
removed = 0
for t in list(b.GetTracks()):
    ln = math.hypot(t.GetEnd().x - t.GetStart().x, t.GetEnd().y - t.GetStart().y) / NM
    for net, lay, wln in want:
        if t.GetNetname() == net and lay.split(".")[0] in str(t.GetLayerName()) and abs(ln - wln) < 0.01:
            b.Remove(t)
            removed += 1
            break
print(f"removed {removed} dangling tracks (wanted {len(want)})")
b.Save(path)
