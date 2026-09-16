#!/usr/bin/env python3
"""Import a Specctra SES session file into the board and SAVE immediately.

Usage: python3 import_ses.py <board.kicad_pcb> <in.ses>
Metrics are printed from a RELOADED copy (the saved board is authoritative).
"""
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
ok = pcbnew.ImportSpecctraSES(board, sys.argv[2])
if not ok:
    print("ImportSpecctraSES returned False")
    sys.exit(1)
board.Save(sys.argv[1])  # save FIRST (pitfall 17), then probe
b2 = pcbnew.LoadBoard(sys.argv[1])
segs = sum(1 for t in b2.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T)
vias = sum(1 for t in b2.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
print(f"imported+saved: tracks={segs} vias={vias}")
