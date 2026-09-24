"""Geometric connectivity self-check for one net straight off the live board.

Builds a graph over the net's pads, tracks and vias (endpoint touching, or a
point landing inside a pad) and reports whether every pad is in one component.
"""

import math
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

EPS = 1.0        # mil — endpoint-to-endpoint / endpoint-to-pad tolerance


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def point_in_pad(px, py, pad, tol):
    return (abs(px - pad["x"]) <= pad["width"] / 2.0 + tol
            and abs(py - pad["y"]) <= pad["height"] / 2.0 + tol)


def seg_point_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    u = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + u * dx), py - (y1 + u * dy))


def seg_seg_touch(a, b, tol):
    """True when two segments share a point (endpoint on segment, or a crossing)."""
    ax1, ay1, ax2, ay2 = a["startX"], a["startY"], a["endX"], a["endY"]
    bx1, by1, bx2, by2 = b["startX"], b["startY"], b["endX"], b["endY"]
    if _cross(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
        return True
    return (seg_point_dist(bx1, by1, ax1, ay1, ax2, ay2) <= tol
            or seg_point_dist(bx2, by2, ax1, ay1, ax2, ay2) <= tol
            or seg_point_dist(ax1, ay1, bx1, by1, bx2, by2) <= tol
            or seg_point_dist(ax2, ay2, bx1, by1, bx2, by2) <= tol)


def seg_rect_touch(x1, y1, x2, y2, pad, tol):
    """True when a segment enters (or grazes) a pad rectangle."""
    hw = pad["width"] / 2.0 + tol
    hh = pad["height"] / 2.0 + tol
    cx, cy = pad["x"], pad["y"]
    if point_in_pad(x1, y1, pad, tol) or point_in_pad(x2, y2, pad, tol):
        return True
    corners = [(cx - hw, cy - hh), (cx + hw, cy - hh),
               (cx + hw, cy + hh), (cx - hw, cy + hh)]
    for k in range(4):
        ex1, ey1 = corners[k]
        ex2, ey2 = corners[(k + 1) % 4]
        if seg_point_dist(ex1, ey1, x1, y1, x2, y2) <= tol or \
           seg_point_dist(x1, y1, ex1, ey1, ex2, ey2) <= tol or \
           seg_point_dist(x2, y2, ex1, ey1, ex2, ey2) <= tol or \
           _cross(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
            return True
    return False


def _cross(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    def o(px, py, qx, qy, rx, ry):
        return (qy - py) * (rx - qx) - (qx - px) * (ry - qy)
    a = o(ax1, ay1, ax2, ay2, bx1, by1)
    b = o(ax1, ay1, ax2, ay2, bx2, by2)
    c = o(bx1, by1, bx2, by2, ax1, ay1)
    d = o(bx1, by1, bx2, by2, ax2, ay2)
    return ((a > 0) != (b > 0)) and ((c > 0) != (d > 0))


def main():
    net = sys.argv[1] if len(sys.argv) > 1 else "SYS"
    path = None
    if "--geom" in sys.argv:
        path = sys.argv[sys.argv.index("--geom") + 1]
    g = geom.load(path)
    tracks = [t for t in g["tracks"] if t.get("net") == net]
    vias = [v for v in g["vias"] if v.get("net") == net]
    pads = [(c, p) for c, p in geom.iter_pads(g["components"]) if p.get("net") == net]

    dsu = DSU()
    for i, t in enumerate(tracks):
        dsu.find(("t", i))
    for i, v in enumerate(vias):
        dsu.find(("v", i))
    for i, _ in enumerate(pads):
        dsu.find(("p", i))

    # track <-> track (same layer, touching)
    for i, a in enumerate(tracks):
        for j in range(i + 1, len(tracks)):
            b = tracks[j]
            if a["layer"] != b["layer"]:
                continue
            if seg_seg_touch(a, b, EPS):
                dsu.union(("t", i), ("t", j))
    # track <-> via (via endpoint on track, any layer)
    for i, a in enumerate(tracks):
        for k, v in enumerate(vias):
            d = seg_point_dist(v["x"], v["y"], a["startX"], a["startY"], a["endX"], a["endY"])
            if d <= (a["lineWidth"] / 2.0 + v["diameter"] / 2.0 - 1.0):
                dsu.union(("t", i), ("v", k))
    # track <-> pad (endpoint inside pad, same layer)
    for i, a in enumerate(tracks):
        for j, (c, p) in enumerate(pads):
            if p.get("layer") != a["layer"]:
                continue
            if seg_rect_touch(a["startX"], a["startY"], a["endX"], a["endY"], p, EPS):
                dsu.union(("t", i), ("p", j))
    # via <-> pad
    for k, v in enumerate(vias):
        for j, (c, p) in enumerate(pads):
            if point_in_pad(v["x"], v["y"], p, EPS):
                dsu.union(("v", k), ("p", j))

    comps = {}
    for j, (c, p) in enumerate(pads):
        comps.setdefault(dsu.find(("p", j)), []).append(
            f"{c['designator']}.{p.get('padNumber')}")
    print(f"{net}: {len(pads)} pads, {len(tracks)} tracks, {len(vias)} vias "
          f"-> {len(comps)} component(s)")
    for k, v in comps.items():
        print("   ", len(v), sorted(v))
    return 0 if len(comps) == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
