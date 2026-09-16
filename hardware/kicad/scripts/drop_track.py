#!/usr/bin/env python3
"""Remove tracks/vias by exact geometry (net + endpoints), used to surgically
revert a bad stub closure (pitfall 29). Usage:
    python3 drop_track.py <board> <net> <x1> <y1> <x2> <y2>
coords mm, endpoint order-insensitive.
"""
import sys
import pcbnew

NM = 1_000_000
path, net = sys.argv[1], sys.argv[2]
pts = [(float(sys.argv[i]), float(sys.argv[i + 1])) for i in (3, 5)]
board = pcbnew.LoadBoard(path)
netc = board.FindNet(net.lstrip("/")) or board.FindNet(net)
removed = 0
for t in list(board.GetTracks()):
    if t.Type() != pcbnew.PCB_TRACE_T or (netc and t.GetNetCode() != netc.GetNetCode()):
        continue
    ends = {(round(t.GetStart().x / NM, 3), round(t.GetStart().y / NM, 3)),
            (round(t.GetEnd().x / NM, 3), round(t.GetEnd().y / NM, 3))}
    if ends == {(round(p[0], 3), round(p[1], 3)) for p in pts}:
        board.Remove(t)
        removed += 1
print("removed:", removed)
if removed:
    board.Save(path)
    print("saved", path)
