#!/usr/bin/env python3
"""Generate the initial bench-breathe PCB via the pcbnew Python API.

Reads the JSON pin map produced by scripts/netlist_json.py (from
`kicad-cli sch export netlist`) and builds a two-layer board with a fixed
placement table, edge-cuts outline, net classes, antenna keepouts, copper
pours, mounting holes, and silk title text.

Usage (inside the parts-tally-kicad:9-arm64 image):
    python3 build_pcb.py <netlist.json> <out.kicad_pcb>

Every pcbnew name used here was probed against the 9.0.9 python bindings.
Board-owned NETINFO_ITEM objects are re-fetched with FindNet and kept alive
until Save (the GC trap in KiCad 9 silently strips nets otherwise).
"""
import json
import sys

import pcbnew

W, H = 65.0, 75.0          # board size mm
EDGE_MARGIN = 0.3          # copper keep-in margin from outline
NM = 1_000_000             # nm per mm

FP_DIRS = {
    "default": "/usr/share/kicad/footprints",
    "bench-breathe": "/hw/lib/bench-breathe.pretty",
}

# ref: (library, footprint_name, x_mm, y_mm, rot_deg)
# The antenna half-space of U1 is oriented toward the top edge (y=0).
PLACEMENT = {
    "J1":  ("Connector_USB", "USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", 32.5, 71.325, 0),
    "U6":  ("Package_SON", "USON-10_2.5x1.0mm_P0.5mm", 24.0, 66.0, 0),
    "R11": ("Resistor_SMD", "R_0603_1608Metric", 21.0, 66.0, 90),
    "R12": ("Resistor_SMD", "R_0603_1608Metric", 21.0, 63.0, 0),
    "F1":  ("Fuse", "Fuse_1812_4532Metric", 12.5, 68.0, 0),
    "D1":  ("Diode_SMD", "D_SMB", 45.0, 67.0, 0),
    "C1":  ("Capacitor_SMD", "C_1206_3216Metric", 14.5, 62.0, 90),
    "U5":  ("Package_SON", "WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm_ThermalVias", 10.5, 54.5, 0),
    "L1":  ("Inductor_SMD", "L_1008_2520Metric", 10.5, 49.0, 0),
    "C2":  ("Capacitor_SMD", "C_1206_3216Metric", 16.5, 49.0, 0),
    "R3":  ("Resistor_SMD", "R_0603_1608Metric", 17.0, 54.0, 90),
    "C3":  ("Capacitor_SMD", "C_1206_3216Metric", 22.0, 49.0, 90),
    "C4":  ("Capacitor_SMD", "C_0603_1608Metric", 25.5, 51.0, 90),
    "U7":  ("Package_TO_SOT_SMD", "SOT-363_SC-70-6", 34.0, 60.0, 0),
    "C10": ("Capacitor_SMD", "C_1206_3216Metric", 40.0, 60.0, 0),
    "J2":  ("Connector_JST", "JST_PH_S5B-PH-K_1x05_P2.00mm_Horizontal", 53.5, 50.0, 0),
    "U3":  ("bench-breathe", "Sensirion_DFN-6-1EP_2.44x2.44mm_P0.8mm", 54.5, 32.0, 0),
    "U4":  ("Sensor_Humidity", "Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad", 49.5, 27.0, 0),
    "C6":  ("Capacitor_SMD", "C_0603_1608Metric", 50.5, 32.0, 90),
    "C7":  ("Capacitor_SMD", "C_0603_1608Metric", 50.0, 36.0, 0),
    "C8":  ("Capacitor_SMD", "C_0603_1608Metric", 54.0, 37.0, 0),
    "U1":  ("RF_Module", "ESP32-C3-WROOM-02", 32.5, 20.5, 0),
    "C5":  ("Capacitor_SMD", "C_0603_1608Metric", 21.0, 15.3, 0),
    "R1":  ("Resistor_SMD", "R_0603_1608Metric", 30.5, 65.0, 0),
    "R2":  ("Resistor_SMD", "R_0603_1608Metric", 38.0, 65.0, 0),
    "R7":  ("Resistor_SMD", "R_0603_1608Metric", 53.5, 28.5, 0),
    "R8":  ("Resistor_SMD", "R_0603_1608Metric", 13.0, 38.5, 0),
    "R4":  ("Resistor_SMD", "R_0603_1608Metric", 21.0, 17.5, 0),
    "R10": ("Resistor_SMD", "R_0603_1608Metric", 11.0, 27.0, 0),
    "R5":  ("Resistor_SMD", "R_0603_1608Metric", 44.5, 30.5, 90),
    "R6":  ("Resistor_SMD", "R_0603_1608Metric", 47.5, 30.5, 90),
    "J3":  ("Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical", 14.4, 30.0, 270),
    "SW1": ("Button_Switch_SMD", "SW_SPST_PTS810", 7.5, 40.0, 0),
    "C9":  ("Capacitor_SMD", "C_0603_1608Metric", 13.0, 41.5, 0),
    "D2":  ("LED_SMD", "LED_0603_1608Metric", 44.0, 40.0, 0),
    "R9":  ("Resistor_SMD", "R_0603_1608Metric", 47.0, 40.0, 90),
    # Test-point row (signal bring-up), left to right:
    "TP1":  ("TestPoint", "TestPoint_Pad_D1.5mm", 14.5, 44.5, 0),
    "TP2":  ("TestPoint", "TestPoint_Pad_D1.5mm", 17.7, 44.5, 0),
    "TP3":  ("TestPoint", "TestPoint_Pad_D1.5mm", 20.9, 44.5, 0),
    "TP4":  ("TestPoint", "TestPoint_Pad_D1.5mm", 24.1, 44.5, 0),
    "TP5":  ("TestPoint", "TestPoint_Pad_D1.5mm", 27.3, 44.5, 0),
    "TP6":  ("TestPoint", "TestPoint_Pad_D1.5mm", 30.5, 44.5, 0),
    "TP7":  ("TestPoint", "TestPoint_Pad_D1.5mm", 33.7, 44.5, 0),
    "TP8":  ("TestPoint", "TestPoint_Pad_D1.5mm", 36.9, 44.5, 0),
    "TP9":  ("TestPoint", "TestPoint_Pad_D1.5mm", 40.1, 44.5, 0),
    "TP10": ("TestPoint", "TestPoint_Pad_D1.5mm", 43.3, 44.5, 0),
    "TP11": ("TestPoint", "TestPoint_Pad_D1.5mm", 25.5, 62.5, 0),
    "TP12": ("TestPoint", "TestPoint_Pad_D1.5mm", 28.5, 60.5, 0),
    "TP13": ("TestPoint", "TestPoint_Pad_D1.5mm", 8.0, 8.0, 0),
    "TP14": ("TestPoint", "TestPoint_Pad_D1.5mm", 8.0, 11.5, 0),
    "TP15": ("TestPoint", "TestPoint_Pad_D1.5mm", 34.5, 64.5, 0),
    "TP16": ("TestPoint", "TestPoint_Pad_D1.5mm", 7.5, 46.5, 0),
    "TP17": ("TestPoint", "TestPoint_Pad_D1.5mm", 54.5, 45.5, 0),
    "TP18": ("TestPoint", "TestPoint_Pad_D1.5mm", 54.5, 42.5, 0),
    "TP19": ("TestPoint", "TestPoint_Pad_D1.5mm", 57.5, 36.0, 0),
}

