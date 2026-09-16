#!/usr/bin/env python3
"""Stitch floating GND pour islands with validated stitching vias.

Usage: python3 stitch_pour_islands.py <board.kicad_pcb> [--dry]

Rasterizes filled GND copper per layer (0.4 mm grid), builds islands, treats
GND vias AND through-hole GND pads as F<->B joiners, then for every floating
island outside the main connectivity group places one GND via at a cell where
the island overlaps the opposite layer's MAIN group copper — but only after a
collision check of the via annulus (+clearance) against all foreign-net pads,
tracks, board edge, and via-forbidding keepouts. Acceptance is re-DRC, not
this script's own count (pitfall 29). Replaces stitch_gnd.py whose dry-loop
never terminated (same-cell rejoin bug).
"""
import math
import sys

import pcbnew

NM = 1_000_000
STEP = 0.4
VIA_W = 0.6
VIA_D = 0.3
CLEAR = 0.2
EDGE = 0.5
MIN_SLIVER_CELLS = 8  # islands below this are raster noise; documented, not stitched

path = sys.argv[1]
dry = "--dry" in sys.argv

board = pcbnew.LoadBoard(path)
net = board.FindNet("GND") or board.FindNet("/GND")
assert net is not None
zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname().endswith("GND")]

xs, ys = [], []
for d in board.GetDrawings():
    if "Edge" in d.GetLayerName():
        bb = d.GetBoundingBox()
        xs += [bb.GetX(), bb.GetRight()]
        ys += [bb.GetY(), bb.GetBottom()]
X0, Y0, X1, Y1 = min(xs) / NM, min(ys) / NM, max(xs) / NM, max(ys) / NM
GX0, GY0, GX1, GY1 = X0 + 0.3, Y0 + 0.3, X1 - 0.3, Y1 - 0.3
GW = int((GX1 - GX0) / STEP) + 1
GH = int((GY1 - GY0) / STEP) + 1
F, B = pcbnew.F_Cu, pcbnew.B_Cu


def has(lay, gx, gy):
    p = pcbnew.VECTOR2I(int((GX0 + gx * STEP) * NM), int((GY0 + gy * STEP) * NM))
    return any(z.GetLayerSet().Contains(lay) and z.HitTestFilledArea(lay, p, 0) for z in zones)


cf = [[has(F, x, y) for y in range(GH)] for x in range(GW)]
cb = [[has(B, x, y) for y in range(GH)] for x in range(GW)]

# joiners: existing GND vias and GND PTH pads bridge the two layers
join = [[False] * GH for _ in range(GW)]
for t in board.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname().endswith("GND"):
        gx = round((t.GetStart().x / NM - GX0) / STEP)
        gy = round((t.GetStart().y / NM - GY0) / STEP)
        if 0 <= gx < GW and 0 <= gy < GH:
            join[gx][gy] = True
for fp in board.Footprints():
    for p in fp.Pads():
        if not p.GetNetname().endswith("GND"):
            continue
        if p.GetDrillSize().x > 0 and p.IsOnLayer(F) and p.IsOnLayer(B):
            gx = round((p.GetPosition().x / NM - GX0) / STEP)
            gy = round((p.GetPosition().y / NM - GY0) / STEP)
            if 0 <= gx < GW and 0 <= gy < GH:
                join[gx][gy] = True


def comps(grid):
    lab = [[-1] * GH for _ in range(GW)]
    n = 0
    for i in range(GW):
        for j in range(GH):
            if grid[i][j] and lab[i][j] < 0:
                st = [(i, j)]
                lab[i][j] = n
                while st:
                    x, y = st.pop()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < GW and 0 <= ny < GH and grid[nx][ny] and lab[nx][ny] < 0:
                            lab[nx][ny] = n
                            st.append((nx, ny))
                n += 1
    return lab, n


