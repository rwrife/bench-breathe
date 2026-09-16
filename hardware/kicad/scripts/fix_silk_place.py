#!/usr/bin/env python3
"""Reposition silkscreen text that collides with other silk/copper/edge rules.

Usage: python3 fix_silk_place.py <board.kicad_pcb> [--dry]

Two policies, both conservative (never delete information):
1. Footprint Reference fields that overlap FOREIGN F.SilkS graphics or other
   visible reference text get stepped away from the collision in a small
   spiral of candidate offsets.
2. Standalone board labels (gr_text on F.SilkS, e.g. the board title) that
   sit over copper or nearer than the silk-edge rule to Edge.Cuts are nudged
   along -Y in 0.1 mm steps until edge- and copper-clear.

KiCad 9 notes honored: board text items live in GetDrawings() as PCB_TEXT;
footprint graphics via fp.GraphicalItems(); pad effective shape needs a layer
arg; collision via SHAPE_POLY_SET(other_bb).Collide(shape, clearance).
"""
import math
import sys

import pcbnew

NM = 1_000_000
SILK_CLEAR = 0.15  # extra clearance between silk features (mm)
EDGE_CLEAR = 0.5   # silk-edge rule in .kicad_pro (mm)
TITLE_TARGET = "bench-breathe"


def bb_poly(item):
    b = item.GetBoundingBox()
    ch = pcbnew.SHAPE_LINE_CHAIN()
    pts = ((b.GetX(), b.GetY()), (b.GetRight(), b.GetY()),
           (b.GetRight(), b.GetBottom()), (b.GetX(), b.GetBottom()))
    for p in pts:
        ch.Append(int(p[0]), int(p[1]), True)
    ch.Append(int(pts[0][0]), int(pts[0][1]))
    ch.SetClosed(True)
    return pcbnew.SHAPE_POLY_SET(ch)


def is_silk_layer(name):
    return "Silk" in name


def main():
    path = sys.argv[1]
    dry = "--dry" in sys.argv
    board = pcbnew.LoadBoard(path)

    # ---- gather edge outline rectangle ----
    xs, ys = [], []
    for d in board.GetDrawings():
        if "Edge" in d.GetLayerName():
            bb = d.GetBoundingBox()
            xs += [bb.GetX(), bb.GetRight()]
            ys += [bb.GetY(), bb.GetBottom()]
    # Edge.Cuts bbox inflated by half stroke; shrink by 0.075 mm conservatively
    X0, Y0 = min(xs) + 0.075, min(ys) + 0.075
    X1, Y1 = max(xs) - 0.075, max(ys) - 0.075

    # ---- copper shapes (needed by both policies) ----
    copper = []
    for fp in board.Footprints():
        for p in fp.Pads():
            copper.append(p.GetEffectiveShape(p.GetLayer()))
    for t in board.GetTracks():
        copper.append(t.GetEffectiveShape())

    def copper_free(item):
        poly = bb_poly(item)
        for sh in copper:
            if sh.Collide(poly, 0):
                return False
        return True

    # ---- gather foreign silk shapes (graphics + visible ref text bboxes) ----
    silk = []   # (shape, owner_token)
    ref_fields = []  # (fp, field, ref)
    for fp in board.Footprints():
        ref = fp.GetReference()
        for g in fp.GraphicalItems():
            if is_silk_layer(g.GetLayerName()):
                silk.append((bb_poly(g), fp))
        for f in fp.GetFields():
            try:
                name = f.GetName()
            except AttributeError:
                name = ""
            if name != "Reference":
                continue
            ref_fields.append((fp, f, ref))
            if f.IsVisible():
                silk.append((bb_poly(f), f))

    def collides_silk(poly, owner):
        for sh, tok in silk:
            if tok is owner:
                continue
            if sh.Collide(poly, int(SILK_CLEAR * NM)):
                return True
        return False

    # ---- policy 1: step colliding reference fields away ----
    moved_refs = 0
    for fp, f, ref in ref_fields:
        if not f.IsVisible():
            continue
        pos0 = f.GetPosition()
        cur = bb_poly(f)
        if not collides_silk(cur, f) and copper_free(f):
            continue
        cands = []
        for rad in (0.6, 1.0, 1.4, 2.0, 2.8, 3.6, 4.5, 5.5):
            for ang in (90, 270, 0, 180, 45, 135, 225, 315, 20, 70, 110, 160, 200, 250, 290, 340):
                dx = int(rad * NM * math.cos(math.radians(ang)))
                dy = int(rad * NM * math.sin(math.radians(ang)))
                cands.append(pcbnew.VECTOR2I(pos0.x + dx, pos0.y + dy))
        done = False
        for c in cands:
            f.SetPosition(c)
            # keep text on the board too
            b = f.GetBoundingBox()
            if (b.GetX() >= X0 * NM and b.GetY() >= Y0 * NM
                    and b.GetRight() <= X1 * NM and b.GetBottom() <= Y1 * NM
                    and not collides_silk(bb_poly(f), f) and copper_free(f)):
                moved_refs += 1
                print(f"MOVED ref {ref} ({pos0.x/NM:.2f},{pos0.y/NM:.2f}) -> ({c.x/NM:.2f},{c.y/NM:.2f})")
                done = True
                break
        if not done:
            f.SetPosition(pos0)
            print(f"KEEP  ref {ref}: no collision-free offset found")

    # ---- edge rule for title placement (copper_free already defined above) ----
    def edge_ok(item):
        b = item.GetBoundingBox()
        return (b.GetX() >= (X0 + EDGE_CLEAR) * NM and b.GetY() >= (Y0 + EDGE_CLEAR) * NM
                and b.GetRight() <= (X1 - EDGE_CLEAR) * NM and b.GetBottom() <= (Y1 - EDGE_CLEAR) * NM)

    def silk_free(item):
        poly = bb_poly(item)
        for sh, tok in silk:
            if sh.Collide(poly, int(SILK_CLEAR * NM)):
                return False
        return True

    # ---- policy 2: nudge board title labels along -Y, then X sweep ----
    moved_titles = 0
    for d in board.GetDrawings():
        if type(d).__name__ != "PCB_TEXT":
            continue
        if not is_silk_layer(d.GetLayerName()):
            continue
        if TITLE_TARGET not in d.GetText().lower():
            continue
        if edge_ok(d) and copper_free(d) and silk_free(d):
            continue
        pos0 = d.GetPosition()
        placed = None
        for dy in [k * 0.1 for k in range(1, 61)]:      # up to 6 mm up
            for dx in [0] + [k * 0.5 * s for k in range(1, 13) for s in (1, -1)]:
                probe = pcbnew.VECTOR2I(pos0.x + int(dx * NM), pos0.y - int(dy * NM))
                old = d.GetPosition()
                d.SetPosition(probe)
                if edge_ok(d) and copper_free(d) and silk_free(d):
                    placed = probe
                    break
                d.SetPosition(old)
            if placed:
                break
        if placed is not None:
            moved_titles += 1
            print(f"MOVED title label ({pos0.x/NM:.2f},{pos0.y/NM:.2f}) -> ({placed.x/NM:.2f},{placed.y/NM:.2f})")
            silk.append((bb_poly(d), d))
        else:
            d.SetPosition(pos0)
            print("KEEP  title label: no collision-free offset found")

    print(f"moved_refs={moved_refs} moved_titles={moved_titles}")
    if not dry and (moved_refs or moved_titles):
        board.Save(path)
        print("saved", path)


if __name__ == "__main__":
    main()
