"""Generate esp32-board-v1.1.kicad_pcb.

Scope of this pass (matches agent.md section 7 step 6):
  * 77 x 45 mm board frame, R2 rounded corners
  * four 2.2 mm locating holes, centres 6 mm from the two nearest board edges
  * 4 layer / 1.2 mm stackup identical to the fab drawing
  * every schematic component placed, respecting the frozen interface
    constraints (USB-C lower right opening down, EPD FPC left centre opening
    left, battery lower left opening left, KEY1..3 on the right)
  * GND plane outline on In1.Cu plus GND fill outlines top/bottom and a
    documented antenna keepout rule area
  * ESP32-S3 antenna keepout enforced as a real DRC keepout

Copper routing (power corridors, USB 90 ohm pair, SPI/I2C) is the next pass;
this file deliberately leaves the ratsnest intact and documents the plan in
PCB_LAYOUT_NOTES.md.
"""

import math
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
import kicad_fp as KF

ROOT = Path("C:/Code/epdf-hardware/esp32-board-v1.1")
NETLIST = ROOT / "current.net"
OUT_PCB = ROOT / "esp32-board-v1.1.kicad_pcb"

BOARD_W = 55.0
BOARD_H = 84.0
CORNER_R = 2.0

# minimum gap kept between two placed courtyards (routing room + silk room)
GAP = 0.40

LAYERS = [
    (0, "F.Cu", "signal"),
    (1, "In1.Cu", "power"),
    (2, "In2.Cu", "power"),
    (31, "B.Cu", "signal"),
    (32, "B.Adhes", "user", "B.Adhesive"),
    (33, "F.Adhes", "user", "F.Adhesive"),
    (34, "B.Paste", "user"),
    (35, "F.Paste", "user"),
    (36, "B.SilkS", "user", "B.Silkscreen"),
    (37, "F.SilkS", "user", "F.Silkscreen"),
    (38, "B.Mask", "user"),
    (39, "F.Mask", "user"),
    (40, "Dwgs.User", "user", "User.Drawings"),
    (41, "Cmts.User", "user", "User.Comments"),
    (42, "Eco1.User", "user", "User.Eco1"),
    (43, "Eco2.User", "user", "User.Eco2"),
    (44, "Edge.Cuts", "user"),
    (45, "Margin", "user"),
    (46, "B.CrtYd", "user", "B.Courtyard"),
    (47, "F.CrtYd", "user", "F.Courtyard"),
    (48, "B.Fab", "user"),
    (49, "F.Fab", "user"),
]


def u():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# netlist
# ---------------------------------------------------------------------------

def load_netlist():
    root = ET.parse(NETLIST).getroot()
    comps = {}
    for c in root.iter("comp"):
        fp = (c.findtext("footprint") or "").strip()
        comps[c.get("ref")] = fp
    nets = {}
    padnets = {}
    for n in root.iter("net"):
        name = n.get("name")
        if name.startswith("unconnected-"):
            continue
        nets[name] = None  # id assigned later
        for node in n.findall("node"):
            padnets[(node.get("ref"), node.get("pin"))] = name
    net_ids = {name: i + 1 for i, name in enumerate(sorted(nets))}
    return comps, net_ids, padnets


# ---------------------------------------------------------------------------
# footprint geometry
# ---------------------------------------------------------------------------

_bbox_cache = {}


