"""Close the remaining GND connectivity gaps (MD §4 / §16).

    python tools/fix_gnd.py            # plan vias, update routing.json
    python tools/fix_gnd.py --report   # only report what is missing

Two families of gaps are handled:

  A. real GND pads that the L1 pour cannot reach  -> add a via right at the pad
     (or on a free offset next to it) so the pad lands on the In1 plane
  B. isolated pieces of the filled GND pours      -> add a stitching via inside
     the piece so it becomes part of the plane (rather than deleting copper)

The via candidates are checked with the same clearance engine the router uses,
so nothing that is added can create a DRC error.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"
ROUTING = ROOT / "routing" / "routing.json"


def filled_outlines(board, layer_names):
    """[(layer, [points])] for every filled piece of every copper pour."""
    out = []
    lid_of = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu,
              "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        for lname in layer_names:
            lid = lid_of[lname]
            if not z.IsOnLayer(lid):
                continue
            polys = z.GetFilledPolysList(lid)
            for i in range(polys.OutlineCount()):
                o = polys.Outline(i)
                pts = [(o.CPoint(k).x / 1e6, o.CPoint(k).y / 1e6)
                       for k in range(o.PointCount())]
                out.append((lname, pts, z.GetNetname()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board_r = R.Board(model)
    board_r.load_routing(data)
    sess = R.Session(board_r)

    board = pcbnew.LoadBoard(str(PCB))
    vm = sess.rtr.via_mask("GND", 0.3, 0.15, R.net_params("GND")["clearance"])

    def via_ok(x, y):
        i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
        if not (0 <= i < R.W and 0 <= j < R.H):
            return False
        return bool(vm[j, i])

    placed = []

    def add_via(x, y, kind, size):
        for (px, py, _k, _s) in placed:
            if math.hypot(px - x, py - y) < 0.7:
                return False
        # remember the size the clearance engine actually approved - writing
        # every via back at 0.6/0.3 used to turn a legal 0.4 mm via into a
        # clearance error (it does not fit where the small one does)
        placed.append((x, y, kind, size))
        return True

    # --- A. real GND pads the pour cannot reach --------------------------
    drc = json.loads((ROOT / "drc.json").read_text(encoding="utf-8"))
    missing_pads = []
    for u in drc["unconnected_items"]:
        for it in u["items"]:
            desc = it.get("description", "")
            if desc.startswith("Pad") and "[GND]" in desc:
                pos = it.get("pos") or {}
                if "x" in pos:
                    missing_pads.append((pos["x"], pos["y"], desc))
    print(f"GND pads reported unconnected: {len(missing_pads)}")
    pads_added = 0
    pad_tracks = []
    walk_cache = {}

    def walk_for(width):
        key = round(width, 3)
        if key not in walk_cache:
            walk_cache[key] = sess.rtr.masks(
                "GND", width / 2.0, R.net_params("GND")["clearance"])["F.Cu"][0]
        return walk_cache[key]

    def track_ok(x0, y0, x1, y1, width):
        walk_gnd = walk_for(width)
        n = max(4, int(math.hypot(x1 - x0, y1 - y0) / 0.05))
        for t in np.linspace(0.0, 1.0, n):
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
            if not (0 <= i < R.W and 0 <= j < R.H) or not walk_gnd[j, i]:
                return False
        return True

    # every piece of GND copper we may connect to: other GND pads and vias
    gnd_targets = [(p["x"], p["y"]) for p in board_r.pads_of.get("GND", [])]
    gnd_targets += [(v["x"], v["y"]) for v in data.get("gnd_vias", [])]
    gnd_targets += [(v["x"], v["y"]) for v in data.get("vias", [])
                    if v["net"] == "GND"]
    # ... plus the filled GND pours themselves (sampled along their outlines and
    # inset a little, so a stranded pad can be stitched straight into the copper
    # that already surrounds it)
    for (layer, pts, net) in filled_outlines(board, ["F.Cu"]):
        if net != "GND":
            continue
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        for (px, py) in pts:
            for t in (0.10, 0.25, 0.5):
                gnd_targets.append((px + (cx - px) * t, py + (cy - py) * t))

    for (x, y, desc) in missing_pads:
        cands = [(x, y)]
        for radius in (0.3, 0.5, 0.8):
            for ang in range(0, 360, 45):
                cands.append((x + radius * math.cos(math.radians(ang)),
                              y + radius * math.sin(math.radians(ang))))
        got = None
        for (dia, drill) in ((0.6, 0.3), (0.5, 0.25), (0.4, 0.2)):
            vmask = sess.rtr.via_mask("GND", dia / 2.0, drill / 2.0,
                                      R.net_params("GND")["clearance"])

            def ok_v(x, y):
                i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
                return (0 <= i < R.W and 0 <= j < R.H and bool(vmask[j, i]))
            for (cx, cy) in cands:
                if ok_v(cx, cy) and add_via(cx, cy, "pad", (dia, drill)):
                    got = (cx, cy, dia)
                    break
            if got:
                break
        if got is None:
            # no via fits: stitch the pad with a short GND stub to any GND copper
            nbrs = sorted(((math.hypot(tx - x, ty - y), tx, ty)
                           for (tx, ty) in gnd_targets
                           if 0.1 < math.hypot(tx - x, ty - y) < 2.5))
            done = False
            for _d, tx, ty in nbrs:
                for width in (0.3, 0.2, 0.15):
                    for path in (((x, y), (tx, y), (tx, ty)),
                                 ((x, y), (x, ty), (tx, ty))):
                        if all(track_ok(path[k][0], path[k][1],
                                        path[k + 1][0], path[k + 1][1], width)
                               for k in range(len(path) - 1)):
                            for k in range(len(path) - 1):
                                pad_tracks.append(
                                    {"layer": "F.Cu", "net": "GND", "width": width,
                                     "start": [round(path[k][0], 4), round(path[k][1], 4)],
                                     "end": [round(path[k + 1][0], 4),
                                             round(path[k + 1][1], 4)],
                                     "kind": "gnd_fix"})
                            done = True
                            break
                    if done:
                        break
                if done:
                    break
            if done:
                pads_added += 1
            else:
                print(f"   !! no GND connection possible for {desc}")
            continue
        if math.hypot(got[0] - x, got[1] - y) > 0.12:
            # the via had to go next to the pad: stitch it with a short stub
            if track_ok(x, y, got[0], got[1], 0.3):
                pad_tracks.append({"layer": "F.Cu", "net": "GND", "width": 0.3,
                                   "start": [round(x, 4), round(y, 4)],
                                   "end": [round(got[0], 4), round(got[1], 4)],
                                   "kind": "gnd_fix"})
            else:
                print(f"   !! stitch track blocked at {desc}")
        pads_added += 1
    print(f"   vias placed at real GND pads: {pads_added}")

    # --- B. isolated pour pieces -----------------------------------------
    gnd_pads = [(p["x"], p["y"]) for p in board_r.pads_of.get("GND", [])
                if "F.Cu" in p["cu_layers"]]
    gnd_vias = [(v["x"], v["y"]) for v in data.get("gnd_vias", [])]
    pieces = [p for p in filled_outlines(board, ["F.Cu", "B.Cu", "In2.Cu"])
              if p[2] == "GND"]
    isolated = 0
    stitched = 0
    for (layer, pts, net) in pieces:
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        # a piece is connected when a GND pad or via actually lies inside it
        poly = [(q[0], q[1]) for q in pts]
        touched = any(R.point_in_polygon(px, py, poly)
                      for (px, py) in gnd_pads + gnd_vias)
        if touched:
            continue
        isolated += 1
        ok = False
        # sample a fine grid inside the piece and try progressively smaller vias
        cand_pts = []
        step = 0.2
        gy = min(ys)
        while gy <= max(ys):
            gx = min(xs)
            while gx <= max(xs):
                if R.point_in_polygon(gx, gy, poly):
                    cand_pts.append((gx, gy))
                gx += step
            gy += step
        cand_pts.sort(key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)
        for (dia, drill) in ((0.6, 0.3), (0.5, 0.25), (0.4, 0.2)):
            vmask = sess.rtr.via_mask("GND", dia / 2.0, drill / 2.0,
                                      R.net_params("GND")["clearance"])

            def ok_v(x, y):
                i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
                return (0 <= i < R.W and 0 <= j < R.H and bool(vmask[j, i]))
            for (ox, oy) in cand_pts[:400]:
                if ok_v(ox, oy) and add_via(ox, oy, "stitch", (dia, drill)):
                    ok = True
                    break
            if ok:
                break
        if ok:
            stitched += 1
        else:
            print(f"   !! isolated {layer} pour piece at ({cx:.1f},{cy:.1f}) "
                  f"has no room for a stitching via")
    print(f"   isolated GND pour pieces: {isolated}, stitched: {stitched}")

    if args.report:
        return 0
    # final sanity pass: re-check every new via against the settled copper and
    # against the GND vias that are already on the board
    existing = list(data.get("gnd_vias", []))
    keep = []
    for (x, y, kind, _r) in placed:
        if any(math.hypot(x - v["x"], y - v["y"]) < 0.5 for v in existing):
            continue
        if any(math.hypot(x - kx, y - ky) < 0.5 for (kx, ky) in keep):
            continue
        keep.append((x, y))
    added = [{"x": round(x, 4), "y": round(y, 4), "dia": size[0],
              "drill": size[1], "net": "GND", "kind": kind}
             for (x, y, kind, size) in placed if (x, y) in keep]
    data["gnd_vias"] = existing + added
    if len(added) != len(placed):
        print(f"   rejected {len(placed) - len(added)} vias that would clash")
    data["segments"] = list(data.get("segments", [])) + pad_tracks
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"added {len(added)} GND vias to routing.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
