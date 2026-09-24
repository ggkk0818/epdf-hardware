"""Write work/route-obstacles.json for sys_router: milled slots + rule regions.

    python tools/make_obstacles.py

Sources: the four M2 mounting-hole cutouts and the keep-out regions that forbid
copper (PCB_INTERFACE_POSITIONS.md section 6).  Coordinates are mil in the
editor frame (origin bottom-left, y up).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

MM = 39.37007874015748
BOARD_H = 84.0 * MM

HOLES = [
    (118.11, 3188.98),
    (2047.24, 3188.98),
    (118.11, 118.11),
    (2047.24, 118.11),
]
HOLE_DIA = 86.61

# J1 (GCT USB4105) footprint carries its own slot regions: four oval shield
# slots and two 0.65 mm locating holes.  Doc 5.1 coordinates, editor frame.
J1_SLOTS = [
    (774.80, 241.40, 814.20, 324.10),
    (1115.00, 241.40, 1154.40, 324.10),
    (774.80, 76.80, 814.20, 147.70),
    (1115.00, 76.80, 1154.40, 147.70),
]
J1_HOLES = [(831.10, 221.70, 25.6), (1058.70, 221.70, 25.6)]

# The board's DRC wants tracks >= 11.8 mil from a slot/region edge; the router
# stamps these as "solid" (5.984 mil).  Inflating by the difference keeps the
# routed result on the right side of the board rule.
INFLATE = 7.0

RECTS_MM = [
    (16.0, 0.0, 39.0, 6.0),
    (32.775, 67.925, 33.525, 71.175),
    (32.775, 72.375, 33.525, 75.975),
    (33.875, 73.775, 34.575, 81.375),
    (42.925, 82.175, 45.475, 83.525),
    (34.575, 72.475, 43.275, 74.075),
]


def main():
    rects = []
    for (x0, y0, x1, y1) in RECTS_MM:
        ax, ay = x0 * MM, BOARD_H - y0 * MM
        bx, by = x1 * MM, BOARD_H - y1 * MM
        rects.append([round(min(ax, bx) - INFLATE, 2), round(min(ay, by) - INFLATE, 2),
                      round(max(ax, bx) + INFLATE, 2), round(max(ay, by) + INFLATE, 2)])
    circles = [[x, y, HOLE_DIA + 2 * INFLATE] for (x, y) in HOLES]
    j1 = 3.0        # J1's own slots sit in the pad field: keep the margin tight
    for (x0, y0, x1, y1) in J1_SLOTS:
        rects.append([x0 - j1, y0 - j1, x1 + j1, y1 + j1])
    for (cx, cy, dia) in J1_HOLES:
        circles.append([cx, cy, dia + 2 * j1])
    out = {"rects": rects, "circles": circles}
    path = os.path.join(geom.ROOT, "work", "route-obstacles.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"{len(rects)} rects + {len(circles)} circles -> {path}")


if __name__ == "__main__":
    main()
