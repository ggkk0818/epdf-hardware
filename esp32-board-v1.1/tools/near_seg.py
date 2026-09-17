"""List foreign copper that comes close to a net's tracks on one layer.

    python tools/near_seg.py <net> <layer> [min_gap] [max_gap]

Used to find the pair of obstacles that squeezes a copper pour into a sliver.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def pt_seg(p, s0, s1):
    v = (s1[0] - s0[0], s1[1] - s0[1])
    den = v[0] ** 2 + v[1] ** 2
    t = 0.0 if den == 0 else max(0.0, min(1.0, ((p[0] - s0[0]) * v[0]
                                               + (p[1] - s0[1]) * v[1]) / den))
    q = (s0[0] + t * v[0], s0[1] + t * v[1])
    return math.hypot(q[0] - p[0], q[1] - p[1])


def cross(p, q, r):
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def center_dist(a, b):
    p0, p1, q0, q1 = a["start"], a["end"], b["start"], b["end"]
    if ((cross(p0, p1, q0) > 0) != (cross(p0, p1, q1) > 0)) and \
            ((cross(q0, q1, p0) > 0) != (cross(q0, q1, p1) > 0)):
        return 0.0
    return min(pt_seg(p0, q0, q1), pt_seg(p1, q0, q1),
               pt_seg(q0, p0, p1), pt_seg(q1, p0, p1))


def main():
    net, layer = sys.argv[1], sys.argv[2]
    lo = float(sys.argv[3]) if len(sys.argv) > 3 else 0.30
    hi = float(sys.argv[4]) if len(sys.argv) > 4 else 0.70
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    segs = [s for s in board.net_segments.get(net, []) if s["layer"] == layer]
    for s in segs:
        length = math.hypot(s["end"][0] - s["start"][0],
                            s["end"][1] - s["start"][1])
        if length < 1.0:
            continue
        print(f"{net} [{s['start'][0]:.2f},{s['start'][1]:.2f}]->"
              f"[{s['end'][0]:.2f},{s['end'][1]:.2f}] w{s['width']}")
        for onet, osegs in board.net_segments.items():
            if onet == net:
                continue
            for o in osegs:
                if o["layer"] != layer:
                    continue
                gap = center_dist(s, o) - (s["width"] + o["width"]) / 2.0
                if lo <= gap <= hi:
                    print(f"    gap {gap:5.3f} to {onet:<14s} "
                          f"[{o['start'][0]:.2f},{o['start'][1]:.2f}]->"
                          f"[{o['end'][0]:.2f},{o['end'][1]:.2f}] w{o['width']}")


if __name__ == "__main__":
    main()