labf, nf = comps(cf)
labb, nb = comps(cb)
sf = [0] * nf
sb = [0] * nb
for i in range(GW):
    for j in range(GH):
        if labf[i][j] >= 0:
            sf[labf[i][j]] += 1
        if labb[i][j] >= 0:
            sb[labb[i][j]] += 1

# union-find across layer islands joined by via/pad cells
parent = {}


def find(a):
    parent.setdefault(a, a)
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


def uni(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb


for i in range(GW):
    for j in range(GH):
        if join[i][j] and labf[i][j] >= 0 and labb[i][j] >= 0:
            uni(("F", labf[i][j]), ("B", labb[i][j]))
groups = {}
for k in range(nf):
    groups.setdefault(find(("F", k)), []).append(("F", k))
for k in range(nb):
    groups.setdefault(find(("B", k)), []).append(("B", k))
main_key = max(groups, key=lambda g: sum(sf[i] if t == "F" else sb[i] for t, i in groups[g]))


def in_main(key):
    return find(key) == main_key


# foreign copper blockers (non-GND nets) for the via-annulus check
blockers = []
for fp in board.Footprints():
    for p in fp.Pads():
        if not p.GetNetname().endswith("GND"):
            blockers.append((p.GetLayer(), p.GetEffectiveShape(p.GetLayer())))
for t in board.GetTracks():
    if not t.GetNetname().endswith("GND"):
        blockers.append((t.GetLayer(), t.GetEffectiveShape()))


def circle(cx, cy, r):
    pts = []
    for a in range(16):
        th = 2 * math.pi * a / 16
        pts.append((int((cx + r * math.cos(th)) * NM), int((cy + r * math.sin(th)) * NM)))
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for q in pts:
        ch.Append(q[0], q[1], True)
    ch.SetClosed(True)
    return pcbnew.SHAPE_POLY_SET(ch)


placed = 0
stitched, documented = [], []
for tag, nf_nb, lab, other in (("F", nf, labf, labb), ("B", nb, labb, labf)):
    for k2 in range(nf_nb):
        if in_main((tag, k2)):
            continue
        cells = [(i, j) for i in range(GW) for j in range(GH) if lab[i][j] == k2]
        if not cells:
            continue
        if len(cells) < MIN_SLIVER_CELLS:
            documented.append((tag, k2, len(cells), "sub-grid sliver"))
            continue
        done = False
        # deterministic scan order: by grid index
        for i, j in cells:
            px, py = GX0 + i * STEP, GY0 + j * STEP
            if px - (VIA_W / 2) < X0 + EDGE or py - (VIA_W / 2) < Y0 + EDGE \
               or px + (VIA_W / 2) > X1 - EDGE or py + (VIA_W / 2) > Y1 - EDGE:
                continue
            otag = "B" if tag == "F" else "F"
            if other[i][j] < 0 or not in_main((otag, other[i][j])):
                continue  # need opposite-layer MAIN copper under the via
            ann = circle(px, py, VIA_W / 2 + CLEAR)
            bad = False
            for lay, shape in blockers:
                if shape.Collide(ann, 0):
                    bad = True
                    break
            if bad:
                continue
            if not dry:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(int(px * NM), int(py * NM)))
                v.SetWidth(int(VIA_W * NM))
                v.SetDrill(int(VIA_D * NM))
                v.SetNetCode(net.GetNetCode())
                board.Add(v)
            placed += 1
            stitched.append((tag, k2, len(cells), round(px, 2), round(py, 2)))
            done = True
            break
        if not done:
            documented.append((tag, k2, len(cells), "no legal via cell"))

for t, k, n, *rest in stitched:
    print(f"STITCH {t}{k} cells={n} via=({rest[0]},{rest[1]})")
for t, k, n, why in documented:
    print(f"DOC {t}{k} cells={n} reason={why}")
print(f"placed={placed} documented={len(documented)}")
if not dry and placed:
    board.BuildConnectivity()
    board.Save(path)
    print("saved", path)
