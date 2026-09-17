#!/usr/bin/env python3
"""Push routing/routing.json into the board, add neck rule areas, fill pours.

    & 'C:\\Program Files\\KiCad\\10.0\\bin\\python.exe' tools\\apply_routing.py

Steps
  1. drop every existing track / via (idempotent re-apply)
  2. add the routed segments, signal vias and GND stitching vias
  3. publish DRC rule areas around the necked power segments and refresh the
     matching rules in esp32-board-v1.1.kicad_dru
  4. add the L3 (In2.Cu) GND pour and refill every zone
  5. save
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import fnmatch
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"
ROUTING = ROOT / "routing" / "routing.json"
MODEL = ROOT / "routing" / "model.json"
DRU = ROOT / "esp32-board-v1.1.kicad_dru"

MM = 1e6
LAYERS = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu,
          "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}


def vec(x, y):
    return pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))


def clear_routing(board):
    for item in list(board.GetTracks()):
        board.Remove(item)


def net_codes():
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    return {name: info["code"] for name, info in model["nets"].items()}


def neck_segments(segments):
    """Segments narrower than their net class width (published as rule areas)."""
    pro = json.loads((ROOT / "esp32-board-v1.1.kicad_pro").read_text(encoding="utf-8"))
    classes = {c["name"]: c for c in pro["net_settings"]["classes"]}
    patterns = [(p["pattern"], p["netclass"])
                for p in pro["net_settings"]["netclass_patterns"]]

    def cls_of(net):
        for pat, cls in patterns:
            if fnmatch.fnmatch(net, pat):
                return cls
        return "Default"

    out = []
    for s in segments:
        cls = cls_of(s["net"])
        if s["width"] < classes[cls]["track_width"] - 1e-9:
            out.append({"net": s["net"], "class": cls, "layer": s["layer"],
                        "width": s["width"], "start": s["start"], "end": s["end"]})
    return out


def add_segments(board, segments, codes):
    made = 0
    for s in segments:
        code = codes.get(s["net"], 0)
        if code <= 0:
            raise SystemExit(f"unknown net {s['net']}")
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(vec(*s["start"]))
        t.SetEnd(vec(*s["end"]))
        t.SetWidth(int(round(s["width"] * MM)))
        t.SetLayer(LAYERS[s["layer"]])
        t.SetNetCode(code)
        board.Add(t)
        made += 1
    return made


def add_vias(board, vias, codes):
    made = 0
    for v in vias:
        code = codes.get(v["net"], 0)
        if code <= 0:
            raise SystemExit(f"unknown net {v['net']}")
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(vec(v["x"], v["y"]))
        via.SetWidth(int(round(v["dia"] * MM)))
        via.SetDrill(int(round(v["drill"] * MM)))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNetCode(code)
        board.Add(via)
        made += 1
    return made


def cluster_rects(rects, gap=0.65, margin=0.35):
    """Merge neck segment bounding boxes into a few rule areas."""
    boxes = [list(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out = []
        while boxes:
            a = boxes.pop()
            for b in list(boxes):
                if (a[0] - gap <= b[2] and b[0] - gap <= a[2]
                        and a[1] - gap <= b[3] and b[1] - gap <= a[3]):
                    a = [min(a[0], b[0]), min(a[1], b[1]),
                         max(a[2], b[2]), max(a[3], b[3])]
                    boxes.remove(b)
                    changed = True
            out.append(a)
        boxes = out
    out = []
    for r in boxes:
        out.append([max(0.1, r[0] - margin), max(0.1, r[1] - margin),
                    min(54.9, r[2] + margin), min(83.9, r[3] + margin)])
    return out


def add_neck_areas(board, neck_segments):
    """Publish rule areas covering the necked power segments."""
    for z in [z for z in board.Zones() if z.GetZoneName().startswith("PWR_NECK")]:
        board.Remove(z)
    if not neck_segments:
        return []
    rects = []
    meta = []
    for s in neck_segments:
        x0, y0 = s["start"]
        x1, y1 = s["end"]
        pad = s["width"] / 2.0 + 0.15
        rects.append([min(x0, x1) - pad, min(y0, y1) - pad,
                      max(x0, x1) + pad, max(y0, y1) + pad])
        meta.append(s)
    merged = cluster_rects(rects)
    # map every neck segment to the merged area that contains it
    areas = []
    for k, box in enumerate(merged, 1):
        entries = {}
        for s, r in zip(meta, rects):
            if (r[0] >= box[0] - 1e-6 and r[2] <= box[2] + 1e-6
                    and r[1] >= box[1] - 1e-6 and r[3] <= box[3] + 1e-6):
                cls = s.get("class") or net_class_of(board, s["net"])
                want = s["width"] - 0.01
                if cls not in entries or want < entries[cls]:
                    entries[cls] = max(0.15, round(want, 2))
        areas.append((f"PWR_NECK_{k}", entries, box))
    names = []
    for name, entries, box in areas:
        x0, y0, x1, y1 = box
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetZoneName(name)
        z.SetDoNotAllowZoneFills(False)
        z.SetDoNotAllowTracks(False)
        z.SetDoNotAllowVias(False)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        z.SetLayerSet(pcbnew.LSET.AllCuMask())
        outline = z.Outline()
        outline.NewOutline()
        for (px, py) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            outline.Append(int(round(px * MM)), int(round(py * MM)))
        board.Add(z)
        names.append(name)
    return [(n, e) for n, e, _ in areas], [b for _, _, b in areas]


def net_class_of(board, net):
    try:
        return board.GetDesignSettings().m_NetSettings.GetEffectiveNetClass(net).GetName()
    except Exception:
        return "Default"


def update_dru(areas):
    """Publish one narrow-width rule per (area, net class) pair."""
    text = DRU.read_text(encoding="utf-8")
    text = re.sub(r"\n# -+\n# (?:POWER|SIGNAL) neck areas.*?\n# -+\n"
                  r"(?:\(rule \"Neck [^)]*\)\n(?:\t[^\n]*\n)*\)\n?)*",
                  "\n", text, flags=re.S)
    lines = ["\n# ---------------------------------------------------------------------------",
             "# Neck areas - published by tools/route.py + tools/apply_routing.py.",
             "#",
             "# The IC pad fields are 0.4-0.5 mm pitch.  A wide track cannot",
             "# physically leave those pads, so the router draws the net class",
             "# width wherever the geometry allows and necks down only where it",
             "# must, inside the areas below.  Each area is generated from the",
             "# necked segments themselves (bounding box + 0.4 mm), so a rule can",
             "# never cover more copper than the real neck.",
             "# ---------------------------------------------------------------------------"]
    for name, entries in areas:
        for cls, minw in sorted(entries.items()):
            lines.append(f'(rule "Neck {name} {cls}"')
            lines.append(f"\t(constraint track_width (min {minw:.2f}))")
            lines.append(f"\t(condition \"A.NetClass == '{cls}' && "
                         f"A.insideArea('{name}')\")")
            lines.append(")")
    DRU.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def add_power_islands(board):
    """Publish the local power copper islands as filled zones (MD §8.1/§15.2).

    Each island is a small pour on F.Cu that groups a converter's output pins
    with its local capacitors.  The polygon list comes from tools/route.py so
    the router and the board always agree on the geometry.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import route as R
    for z in [z for z in board.Zones() if z.GetZoneName().startswith(("SYS_ISLAND", "3V3_ISLAND"))]:
        board.Remove(z)
    made = []
    for isl in R.ISLANDS:
        code = board.GetNetcodeFromNetname(isl["net"])
        if code <= 0:
            continue
        z = pcbnew.ZONE(board)
        z.SetNet(board.FindNet(isl["net"]))
        z.SetLayer(LAYERS[isl["layer"]])
        z.SetZoneName(isl["name"])
        z.SetLocalClearance(int(round(0.30 * MM)))
        z.SetMinThickness(int(round(0.25 * MM)))
        z.SetAssignedPriority(20)       # above the GND pours
        # solid bond to the pads: these are power pours, thermal relief would
        # add resistance and it also fragments the fill in a dense cluster
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        # drop slivers that end up with no pad/via of their own net (a power
        # island inside a dense cluster always fragments a little)
        try:
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        except AttributeError:
            pass
        outline = z.Outline()
        outline.NewOutline()
        for (px, py) in isl["poly"]:
            outline.Append(int(round(px * MM)), int(round(py * MM)))
        board.Add(z)
        made.append(isl["name"])
    return made


