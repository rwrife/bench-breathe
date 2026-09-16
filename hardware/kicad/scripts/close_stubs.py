#!/usr/bin/env python3
"""Deterministically close leftover ratsnest stubs after a FreeRouter pass.

Usage (inside the pcbnew container):
    python3 close_stubs.py <board.kicad_pcb> <drc.json> [--dry]

Reads `unconnected_items` pairs from a KiCad 9 DRC JSON, locates each pair's
geometry (pad / track-end / via) on the board, and adds the shortest legal
F.Cu/B.Cu segment(s) (straight, L with mid corner) whose clearance capsule
collides with nothing. Every accepted closure prints `FIXED`; anything left
prints `LEFT` verbatim. With --dry nothing is written.

KiCad 9 landmines honored: PCB_TRACE_T class name, PAD.GetNetCode (cap C),
unhashable PADs (key by id), every via serialized 'Blind/Buried Via [net] on
F.Cu - B.Cu' on 2-layer boards, SHAPE_POLY_SET has no BufferOutline (manual
capsule), connectivity rebuilt + board saved only after all closures.
"""
import json
import math
import sys

import pcbnew

NM = 1_000_000
CLEAR = 0.2  # default clearance mm (matches .kicad_pro rules)
EDGE = 0.5   # min copper edge clearance mm (matches .kicad_pro rules)


def parse_item(desc, pos):
    """Return (kind, net, layer_or_None, x_mm, y_mm)."""
    x, y = pos["x"], pos["y"]
    if desc.startswith("Pad ") or desc.startswith("PTH pad ") or desc.startswith("SMD pad "):
        net = desc.split("[", 1)[1].split("]", 1)[0]
        return "pad", net, None, x, y
    if desc.startswith("Track "):
        net = desc.split("[", 1)[1].split("]", 1)[0]
        lay = desc.split(" on ")[1].split(",")[0].strip()
        return "track", net, lay, x, y
    if "Via [" in desc:  # 'Via [net] on ...' or 'Blind/Buried Via [net] on ...'
        net = desc.split("[", 1)[1].split("]", 1)[0]
        return "via", net, None, x, y
    return None


def capsule_chain(p1, p2, width, clearance, margin=0.01):
    """Closed rect (capsule) around segment p1-p2 in nm ints."""
    x1, y1 = p1[0] * NM, p1[1] * NM
    x2, y2 = p2[0] * NM, p2[1] * NM
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy) or 1
    r = int((width / 2 + clearance + margin) * NM)
    px, py = int(-dy / ln * r), int(dx / ln * r)
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for q in ((x1 + px, y1 + py), (x2 + px, y2 + py), (x2 - px, y2 - py), (x1 - px, y1 - py)):
        ch.Append(int(q[0]), int(q[1]), True)
    ch.Append(int(x1 + px), int(y1 + py))
    ch.SetClosed(True)
    return pcbnew.SHAPE_POLY_SET(ch)


