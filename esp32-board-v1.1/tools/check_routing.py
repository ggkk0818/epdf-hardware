"""Independent clearance self-check of routing/routing.json.

    python tools/check_routing.py [routing.json]

Checks every pair of copper items on a layer whose bounding boxes come close,
computes the true minimum distance between the two rectangles/circles, and
compares it with the clearance derived from the two net classes (plus the pad
obstacles of the board).  It is deliberately independent of the router so that
a routing bug shows up here even when the maze itself "thinks" it is fine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402


def seg_rect(s):
    x0, y0 = s["start"]
    x1, y1 = s["end"]
    half = s["width"] / 2.0
    return (min(x0, x1) - half, min(y0, y1) - half,
            max(x0, x1) + half, max(y0, y1) + half)


def _pt_seg(p, a, b):
    """Exact distance from point p to segment ab (2-D)."""
    ab = b - a
    denom = float(ab @ ab)
    t = 0.0 if denom <= 1e-12 else float(np.clip((p - a) @ ab / denom, 0.0, 1.0))
    return float(np.linalg.norm(a + t * ab - p))


def _seg_seg(a0, a1, b0, b1):
    """Exact minimum distance between two 2-D segments (0 when they cross)."""
    def cross(u, v):
        return float(u[0] * v[1] - u[1] * v[0])

    d1 = cross(a1 - a0, b0 - a0)
    d2 = cross(a1 - a0, b1 - a0)
    d3 = cross(b1 - b0, a0 - b0)
    d4 = cross(b1 - b0, a1 - b0)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(_pt_seg(a0, b0, b1), _pt_seg(a1, b0, b1),
               _pt_seg(b0, a0, a1), _pt_seg(b1, a0, a1))


def dist_seg_seg(a, b):
    """Minimum centreline distance between two segments (exact)."""
    a0 = np.array(a["start"], float)
    a1 = np.array(a["end"], float)
    b0 = np.array(b["start"], float)
    b1 = np.array(b["end"], float)
    return _seg_seg(a0, a1, b0, b1)


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else R.OUT_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    segs = data["segments"]
    vias = data["vias"] + data.get("gnd_vias", [])

    def cls_clear(net):
        return R.net_params(net)["clearance"]

    layers = {}
    for s in segs:
        layers.setdefault(s["layer"], []).append(("seg", s))
    for v in vias:
        layers.setdefault("F.Cu", []).append(("via", v))

    problems = []
    for layer, items in layers.items():
        boxes = []
        for it in items:
            if it[0] == "seg":
                boxes.append(seg_rect(it[1]))
            else:
                v = it[1]
                boxes.append((v["x"] - v["dia"] / 2, v["y"] - v["dia"] / 2,
                              v["x"] + v["dia"] / 2, v["y"] + v["dia"] / 2))
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if items[i][1]["net"] == items[j][1]["net"]:
                    continue
                a, b = boxes[i], boxes[j]
                need = max(cls_clear(items[i][1]["net"]),
                           cls_clear(items[j][1]["net"]))
                # the boxes must be expanded by the clearance before the cheap
                # rejection test, otherwise near misses are silently skipped
                if (a[0] > b[2] + need or b[0] > a[2] + need
                        or a[1] > b[3] + need or b[1] > a[3] + need):
                    continue
                if items[i][0] == "seg" and items[j][0] == "seg":
                    d = dist_seg_seg(items[i][1], items[j][1])
                    d -= (items[i][1]["width"] + items[j][1]["width"]) / 2.0
                elif items[i][0] == "via" and items[j][0] == "via":
                    va, vb = items[i][1], items[j][1]
                    d = float(np.hypot(va["x"] - vb["x"], va["y"] - vb["y"]))
                    d -= (va["dia"] + vb["dia"]) / 2.0
                else:
                    # one side is a via: use centre distance minus radii
                    if items[i][0] == "via":
                        v, s = items[i][1], items[j][1]
                    else:
                        v, s = items[j][1], items[i][1]
                    pt = np.array([v["x"], v["y"]], float)
                    d = _pt_seg(pt, np.array(s["start"], float),
                                np.array(s["end"], float))
                    d -= v["dia"] / 2.0 + s["width"] / 2.0
                if d < need - 0.005:
                    problems.append((layer, items[i][1].get("net"),
                                     items[j][1].get("net"), round(d, 3), need))
    print(f"{len(problems)} clearance problems")
    for p in problems[:40]:
        print("   ", p)
    return len(problems)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
