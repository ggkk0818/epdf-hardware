"""DFM stage B - move the seven pad-centre GND stitching vias off their pads.

    python tools/fix_via_in_pad.py [--dry-run] [--margin 0.15] [--radius 1.2]

Round 16 stitched seven isolated GND patches by dropping a 0.40/0.20 via on
the *centre* of the patch's GND pad (SW1.2, U6.2, C31.2, R31.2, C16.2, R8.2,
D3.2).  That closes the DRC record but leaves a via in the pad, which wicks
solder during reflow (MD stage B / DFM).

This script searches, for each of the seven, the legal 0.40/0.20 via spots
inside the *same* filled GND patch that keep a DFM margin from every pad of the
net (the MD's "pad_mask + DFM margin"), and picks the one closest to the old
position.  Only routing/routing.json is rewritten; tools/apply_routing.py
rebuilds the board afterwards.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pcbnew  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"
ROUTING = ROOT / "routing" / "routing.json"

# pad -> the pad-centre via that round 16 placed on it
TARGETS = ["SW1.2", "U6.2", "C31.2", "R31.2", "C16.2", "R8.2", "D3.2"]

# pads that must keep their via in the pad (MD Final DFM Plan Phase B): the
# decoupling loops of C3/C18 stay short, R29 gets its own manual review
KEEP_IN_PAD = {"C3.2", "R29.2", "C18.2"}


def pour_polys(board, layer=pcbnew.F_Cu, net="GND"):
    """[(zone name, polygon)] of every filled GND piece on that layer."""
    out = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsOnLayer(layer):
            continue
        ps = z.GetFilledPolysList(layer)
        for k in range(ps.OutlineCount()):
            o = ps.Outline(k)
            pts = [(o.CPoint(t).x / 1e6, o.CPoint(t).y / 1e6)
                   for t in range(o.PointCount())]
            if len(pts) >= 3:
                out.append((f"{z.GetZoneName()}#{k}", pts))
    return out


def pour_id(polys, x, y):
    """Which filled GND piece covers (x,y)?  None when it is bare board."""
    for name, pts in polys:
        if R.point_in_polygon(x, y, pts):
            return name
    return None


def patch_id(board, polys, pad, margin=0.25):
    """The filled GND piece that surrounds this pad."""
    for radius in (0.3, 0.4, 0.5, 0.6, 0.8, 1.0):
        for ang in range(0, 360, 10):
            x = pad["x"] + radius * math.cos(math.radians(ang))
            y = pad["y"] + radius * math.sin(math.radians(ang))
            pid = pour_id(polys, x, y)
            if pid:
                return pid
    return None


def stub_ok(sess, x0, y0, x1, y1, width):
    """Can a GND stub of that width run from the pad to the via centre?"""
    walk = sess.rtr.masks("GND", width / 2.0,
                          R.net_params("GND")["clearance"])["F.Cu"][0]
    n = max(5, int(math.hypot(x1 - x0, y1 - y0) / 0.05))
    for t in range(n + 1):
        x = x0 + (x1 - x0) * t / n
        y = y0 + (y1 - y0) * t / n
        i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
        if not (0 <= i < R.W and 0 <= j < R.H) or not walk[j, i]:
            return None
    return width


def stub_segments(pad, vx, vy, sess):
    """Pick the widest legal stub from the pad centre to the new via."""
    for width in (0.3, 0.25, 0.2, 0.15):
        if stub_ok(sess, pad["x"], pad["y"], vx, vy, width):
            return [{"layer": "F.Cu", "net": "GND", "width": width,
                     "start": [round(pad["x"], 4), round(pad["y"], 4)],
                     "end": [round(vx, 4), round(vy, 4)],
                     "kind": "via_in_pad_stub"}]
        # L-shaped exit: leave along the pad's own axis first, then turn
        for (mx, my) in ((vx, pad["y"]), (pad["x"], vy)):
            if stub_ok(sess, pad["x"], pad["y"], mx, my, width) and \
                    stub_ok(sess, mx, my, vx, vy, width):
                return [{"layer": "F.Cu", "net": "GND", "width": width,
                         "start": [round(pad["x"], 4), round(pad["y"], 4)],
                         "end": [round(mx, 4), round(my, 4)],
                         "kind": "via_in_pad_stub"},
                        {"layer": "F.Cu", "net": "GND", "width": width,
                         "start": [round(mx, 4), round(my, 4)],
                         "end": [round(vx, 4), round(vy, 4)],
                         "kind": "via_in_pad_stub"}]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--margin", type=float, default=0.15,
                    help="DFM gap the via annulus keeps from pad copper (mm)")
    ap.add_argument("--radius", type=float, default=1.2,
                    help="search radius around the old via position (mm)")
    ap.add_argument("--all-at-centre", action="store_true",
                    help="also plan moves for the older 0.6/0.3 pad-centre "
                         "GND vias (report only, unless --apply-all)")
    ap.add_argument("--apply-all", action="store_true",
                    help="with --all-at-centre: really move every one of them")
    ap.add_argument("--only", default=None,
                    help="comma separated pad list; overrides the default "
                         "target list and the KEEP_IN_PAD guard")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board_r = R.Board(model)
    board_r.load_routing(data)
    sess = R.Session(board_r, log=lambda *a: None)
    board = pcbnew.LoadBoard(str(PCB))

    pads = {f"{p['ref']}.{p['num']}": p for p in board_r.pads_of.get("GND", [])}
    gnd_pads = list(board_r.pads_of.get("GND", []))
    shapes = {id(p): board_r._shape_from_pad(p) for p in gnd_pads}
    gnd_vias = data.get("gnd_vias", [])
    polys = pour_polys(board)
    named = [(f"{p['ref']}.{p['num']}", p) for p in gnd_pads]

    moved, kept, new_segs = [], [], []
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    for v in gnd_vias:
        host = None
        for key in TARGETS:
            for (name, p) in named:
                if name == key and math.hypot(p["x"] - v["x"],
                                              p["y"] - v["y"]) < 0.06:
                    host = key
                    break
            if host:
                break
        if host is None and (args.all_at_centre or only is not None):
            for (name, p) in named:
                if math.hypot(p["x"] - v["x"], p["y"] - v["y"]) < 0.06:
                    host = name
                    break
        if only is not None and host not in only:
            kept.append(v)
            continue
        report_only = (host is not None and host not in TARGETS
                       and not (args.all_at_centre and args.apply_all))
        if only is not None:
            report_only = args.dry_run
        if host is None:
            kept.append(v)
            continue
        if host in KEEP_IN_PAD and only is None:
            print(f"  {host}: keep the via in the pad (MD Final DFM Plan "
                  f"Phase B - keep the decoupling loop short)")
            kept.append(v)
            continue
        host_pad = next(p for (name, p) in named if name == host)
        pid = patch_id(board, polys, host_pad)
        if pid is None:
            print(f"  {host}: no GND pour around the pad -> keep the via")
            kept.append(v)
            continue
        vm = sess.rtr.via_mask("GND", v["dia"] / 2.0, v["drill"] / 2.0,
                               R.net_params("GND")["clearance"])
        best = None
        for margin in (args.margin, args.margin - 0.05, args.margin - 0.10,
                       0.0):
            if margin < 0:
                continue
            need = v["dia"] / 2.0 + margin
            n = int(args.radius / R.PITCH)
            for jj in range(-n, n + 1):
                for ii in range(-n, n + 1):
                    cx = v["x"] + ii * R.PITCH
                    cy = v["y"] + jj * R.PITCH
                    d = math.hypot(cx - v["x"], cy - v["y"])
                    if d > args.radius or (best and d >= best[0]):
                        continue
                    i, j = int(round(cx / R.PITCH)), int(round(cy / R.PITCH))
                    if not (0 <= i < R.W and 0 <= j < R.H) or not vm[j, i]:
                        continue
                    if pour_id(polys, i * R.PITCH, j * R.PITCH) != pid:
                        continue
                    px = np.array([i * R.PITCH], np.float32)
                    py = np.array([j * R.PITCH], np.float32)
                    if any(float(shapes[id(p)].dist(px, py)[0]) < need
                           for p in gnd_pads
                           if abs(p["x"] - cx) < 2.0 and abs(p["y"] - cy) < 2.0):
                        continue
                    best = (d, i * R.PITCH, j * R.PITCH, margin)
            if best:
                break
        if best is None:
            print(f"  {host}: no off-pad spot within {args.radius} mm -> keep "
                  f"the via in the pad")
            kept.append(v)
            continue
        d, nx, ny, margin = best
        tag = " (report only)" if report_only else ""
        segs = None
        if host not in TARGETS:          # the round-16 seven are pour-bonded
            segs = stub_segments(host_pad, nx, ny, sess)
            if segs is None and not report_only:
                print(f"  {host}: no legal GND stub from the pad to "
                      f"({nx:.3f},{ny:.3f}) -> keep the via in the pad")
                kept.append(v)
                continue
        print(f"  {host}: ({v['x']:.3f},{v['y']:.3f}) -> ({nx:.3f},{ny:.3f})  "
              f"move {d:.2f} mm, pad margin {margin:.2f} mm, stub "
              f"{segs[0]['width'] if segs else '-'} mm{tag}   "
              f"{v['dia']}/{v['drill']}")
        if report_only:
            kept.append(v)
            continue
        moved.append(dict(v, x=round(nx, 4), y=round(ny, 4),
                          kind=v.get("kind", "pad")))
        new_segs.extend(segs)

    print(f"off-pad: {len(moved)} moved")
    if args.dry_run or not moved:
        return 0
    shutil.copyfile(ROUTING, ROUTING.with_name("_pre_via_in_pad.json"))
    data["gnd_vias"] = kept + moved
    data["segments"] = list(data.get("segments", [])) + new_segs
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name} (+{len(new_segs)} stub segments, "
          f"backup: _pre_via_in_pad.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
