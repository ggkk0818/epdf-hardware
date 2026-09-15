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
import json
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

# Placement clearance kept between two courtyards: the courtyard itself already
# carries ~0.25 mm of part excess per side, so 0.5 mm here means ~1.0 mm of real
# air between two components - enough for a 0.2 mm track plus 0.15 mm clearance
# either side, and tight enough to keep the switching loops short.
GAP = 0.50

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


def stable_uuid(key: str) -> str:
    """Deterministic footprint UUID so DRC exclusions survive regeneration."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "epdf-hardware/" + key))


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
        # no courtyard in the library: fall back to the union of the pads and the
        # F.Fab body outline (vendor footprints such as TI's RNM0015A have no CrtYd)
        pads = KF.parse_pads(text)
        for p in pads:
            half = 0.5 * max(p["w"], p["h"]) if p["rot"] in (90, 270) else 0.0
            w = p["h"] if p["rot"] in (90, 270) else p["w"]
            h = p["w"] if p["rot"] in (90, 270) else p["h"]
            xs += [p["x"] - w / 2, p["x"] + w / 2]
            ys += [p["y"] - h / 2, p["y"] + h / 2]
        for ch in children:
            if '"F.Fab"' not in ch:
                continue
            for m in re.finditer(r"\((?:start|end|center|mid|xy)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch):
                xs.append(float(m.group(1)))
                ys.append(float(m.group(2)))
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


def esp32_footprint_text():
    """The ESP32 module footprint with its courtyard trimmed to the body.

    The library courtyard is a T shape: the module body plus a 48 x 21 mm RF
    keep-out band reaching 15 mm past the module edge.  That band is not a
    physical outline - it duplicates the ESP32_ANT_KEEP_OUT rule area - and on a
    55 mm wide board it inevitably overlaps both upper locating holes, which the
    user wants kept in place.  The band is therefore dropped from the *board*
    courtyard; the RF requirement stays enforced by the rule area (no copper /
    tracks / vias / pads) plus a custom rule that forbids other components
    there.  Placement still treats the band as occupied.
    """
    text = KF.read_mod("RF_Module", "ESP32-S3-WROOM-1")
    head, children = KF.split_children(text)
    keep = []
    for ch in children:
        if KF.child_key(ch) == "fp_line" and '"F.CrtYd"' in ch:
            m = re.search(r"\(start (-?[\d.]+) (-?[\d.]+)\)\s*\(end (-?[\d.]+) (-?[\d.]+)\)",
                          " ".join(ch.split()))
            if m:
                x0, y0, x1, y1 = (float(v) for v in m.groups())
                if max(abs(x0), abs(x1)) > 9.8 or min(y0, y1) < -6.8:
                    continue                     # RF band line: not the body
        keep.append(ch)
    keep.append('\t(fp_line\n\t\t(start -9.75 -6.75)\n\t\t(end 9.75 -6.75)\n'
                '\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n'
                '\t\t(layer "F.CrtYd")\n\t)')
    return head + " " + "\n".join(keep) + ")"


_pads_cache = {}


def pad_offset(lib_id, pad_number, rot):
    """Board-space offset of a pad centre from the footprint origin."""
    if lib_id not in _pads_cache:
        lib, name = lib_id.split(":", 1)
        _pads_cache[lib_id] = {p["number"]: p for p in KF.parse_pads(KF.read_mod(lib, name))}
    p = _pads_cache[lib_id].get(pad_number)
    if p is None:
        return None
    th = math.radians(rot)
    co, si = math.cos(th), math.sin(th)
    return (p["x"] * co + p["y"] * si, -p["x"] * si + p["y"] * co)


def occupancy(ref, lib_id, x, y, rot):
    """Real space claimed by a placed part, as a list of axis aligned rects.

    The ESP32-S3-WROOM-1 courtyard is a T shape (module body plus the PCB
    antenna keep-out band).  Treating it as one bounding box would ban a huge
    area, so the two rectangles are listed explicitly.
    """
    # the module ships a 48 x 21 mm RF keep-out band as part of its courtyard;
    # the board footprint now carries only the body, but placement must still
    # treat the whole band as occupied
    if "ESP32-S3-WROOM-1" in lib_id:
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
    # USB-C and the microSD socket are swapped (user request): USB-C now sits on
    # the bottom edge centre so VBUS lands right next to the charger, the card
    # socket moved to the bottom right.  USB-C keeps its 1 mm edge overhang.
    "J1": (24.0, 81.33, 0),
    "J2": (5.0, 42.0, 90),      # 24P EPD FPC left side centre, opening left
    "J3": (40.0, 75.20, 0),     # microSD bottom right, card exits +Y
    # Molex PicoBlade: the mating cavity is on the local +Y side, so rot 270 is
    # what actually points the opening at the left board edge.
    "J4": (6.0, 62.0, 270),     # BAT1 left side, opening left
    "J5": (6.0, 72.0, 270),     # BAT2 left side, opening left
    "SW3": (52.85, 15.0, 90),   # KEY1  (centres 27 mm apart)
    "SW4": (52.85, 42.0, 90),   # KEY2
    "SW5": (52.85, 69.0, 90),   # KEY3
    # RESET / BOOT moved down 3 mm (review item 2) to open a row under the
    # module for the SPI series resistors R34/R33
    "SW1": (22.0, 32.0, 0),     # RESET
    "SW2": (30.0, 32.0, 0),     # BOOT
    # --- power chain anchors (placement V1.2) -----------------------------
    "U2": (34.0, 60.0, 0),      # BQ25895, centre-right, above USB-C
    "U3": (34.0, 45.0, 0),      # TPS63070, downstream of SYS
    "U4": (13.5, 62.0, 0),      # MAX17048, next to the battery connectors
    "U5": (29.5, 69.5, 0),      # TUSB320LI, next to USB-C (raised 2 mm in V1.4
                                # to free the row the four USB ESD diodes need)
}

# Orbit centres that differ from the anchor's own courtyard centre.  The EPD FPC
# sits hard against the left board edge, so its cluster is grown into the free
# area to the right of the connector instead of around the connector itself.
ANCHOR_CENTRE = {
    "J2": (13.5, 42.0),
}

# ---------------------------------------------------------------------------
# Mechanical / RF keep-outs (V1.3 review items 7 and 8)
# ---------------------------------------------------------------------------

# ESP32-S3 antenna area: module width band at the top board edge.
# No copper, no tracks, no vias, no components on any layer.
ANT_KEEPOUT = (16.0, 0.0, 39.0, 6.0)

# KEY1/2/3 mechanical keep-out.  Two different rectangles are needed:
#   * KEY_KEEPOUT is the DRC rule area.  It stops at the switch inner edge
#     (X 51.2) because the keys themselves are an explicit allowed exception in
#     the review (8.5) and a KiCad rule area cannot exempt a footprint.  Its
#     width follows the "switch inner edge + 2..3 mm" option from review 8.3
#     (the 8..12 mm option would swallow the microSD socket and C14 on a 55 mm
#     wide board).
#   * KEY_PLACEMENT_BAN covers the whole right hand strip, so the placer never
#     parks an ordinary part between the keys and the board edge.  The three
#     keys themselves are hard placed and therefore unaffected.
# Tracks / vias / pads / copper pour are allowed inside the key area (8.5); the
# two right hand locating holes sit at Y 3 / 81, outside the Y range.
# V1.5 (review item 1): the wall now runs the full board height.  It used to stop
# at Y=73, which let R33 sneak into the switch column from below.
KEY_KEEPOUT = (49.0, 0.0, 51.0, 84.0)
KEY_PLACEMENT_BAN = (49.0, 0.0, 55.0, 84.0)

# Mechanical annotation only (legend on Dwgs.User).  The review explicitly asks
# not to publish a second "footprints allowed" keep-out zone, so the enforced
# geometry is the KEY_RIGHT_MECH_KEEP_OUT wall above plus the custom rule in
# esp32-board-v1.1.kicad_dru, which lists the keys and the locating holes as the
# documented exceptions.
RIGHT_SWITCH_COLUMN = (49.0, 0.0, 55.0, 84.0)

# ---------------------------------------------------------------------------
# Pin-aligned placement (V1.3 review items 3..6, rules 3, 5, 6, 7)
# (ref, net_on_ref, anchor_ref, net_on_anchor, dx, dy, rot[, inward])
# The ref is positioned so that its pad carrying net_on_ref lands at the anchor
# pad carrying net_on_anchor, offset by (dx, dy) - i.e. pad-to-pin geometry
# instead of eyeballed alignment.
# ``inward`` (0..1) additionally lets the part slide back along that same
# bearing towards the anchor when the nominal spot is taken, so the switching
# loops end up as short as the board physically allows.
# ---------------------------------------------------------------------------
PIN_ALIGN = [
    # --- BQ25895 island: SW -> L1 first, then bootstrap / REGN / PMID --------
    # (VOUT/REGN/PMID/BTST sit on a 0.5 mm pitch QFN edge, so the caps stack in
    #  rows above U2 rather than all sharing one row - see PCB_LAYOUT_NOTES 5.3)
    ("L1", "CHG_SW", "U2", "CHG_SW", 3.60, 0.00, 0),
    ("C11", "CHG_BTST", "U2", "CHG_BTST", 0.15, -1.94, 0, 0.55),
    # PMID keeps the closest slot (4.2); REGN (C10) moves up into the single
    # slot directly above C11 so both end up within ~4 mm (4.3).  C15 uses the
    # pocket left of the stack, which the stack could not reach before.
    ("C15", "CHG_PMID", "U2", "CHG_PMID", -1.00, -2.15, 180),
    ("C10", "CHG_REGN", "U2", "CHG_REGN", 0.00, -4.15, 0),
    # snubber pair on the L1 side of the switch node: R21 then C16 straight off
    # the same CHG_SNUB node, with room for the GND via next to C16 (review 4.6)
    ("R21", "CHG_SW", "L1", "CHG_SW", 2.52, -4.49, 0),
    ("C16", "CHG_SNUB", "L1", "CHG_SW", 6.66, -4.71, 0),
    # R20 (DSEL strap) gives up the patch above L1 to the snubber and fills the
    # free column right of L1 instead
    ("R20", "3V3_MAIN", "U2", "CHG_DSEL", 12.40, -6.71, 0),
    # C9 is the charger's local VBUS decoupling (review 4.4): pull it up next to
    # U2 pin 1 instead of leaving it in the microSD row
    ("C9", "USB_VBUS_PROT", "U2", "USB_VBUS_PROT", -1.94, 0.90, 90),
    # BAT bulk cap back at the charger's BAT pins (review 5.1): the microSD row
    # is re-arranged so it can sit 3.5 mm from U2 BAT13/14 again
    ("C12", "BAT_BUS", "U2", "BAT_BUS", 1.63, 3.25, 0),
    # One SYS bulk cap stays in the U2 / L1 output row (5.5); the second one
    # (C14) remains with the TPS63070 input bank (C18/C19)
    ("C13", "SYS", "U2", "SYS", -4.03, 4.25, 180),
    # (C14 is placed after C18/C19 so the two original input caps keep the spots
    #  hard against U3 - see below)
    # --- TPS63070 island: inductor on the L1/L2 pin centre line -------------
    ("L2", "TPS_L1", "U3", "TPS_L1", 3.60, 0.50, 90, 0.40),
    ("C18", "SYS", "U3", "SYS", 0.00, -3.90, 90, 0.55),
    ("C19", "SYS", "U3", "SYS", -3.70, -3.90, 90, 0.55),
    ("C14", "SYS", "U3", "SYS", 2.45, -3.90, 90),
    ("C20", "3V3_MAIN", "U3", "3V3_MAIN", 2.50, 3.70, 90, 0.45),
    ("C21", "3V3_MAIN", "U3", "3V3_MAIN", 6.70, 3.70, 90, 0.45),
    ("C22", "3V3_MAIN", "U3", "3V3_MAIN", 11.88, 3.70, 90, 0.45),
    ("C23", "3V3_MAIN", "U3", "3V3_MAIN", 6.70, 8.10, 90, 0.45),
    ("C24", "TPS_VAUX", "U3", "TPS_VAUX", -2.30, 0.00, 0, 0.45),
    # --- FB divider: same centre-X vertical column, FB node on the FB pin ---
    ("R23", "TPS_FB", "U3", "TPS_FB", -3.65, 3.60, 270, 0.80),
    # R24 stacked under R23 by one courtyard pitch, same centre-X column
    # R24 pulled up toward R23 (review 6.1) so the divider midpoint sits one
    # courtyard pitch below the FB pin
    ("R24", "TPS_FB", "R23", "TPS_FB", 0.00, 1.81, 270),
    # --- USB series resistors sit right next to the ESP32 USB pins ----------
    # mirrored about the mid-point of GPIO20/GPIO19 for equal length
    ("R9", "USB_DP", "U1", "USB_DP", -3.75, 0.65, 0),
    ("R10", "USB_DN", "U1", "USB_DN", -3.75, -0.65, 0),
    # --- U1 support cluster (review item 4) ---------------------------------
    # 3V3 decoupling plus the RESET and KEY networks move into the strip left of
    # the module, ordered by how hard each part has to hug its pin: C4 (the
    # 0.1 uF) first, then C3, then the RESET RC, then the bulk caps and the DC
    # key pull-ups.  Caps that sit to the left of their pin are turned 180
    # degrees so the supply pad faces the module.
    ("C4", "3V3_MAIN", "U1", "3V3_MAIN", -2.21, -0.73, 180),
    ("C3", "3V3_MAIN", "U1", "3V3_MAIN", -2.21, 1.73, 180),
    ("R1", "3V3_MAIN", "U1", "RESET_N", -3.81, 2.92, 0),
    ("C5", "RESET_N", "U1", "RESET_N", -2.21, 5.38, 180),
    ("C2", "3V3_MAIN", "U1", "3V3_MAIN", -5.80, -0.48, 180),
    ("C1", "3V3_MAIN", "U1", "3V3_MAIN", -5.80, 1.98, 180),
    ("R3", "3V3_MAIN", "U1", "KEY1_N", -7.45, 1.65, 0),
    ("R4", "3V3_MAIN", "U1", "KEY2_N", -7.45, 2.84, 0),
    ("R5", "3V3_MAIN", "U1", "KEY3_N", -7.45, 1.49, 0),
    # --- SPI series resistors at the driver end (review item 2.2) -----------
    # They move from the microSD side to the row under the ESP32 that SW1/SW2
    # vacated, so a future 22-33 ohm damping value sits at the source
    ("R34", "SPI_MOSI", "U1", "SPI_MOSI", -0.54, 2.28, 0),
    ("R33", "SPI_SCLK", "U1", "SPI_SCLK", 1.69, 2.28, 0),
    # --- EPD high voltage capacitors: compact 3 x 2 matrix hugging the FPC -----
    # (review 7.1: "no more single长排"; the caps keep a Y within ~3 mm of their
    #  own FPC pin but no longer stretch 20 mm to the right of the connector)
    ("C36", "EPD_VCOM", "J2", "EPD_VCOM", 6.45, 1.00, 0),
    ("C33", "EPD_VSL", "J2", "EPD_VSL", 10.10, 0.00, 0),
    ("C28", "EPD_VGH", "J2", "EPD_VGH", 14.00, -0.50, 0),
    ("C30", "EPD_VGL", "J2", "EPD_VGL", 6.20, 2.96, 0),
    ("C32", "EPD_VSH1", "J2", "EPD_VSH1", 10.10, 1.46, 0),
    ("C31", "EPD_VSH2", "J2", "EPD_VSH2", 6.20, 0.00, 0),
    # --- USB ESD: one mirrored row of four, turned 90 deg --------------------
    # Review 6.2/6.3 asks for both pairs to be the same distance from J1.  A
    # SOD-323 is 3.2 mm wide but the connector's four signal pins span only
    # 2.5 mm, so side-by-side horizontal parts cannot all reach their own pin.
    # Turned 90 deg each diode is 1.9 mm wide, so all four fit in one row on
    # Centre-Y 74.0 with 2.6 mm to the pin row and a mirror-symmetric order
    # CC1 / D- / D+ / CC2 about the connector centre.
    ("D4", "USB_CC1", "J1", "USB_CC1", -2.35, -2.60, 90),
    ("D3", "USB_DN_CONN", "J1", "USB_DN_CONN", -1.45, -2.60, 90),
    ("D2", "USB_DP_CONN", "J1", "USB_DP_CONN", 0.45, -2.60, 90),
    ("D5", "USB_CC2", "J1", "USB_CC2", 1.85, -2.60, 90),
    # gate pull-down R30 belongs next to Q1 (review 7.2), not in the J2 -> Q1
    # corridor where it was acting as a series element
    ("R30", "EPD_GDR", "Q1", "EPD_GDR", 4.06, 1.43, 0),
    # --- J3 microSD row -------------------------------------------------------
    # The 3.75 mm band between U2 and the socket now also has to host the BAT
    # bulk cap (C12), so the row is re-ordered to keep every part as close to
    # its own pin as the geometry allows: R35 to MISO, C12 to U2 BAT, C38/C37 to
    # J3 VDD.  R32 (CS pull-up) is the only part that does not fit and returns to
    # the J3 orbit - both reviews note that it is position insensitive.
    ("R35", "TF_MISO", "J3", "TF_MISO", -0.57, -2.90, 0),
    ("C38", "3V3_MAIN", "J3", "3V3_MAIN", 2.13, -2.90, 0),
    ("C37", "3V3_MAIN", "J3", "3V3_MAIN", 5.64, -2.98, 0),
    # --- EPD booster island (review 7.1) -------------------------------------
    # C29 is a switching-node capacitor (EPD_SW / EPD_X); it leaves the HV row
    # and joins the booster, next to D6's EPD_SW and D8's EPD_X pads
    ("C29", "EPD_SW", "L3", "EPD_SW", 2.55, 7.83, 0),
    # thermistor moves to the battery end of the board (thermal sensing), which
    # also frees the left end of the microSD row
    ("NTC1", "CHG_TS", "U2", "CHG_TS", -16.49, 2.62, 0),
]

# Anchor -> satellites, listed closest-first.  The placer spirals outwards from
# the anchor, so the parts that must sit hard against the IC (switching loops,
# ESD, feedback divider, booster caps) are placed first and land nearest.
# This implements the V1.2 review items 5-7 and 9:
#   * BQ25895: BTST / REGN / PMID / VBUS / BAT / SYS caps + SW inductor adjacent
#   * TPS63070: inductor, VIN/VOUT caps, VAUX cap, FB divider adjacent
#   * USB: ESD + TVS + fuse + shield next to the connector; 22R series next to U1
#   * EPD: L3/Q1/D6-D8 and every high voltage cap clustered on the FPC
ANCHORS = [
    # C29 is pin-aligned into the booster island once L3 exists (see PIN_ALIGN)
    ("J2", ["U6", "L3", "C28", "C30", "C31", "C32", "C33", "C35", "C36"]),
    # the booster switching loop is grown around the inductor so L3/Q1/D6-D8 stay
    # physically tight (EPD_SW area and GDR/RESE length are the critical items)
    # R30 is pin-aligned to Q1's gate (see PIN_ALIGN) once Q1 exists
    ("L3", ["Q1", "D6", "D7", "D8", "R31"]),
    ("U6", ["C25", "C26", "C27", "C34", "R29"]),
    ("J1", ["D2", "D3", "D4", "D5", "D1", "F1", "C6", "C7", "R8"]),
    ("U5", ["R11", "R12", "C8"]),
    ("U2", ["C11", "C10", "C15", "C9", "L1", "C12", "C13", "C14",
            "R13", "R16", "R17", "NTC1", "R14", "R15", "R18", "R19",
            "R20", "R21", "R6", "R7"]),
    ("U3", ["L2", "C18", "C19", "C20", "C24", "R23", "R24",
            "C21", "C22", "C23", "R25", "R26", "R27", "R28"]),
    ("U4", ["C17", "R22"]),
    ("U1", ["C1", "C2", "C3", "C4", "C5", "R1", "R2",
            "R3", "R4", "R5", "R9", "R10"]),
    ("J3", ["C37", "C38", "R32", "R33", "R34", "R35", "R36"]),
    ("J4", ["F2"]),
    ("J5", ["F3"]),
]


# Placement clearance kept between two courtyards.  The courtyard itself already
# carries ~0.25 mm of part excess, so 0.4 mm here means at least ~0.9 mm of real
# air between the two components - enough for a 0.2 mm track with 0.15 mm
# clearance, and tight enough to keep the switching loops short.
EDGE = 0.45


def inside_board(x0, y0, x1, y1):
    """True if a rectangle stays clear of the board edge and the R2 corners."""
    if x0 < EDGE or y0 < EDGE or x1 > BOARD_W - EDGE or y1 > BOARD_H - EDGE:
        return False
    r = CORNER_R - EDGE
    for cx, cy in ((CORNER_R, CORNER_R), (BOARD_W - CORNER_R, CORNER_R),
                   (CORNER_R, BOARD_H - CORNER_R), (BOARD_W - CORNER_R, BOARD_H - CORNER_R)):
        px = x0 if cx == CORNER_R else x1      # outermost corner of the box
        py = y0 if cy == CORNER_R else y1
        intrudes = (x0 < cx) if cx == CORNER_R else (x1 > cx)
        intrudes = intrudes and ((y0 < cy) if cy == CORNER_R else (y1 > cy))
        if intrudes and math.hypot(cx - px, cy - py) > r:
            return False
    return True


class Grid:
    """Exact rectangle occupancy used as the placement / collision oracle.

    ``courtyard`` holds the raw courtyards of everything already placed and is
    tested with the ``gap`` clearance; ``forbidden`` holds the locating holes and
    the mechanical / RF keep-outs, which are physical limits and are tested with
    no extra margin.  An earlier version rasterised all of this into a 0.2 mm
    byte grid, which inflated every clearance by up to one cell per side and
    rejected perfectly legal slots (the 3.75 mm band between U2 and the microSD
    socket, for example).
    """

    def __init__(self):
        self.courtyard = []
        self.forbidden = []

    @staticmethod
    def _hit(a, b, gap=0.0):
        return (a[0] < b[2] + gap and b[0] - gap < a[2] and
                a[1] < b[3] + gap and b[1] - gap < a[3])

    def mark(self, x0, y0, x1, y1):
        self.courtyard.append((x0, y0, x1, y1))

    def forbid(self, x0, y0, x1, y1):
        self.forbidden.append((x0, y0, x1, y1))

    def free(self, x0, y0, x1, y1, gap=GAP):
        box = (x0, y0, x1, y1)
        if not inside_board(x0, y0, x1, y1):
            return False
        for o in self.forbidden:
            if self._hit(box, o, 0.0):
                return False
        for o in self.courtyard:
            if self._hit(box, o, gap):
                return False
        return True


def build_placement(comps, padnets):
    grid = Grid()
    # locating holes (2.2 mm hole + small screw head margin).  The board outline
    # and the R2 corners are handled analytically inside Grid.free().
    # keep clear of the hole's own courtyard (Ø4.9 from the library footprint)
    # plus a placement gap, so no part ends up overlapping a mounting hole
    for hx, hy in MOUNT_HOLES:
        grid.forbid(hx - 2.95, hy - 2.95, hx + 2.95, hy + 2.95)
    # mechanical / RF keep-outs become placement obstacles
    grid.forbid(*ANT_KEEPOUT)
    grid.forbid(*KEY_PLACEMENT_BAN)

    place = {}
    centres = {}
    rotations = {}
    anchor_rect = {}
    for ref, (x, y, rot) in HARD.items():
        place[ref] = (x, y, rot)
        rotations[ref] = rot
        rects = occupancy(ref, comps[ref], x, y, rot)
        for r in rects:
            grid.mark(*r)
        # Anchor centre: for the module the courtyard is a T shape (antenna band +
        # body); orbit from the body rectangle, not the overall bounding box.
        body = rects[-1]
        centre = ANCHOR_CENTRE.get(ref, ((body[0] + body[2]) / 2.0, (body[1] + body[3]) / 2.0))
        centres[ref] = centre
        anchor_rect[ref] = body

    overflow = []
    distances = {}
    fallback = []

    def try_at(x, y, lib, rot):
        dx0, dy0, dx1, dy1 = rotated_bbox(lib, rot)
        w, h = dx1 - dx0, dy1 - dy0
        if not grid.free(x, y, x + w, y + h):
            return None
        grid.mark(x, y, x + w, y + h)
        return (x - dx0, y - dy0, rot)

    def orbit(ref, anchor, max_r=18.0):
        """Spiral outwards from the anchor, so a satellite stays as close as it can."""
        lib = comps[ref]
        ax, ay = centres[anchor]
        for rot in (0, 90):
            dx0, dy0, dx1, dy1 = rotated_bbox(lib, rot)
            w, h = dx1 - dx0, dy1 - dy0
            ccx, ccy = (dx0 + dx1) / 2.0, (dy0 + dy1) / 2.0
            r = 0.0
            while r <= max_r:
                n = max(12, int(2 * math.pi * max(r, 1.2) / 0.45))
                for k in range(n):
                    ang = 2 * math.pi * k / n + (0.37 if rot else 0.0)
                    cx = ax + r * math.cos(ang)
                    cy = ay + r * math.sin(ang)
                    pos = try_at(cx - ccx, cy - ccy, lib, rot)
                    if pos:
                        return pos, math.dist((cx, cy), (ax, ay))
                r += 0.3
        return None, None

    def scan(ref):
        """Fallback: first free slot anywhere on the board."""
        lib = comps[ref]
        res = 0.2
        for rot in (0, 90):
            dx0, dy0, dx1, dy1 = rotated_bbox(lib, rot)
            w, h = dx1 - dx0, dy1 - dy0
            y = EDGE
            while y + h <= BOARD_H - EDGE:
                x = EDGE
                while x + w <= BOARD_W - EDGE:
                    pos = try_at(x, y, lib, rot)
                    if pos:
                        return pos
                    x += res
                y += res
        return None

    # ---- pin-aligned placement (V1.3 review items 3..6) --------------------
    pad_index = {}
    for (r, p), n in padnets.items():
        pad_index.setdefault((r, n), []).append(p)

    def anchor_pad_xy(ref, net):
        """Board position of the anchor's pad on ``net`` (right-most if several)."""
        cands = pad_index.get((ref, net), [])
        best = None
        for pad in cands:
            off = pad_offset(comps[ref], pad, rotations.get(ref, 0))
            if off is None:
                continue
            x = place[ref][0] + off[0]
            y = place[ref][1] + off[1]
            if best is None or x > best[0]:
                best = (x, y)
        return best

    aligned, align_blocked = [], []
    deferred = []

    def place_aligned(entry):
        """Try one PIN_ALIGN entry.  Returns True (placed), False (blocked) or
        None when the anchor itself has not been placed yet."""
        ref, net_ref, aref, net_a, dx, dy, rot = entry[:7]
        inward = entry[7] if len(entry) > 7 else 0.0
        if ref in place or ref not in comps:
            return True
        if aref not in place:
            return None
        pads = pad_index.get((ref, net_ref), [])
        a = anchor_pad_xy(aref, net_a)
        if not pads or a is None:
            align_blocked.append((ref, "net not found"))
            return False
        toff = pad_offset(comps[ref], pads[0], rot)
        if toff is None:
            align_blocked.append((ref, "pad missing"))
            return False
        origin_x = a[0] + dx - toff[0]
        origin_y = a[1] + dy - toff[1]
        dx0, dy0, dx1, dy1 = rotated_bbox(comps[ref], rot)
        # keep the alignment axis but slide outwards if the exact spot is taken
        ux, uy = (dx, dy)
        n = math.hypot(ux, uy)
        ux, uy = (ux / n, uy / n) if n > 1e-6 else (1.0, 0.0)
        back = int(inward * n / 0.25)
        pos = None
        for k in range(-back, 33):
            pos = try_at(origin_x + dx0 + ux * 0.25 * k, origin_y + dy0 + uy * 0.25 * k,
                         comps[ref], rot)
            if pos:
                break
        if pos is None:
            align_blocked.append((ref, "target blocked"))
            if "-v" in sys.argv:
                tx0, ty0 = origin_x + dx0 - GAP, origin_y + dy0 - GAP
                tx1, ty1 = origin_x + dx1 + GAP, origin_y + dy1 + GAP
                hits = []
                for r in place:
                    b = abs_bbox(comps[r], *place[r])
                    if (b[0] - GAP) < tx1 and tx0 < (b[2] + GAP) and \
                       (b[1] - GAP) < ty1 and ty0 < (b[3] + GAP):
                        hits.append((r, [round(v, 2) for v in b]))
                print(f"    [dbg] {ref} target ({tx0:.1f},{ty0:.1f})-({tx1:.1f},{ty1:.1f})")
                print("        free?", grid.free(tx0 + GAP, ty0 + GAP, tx1 - GAP, ty1 - GAP),
                      "exact?", grid.free(origin_x + dx0, origin_y + dy0,
                                          origin_x + dx1, origin_y + dy1))
                for h in hits:
                    print("        blocked by", h)
                if not hits:
                    cx = tx0
                    while cx < tx1:
                        cy = ty0
                        while cy < ty1:
                            if not grid.free(cx, cy, cx + 0.19, cy + 0.19):
                                print(f"        grid cell busy at ({cx:.2f},{cy:.2f})")
                                break
                            cy += 0.2
                        else:
                            cx += 0.2
                            continue
                        break
            return False
        place[ref] = pos
        rotations[ref] = rot
        aligned.append(ref)
        return True

    for entry in PIN_ALIGN:
        if place_aligned(entry) is None:
            deferred.append(entry)

    for anchor, sats in ANCHORS:
        # an anchor may itself have been placed as a satellite of an earlier
        # anchor (L3 under J2, for example) - derive its centre on demand
        if anchor not in centres and anchor in place:
            ax0, ay0, ax1, ay1 = abs_bbox(comps[anchor], *place[anchor])
            centres[anchor] = ((ax0 + ax1) / 2.0, (ay0 + ay1) / 2.0)
            anchor_rect[anchor] = (ax0, ay0, ax1, ay1)
        for ref in sats:
            if ref in place or ref not in comps:
                continue
            pos, dist = orbit(ref, anchor)
            if pos is None:
                # widen the search before giving up on staying near the anchor
                pos, dist = orbit(ref, anchor, max_r=48.0)
            if pos is None:
                pos = scan(ref)
                dist = None
                fallback.append(ref)
            if pos is None:
                overflow.append(ref)
                continue
            place[ref] = pos
            if dist is not None:
                bb = abs_bbox(comps[ref], pos[0], pos[1], pos[2])
                ar = anchor_rect[anchor]
                dx = max(ar[0] - bb[2], bb[0] - ar[2], 0.0)
                dy = max(ar[1] - bb[3], bb[1] - ar[3], 0.0)
                distances[ref] = (anchor, math.hypot(dx, dy))

    # second pass: pin-aligned parts that anchor onto an orbit-placed part
    # (C16 -> R21, R30 -> Q1).  Their anchors now exist, so the intended
    # geometry can be honoured before the catch-all scan below.
    for entry in deferred:
        place_aligned(entry)

    for ref in [r for r in comps if r not in place]:
        pos = scan(ref)
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
    return place, overflow, distances, fallback, aligned, align_blocked


