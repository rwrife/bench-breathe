#!/usr/bin/env python3
"""Per-pair stuck-ratsnest diagnostic: for each DRC unconnected pair, print the
FIRST colliding foreign object for straight/L/L2 candidate routes on F.Cu.

Usage: python3 diagnose_stubs.py <board.kicad_pcb> <drc.json>
Evidence artifact for documented-exception claims (pitfall 30/44).
"""
import json
import math
import sys

import pcbnew

NM = 1_000_000


def capsule(p1, p2, halfw):
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy) or 1
    px, py = int(-dy / ln * halfw), int(dx / ln * halfw)
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for q in ((x1 + px, y1 + py), (x2 + px, y2 + py), (x2 - px, y2 - py), (x1 - px, y1 - py)):
        ch.Append(int(q[0]), int(q[1]), True)
    ch.Append(int(x1 + px), int(y1 + py))
    ch.SetClosed(True)
    return pcbnew.SHAPE_POLY_SET(ch)


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    drc = json.load(open(sys.argv[2]))

    pads = []
    for fp in board.Footprints():
        for p in fp.Pads():
            c = p.GetPosition()
            pads.append((c.x, c.y, p.GetNetname(), fp.GetReference(), p.GetPadName(), p))
    tracks = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]

    blockers = []
    for pd in pads:
        blockers.append((pd[5].GetLayer(), pd[5].GetEffectiveShape(pd[5].GetLayer()), f"pad {pd[3]}.{pd[4]} [{pd[2]}]"))
    for t in tracks:
        blockers.append((t.GetLayer(), t.GetEffectiveShape(),
                         f"track [{t.GetNetname()}] {t.GetStart().x/NM:.2f},{t.GetStart().y/NM:.2f}->{t.GetEnd().x/NM:.2f},{t.GetEnd().y/NM:.2f}"))

    def find_pad(x, y):
        best, bd = None, 0.4 * NM
        for pd in pads:
            d = math.hypot(pd[0] - x, pd[1] - y)
            if d < bd:
                best, bd = pd, d
        return best

    def find_track_end(x, y):
        best, bd = None, 0.4 * NM
        for t in tracks:
            for pt in (t.GetStart(), t.GetEnd()):
                d = math.hypot(pt.x - x, pt.y - y)
                if d < bd:
                    best, bd = (t, pt), d
        return best

    def find_via(x, y):
        best, bd = None, 0.4 * NM
        for v in board.GetTracks():
            if v.Type() != pcbnew.PCB_VIA_T:
                continue
            p = v.GetStart()
            d = math.hypot(p.x - x, p.y - y)
            if d < bd:
                best, bd = (v, p), d
        return best

    def parse(desc, pos):
        x = int(float(pos["x"]) * NM)
        y = int(float(pos["y"]) * NM)
        low = desc.lower()
        if "pad " in low.split("[")[0]:
            net = desc.split("[", 1)[1].split("]", 1)[0]
            pd = find_pad(x, y)
            return (net, pcbnew.VECTOR2I(pd[0], pd[1])) if pd else None
        if desc.startswith("Track"):
            net = desc.split("[", 1)[1].split("]", 1)[0]
            tr = find_track_end(x, y)
            return (net, tr[1]) if tr else None
        if "Via [" in desc:
            net = desc.split("[", 1)[1].split("]", 1)[0]
            vv = find_via(x, y)
            return (net, vv[1]) if vv else None
        return None

    for entry in drc.get("unconnected_items", []):
        items = entry.get("items", [])
        if len(items) != 2:
            continue
        descs = [it.get("description", "") for it in items]
        if "Zone" in descs[0] or "Zone" in descs[1]:
            continue  # pseudo-ratsnest
        a = parse(descs[0], items[0].get("pos", {}))
        b = parse(descs[1], items[1].get("pos", {}))
        if a is None or b is None:
            print(f"UNRESOLVED: {descs[0]} <-> {descs[1]}")
            continue
        net, pa, pb = a[0], a[1], b[1]
        cands = {
            "straight": [pa, pb],
            "L-h": [pa, pcbnew.VECTOR2I(pb.x, pa.y), pb],
            "L-v": [pa, pcbnew.VECTOR2I(pa.x, pb.y), pb],
        }
        report = []
        for cname, pts in cands.items():
            first = None
            for s, e in zip(pts, pts[1:]):
                cap = capsule((s.x, s.y), (e.x, e.y), int((0.25 / 2 + 0.2) * NM))
                for lay, sh, tok in blockers:
                    if f"[{net}]" in tok or f"[/{net.lstrip('/')}]" in tok or f"[{net.lstrip('/')}]" in tok:
                        continue
                    if sh.Collide(cap, 0):
                        first = tok
                        break
                if first:
                    break
            report.append(f"{cname}: {'BLOCKED by ' + first if first else 'CLEAR'}")
        d = math.hypot(pa.x - pb.x, pa.y - pb.y) / NM
        print(f"\n{net} ({d:.2f} mm): {descs[0]} <-> {descs[1]}")
        for r in report:
            print("   ", r)


if __name__ == "__main__":
    main()