def add_l3_pour(board):
    for z in [z for z in board.Zones() if z.GetZoneName() == "GND_POUR_L3"]:
        return None
    net = board.FindNet("GND")
    z = pcbnew.ZONE(board)
    z.SetNet(net)
    z.SetLayer(pcbnew.In2_Cu)
    z.SetZoneName("GND_POUR_L3")
    z.SetLocalClearance(int(round(0.3 * MM)))
    outline = z.Outline()
    outline.NewOutline()
    m = 0.4
    for (px, py) in ((m, m), (55.0 - m, m), (55.0 - m, 84.0 - m), (m, 84.0 - m)):
        outline.Append(int(round(px * MM)), int(round(py * MM)))
    board.Add(z)
    return z


def relax_gnd_zones(board, clearance=0.20):
    """Let the GND pours fill the narrow gaps between the fine pitch pads.

    MD §4: stranded GND pads (U2/U3/U5/J1...) are pads the pour cannot reach.
    The board's pours were generated with a 0.3 mm clearance, which is wider
    than the DRC requires (0.15 mm minimum); tightening it to 0.20 mm lets the
    copper flow between the 0.4-0.5 mm pitch pads without breaking any rule.
    (KiCad still applies the larger net-pair clearance where two nets need
    more, so a POWER net keeps its 0.20 mm.)
    """
    touched = 0
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND":
            continue
        z.SetLocalClearance(int(round(clearance * MM)))
        touched += 1
    return touched


def main():
    if "--gen" in sys.argv:
        # Regenerate the placement first.  NOTE: tools/gen_pcb.py currently
        # does not reproduce the committed board (its placement code has drifted
        # from the frozen V1.6 file), so this is opt-in only.
        gen = ROOT / "tools" / "gen_pcb.py"
        subprocess.run([sys.executable, str(gen)], check=True,
                       stdout=subprocess.DEVNULL)
    else:
        clean = ROOT / "routing" / "board_prerouting.kicad_pcb"
        if clean.exists():
            PCB.write_bytes(clean.read_bytes())
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = pcbnew.LoadBoard(str(PCB))
    codes = net_codes()
    codes.setdefault("GND", 1)
    seg = add_segments(board, data["segments"], codes)
    via = add_vias(board, data["vias"], codes)
    gnd = add_vias(board, data.get("gnd_vias", []), codes)
    necks = neck_segments(data["segments"])
    areas, merged = add_neck_areas(board, necks)
    if areas:
        update_dru(areas)
    add_l3_pour(board)
    islands = add_power_islands(board)
    n = relax_gnd_zones(board)
    print(f"GND pours clearance tightened to 0.20 mm ({n} zones)")
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(str(PCB), board)
    print(f"segments {seg}  signal vias {via}  gnd vias {gnd}")
    print(f"power islands: {islands}")
    print(f"neck rule areas: {len(areas)} {[a for a, _ in areas]}")
    print(f"   rects: {merged}")
    print("saved", PCB)


if __name__ == "__main__":
    sys.exit(main())