MOUNTING_HOLES = [(3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)]

# ESP32-C3-WROOM-02 antenna keepout rectangle relative to U1 origin (mm).
ANT_KEEP = (32.5 - 14.25, 20.5 - 18.35, 32.5 + 14.25, 20.5 - 6.85)

PSEUDO_PREFIX = "unconnected-("
POWER_NETS = ["/VBUS", "/VBUS_FUSED", "/SW_NODE", "/PM_5V", "/+3V3"]
USB_NETS = ["/USB_DP", "/USB_DM", "/USB_CONN_DP", "/USB_CONN_DM"]


def add_net(b, name, keep):
    b.Add(pcbnew.NETINFO_ITEM(b, name))
    keep[name] = b.FindNet(name)
    assert keep[name] is not None, name


def edge_rect(b, w, h):
    pts = [(0, 0), (w, h)]
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    for i in range(4):
        s = corners[i]
        e = corners[(i + 1) % 4]
        seg = pcbnew.PCB_SHAPE(b)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I(int(s[0] * NM), int(s[1] * NM)))
        seg.SetEnd(pcbnew.VECTOR2I(int(e[0] * NM), int(e[1] * NM)))
        seg.SetWidth(int(0.15 * NM))
        seg.SetLayer(pcbnew.Edge_Cuts)
        b.Add(seg)


def rect_chain(x1, y1, x2, y2):
    lc = pcbnew.SHAPE_LINE_CHAIN()
    for px, py in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
        lc.Append(int(px * NM), int(py * NM))
    lc.SetClosed(True)
    return lc