def fp_bbox(lib_id: str):
    if lib_id in _bbox_cache:
        return _bbox_cache[lib_id]
    lib, name = lib_id.split(":", 1)
    text = KF.read_mod(lib, name)
    _, children = KF.split_children(text)
    xs, ys = [], []
    for ch in children:
        if '"F.CrtYd"' not in ch:
            continue
        if KF.child_key(ch) == "fp_circle":
            c = re.search(r"\(center\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch)
            e = re.search(r"\(end\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch)
            cx, cy = float(c.group(1)), float(c.group(2))
            r = math.dist((cx, cy), (float(e.group(1)), float(e.group(2))))
            xs += [cx - r, cx + r]
            ys += [cy - r, cy + r]
            continue
        for m in re.finditer(r"\((?:start|end|center|mid|xy)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch):
            xs.append(float(m.group(1)))
            ys.append(float(m.group(2)))
    if not xs:
        pads = KF.parse_pads(text)
        for p in pads:
            xs += [p["x"] - p["w"] / 2, p["x"] + p["w"] / 2]
            ys += [p["y"] - p["h"] / 2, p["y"] + p["h"] / 2]
    bb = (min(xs), min(ys), max(xs), max(ys))
    _bbox_cache[lib_id] = bb
    return bb


def rotated_bbox(lib_id, rot):
    """Axis aligned bbox of the courtyard after rotating the footprint."""
    x0, y0, x1, y1 = fp_bbox(lib_id)
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    th = math.radians(rot)
    c, s = math.cos(th), math.sin(th)
    pts = [(px * c + py * s, -px * s + py * c) for px, py in corners]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def abs_bbox(lib_id, x, y, rot):
    dx0, dy0, dx1, dy1 = rotated_bbox(lib_id, rot)
    return (x + dx0, y + dy0, x + dx1, y + dy1)


def occupancy(ref, lib_id, x, y, rot):
    """Real space claimed by a placed part, as a list of axis aligned rects.

    The ESP32-S3-WROOM-1 courtyard is a T shape (module body plus the PCB
    antenna keep-out band).  Treating it as one bounding box would ban a huge
    area, so the two rectangles are listed explicitly.
    """
    if lib_id.endswith("ESP32-S3-WROOM-1"):
        # keep-out band and module body in board coordinates for rot 0
        return [
            (x - 24.0, y - 27.75, x + 24.0, y - 6.75),
            (x - 9.75, y - 6.75, x + 9.75, y + 13.45),
        ]
    return [abs_bbox(lib_id, x, y, rot)]


# ---------------------------------------------------------------------------
# placement
# ---------------------------------------------------------------------------

# Interface constraints frozen by agent.md / the confirmation document.
HARD = {
    # ref: (x, y, rot)   rot CCW, 0 = as drawn in the KiCad library
    # --- mechanically constrained (user requirements) ---------------------
    "U1": (27.5, 12.75, 0),     # module body flush with the top edge, antenna out
    # USB-C lower right, opening down.  The footprint's board edge reference is
    # local y = +3.675, so keeping that 1 mm past the outline makes the shell
    # overhang the board edge by exactly 1 mm.
    "J1": (45.5, 81.33, 0),
    "J2": (4.0, 42.0, 90),      # 24P EPD FPC left side centre, opening left
    "J3": (20.0, 75.20, 0),     # microSD bottom edge, card exits +Y
    "J4": (5.0, 71.15, 90),     # BAT1 lower left, opening left
    "J5": (5.0, 76.45, 90),     # BAT2 lower left, opening left
    "SW3": (52.85, 15.0, 90),   # KEY1  (centres 27 mm apart)
    "SW4": (52.85, 42.0, 90),   # KEY2
    "SW5": (52.85, 69.0, 90),   # KEY3
    "SW1": (24.0, 29.0, 0),     # RESET (position free)
    "SW2": (31.0, 29.0, 0),     # BOOT  (position free)
}

# functional regions used to place everything that is not hard placed.
# They must not overlap hard-placed courtyards - the placer treats those as
# obstacles anyway, but a clean partition keeps the result readable.
REGIONS = {
    "top_l":  (9.2, 7.2, 17.4, 31.4),     # left of the ESP32 module
    "top_r":  (37.8, 7.2, 50.6, 31.4),    # right of the ESP32 module
    "epd":    (9.4, 32.0, 27.4, 51.0),    # EPD booster, right of the FPC
    "pwr":    (28.0, 32.0, 50.6, 66.2),   # power / charger block (right half)
    "low":    (9.4, 51.4, 27.6, 66.2),    # below the FPC, above the microSD
    "bat":    (7.4, 66.6, 11.8, 80.0),    # battery branch fuses, next to J4/J5
    "low_r":  (28.3, 66.6, 42.6, 76.0),   # right of the microSD
    "bot":    (28.3, 76.2, 42.6, 83.4),   # between microSD and USB-C
}

REGION_ORDER = ["epd", "pwr", "top_l", "top_r", "low", "bat", "low_r", "bot"]

GROUP_ORDER = [
    # EPD load switch + booster cluster: tight, adjacent to the 24P FPC
    ("epd", ["U6", "L3", "Q1", "R29", "R30", "R31",
             "D6", "D7", "D8",
             "C25", "C26", "C27", "C28", "C29", "C30",
             "C31", "C32", "C33", "C34", "C35", "C36"]),
    # charger / regulator / fuel gauge / Type-C block
    ("pwr", ["U2", "U3", "L1", "L2", "U4", "U5",
             "C9", "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17",
             "C18", "C19", "C20", "C21", "C22", "C23", "C24",
             "R13", "R14", "R15", "R16", "R17", "R18", "R19", "R20", "R21",
             "R22", "R23", "R24", "R25", "R26", "R27", "R28", "NTC1"]),
    # ESP32 supply decoupling + reset/boot network
    ("top_l", ["C1", "C2", "C3", "C4", "C5", "R1", "R2"]),
    # USB front end (ESD, series R, shield)
    ("top_r", ["D1", "D2", "D3", "D4", "D5", "C6", "C7", "C8",
               "R8", "R9", "R10", "R11", "R12", "F1",
               "R3", "R4", "R5"]),
    # I2C pull-ups next to the PMIC cluster
    ("pwr", ["R6", "R7"]),
    # MicroSD + battery branch protection
    ("low", ["C37", "C38", "R32", "R33", "R34", "R35", "R36"]),
    ("bat", ["F2", "F3"]),
]


class Grid:
    """Coarse occupancy grid used as a placement / collision oracle."""

    def __init__(self, res=0.2, w=BOARD_W, h=BOARD_H):
        self.res = res
        self.nx = int(w / res) + 2
        self.ny = int(h / res) + 2
        self.g = bytearray(self.nx * self.ny)

    def _scan(self, x0, y0, x1, y1):
        ix0 = max(0, int(math.floor(x0 / self.res)))
        iy0 = max(0, int(math.floor(y0 / self.res)))
        ix1 = min(self.nx - 1, int(math.ceil(x1 / self.res)))
        iy1 = min(self.ny - 1, int(math.ceil(y1 / self.res)))
        return ix0, iy0, ix1, iy1

    def mark(self, x0, y0, x1, y1):
        ix0, iy0, ix1, iy1 = self._scan(x0, y0, x1, y1)
        for iy in range(iy0, iy1 + 1):
            base = iy * self.nx
            for ix in range(ix0, ix1 + 1):
                self.g[base + ix] = 1

    def free(self, x0, y0, x1, y1):
        ix0, iy0, ix1, iy1 = self._scan(x0, y0, x1, y1)
        for iy in range(iy0, iy1 + 1):
            base = iy * self.nx
            for ix in range(ix0, ix1 + 1):
                if self.g[base + ix]:
                    return False
        return True


def build_placement(comps):
    grid = Grid()
    # board outline keep-out, including the R2 rounded corners
    edge = 0.45
    corners = [(CORNER_R, CORNER_R), (BOARD_W - CORNER_R, CORNER_R),
               (CORNER_R, BOARD_H - CORNER_R), (BOARD_W - CORNER_R, BOARD_H - CORNER_R)]
    step = grid.res
    yy = 0.0
    while yy < BOARD_H:
        xx = 0.0
        while xx < BOARD_W:
            out = not (edge <= xx <= BOARD_W - edge and edge <= yy <= BOARD_H - edge)
            if not out:
                for cx, cy in corners:
                    near_x = (cx == CORNER_R and xx < CORNER_R) or \
                             (cx != CORNER_R and xx > BOARD_W - CORNER_R)
                    near_y = (cy == CORNER_R and yy < CORNER_R) or \
                             (cy != CORNER_R and yy > BOARD_H - CORNER_R)
                    if near_x and near_y and math.dist((xx, yy), (cx, cy)) > CORNER_R - edge:
                        out = True
            if out:
                grid.mark(xx, yy, xx + step, yy + step)
            xx += step
        yy += step
    # locating holes (2.2 mm hole + small screw head margin)
    for hx, hy in MOUNT_HOLES:
        grid.mark(hx - 1.7, hy - 1.7, hx + 1.7, hy + 1.7)

    place = {}
    for ref, (x, y, rot) in HARD.items():
        place[ref] = (x, y, rot)
        for r in occupancy(ref, comps[ref], x, y, rot):
            grid.mark(r[0] - GAP, r[1] - GAP, r[2] + GAP, r[3] + GAP)

    overflow = []

    THT = ("Connector", "Switch", "RF_Module", "Battery_Management", "Package_DFN",
           "Package_TO_SOT", "Inductor", "Diode", "Fuse", "MountingHole", "TestPoint")

    def try_place(ref, lib, region_order, rotations=(0, 90)):
        for rot in rotations:
            dx0, dy0, dx1, dy1 = rotated_bbox(lib, rot)
            w, h = dx1 - dx0, dy1 - dy0
            for reg in region_order:
                x0, y0, x1, y1 = REGIONS[reg]
                y = y0
                while y + h <= y1:
                    x = x0
                    while x + w <= x1:
                        if grid.free(x - GAP, y - GAP, x + w + GAP, y + h + GAP):
                            grid.mark(x - GAP, y - GAP, x + w + GAP, y + h + GAP)
                            return (x - dx0, y - dy0, rot)
                        x += grid.res
                    y += grid.res
        return None

    for primary, refs in GROUP_ORDER:
        for ref in refs:
            if ref not in comps:
                continue
            order = [primary] + [r for r in REGION_ORDER if r != primary]
            pos = try_place(ref, comps[ref], order)
            if pos is None:
                overflow.append(ref)
            else:
                place[ref] = pos

    # test points: last, smallest priority - spread them in whatever is left
    tp_refs = [r for r in comps if r.startswith("TP") and r not in place]
    for ref in sorted(tp_refs, key=lambda s: int(re.sub(r"\D", "", s) or 0)):
        pos = try_place(ref, comps[ref], REGION_ORDER)
        if pos is None:
            overflow.append(ref)
        else:
            place[ref] = pos
    if overflow and "-v" in sys.argv:
        step = 1.0
        print("      " + "".join(str(int(x)) for x in range(0, int(BOARD_W), int(step))))
        for iy in range(0, int(BOARD_H), int(step)):
            row = ""
            for ix in range(0, int(BOARD_W), int(step)):
                free = grid.free(ix, iy, ix + step - 0.01, iy + step - 0.01)
                row += "." if free else "#"
            print(f"{iy:4d}  {row}")
    return place, overflow


# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------

def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def gen_outline():
    out = []
    seg = [
        ((CORNER_R, 0.0), (BOARD_W - CORNER_R, 0.0)),
        ((BOARD_W, CORNER_R), (BOARD_W, BOARD_H - CORNER_R)),
        ((BOARD_W - CORNER_R, BOARD_H), (CORNER_R, BOARD_H)),
        ((0.0, BOARD_H - CORNER_R), (0.0, CORNER_R)),
    ]
    for (a, b) in seg:
        out.append(
            "\t(gr_line\n"
            f"\t\t(start {fmt(a[0])} {fmt(a[1])})\n"
            f"\t\t(end {fmt(b[0])} {fmt(b[1])})\n"
            "\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type solid)\n\t\t)\n"
            '\t\t(layer "Edge.Cuts")\n'
            f'\t\t(uuid "{u()}")\n\t)'
        )
    def arc(sx, sy, ex, ey, ccx, ccy):
        # mid point of a 90 degree corner arc: bisector of the two radii
        ux = (sx - ccx) / CORNER_R + (ex - ccx) / CORNER_R
        uy = (sy - ccy) / CORNER_R + (ey - ccy) / CORNER_R
        n = math.hypot(ux, uy)
        mx = ccx + CORNER_R * ux / n
        my = ccy + CORNER_R * uy / n
        return (
            "\t(gr_arc\n"
            f"\t\t(start {fmt(sx)} {fmt(sy)})\n"
            f"\t\t(mid {fmt(mx)} {fmt(my)})\n"
            f"\t\t(end {fmt(ex)} {fmt(ey)})\n"
            "\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type solid)\n\t\t)\n"
            '\t\t(layer "Edge.Cuts")\n'
            f'\t\t(uuid "{u()}")\n\t)'
        )

    out.append(arc(CORNER_R, 0.0, 0.0, CORNER_R, CORNER_R, CORNER_R))            # top-left
    out.append(arc(BOARD_W, CORNER_R, BOARD_W - CORNER_R, 0.0,
                   BOARD_W - CORNER_R, CORNER_R))                                 # top-right
    out.append(arc(BOARD_W - CORNER_R, BOARD_H, BOARD_W, BOARD_H - CORNER_R,
                   BOARD_W - CORNER_R, BOARD_H - CORNER_R))                       # bottom-right
    out.append(arc(0.0, BOARD_H - CORNER_R, CORNER_R, BOARD_H,
                   CORNER_R, BOARD_H - CORNER_R))                                 # bottom-left
    return "\n".join(out)


# 3 mm from each of the two nearest board edges
MOUNT_HOLES = [(3.0, 3.0), (52.0, 3.0), (3.0, 81.0), (52.0, 81.0)]


def gen_mount_holes():
    out = []
    for i, (x, y) in enumerate(MOUNT_HOLES, start=1):
        out.append(
            '\t(footprint "MountingHole:MountingHole_2.2mm_M2"\n'
            '\t\t(layer "F.Cu")\n'
            f'\t\t(uuid "{u()}")\n'
            f"\t\t(at {fmt(x)} {fmt(y)})\n"
            f'\t\t(descr "Mounting Hole 2.2mm, no annular")\n'
            f'\t\t(attr exclude_from_pos_files exclude_from_bom)\n'
            '\t\t(fp_circle\n'
            "\t\t\t(center 0 0)\n\t\t\t(end 2.2 0)\n"
            "\t\t\t(stroke\n\t\t\t\t(width 0.15)\n\t\t\t\t(type default)\n\t\t\t)\n"
            '\t\t\t(fill no)\n\t\t\t(layer "Cmts.User")\n'
            f'\t\t\t(uuid "{u()}")\n\t\t)\n'
            '\t\t(pad "" np_thru_hole circle\n'
            "\t\t\t(at 0 0)\n\t\t\t(size 2.2 2.2)\n\t\t\t(drill 2.2)\n"
            '\t\t\t(layers "*.Cu" "*.Mask")\n'
            f'\t\t\t(uuid "{u()}")\n\t\t)\n'
            "\t)"
        )
    return "\n".join(out)


def gen_stackup():
    return (
        '\t\t(stackup\n'
        '\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))\n'
        '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))\n'
        '\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01))\n'
        '\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))\n'
        '\t\t\t(layer "dielectric 1" (type "prepreg") (color "FR4") (thickness 0.195) '
        '(material "7628") (epsilon_r 4.2) (loss_tangent 0.02))\n'
        '\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.035))\n'
        '\t\t\t(layer "dielectric 2" (type "core") (color "FR4") (thickness 0.63) '
        '(material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))\n'
        '\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.035))\n'
        '\t\t\t(layer "dielectric 3" (type "prepreg") (color "FR4") (thickness 0.195) '
        '(material "7628") (epsilon_r 4.2) (loss_tangent 0.02))\n'
        '\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))\n'
        '\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.01))\n'
        '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))\n'
        '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))\n'
        '\t\t\t(copper_finish "None")\n'
        '\t\t\t(dielectric_constraints no)\n'
        "\t\t)"
    )


def zone_gnd(layer, name):
    m = 0.4
    pts = [(m, m), (BOARD_W - m, m), (BOARD_W - m, BOARD_H - m), (m, BOARD_H - m)]
    p = " ".join(f"(xy {fmt(px)} {fmt(py)})" for px, py in pts)
    return (
        "\t(zone\n"
        "\t\t(net 1)\n"
        '\t\t(net_name "GND")\n'
        f'\t\t(layer "{layer}")\n'
        f'\t\t(uuid "{u()}")\n'
        f'\t\t(name "{name}")\n'
        "\t\t(hatch edge 0.5)\n"
        "\t\t(connect_pads\n\t\t\t(clearance 0.3)\n\t\t)\n"
        "\t\t(min_thickness 0.25)\n"
        "\t\t(filled_areas_thickness no)\n"
        "\t\t(fill\n\t\t\t(thermal_gap 0.3)\n\t\t\t(thermal_bridge_width 0.4)\n\t\t)\n"
        "\t\t(polygon\n\t\t\t(pts\n"
        f"\t\t\t\t{p}\n"
        "\t\t\t)\n\t\t)\n"
        "\t)"
    )


def zone_keepout(layers, name, x0, y0, x1, y1):
    p = " ".join(f"(xy {fmt(a)} {fmt(b)})"
                 for a, b in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    lay = " ".join(f'"{l}"' for l in layers)
    return (
        "\t(zone\n"
        "\t\t(net 0)\n"
        f"\t\t(layers {lay})\n"
        f'\t\t(uuid "{u()}")\n'
        f'\t\t(name "{name}")\n'
        "\t\t(hatch edge 0.5)\n"
        "\t\t(keepout\n\t\t\t(tracks not_allowed)\n\t\t\t(vias not_allowed)\n"
        "\t\t\t(pads not_allowed)\n\t\t\t(copperpour not_allowed)\n"
        "\t\t\t(footprints allowed)\n"
        "\t\t)\n"
        "\t\t(polygon\n\t\t\t(pts\n"
        f"\t\t\t\t{p}\n"
        "\t\t\t)\n\t\t)\n"
        "\t)"
    )


def main():
    comps, net_ids, padnets = load_netlist()
    place, overflow = build_placement(comps)

    missing = [r for r in comps if r not in place]
    if missing or overflow:
        print("PLACEMENT PROBLEM")
        print("  no position:", missing)
        print("  overflow:", overflow)
        raise SystemExit(1)

    # sanity: courtyard collisions
    boxes = {ref: occupancy(ref, comps[ref], *place[ref]) for ref in place}
    refs = sorted(boxes)

    def overlap(a, b):
        for ra in boxes[a]:
            for rb in boxes[b]:
                if ra[0] < rb[2] and rb[0] < ra[2] and ra[1] < rb[3] and rb[1] < ra[3]:
                    return (ra, rb)
        return None

    collisions = []
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            hit = overlap(a, b)
            if hit:
                collisions.append((a, b, hit[0], hit[1]))
    print("placed:", len(place), "courtyard collisions:", len(collisions))
    for c in collisions[:80]:
        print(f"   collide {c[0]:5s} {[round(v,2) for v in c[2]]}  x  {c[1]:5s} {[round(v,2) for v in c[3]]}")

    lines = []
    lines.append("(kicad_pcb")
    lines.append("\t(version 20241229)")
    lines.append('\t(generator "pcbnew")')
    lines.append('\t(generator_version "9.0")')
    lines.append("\t(general")
    lines.append("\t\t(thickness 1.2)")
    lines.append("\t\t(legacy_teardrops no)")
    lines.append("\t)")
    lines.append('\t(paper "A4")')
    lines.append("\t(title_block")
    lines.append('\t\t(title "ESP32-S3 GDEM102T91 Mainboard")')
    lines.append('\t\t(date "2026-09-10")')
    lines.append('\t\t(rev "V1.1")')
    lines.append('\t\t(company "EPDF Hardware")')
    lines.append("\t)")
    lines.append("\t(layers")
    for ent in LAYERS:
        if len(ent) == 3:
            lines.append(f'\t\t({ent[0]} "{ent[1]}" {ent[2]})')
        else:
            lines.append(f'\t\t({ent[0]} "{ent[1]}" {ent[2]} "{ent[3]}")')
    lines.append("\t)")
    lines.append("\t(setup")
    lines.append(gen_stackup())
    lines.append("\t\t(pad_to_mask_clearance 0)")
    lines.append("\t\t(solder_mask_min_width 0.05)")
    lines.append("\t\t(pad_to_paste_clearance 0)")
    lines.append("\t\t(allow_soldermask_bridges_in_footprints no)")
    lines.append("\t)")
    lines.append('\t(net 0 "")')
    for name, nid in sorted(net_ids.items(), key=lambda kv: kv[1]):
        lines.append(f'\t(net {nid} "{name}")')

    lines.append(gen_mount_holes())

    # footprints
    for ref in sorted(place, key=lambda s: (s[0], int(re.sub(r"\D", "", s) or 0))):
        lib_id = comps[ref]
        x, y, rot = place[ref]
        lib, name = lib_id.split(":", 1)
        text = KF.read_mod(lib, name)
        nets = {}
        for (r, pad), netname in padnets.items():
            if r == ref:
                nets[pad] = (net_ids[netname], netname)
        lines.append(KF.place(text, lib_id, ref, name, x, y, rot, nets))

    lines.append(gen_outline())

    # copper pours (outline only - fill in KiCad with "B"/Edit > Fill All Zones)
    lines.append(zone_gnd("In1.Cu", "GND_PLANE_L2"))
    lines.append(zone_gnd("F.Cu", "GND_POUR_L1"))
    lines.append(zone_gnd("B.Cu", "GND_POUR_L4"))
    # ESP32-S3 PCB antenna keepout: no copper of any kind over the antenna area
    lines.append(zone_keepout(["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"],
                              "ANTENNA_KEEPOUT", 17.0, 0.0, 38.0, 6.0))

    lines.append(")")
    OUT_PCB.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT_PCB)


if __name__ == "__main__":
    main()