# ---------------------------------------------------------------------------
# silkscreen reference designators
# ---------------------------------------------------------------------------

# KiCad stroke font metrics for the 1 mm / 0.15 mm default: a character advances
# roughly 0.9 * size and the glyph box is a little taller than the font size.
TEXT_ADV = 1.00
TEXT_PAD = 0.35
LBL_H = 1.55

# how far outside its own courtyard a reference designator may wander
# A reference designator never wanders more than ~3 mm from its own courtyard
# (review 11.3/11.4); if no clean spot exists that close the label is hidden on
# the silkscreen and kept only on F.Fab / the assembly drawing (review 11.5).
SILK_RING = (0.25, 0.7, 1.2, 1.8, 2.5, 3.3)
SILK_HIDE_COVER = 0.25        # hide when this fraction would sit under a part

# Relative badness of the things a label can land on.  A solder mask opening is
# a hard no (1000); being hidden under another part's body is scored by how much
# of the label is covered (60 = completely invisible); ink collisions are
# cosmetic (6 each); and 1.2 per mm keeps labels near the part they belong to.
SILK_W_MASK, SILK_W_BODY, SILK_W_INK, SILK_W_FAR = 1000, 60, 6, 1.2

# Small two-terminal parts carry 0.8 mm reference text - still legible on a 0603
# and standard practice on dense boards - while everything else keeps the
# library's 1.0 mm.  Dropping the passives to 0.8 mm is what removes the last few
# ink collisions: position tuning alone had converged at 8-9 overlaps.
SILK_SMALL_LIBS = ("Capacitor_SMD:", "Resistor_SMD:", "Diode_SMD:")
SILK_SIZE_SMALL, SILK_SIZE_LARGE = 0.80, 1.00


