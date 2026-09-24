"""Exact (non-grid) clearance oracle for tracks and vias.

Uses the live DRC rule matrix (`pcb drc-rules` -> Spacing/Safe Spacing/
copperThickness1oz, 1 oz outer layer):

    Track <-> Track          4.016 mil  (0.102 mm)
    Track <-> Pad/Via        5.984 mil  (0.152 mm)
    Via   <-> Track/Pad/Via  5.984 mil
    Track <-> Board outline 11.800 mil  (0.29972 mm)

Positives are margin (how much room is left); negatives are violations.
"""

import collections
import math

import geom as _geom

CLR_TRACK = 4.016
CLR_SOLID = 5.984
CLR_EDGE = 11.8
CELL = 160.0


def _buckets(items, bbox_of):
    grid = collections.defaultdict(list)
    for it in items:
        b = bbox_of(it)
        for i in range(int(b[0] // CELL), int(b[2] // CELL) + 1):
            for j in range(int(b[1] // CELL), int(b[3] // CELL) + 1):
                grid[(i, j)].append(it)
    return grid


def _near(grid, px, py, r):
    out, seen = [], set()
    for i in range(int((px - r) // CELL), int((px + r) // CELL) + 1):
        for j in range(int((py - r) // CELL), int((py + r) // CELL) + 1):
            for it in grid.get((i, j), ()):
                if id(it) not in seen:
                    seen.add(id(it))
                    out.append(it)
    return out


def seg_distance(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    u = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + u * dx), py - (y1 + u * dy))


def rect_distance(px, py, pad):
    dx, dy = px - pad["x"], py - pad["y"]
    hw = (pad.get("width") or 0.0) / 2.0
    hh = (pad.get("height") or 0.0) / 2.0
    return math.hypot(max(abs(dx) - hw, 0.0), max(abs(dy) - hh, 0.0))


class Oracle:
    def __init__(self, geom_data=None, net=None, ignore=None):
        g = geom_data or _geom.load()
        ignore = ignore or set()
        if isinstance(net, str):
            net = {net}
        net = net or set()
        self.tracks = [t for t in g["tracks"]
                       if t.get("net") not in net and t.get("primitiveId") not in ignore]
        self.pads = [(c, p) for c, p in _geom.iter_pads(g["components"])
                     if p.get("net") not in net]
        self.vias = [v for v in g["vias"]
                     if v.get("net") not in net and v.get("primitiveId") not in ignore]
        self.outline = [tuple(p) for p in (g.get("outline") or {}).get("points", []) or []]
        self.tg = _buckets(self.tracks, lambda t: (
            min(t["startX"], t["endX"]) - 40, min(t["startY"], t["endY"]) - 40,
            max(t["startX"], t["endX"]) + 40, max(t["startY"], t["endY"]) + 40))
        self.pg = _buckets(self.pads, lambda cp: (
            cp[1]["x"] - cp[1]["width"] - 30, cp[1]["y"] - cp[1]["height"] - 30,
            cp[1]["x"] + cp[1]["width"] + 30, cp[1]["y"] + cp[1]["height"] + 30))
        self.vg = _buckets(self.vias, lambda v: (
            v["x"] - 30, v["y"] - 30, v["x"] + 30, v["y"] + 30))
        n = len(self.outline)
        self.og = _buckets(list(range(n)), lambda k: (
            min(self.outline[k][0], self.outline[(k + 1) % n][0]) - 40,
            min(self.outline[k][1], self.outline[(k + 1) % n][1]) - 40,
            max(self.outline[k][0], self.outline[(k + 1) % n][0]) + 40,
            max(self.outline[k][1], self.outline[(k + 1) % n][1]) + 40))

    def _edge_margin(self, px, py, r):
        best = 1e9
        for k in _near(self.og, px, py, 60):
            n = len(self.outline)
            x1, y1 = self.outline[k]
            x2, y2 = self.outline[(k + 1) % n]
            best = min(best, seg_distance(px, py, x1, y1, x2, y2) - r - CLR_EDGE)
        return best

    def point_margin(self, px, py, r, layer, want_layer=None):
        """Worst margin at a point for a copper disc of radius r.

        `layer=None` means every layer (through via).
        """
        best = 1e9
        who = None
        for t in _near(self.tg, px, py, 220):
            if layer is not None and t["layer"] != layer:
                continue
            m = (seg_distance(px, py, t["startX"], t["startY"], t["endX"], t["endY"])
                 - r - t["lineWidth"] / 2.0 - CLR_SOLID)
            if m < best:
                best, who = m, f"track/{t.get('net')}"
        for c, p in _near(self.pg, px, py, 220):
            if layer is not None and p.get("layer") != layer:
                continue
            m = rect_distance(px, py, p) - r - CLR_SOLID
            if m < best:
                best, who = m, f"pad {c['designator']}.{p.get('padNumber')}"
        for v in _near(self.vg, px, py, 220):
            m = math.hypot(px - v["x"], py - v["y"]) - r - (v.get("diameter") or 24) / 2.0 - CLR_SOLID
            if m < best:
                best, who = m, f"via/{v.get('net')}"
        m = self._edge_margin(px, py, r)
        if m < best:
            best, who = m, "board edge"
        return best, who

    def seg_margin(self, x1, y1, x2, y2, width, layer, step=1.0):
        """Worst margin along a straight track run."""
        r = width / 2.0
        L = math.hypot(x2 - x1, y2 - y1)
        n = max(2, int(L / step) + 1)
        best = 1e9
        who = None
        for k in range(n + 1):
            u = k / n
            px = x1 + u * (x2 - x1)
            py = y1 + u * (y2 - y1)
            seen = set()
            for t in _near(self.tg, px, py, 220):
                if t["layer"] != layer:
                    continue
                c = (t["startX"], t["startY"], t["endX"], t["endY"], t["lineWidth"])
                if c in seen:
                    continue
                seen.add(c)
                m = (seg_distance(px, py, t["startX"], t["startY"],
                                  t["endX"], t["endY"])
                     - r - t["lineWidth"] / 2.0 - CLR_TRACK)
                if m < best:
                    best, who = m, f"track/{t.get('net')}"
            for c0, p in _near(self.pg, px, py, 220):
                if p.get("layer") != layer:
                    continue
                m = rect_distance(px, py, p) - r - CLR_SOLID
                if m < best:
                    best, who = m, f"pad {c0['designator']}.{p.get('padNumber')}"
            for v in _near(self.vg, px, py, 220):
                m = (math.hypot(px - v["x"], py - v["y"]) - r
                     - (v.get("diameter") or 24) / 2.0 - CLR_SOLID)
                if m < best:
                    best, who = m, f"via/{v.get('net')}"
            m = self._edge_margin(px, py, r)
            if m < best:
                best, who = m, "board edge"
        return best, who
