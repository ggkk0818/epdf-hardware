"""Give every power island an explicit via anchor (MD §5.1 / §15.2).

    python tools/anchor_islands.py [--dry-run]

A pour is only part of the net once track/via copper actually touches it.  This
looks for a same-net via inside each island; if there is none it tries to drop
one (0.6 -> 0.5 -> 0.4 mm) on a fine grid inside the polygon, checked with the
router's clearance engine, so the island is bonded to the copper underneath
(the In2.Cu trunks run below the converters).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=print)
    added = []

    for isl in R.ISLANDS:
        net, layer = isl["net"], isl["layer"]
        if net not in board.net_segments and net not in board.pads_of:
            continue
        params = R.net_params(net)
        x0, y0, x1, y1 = R.polygon_rect(isl["poly"])
        existing = [(v["x"], v["y"]) for v in board.net_vias.get(net, [])]
        inside = [v for v in existing
                  if R.point_in_polygon(v[0], v[1], isl["poly"])]
        if inside:
            print(f"  {isl['name']}: already has {len(inside)} via(s) inside")
            continue
        # candidate points on a 0.25 mm grid inside the polygon
        cands = []
        step = 0.25
        gy = y0 + 0.15
        while gy <= y1 - 0.15:
            gx = x0 + 0.15
            while gx <= x1 - 0.15:
                if R.point_in_polygon(gx, gy, isl["poly"]):
                    cands.append((gx, gy))
                gx += step
            gy += step
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cands.sort(key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)
        got = None
        for (dia, drill) in ((0.6, 0.3), (0.5, 0.25), (0.4, 0.2)):
            vmask = sess.rtr.via_mask(net, dia / 2.0, drill / 2.0,
                                      params["clearance"])
            for (vx, vy) in cands:
                i, j = int(round(vx / R.PITCH)), int(round(vy / R.PITCH))
                if 0 <= i < R.W and 0 <= j < R.H and vmask[j, i]:
                    got = (vx, vy, dia, drill)
                    break
            if got:
                break
        if got is None:
            print(f"  {isl['name']}: no room for a via inside")
            continue
        added.append({"x": round(got[0], 4), "y": round(got[1], 4),
                      "dia": got[2], "drill": got[3], "net": net,
                      "kind": "island"})
        print(f"  {isl['name']}: via {got[2]}/{got[3]} added at "
              f"({got[0]:.2f},{got[1]:.2f})")

    if args.dry_run:
        return 0
    if added:
        data["vias"] = list(data.get("vias", [])) + added
        ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"added {len(added)} island anchor via(s) to {ROUTING.name}")
    else:
        print("nothing added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
