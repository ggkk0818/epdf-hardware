"""List every via that sits on a pad (via-in-pad), read-only.

    python tools/find_via_in_pad.py [--net GND]

A via counts as via-in-pad when its *drill* lands on the pad's copper, i.e.
when the distance from the via centre to the pad shape is smaller than the
drill radius.  For each hit the nearest legal off-pad position of the same via
size is printed as well (checked with the router's own clearance engine plus a
DFM pad margin), so stage B can move it without thinking.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", default=None)
    ap.add_argument("--margin", type=float, default=0.20,
                    help="DFM margin the moved via keeps from pad copper")
    ap.add_argument("--at-centre", action="store_true",
                    help="only list vias sitting on a pad's centre (the "
                         "staged 'pad-centre' stitching vias)")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)

    pads_by_net = {}
    for p in board.pads:
        if p["net"]:
            pads_by_net.setdefault(p["net"], []).append(p)

    all_vias = ([dict(v, kind=v.get("kind", "signal"))
                 for v in data.get("vias", [])]
                + [dict(v, kind=v.get("kind", "gnd"))
                   for v in data.get("gnd_vias", [])])
    if args.at_centre:
        print("vias sitting on a pad centre:")
        for v in all_vias:
            if args.net and v["net"] != args.net:
                continue
            for p in pads_by_net.get(v["net"], []):
                if math.hypot(p["x"] - v["x"], p["y"] - v["y"]) < 0.06:
                    print(f"  {v['net']:<8s} {p['ref']}.{p['num']:<3s} "
                          f"({v['x']:7.3f},{v['y']:7.3f}) {v['dia']}/"
                          f"{v['drill']} kind={v['kind']}")
                    break
        return

    hits = []
    for v in all_vias:
        if args.net and v["net"] != args.net:
            continue
        drill_r = v["drill"] / 2.0
        for p in pads_by_net.get(v["net"], []):
            s = board._shape_from_pad(p) if hasattr(board, "_shape_from_pad") \
                else None
            if s is None:
                continue
            px = np.array([v["x"]], np.float32)
            py = np.array([v["y"]], np.float32)
            d = float(s.dist(px, py)[0])
            if d < drill_r - 1e-6:
                hits.append((v, p, d))
                break

    print(f"via-in-pad: {len(hits)}")
    sess = R.Session(board, log=lambda *a: None)
    for (v, p, d) in hits:
        print(f"  {v['net']:<6s} via ({v['x']:7.3f},{v['y']:7.3f}) "
              f"{v['dia']}/{v['drill']} kind={v['kind']:<8s} "
              f"-> pad {p['ref']}.{p['num']} "
              f"{p['w']}x{p['h']} rot{p.get('rot')} (centre offset "
              f"{d:+.3f} mm)")

    if hits and args.margin is not None:
        print("\nnearest legal off-pad position (pad margin "
              f"{args.margin} mm, router clearance engine):")
    for (v, p, d) in hits:
        clear = R.net_params(v["net"])["clearance"]
        vm = sess.rtr.via_mask(v["net"], v["dia"] / 2.0, v["drill"] / 2.0,
                               clear)
        # forbidden band around every pad of the net: the via may not come
        # closer than (drill/2 + margin) to pad copper
        best = None
        for radius in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4):
            for ang in range(0, 360, 15):
                cx = v["x"] + radius * math.cos(math.radians(ang))
                cy = v["y"] + radius * math.sin(math.radians(ang))
                i, j = int(round(cx / R.PITCH)), int(round(cy / R.PITCH))
                if not (0 <= i < R.W and 0 <= j < R.H) or not vm[j, i]:
                    continue
                ok = True
                for p2 in pads_by_net.get(v["net"], []):
                    s2 = board._shape_from_pad(p2)
                    dd = float(s2.dist(np.array([i * R.PITCH], np.float32),
                                       np.array([j * R.PITCH],
                                                np.float32))[0])
                    if dd < v["drill"] / 2.0 + args.margin:
                        ok = False
                        break
                if ok:
                    best = (i * R.PITCH, j * R.PITCH, radius)
                    break
            if best:
                break
        if best:
            print(f"  ({v['x']:7.3f},{v['y']:7.3f}) -> "
                  f"({best[0]:7.3f},{best[1]:7.3f})  r={best[2]:.2f} mm  "
                  f"move {math.hypot(best[0] - v['x'], best[1] - v['y']):.3f} mm")
        else:
            print(f"  ({v['x']:7.3f},{v['y']:7.3f}) -> no legal off-pad spot "
                  f"within 1.4 mm")


if __name__ == "__main__":
    main()