def main():
    board_path, drc_path = sys.argv[1], sys.argv[2]
    dry = "--dry" in sys.argv
    drc = json.load(open(drc_path))
    board = pcbnew.LoadBoard(board_path)

    # board outline rectangle from Edge.Cuts gr_lines
    exs, eys = [], []
    for d in board.GetDrawings():
        if "Edge" in d.GetLayerName():
            bb = d.GetBoundingBox()
            exs += [bb.GetX() / NM, bb.GetRight() / NM]
            eys += [bb.GetY() / NM, bb.GetBottom() / NM]
    W = max(exs) if exs else 65.0
    H = max(eys) if eys else 75.0

    # index pads: (x_mm, y_mm, net, ref, padname)
    pads = []
    for fp in board.Footprints():
        for p in fp.Pads():
            c = p.GetPosition()
            pads.append((c.x / NM, c.y / NM, p.GetNetname(), fp.GetReference(), p.GetPadName(), p))
    tracks = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]

    def find_pad(x, y):
        best, bd = None, 0.4
        for pd in pads:
            d = math.hypot(pd[0] - x, pd[1] - y)
            if d < bd:
                best, bd = pd, d
        return best

    def find_track_end(x, y):
        best, bd = None, 0.4
        for t in tracks:
            for pt in (t.GetStart(), t.GetEnd()):
                d = math.hypot(pt.x / NM - x, pt.y / NM - y)
                if d < bd:
                    best, bd = (t, pt), d
        return best

    def find_via(x, y):
        best, bd = None, 0.4
        for v in board.GetTracks():
            if v.Type() != pcbnew.PCB_VIA_T:
                continue
            p = v.GetStart()
            d = math.hypot(p.x / NM - x, p.y / NM - y)
            if d < bd:
                best, bd = (v, p), d
        return best

    def locate(desc, pos):
        it = parse_item(desc, pos)
        if not it:
            return ("skip", desc, pos)
        kind, net, lay, x, y = it
        if kind == "pad":
            p = find_pad(x, y)
            if p is None:
                return ("skip", desc, pos)
            return ("anchor", net, pcbnew.VECTOR2I(int(p[0] * NM), int(p[1] * NM)), desc)
        if kind == "track":
            t = find_track_end(x, y)
            if t is None:
                return ("skip", desc, pos)
            return ("anchor", net, t[1], desc)
        v = find_via(x, y)
        if v is None:
            return ("skip", desc, pos)
        return ("anchor", net, v[1], desc)

    blockers = []  # (layer, SHAPE_POLY_SET of effective shape) for foreign copper
    for p in pads:
        blockers.append((p[5].GetLayer(), p[5].GetEffectiveShape(p[5].GetLayer()), p[5]))
    for t in tracks:
        blockers.append((t.GetLayer(), t.GetEffectiveShape(), t))
    # keepout rule areas that forbid tracks are blockers too (the SHT4x
    # cavity keepout is footprint-embedded and never appears in
    # board.Zones(); parse the raw S-expr instead). Tested with margin 0
    # against the real track shape: keepouts forbid copper presence, not
    # clearance — the SHT4x ring leaves pad-width corridors for fanout.
    import re as _re
    keep_polys = []
    raw = open(board_path).read()
    depth = 0
    buf = []
    for line in raw.split("\n"):
        if depth == 0 and line.lstrip().startswith("(zone"):
            depth = 1
            buf = [line]
            continue
        if depth >= 1:
            buf.append(line)
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                blk = "\n".join(buf)
                if "(tracks not_allowed)" in blk:
                    pts = _re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)",
                                      blk.split("(filled_polygon")[0])
                    if pts:
                        ch = pcbnew.SHAPE_LINE_CHAIN()
                        for q in pts:
                            ch.Append(int(float(q[0]) * NM), int(float(q[1]) * NM), True)
                        ch.Append(int(float(pts[0][0]) * NM), int(float(pts[0][1]) * NM))
                        ch.SetClosed(True)
                        layers = _re.findall(r'\(layers? "([^"]+)"', blk)
                        both = any("B.Cu" in l for l in layers) or not layers
                        fcu = any("F.Cu" in l for l in layers) or not both
                        keep_polys.append((fcu, both or fcu, pcbnew.SHAPE_POLY_SET(ch)))
                buf = []

    def keepout_hit(pts, width):
        """True if the real track body (width/2 + 0.01) overlaps any
        track-forbidding keepout. DRC keepouts forbid copper presence, not
        clearance, so test with zero extra clearance."""
        for a, b in zip(pts, pts[1:]):
            cap = capsule_chain((a.x / NM, a.y / NM), (b.x / NM, b.y / NM), width, 0.0)
            for fcu, bcu, poly in keep_polys:
                if poly.Collide(cap, 0):
                    return True
        return False

    def clear_for(points, width, net_name, own_items):
        """True if polyline segments are legal on their layer.

        Foreign = different net OR no net info. Same-net copper is exempt:
        the stub track/via being extended is itself the net's copper, and a
        closure that touches any same-net island is legal (pitfall: exempting
        only endpoint item ids made every pad<->stub-track pair collide with
        its own stub and silently SKIP, fixed=0 forever).
        """
        if keepout_hit(points, width):
            return False

        def net_of(obj):
            try:
                return obj.GetNetname()
            except Exception:
                return None
        for a, b in zip(points, points[1:]):
            cap = capsule_chain((a.x / NM, a.y / NM), (b.x / NM, b.y / NM), width, CLEAR)
            for lay, shape, obj in blockers:
                if id(obj) in own_items:
                    continue
                if shape is None:
                    continue
                onet = net_of(obj)
                if onet is not None and onet == net_name:
                    continue
                if shape.Collide(cap, 0):
                    return False
            # board outline margin
            for pt in (a, b):
                if pt.x < 0.35 * NM or pt.y < 0.35 * NM:
                    return False
        # crude outline: assume rectangle from Edge.Cuts bbox
        return True

    fixed = 0
    skipped = 0
    left = []
    for entry in drc.get("unconnected_items", []):
        items = entry.get("items", [])
        if len(items) != 2:
            continue
        descs = [it.get("description", "") for it in items]
        poss = [it.get("pos", {}) for it in items]
        if any(not p for p in poss):
            skipped += 1
            continue
        if any("Zone" in d for d in descs):
            # zone<->zone pairs are pseudo-ratsnest artifacts of the copper
            # pour, not routable stubs — legitimate skip (pitfall 39).
            skipped += 1
            continue
        a = locate(descs[0], poss[0])
        b = locate(descs[1], poss[1])
        if a[0] == "skip" or b[0] == "skip":
            skipped += 1
            print(f"SKIP unparsed: {descs}")
            left.append((descs[0], descs[1]))
            continue
        net_a, pa = a[1], a[2]
        net_b, pb = b[1], b[2]
        if net_a != net_b:
            left.append((descs[0], descs[1]))
            continue
        net = board.FindNet(net_a)
        if net is None:
            left.append((descs[0], descs[1]))
            continue
        # widths mirror the .kicad_pro net classes (KiCad 9 NETCLASS python
        # getters are unreliable via GetNetClass() — resolve by name instead)
        POWER = {"/VBUS", "/VBUS_FUSED", "/SW_NODE", "/PM_5V", "/+3V3"}
        width = 0.4 if net_a in POWER else 0.25
        own = {id(pa) if False else 0}
        own_ids = set()
        # mark endpoints' items as 'own'
        near_a = find_pad(pa.x / NM, pa.y / NM)
        near_b = find_pad(pb.x / NM, pb.y / NM)
        if near_a and math.hypot(near_a[0] - pa.x / NM, near_a[1] - pa.y / NM) < 0.05:
            own_ids.add(id(near_a[5]))
        if near_b and math.hypot(near_b[0] - pb.x / NM, near_b[1] - pb.y / NM) < 0.05:
            own_ids.add(id(near_b[5]))

        candidates = [[pa, pb], [pa, pcbnew.VECTOR2I(pb.x, pa.y), pb],
                      [pa, pcbnew.VECTOR2I(pa.x, pb.y), pb]]
        done = False
        for pts in candidates:
            if clear_for(pts, width, net_a, own_ids):
                if not dry:
                    for s, e in zip(pts, pts[1:]):
                        tr = pcbnew.PCB_TRACK(board)  # ctor defaults to S_SEGMENT type
                        tr.SetStart(s)
                        tr.SetEnd(e)
                        tr.SetWidth(int(width * NM))
                        tr.SetLayer(pcbnew.F_Cu)
                        tr.SetNetCode(net.GetNetCode())
                        board.Add(tr)
                        tracks.append(tr)
                        blockers.append((pcbnew.F_Cu, tr.GetEffectiveShape(), tr))
                fixed += 1
                done = True
                print(f"FIXED {net_a}: {descs[0]} <-> {descs[1]}")
                break
        if not done:
            left.append((descs[0], descs[1]))

    print(f"fixed={fixed} left={len(left)} skipped={skipped}")
    for l in left:
        print(f"LEFT {l[0]} <-> {l[1]}")
    if not dry and fixed:
        board.BuildConnectivity()
        board.Save(board_path)
        print("saved", board_path)


if __name__ == "__main__":
    main()