def add_rect(b, layer, x1, y1, x2, y2, width_mm):
    sh = pcbnew.PCB_SHAPE(b)
    sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
    sh.SetStart(pcbnew.VECTOR2I(int(x1 * NM), int(y1 * NM)))
    sh.SetEnd(pcbnew.VECTOR2I(int(x2 * NM), int(y2 * NM)))
    sh.SetWidth(int(width_mm * NM))
    sh.SetLayer(layer)
    b.Add(sh)


def main(net_json, out_path):
    data = json.load(open(net_json))
    nets, comps = data["nets"], data["components"]

    b = pcbnew.NewBoard(out_path)
    b.SetFileName(out_path)
    edge_rect(b, W, H)

    dr = b.GetDesignSettings()
    dr.m_minClearance = int(0.2 * NM)
    dr.m_MinThroughDrill = int(0.2 * NM)  # library thermal/heat-sink vias (U1 pad 19, U5 EP) use 0.2 mm drills

    # ---- nets -------------------------------------------------------------
    keep = {}
    functional = [n for n in nets if not n.startswith(PSEUDO_PREFIX)]
    for n in sorted(functional):
        add_net(b, n, keep)

    # ---- net classes ------------------------------------------------------
    ns = b.GetDesignSettings().m_NetSettings
    def make_class(name, width, clearance, nets_here):
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(int(width * NM))
        nc.SetClearance(int(clearance * NM))
        nc.SetViaDiameter(int(0.7 * NM))
        nc.SetViaDrill(int(0.3 * NM))
        ns.SetNetclass(name, nc)
        shared = ns.GetNetClassByName(name)
        for n in nets_here:
            if n in keep:
                keep[n].SetNetClass(shared)
    make_class("Power", 0.4, 0.2, POWER_NETS)
    make_class("USB", 0.25, 0.2, USB_NETS)

    # ---- footprints -------------------------------------------------------
    pad_owner = {}
    for ref, (lib, ffname, x, y, rot) in PLACEMENT.items():
        if ref not in comps:
            sys.exit(f"placement ref {ref} not in netlist components")
        d = FP_DIRS.get(lib, FP_DIRS["default"] + "/" + lib + ".pretty")
        fp = pcbnew.FootprintLoad(d, ffname)
        if fp is None:
            sys.exit(f"FootprintLoad failed for {lib}:{ffname}")
        fp.SetReference(ref)
        fp.SetLayer(pcbnew.F_Cu)
        fp.SetPosition(pcbnew.VECTOR2I(int(x * NM), int(y * NM)))
        fp.SetOrientationDegrees(rot)
        b.Add(fp)
        # bind pads by netlist node (ref, pad name)
        node_net = {}
        for n in functional:
            for r, p in nets[n]:
                if r == ref:
                    node_net[p] = n
        for pad in fp.Pads():
            pad_owner[id(pad)] = ref
            pn = pad.GetPadName()
            if pn in node_net:
                pad.SetNet(keep[node_net[pn]])
        # sanity: every named pad either bound or intentionally NC
    missing = [r for r in comps if r not in PLACEMENT]
    if missing:
        sys.exit(f"netlist refs missing from placement table: {missing}")

    # ---- mounting holes ---------------------------------------------------
    for i, (hx, hy) in enumerate(MOUNTING_HOLES, 1):
        fp = pcbnew.FootprintLoad(FP_DIRS["default"] + "/MountingHole.pretty", "MountingHole_3.2mm_M3")
        fp.SetReference(f"MK{i}")
        fp.SetPosition(pcbnew.VECTOR2I(int(hx * NM), int(hy * NM)))
        b.Add(fp)

    # ---- antenna keepout rule areas (explicit, both copper layers) -------
    ax1, ay1, ax2, ay2 = ANT_KEEP
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.AddPolygon(rect_chain(ax1, ay1, ax2, ay2))
        z.SetIsRuleArea(True)
        z.SetLayer(layer)
        z.SetAssignedPriority(1)  # carves the priority-0 GND pour
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowTracks(False)
        z.SetDoNotAllowVias(False)
        z.SetDoNotAllowFootprints(False)
        z.SetDoNotAllowCopperPour(True)
        b.Add(z)
        # note: SetAssignedPriority is set before b.Add() per KiCad 9 pitfall list

    # ---- copper-free rings: mounting holes + USB-C press-fit tabs -------
    # Rule areas that carve copper pour but must ALLOW the hole's own pad
    # (default rule areas also forbid pads -> items_not_allowed on the hole).
    def carve_ring(cx, cy, r):
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            z = pcbnew.ZONE(b)
            z.AddPolygon(rect_chain(cx - r, cy - r, cx + r, cy + r))
            z.SetIsRuleArea(True)
            z.SetLayer(layer)
            z.SetAssignedPriority(1)
            z.SetDoNotAllowPads(False)
            z.SetDoNotAllowTracks(False)
            z.SetDoNotAllowVias(False)
            z.SetDoNotAllowFootprints(False)
            z.SetDoNotAllowCopperPour(True)
            b.Add(z)

    for hx, hy in MOUNTING_HOLES:
        carve_ring(hx, hy, 2.7)
    # J1 non-plated anchoring slots (footprint-local x=+-2.89, y=-2.605)
    for tx in (-2.89, 2.89):
        carve_ring(32.5 + tx, 71.325 - 2.605, 0.95)

    # ---- GND pours (ground strategy: solid pour both layers, thermal) ----
    gnd = keep["/GND"]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.AddPolygon(rect_chain(EDGE_MARGIN, EDGE_MARGIN, W - EDGE_MARGIN, H - EDGE_MARGIN))
        z.SetNetCode(gnd.GetNetCode())
        z.SetLayer(layer)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetLocalClearance(int(0.25 * NM))
        b.Add(z)

    # ---- silk title -------------------------------------------------------
    t = pcbnew.PCB_TEXT(b)
    t.SetText("bench-breathe A0")
    t.SetPosition(pcbnew.VECTOR2I(int(6 * NM), int(73.3 * NM)))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(int(1.0 * NM), int(1.0 * NM)))
    t.SetTextThickness(int(0.15 * NM))
    t.SetVisible(True)
    b.Add(t)

    # Starved-relief fixes: edge-adjacent / small GND pads connect solid.
    for ref, pad_name in [("J1", "A12"), ("J1", "B1"), ("U6", "3"), ("U3", "2")]:
        fp = next(f for f in b.Footprints() if f.GetReference() == ref)
        for pad in fp.Pads():
            if pad.GetPadName() == pad_name:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(out_path)
    print(f"saved {out_path}")

    # ---- reload probe -----------------------------------------------------
    b2 = pcbnew.LoadBoard(out_path)
    assert b2.GetNetCount() > 20, f"net loss on reload: {b2.GetNetCount()}"
    u1 = [fp for fp in b2.Footprints() if fp.GetReference() == "U1"][0]
    p1 = [p for p in u1.Pads() if p.GetPadName() == "1"][0]
    assert p1.GetNetname() == "/+3V3", p1.GetNetname()
    gndpads = sum(1 for fp in b2.Footprints() for p in fp.Pads() if p.GetNetname() == "/GND")
    print(f"reload OK: nets={b2.GetNetCount()} fp={len(list(b2.Footprints()))} gnd-pads={gndpads}")

    # ---- courtyard overlap dump -------------------------------------------
    def crt_bbox(fp):
        xs, ys = [], []
        for it in fp.GraphicalItems():
            if "CrtYd" in str(it.GetLayerName()):
                bb = it.GetBoundingBox()
                xs += [bb.GetX(), bb.GetX() + bb.GetWidth()]
                ys += [bb.GetY(), bb.GetY() + bb.GetHeight()]
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            xs += [bb.GetX(), bb.GetX() + bb.GetWidth()]
            ys += [bb.GetY(), bb.GetY() + bb.GetHeight()]
        return min(xs), min(ys), max(xs), max(ys)

    boxes = []
    for fp in b2.Footprints():
        ref = fp.GetReference()
        if ref.startswith("MK"):
            continue
        x1, y1, x2, y2 = crt_bbox(fp)
        boxes.append((ref, x1 / NM, y1 / NM, x2 / NM, y2 / NM))
    ov = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, bb_ = boxes[i], boxes[j]
            ix = min(a[3], bb_[3]) - max(a[1], bb_[1])
            iy = min(a[4], bb_[4]) - max(a[2], bb_[2])
            if ix > 0 and iy > 0:
                ov += 1
                print(f"OVERLAP {a[0]} x {bb_[0]}: {ix:.2f} x {iy:.2f} mm")
    off = [b_ for b_ in boxes if b_[1] < -0.01 or b_[2] < -0.01 or b_[3] > W + 0.01 or b_[4] > H + 0.01]
    for o in off:
        print(f"OUTLINE {o[0]}: ({o[1]:.2f},{o[2]:.2f})..({o[3]:.2f},{o[4]:.2f})")
    print(f"courtyard overlaps: {ov}, off-outline: {len(off)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
