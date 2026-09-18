"""Neck one trunk segment down over a short stretch, keeping its centre line.

    python tools/neck_trunk.py <net> <layer> x0,y0 x1,y1 d0 d1 width [taper]

The segment from (x0,y0) to (x1,y1) is replaced by

    full width  ->  taper  ->  narrow  ->  taper  ->  full width

where `d0` / `d1` are the distances (mm, measured along the segment) between
which the narrow width applies and `taper` (default 0.35 mm, a 45 degree step)
is the length of each transition.  Nothing else is touched - the two ends stay
exactly where they were, so the trunk keeps its connectivity.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("net")
    ap.add_argument("layer")
    ap.add_argument("p0", help="x,y")
    ap.add_argument("p1", help="x,y")
    ap.add_argument("d0", type=float)
    ap.add_argument("d1", type=float)
    ap.add_argument("width", type=float)
    ap.add_argument("taper", type=float, nargs="?", default=0.35)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    a = tuple(float(v) for v in args.p0.split(","))
    b = tuple(float(v) for v in args.p1.split(","))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    hit = None
    for s in data["segments"]:
        if s["net"] != args.net or s["layer"] != args.layer:
            continue
        if (abs(s["start"][0] - a[0]) < 1e-3 and abs(s["start"][1] - a[1]) < 1e-3
                and abs(s["end"][0] - b[0]) < 1e-3
                and abs(s["end"][1] - b[1]) < 1e-3):
            hit = s
            break
    if hit is None:
        print(f"no {args.net} {args.layer} segment from {a} to {b}")
        return 1
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length

    def pt(d):
        return [round(a[0] + ux * d, 4), round(a[1] + uy * d, 4)]

    full = hit["width"]
    mid = (full + args.width) / 2.0
    stops = [(0.0, pt(0.0), full),
             (max(0.0, args.d0 - args.taper), pt(max(0.0, args.d0 - args.taper)),
              full),
             (args.d0, pt(args.d0), mid),
             (args.d1, pt(args.d1), mid),
             (min(length, args.d1 + args.taper),
              pt(min(length, args.d1 + args.taper)), full),
             (length, pt(length), full)]
    new = []
    for (d_a, p_a, w_a), (d_b, p_b, w_b) in zip(stops, stops[1:]):
        if d_b - d_a < 1e-6:
            continue
        # the width that applies to this piece: the narrow one inside the neck,
        # the intermediate one inside a taper, the original outside
        t_in0, t_out1 = args.d0 - args.taper, args.d1 + args.taper
        near = lambda u, v: abs(u - v) < 1e-6
        if near(d_a, t_in0) and near(d_b, args.d0):
            w = mid
        elif near(d_a, args.d0) and near(d_b, args.d1):
            w = args.width
        elif near(d_a, args.d1) and near(d_b, t_out1):
            w = mid
        else:
            w = full
        new.append({"layer": args.layer, "net": args.net, "width": round(w, 3),
                    "start": p_a, "end": p_b, "kind": hit.get("kind", "route")})
    for s in new:
        print(f"  {s['layer']} w{s['width']:<5} {s['start']} -> {s['end']}")
    print(f"replacing 1 segment with {len(new)}")
    if args.dry_run:
        return 0
    idx = data["segments"].index(hit)
    data["segments"][idx:idx + 1] = new
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
