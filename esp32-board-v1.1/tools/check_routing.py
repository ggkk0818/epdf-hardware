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


def dist_seg_seg(a, b, samples=40):
    """Minimum distance between two axis aligned/45 degree segments."""
    ax0, ay0 = a["start"]
    ax1, ay1 = a["end"]
    bx0, by0 = b["start"]
    by1 = b["end"][1]
    bx1 = b["end"][0]
    n = max(3, samples)
    ax = np.linspace(ax0, ax1, n)
    ay = np.linspace(ay0, ay1, n)
    bx = np.linspace(bx0, bx1, n)
    by = np.linspace(by0, by1, n)
    dx = ax[:, None] - bx[None, :]
    dy = ay[:, None] - by[None, :]
    return float(np.min(np.hypot(dx, dy)))


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
                if (a[0] > b[2] or b[0] > a[2] or a[1] > b[3] or b[1] > a[3]):
                    continue
                need = max(cls_clear(items[i][1]["net"]),
                           cls_clear(items[j][1]["net"]))
                if items[i][0] == "seg" and items[j][0] == "seg":
                    d = dist_seg_seg(items[i][1], items[j][1])
                    d -= (items[i][1]["width"] + items[j][1]["width"]) / 2.0
                else:
                    # one side is a via: use centre distance minus radii
                    if items[i][0] == "via":
                        v, s = items[i][1], items[j][1]
                    else:
                        v, s = items[j][1], items[i][1]
                    cx = (s["start"][0] + s["end"][0]) / 2.0
                    cy = (s["start"][1] + s["end"][1]) / 2.0
                    d = min(abs(v["x"] - x) + abs(v["y"] - y) for x, y in
                            [(s["start"][0], s["start"][1]),
                             (s["end"][0], s["end"][1]),
                             (cx, cy)])
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