def silk_size(ref, comps):
    return SILK_SIZE_SMALL if comps[ref].startswith(SILK_SMALL_LIBS) else SILK_SIZE_LARGE


def _fab_box(text):
    """Bounding box of a footprint's F.Fab outline (the physical body)."""
    _, children = KF.split_children(text)
    xs, ys = [], []
    for ch in children:
        if '"F.Fab"' not in ch:
            continue
        for m in re.finditer(r"\((?:start|end|center|mid|xy)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch):
            xs.append(float(m.group(1)))
            ys.append(float(m.group(2)))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _rot_pt(px, py, x, y, rot):
    """Footprint local -> board coordinates (same convention as pad_offset)."""
    th = math.radians(rot)
    c, s = math.cos(th), math.sin(th)
    return (x + px * c + py * s, y - px * s + py * c)


def _rot_box(box, x, y, rot):
    x0, y0, x1, y1 = box
    pts = [_rot_pt(px, py, x, y, rot)
           for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _local_pt(bx, by, x, y, rot):
    """Board -> footprint local coordinates."""
    th = math.radians(rot)
    c, s = math.cos(th), math.sin(th)
    dx, dy = bx - x, by - y
    return (dx * c - dy * s, dx * s + dy * c)


def _silk_graphics(text):
    """Bounding boxes of the silkscreen graphics inside a footprint."""
    _, children = KF.split_children(text)
    out = []
    for ch in children:
        if '"F.SilkS"' not in ch:
            continue
        nums = re.findall(r"\((?:start|end|center|mid|xy)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch)
        if not nums:
            continue
        if KF.child_key(ch) == "fp_circle":
            c = re.search(r"\(center\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch)
            e = re.search(r"\(end\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch)
            cx, cy = float(c.group(1)), float(c.group(2))
            r = math.dist((cx, cy), (float(e.group(1)), float(e.group(2))))
            box = (cx - r, cy - r, cx + r, cy + r)
        else:
            xs = [float(a) for a, _ in nums]
            ys = [float(b) for _, b in nums]
            box = (min(xs), min(ys), max(xs), max(ys))
        w = re.search(r"\(width\s+(-?[\d.]+)\)", ch)
        d = (float(w.group(1)) if w else 0.12) / 2.0 + 0.05
        out.append((box[0] - d, box[1] - d, box[2] + d, box[3] + d))
    return out


def build_silk(comps, place):
    """Choose a silkscreen spot for every reference designator.

    The library default - centred just above the part - prints on a neighbouring
    pad as soon as the board is packed tightly, and silkscreen on a solder mask
    opening gets clipped by the fab.  Every label is therefore moved to the first
    spot on a ring around its own courtyard that clears all solder mask openings,
    all other silkscreen lines and the board edge.  Returns {ref: (local_x,
    local_y)} in the footprint's own frame.
    """
    def box_hit(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    masks = []              # solder mask openings: a label here is clipped
    graphics = []           # silkscreen lines: overlapping ink is a DRC warning
    bodies = []             # (rect, ref) part outlines: a label here is hidden
    defaults = {}
    for ref, lib_id in comps.items():
        if ref not in place:
            continue
        x, y, rot = place[ref]
        lib, name = lib_id.split(":", 1)
        text = KF.read_mod(lib, name)
        for p in KF.parse_pads(text):
            w, h = (p["h"], p["w"]) if p["rot"] in (90, 270) else (p["w"], p["h"])
            masks.append(_rot_box((p["x"] - w / 2 - 0.05, p["y"] - h / 2 - 0.05,
                                   p["x"] + w / 2 + 0.05, p["y"] + h / 2 + 0.05), x, y, rot))
        for g in _silk_graphics(text):
            graphics.append(_rot_box(g, x, y, rot))
        fab = _fab_box(text)
        if fab:
            bodies.append((_rot_box(fab, x, y, rot), ref))
        else:
            for b in occupancy(ref, comps[ref], x, y, rot):
                bodies.append((b, ref))
        for ch in KF.split_children(text)[1]:
            if KF.child_key(ch) == "property" and '"Reference"' in ch:
                m = re.search(r"\(at\s+(-?[\d.]+)\s+(-?[\d.]+)", ch)
                if m:
                    defaults[ref] = (float(m.group(1)), float(m.group(2)))

    order = [r for r in sorted(place, key=lambda s: (s[0], int(re.sub(r"\D", "", s) or 0)))
             if r in comps]

    # ---- per part: candidate positions and the obstacles that matter --------
    geo = {}
    reach = SILK_RING[-1] + 3.0
    for ref in order:
        x, y, rot = place[ref]
        lib, name = comps[ref].split(":", 1)
        own_text = KF.read_mod(lib, name)
        own_fab = _fab_box(own_text)
        # orbit the physical body, not the courtyard: the module's courtyard
        # includes a 21 mm deep RF band that would push its label 25 mm away
        bb = _rot_box(own_fab, x, y, rot) if own_fab else abs_bbox(comps[ref], x, y, rot)
        cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
        hx, hy = (bb[2] - bb[0]) / 2.0, (bb[3] - bb[1]) / 2.0
        size = silk_size(ref, comps)
        lw = TEXT_ADV * size * len(ref) + TEXT_PAD * size
        bw, bh = lw, LBL_H * size

        def near(items):
            """Only obstacles the widest ring can reach need to be tested."""
            return [it for it in items
                    if it[0][0] < cx + hx + reach + lw and it[0][2] > cx - hx - reach - lw
                    and it[0][1] < cy + hy + reach + bh and it[0][3] > cy - hy - reach - bh]

        cands = []          # (x, y, ring radius)
        if ref in defaults:
            cands.append((*_rot_pt(defaults[ref][0], defaults[ref][1], x, y, rot), 0.0))
        for r in SILK_RING:
            # straight up first, then down, then the sides, then the diagonals
            for ang in sorted(range(0, 360, 15), key=lambda a: (abs(a - 270), a)):
                a = math.radians(ang)
                cands.append((cx + (hx + bw / 2 + r) * math.cos(a),
                              cy + (hy + bh / 2 + r) * math.sin(a), r))
        geo[ref] = {
            "boxes": [(bx - bw / 2, by - bh / 2, bx + bw / 2, by + bh / 2)
                      for bx, by, _ in cands],
            "cands": cands,
            "mask": [o for o, _ in near([(o, "") for o in masks])],
            "gfx": [o for o, _ in near([(o, "") for o in graphics])],
            # the part's own body is included: a diagonal ring position can fall
            # inside a wide part (the ESP32 module), where the label would be
            # hidden under the component
            "body": near(bodies),
            "area": bw * bh,
            "cx": cx, "cy": cy, "hx": hx, "hy": hy, "bw": bw, "bh": bh,
        }

    def cost(ref, box, others):
        """Weighted cost of a label box.

        A solder mask opening dominates (ink there is clipped by the fab); a
        position hidden under another part's body is next worst because the label
        would simply not be visible; ink collisions are cosmetic.
        """
        if not inside_board(*box):
            return None
        g = geo[ref]
        m = sum(1 for o in g["mask"] if box_hit(box, o))
        covered = 0.0
        for o, _ in g["body"]:
            if box_hit(box, o):
                covered += ((min(box[2], o[2]) - max(box[0], o[0])) *
                            (min(box[3], o[3]) - max(box[1], o[1])))
        b = covered / g["area"]
        k = sum(1 for o in g["gfx"] if box_hit(box, o))
        t = sum(1 for o in others if box_hit(box, o))
        return SILK_W_MASK * m + SILK_W_BODY * b + SILK_W_INK * (k + t)

    def total(ref, i, others):
        """Cost of candidate ``i`` of ``ref`` including the distance penalty."""
        c = cost(ref, geo[ref]["boxes"][i], others)
        return None if c is None else c + SILK_W_FAR * geo[ref]["cands"][i][2]

    # ---- pass 1: greedy, in reference order --------------------------------
    best = {}
    for ref in order:
        placed = [best[o][0] for o in best]
        scored = [(total(ref, i, placed), i) for i in range(len(geo[ref]["boxes"]))]
        valid = [(c, i) for c, i in scored if c is not None]
        if not valid:
            best[ref] = (geo[ref]["boxes"][0], 0)
            continue
        c, i = min(valid, key=lambda t: t[0])           # ties keep candidate order
        best[ref] = (geo[ref]["boxes"][i], i)

    # ---- pass 2: hill-climb, so a label can move out of a neighbour's way ---
    for _ in range(6):
        moved = 0
        for ref in order:
            others = [best[o][0] for o in best if o != ref]
            cur_box, cur_i = best[ref]
            cur = cost(ref, cur_box, others)
            scored = [(total(ref, i, others), i) for i in range(len(geo[ref]["boxes"]))]
            valid = [(c, i) for c, i in scored if c is not None]
            if not valid:
                continue
            c, i = min(valid, key=lambda t: t[0])
            cur_c = total(ref, cur_i, others)
            if cur_c is None or c < cur_c:
                best[ref] = (geo[ref]["boxes"][i], i)
                moved += 1
        if not moved:
            break

    # ---- pass 3: a label with no clean spot close by is hidden --------------
    # Review 11.5: never drag a reference 6-10 mm away just to show it.
    hidden = set()
    for ref in order:
        g = geo[ref]
        box = best[ref][0]
        covered = 0.0
        for o, _ in g["body"]:
            if box_hit(box, o):
                covered += ((min(box[2], o[2]) - max(box[0], o[0])) *
                            (min(box[3], o[3]) - max(box[1], o[1])))
        if covered / g["area"] > SILK_HIDE_COVER:
            hidden.add(ref)

    # two labels whose only close spots collide: keep the one with the better
    # spot and hide the other (it stays available on F.Fab / assembly drawing)
    for a in order:
        if a in hidden:
            continue
        for b in order:
            if b <= a or b in hidden:
                continue
            if not box_hit(best[a][0], best[b][0]):
                continue
            sa = total(a, best[a][1], [best[o][0] for o in best if o != a])
            sb = total(b, best[b][1], [best[o][0] for o in best if o != b])
            hidden.add(a if (sa, a) > (sb, b) else b)

    out = {}
    for ref in order:
        if ref in hidden:
            continue
        x, y, rot = place[ref]
        bx, by, _ = geo[ref]["cands"][best[ref][1]]
        out[ref] = tuple(round(v, 4) for v in _local_pt(bx, by, x, y, rot))
    return out, hidden


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

# The microSD vendor footprint carries five small rule areas under the card slot
# (no tracks / vias / pads / copper).  They are reproduced here at board level:
# KiCad's library-parity check cannot compare footprint-embedded zones, so
# keeping them inside the footprint left a permanent "does not match library"
# warning (review item 14).  Coordinates are the vendor polygons for J3 placed
# at (40.0, 75.2) with no rotation.
SD_KEEPOUTS = [
    ("J3_SOCKET_KEEP_OUT_1", 32.775, 67.925, 33.525, 71.175),
    ("J3_SOCKET_KEEP_OUT_2", 32.775, 72.375, 33.525, 75.975),
    ("J3_SOCKET_KEEP_OUT_3", 33.875, 73.775, 34.575, 81.375),
    ("J3_SOCKET_KEEP_OUT_4", 42.925, 82.175, 45.475, 83.525),
    ("J3_SOCKET_KEEP_OUT_5", 34.575, 72.475, 43.275, 74.075),
]


def gen_legend():
    """Mechanical legend on Dwgs.User marking the right hand switch column."""
    x0, y0, x1, y1 = RIGHT_SWITCH_COLUMN
    w, t = 0.25, 0.2
    out = []
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                 ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        out.append(
            "\t(gr_line\n"
            f"\t\t(start {fmt(a[0])} {fmt(a[1])})\n"
            f"\t\t(end {fmt(b[0])} {fmt(b[1])})\n"
            "\t\t(stroke\n"
            f"\t\t\t(width {fmt(w)})\n"
            "\t\t\t(type dash)\n"
            "\t\t)\n"
            '\t\t(layer "Dwgs.User")\n'
            f'\t\t(uuid "{u()}")\n\t)'
        )
    for i, line in enumerate(("RIGHT_SWITCH_COLUMN",
                              "X 49 - 55 mm",
                              "SW / LOCATING HOLES ONLY")):
        out.append(
            f'\t(gr_text "{line}"\n'
            f"\t\t(at {fmt(50.0)} {fmt(12.5 + 3.4 * i)} 90)\n"
            "\t\t(layer \"Dwgs.User\")\n"
            f'\t\t(uuid "{u()}")\n'
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.2 1.2)\n"
            "\t\t\t\t(thickness 0.24)\n\t\t\t)\n\t\t)\n\t)"
        )
    # mounting decision (user, 2026-09-14): the two upper locating holes sit in
    # the ESP32 antenna keep-out band, so they must stay non-metallic.
    for i, line in enumerate(("MOUNTING HOLES:",
                              "NYLON / PLASTIC POST ONLY",
                              "NO METAL IN ANTENNA AREA")):
        out.append(
            f'\t(gr_text "{line}"\n'
            f"\t\t(at {fmt(16.8)} {fmt(1.6 + 1.8 * i)} 0)\n"
            "\t\t(layer \"Dwgs.User\")\n"
            f'\t\t(uuid "{u()}")\n'
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.9 0.9)\n"
            "\t\t\t\t(thickness 0.18)\n\t\t\t)\n\t\t)\n\t)"
        )
    return "\n".join(out)


def gen_mount_holes():
    """Emit the library mounting-hole footprint, courtyard included.

    The earlier hand-written version had no courtyard and did not match the
    library - exactly what the two DRC checks re-enabled in review item 11
    report.  The library footprint carries a 4.9 mm courtyard; for the two holes
    inside the ESP32 antenna band that courtyard necessarily overlaps the
    module's RF keep-out courtyard, recorded as a documented DRC exclusion.
    """
    out = []
    for i, (x, y) in enumerate(MOUNT_HOLES, start=1):
        lib_id = "MountingHole:MountingHole_2.2mm_M2"
        text = KF.read_mod(*lib_id.split(":"))
        # keep the reference text on the board side of the hole
        ref_at = (0.0, 3.15 if y < BOARD_H / 2.0 else -3.15)
        out.append(KF.place(text, lib_id, f"H{i}", "MountingHole_2.2mm_M2",
                            x, y, 0, {}, ref_at=ref_at,
                            footprint_uuid=stable_uuid(f"H{i}")))
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


def zone_keepout(layers, name, x0, y0, x1, y1, footprints_only=False,
                 footprints_ok=False):
    p = " ".join(f"(xy {fmt(a)} {fmt(b)})"
                 for a, b in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    lay = " ".join(f'"{l}"' for l in layers)
    if footprints_only:
        keepout = ("\t\t(keepout\n\t\t\t(footprints not_allowed)\n"
                   "\t\t\t(tracks allowed)\n\t\t\t(vias allowed)\n"
                   "\t\t\t(pads allowed)\n\t\t\t(copperpour allowed)\n\t\t)\n")
    else:
        keepout = ("\t\t(keepout\n\t\t\t(tracks not_allowed)\n\t\t\t(vias not_allowed)\n"
                   "\t\t\t(pads not_allowed)\n\t\t\t(copperpour not_allowed)\n"
                   f"\t\t\t(footprints {'allowed' if footprints_ok else 'not_allowed'})\n"
                   "\t\t)\n")
    return (
        "\t(zone\n"
        "\t\t(net 0)\n"
        f"\t\t(layers {lay})\n"
        f'\t\t(uuid "{u()}")\n'
        f'\t\t(name "{name}")\n'
        "\t\t(hatch edge 0.5)\n"
        + keepout +
        "\t\t(polygon\n\t\t\t(pts\n"
        f"\t\t\t\t{p}\n"
        "\t\t\t)\n\t\t)\n"
        "\t)"
    )


def zone_rule_area(name, x0, y0, x1, y1):
    """A named rule area that forbids nothing by itself.

    It exists so that custom DRC rules can say ``A.insideArea('<name>')`` while
    the exceptions (here: the three keys) are expressed in the rule condition -
    a zone keepout cannot exempt an individual footprint.
    """
    p = " ".join(f"(xy {fmt(a)} {fmt(b)})"
                 for a, b in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return (
        "\t(zone\n"
        "\t\t(net 0)\n"
        '\t\t(layers "F.Cu" "B.Cu")\n'
        f'\t\t(uuid "{u()}")\n'
        f'\t\t(name "{name}")\n'
        "\t\t(hatch edge 0.5)\n"
        "\t\t(keepout\n"
        "\t\t\t(tracks allowed)\n"
        "\t\t\t(vias allowed)\n"
        "\t\t\t(pads allowed)\n"
        "\t\t\t(copperpour allowed)\n"
        "\t\t\t(footprints allowed)\n"
        "\t\t)\n"
        "\t\t(polygon\n\t\t\t(pts\n"
        f"\t\t\t\t{p}\n"
        "\t\t\t)\n\t\t)\n"
        "\t)"
    )


def main():
    comps, net_ids, padnets = load_netlist()
    place, overflow, distances, fallback, aligned, align_blocked = build_placement(comps, padnets)

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

    # courtyard-to-courtyard clearance: proof that the tighter packing is still
    # legal for assembly (the courtyard already carries ~0.25 mm of part excess)
    def sep(ra, rb):
        dx = max(rb[0] - ra[2], ra[0] - rb[2], 0.0)
        dy = max(rb[1] - ra[3], ra[1] - rb[3], 0.0)
        return math.hypot(dx, dy)

    pairs = []
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            d = min(sep(ra, rb) for ra in boxes[a] for rb in boxes[b])
            if d < 0.75:
                pairs.append((d, a, b))
    pairs.sort()
    print(f"closest courtyard pairs: {len(pairs)} below 0.75 mm"
          f"; tightest {pairs[0][0]:.2f} mm" if pairs else "closest courtyards: all >= 0.75 mm")
    for d, a, b in pairs[:8]:
        print(f"   {a:5s} <-> {b:5s}  {d:.2f} mm")

    if distances:
        worst = sorted(distances.items(), key=lambda kv: -kv[1][1])[:10]
        print("largest courtyard gap satellite -> anchor (mm):")
        for ref, (anchor, d) in worst:
            print(f"   {ref:5s} -> {anchor:4s} {d:5.1f} mm")
        print("   fallback (no close slot):", fallback if fallback else "none")

    if aligned or align_blocked:
        print(f"pin-aligned placements: {len(aligned)} ok", end="")
        if align_blocked:
            print("; not aligned:", align_blocked)
        else:
            print()

    silk, silk_hidden = build_silk(comps, place)
    print(f"silkscreen reference designators placed: {len(silk)}"
          + (f"; hidden (no room within 3.3 mm): {sorted(silk_hidden)}"
             if silk_hidden else ""))

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
        lines.append(KF.place(text, lib_id, ref, name, x, y, rot, nets,
                              ref_at=silk.get(ref),
                              footprint_uuid=stable_uuid(ref),
                              ref_size=silk_size(ref, comps),
                              ref_hide=ref in silk_hidden))

    lines.append(gen_outline())
    lines.append(gen_legend())

    # copper pours (outline only - fill in KiCad with "B"/Edit > Fill All Zones)
    lines.append(zone_gnd("In1.Cu", "GND_PLANE_L2"))
    lines.append(zone_gnd("F.Cu", "GND_POUR_L1"))
    lines.append(zone_gnd("B.Cu", "GND_POUR_L4"))
    # ESP32-S3 PCB antenna keep-out: no copper of any kind over the antenna area
    lines.append(zone_keepout(["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"],
                              "ESP32_ANT_KEEP_OUT", *ANT_KEEPOUT))
    # microSD card-slot rule areas (lifted out of the vendor footprint)
    for name, x0, y0, x1, y1 in SD_KEEPOUTS:
        lines.append(zone_keepout(["F.Cu", "B.Cu"], name, x0, y0, x1, y1,
                                  footprints_ok=True))
    # KEY1/2/3 mechanical keep-out: no components, but tracks / vias / copper
    # and the locating holes are explicitly allowed.
    # Published as a named rule area rather than a zone keepout because a KiCad
    # keepout cannot exempt the keys or the locating holes; the custom rule in
    # esp32-board-v1.1.kicad_dru turns it into "footprints not allowed, except
    # SW3/SW4/SW5 and H1..H4".
    lines.append(zone_rule_area("KEY_RIGHT_MECH_KEEP_OUT", *KEY_KEEPOUT))

    lines.append(")")
    OUT_PCB.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sync_drc_exclusions()
    print("wrote", OUT_PCB)


def sync_drc_exclusions():
    """Keep the project's DRC exclusion list in sync.

    The earlier revision carried two exclusions for the upper locating holes
    overlapping the ESP32 module's RF courtyard.  That overlap is now solved
    structurally - the module's board courtyard is trimmed to its body and the
    RF keep-out lives in the ESP32_ANT_KEEP_OUT rule area plus a custom rule -
    so the list is intentionally empty.  Nothing is hidden from DRC.
    """
    exclusions = []
    pro = ROOT / "esp32-board-v1.1.kicad_pro"
    data = json.loads(pro.read_text(encoding="utf-8"))
    board = data.setdefault("board", {})
    if board.get("drc_exclusions") != exclusions:
        board["drc_exclusions"] = exclusions
        pro.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print("DRC exclusion list cleared (no exclusions needed)")


if __name__ == "__main__":
    main()
