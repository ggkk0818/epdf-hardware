"""Clearance-aware maze router for a single net, on the *existing* board.

Rebuilds only the target net's copper (tracks + vias) at the widest width its
corridors allow, leaving every other net, pad and keep-out untouched.

Obstacle model is calibrated against the live DRC rule matrix
(`pcb drc-rules` -> Spacing/Safe Spacing/copperThickness1oz):

    Track  <-> Track          4.016 mil
    Track  <-> SMD pad / Via  5.984 mil
    Track  <-> Copper zone   10.000 mil   (pours re-flow, so not modelled)
    Track  <-> Board outline 11.800 mil

Pad `width`/`height` from `pcb dump` are already world-axis extents; the reported
pad `rotation` must NOT be applied again (doing so makes neighbouring 0.5 mm QFN
pads overlap, and the model then disagrees with the live DRC).
"""

import array
import collections
import heapq
import json
import math
import os
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

STEP = 4.0                 # mil — grid pitch
CLR_TRACK = 4.016          # mil — track to track
CLR_SOLID = 5.984          # mil — track to pad / via
CLR_EDGE = 11.8            # mil — track to board outline
SAFETIES = [3.0, 2.0, 1.2]  # mil — covers 8-connected grid discretisation,
                            # tried in order so only hard spots relax
FINAL_SAFETY = 2.5         # mil — used when grading a finished path
VIA_D = 24.0
VIA_HOLE = 12.0
VIA_COST = 90.0            # mil-equivalent penalty for a layer change
VIA_EXTRA = 3.0            # mil — extra margin asked of a NEW via (seeded vias are
                           # reused at their exact legal coordinates instead)
WALL_PULL = 0.35           # centring nudge so paths do not hug obstacles
MAX_EXPAND = 3000000
LAYERS = [1, 2, 16]        # Top, Bottom, Inner2 (Inner1 is the GND plane)

# Extra obstacles the board carries that the plain dump does not expose as
# tracks/vias/pads: milled slots (mounting holes) and rule regions (keep-outs).
# Written by route_power.py as work/route-obstacles.json:
#   {"rects": [[x0,y0,x1,y1], ...], "circles": [[cx,cy,dia], ...]}
_OBST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "work", "route-obstacles.json")
EXTRA_RECTS, EXTRA_CIRCLES = [], []
if os.path.exists(_OBST):
    try:
        _d = json.load(open(_OBST, encoding="utf-8"))
        EXTRA_RECTS = [tuple(r) for r in (_d.get("rects") or [])]
        EXTRA_CIRCLES = [tuple(c) for c in (_d.get("circles") or [])]
    except Exception:
        pass
WIDTH_LADDER = [31.5, 28.0, 25.0, 22.0, 20.0, 18.0, 16.0, 14.0, 12.0,
                10.0, 9.0, 8.0]
LADDER = list(WIDTH_LADDER)   # narrowed by --max-width in main()


class Field:
    def __init__(self, x0, y0, nx, ny):
        self.x0, self.y0, self.nx, self.ny = x0, y0, nx, ny
        self.d = array.array("f", [1e9]) * (nx * ny)

    def idx(self, i, j):
        return j * self.nx + i

    def point(self, px, py):
        i = int(round((px - self.x0) / STEP))
        j = int(round((py - self.y0) / STEP))
        if 0 <= i < self.nx and 0 <= j < self.ny:
            return self.d[j * self.nx + i]
        return -1.0


def rect_distance(px, py, pad):
    dx, dy = px - pad["x"], py - pad["y"]
    hw = (pad.get("width") or 0.0) / 2.0
    hh = (pad.get("height") or 0.0) / 2.0
    return math.hypot(max(abs(dx) - hw, 0.0), max(abs(dy) - hh, 0.0))


def seg_distance(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    u = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + u * dx), py - (y1 + u * dy))


def poly_distance(px, py, pts):
    best = 1e9
    n = len(pts)
    for k in range(n):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % n]
        best = min(best, seg_distance(px, py, x1, y1, x2, y2))
    return best


class Board:
    def __init__(self, g, net):
        self.net = net
        self.g = g
        self.tracks = list(g["tracks"])
        self.vias = list(g["vias"])
        self.comps = g["components"]

        xs, ys = [], []
        for t in self.tracks:
            xs += [t["startX"], t["endX"]]
            ys += [t["startY"], t["endY"]]
        outline = g.get("outline") or {}
        self.outline = [tuple(p) for p in (outline.get("points") or [])]
        for p in self.outline:
            xs.append(p[0]); ys.append(p[1])
        self.x0 = min(xs) - 60.0
        self.y0 = min(ys) - 60.0
        self.nx = int((max(xs) + 60.0 - self.x0) / STEP) + 1
        self.ny = int((max(ys) + 60.0 - self.y0) / STEP) + 1
        self.N = self.nx * self.ny

        # per-layer distance to the nearest foreign track edge / pad-via edge
        self.f_track = {lay: self._mk() for lay in LAYERS}
        self.f_solid = {lay: self._mk() for lay in LAYERS}
        self.f_edge = self._mk()      # distance to board outline (layer independent)
        self.inside = bytearray(self.N)
        # Existing vias of this net are legal by construction: the rest of the
        # board was routed *around* them, so their pocket is exactly via-sized
        # and no grid-discretised search can rediscover it. Reuse them.
        self.seed_vias = [(v["x"], v["y"]) for v in self.vias if v.get("net") == net]
        self.seed_cells = {}
        for (vx, vy) in self.seed_vias:
            self.seed_cells[self.cell_of(vx, vy)] = (vx, vy)
        self._fill_outline()
        self._fill()

    def _fill_outline(self):
        """Scanline inside-mask + stamped edge distance (cheap, no per-cell polygon loop)."""
        pts = self.outline
        if not pts:
            for k in range(self.N):
                self.inside[k] = 1
            return
        n = len(pts)
        for j in range(self.ny):
            py = self.y0 + j * STEP
            xs = []
            for k in range(n):
                x1, y1 = pts[k]
                x2, y2 = pts[(k + 1) % n]
                if (y1 > py) != (y2 > py):
                    xs.append(x1 + (py - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            base = j * self.nx
            for m in range(0, len(xs) - 1, 2):
                i0 = int(math.ceil((xs[m] - self.x0) / STEP))
                i1 = int(math.floor((xs[m + 1] - self.x0) / STEP))
                for i in range(max(i0, 0), min(i1, self.nx - 1) + 1):
                    self.inside[base + i] = 1
        M = 260.0
        f = self.f_edge
        for k in range(n):
            x1, y1 = pts[k]
            x2, y2 = pts[(k + 1) % n]
            i0, i1, j0, j1 = self._cells(min(x1, x2) - M, min(y1, y2) - M,
                                         max(x1, x2) + M, max(y1, y2) + M)
            for j in range(j0, j1 + 1):
                py = self.y0 + j * STEP
                base = j * self.nx
                for i in range(i0, i1 + 1):
                    d = seg_distance(self.x0 + i * STEP, py, x1, y1, x2, y2)
                    if d < f.d[base + i]:
                        f.d[base + i] = d

    def _mk(self):
        f = Field(self.x0, self.y0, self.nx, self.ny)
        return f

    def _cells(self, bx0, by0, bx1, by1):
        i0 = int(math.floor((bx0 - self.x0) / STEP))
        i1 = int(math.ceil((bx1 - self.x0) / STEP))
        j0 = int(math.floor((by0 - self.y0) / STEP))
        j1 = int(math.ceil((by1 - self.y0) / STEP))
        return max(i0, 0), min(i1, self.nx - 1), max(j0, 0), min(j1, self.ny - 1)

    def _fill(self):
        net = self.net
        M = 60.0
        for t in self.tracks:
            if t.get("net") == net or t["layer"] not in LAYERS:
                continue
            f = self.f_track[t["layer"]]
            r = t["lineWidth"] / 2.0
            i0, i1, j0, j1 = self._cells(
                min(t["startX"], t["endX"]) - r - M, min(t["startY"], t["endY"]) - r - M,
                max(t["startX"], t["endX"]) + r + M, max(t["startY"], t["endY"]) + r + M)
            for j in range(j0, j1 + 1):
                py = self.y0 + j * STEP
                base = j * self.nx
                for i in range(i0, i1 + 1):
                    d = seg_distance(self.x0 + i * STEP, py, t["startX"], t["startY"],
                                     t["endX"], t["endY"]) - r
                    if d < f.d[base + i]:
                        f.d[base + i] = d
        for c, p in geom.iter_pads(self.comps):
            if p.get("net") == net or p.get("layer") not in LAYERS:
                continue
            f = self.f_solid[p["layer"]]
            hw = (p.get("width") or 0) / 2.0
            hh = (p.get("height") or 0) / 2.0
            i0, i1, j0, j1 = self._cells(p["x"] - hw - M, p["y"] - hh - M,
                                         p["x"] + hw + M, p["y"] + hh + M)
            for j in range(j0, j1 + 1):
                py = self.y0 + j * STEP
                base = j * self.nx
                for i in range(i0, i1 + 1):
                    d = rect_distance(self.x0 + i * STEP, py, p)
                    if d < f.d[base + i]:
                        f.d[base + i] = d

        # Through-hole / multi-layer pads (layer 12) obstruct EVERY routing layer:
        # the plain pad loop above skips them because their layer is not 1/2/16.
        for c, p in geom.iter_pads(self.comps):
            if p.get("net") == net or p.get("layer") in LAYERS:
                continue
            hw = (p.get("width") or 0) / 2.0
            hh = (p.get("height") or 0) / 2.0
            i0, i1, j0, j1 = self._cells(p["x"] - hw - M, p["y"] - hh - M,
                                         p["x"] + hw + M, p["y"] + hh + M)
            for lay in LAYERS:
                f = self.f_solid[lay]
                for j in range(j0, j1 + 1):
                    py = self.y0 + j * STEP
                    base = j * self.nx
                    for i in range(i0, i1 + 1):
                        d = rect_distance(self.x0 + i * STEP, py, p)
                        if d < f.d[base + i]:
                            f.d[base + i] = d

        # Milled slots (mounting holes) and rule/keep-out regions.
        for (x0, y0, x1, y1) in EXTRA_RECTS:
            i0, i1, j0, j1 = self._cells(x0 - M, y0 - M, x1 + M, y1 + M)
            box = {"x": (x0 + x1) / 2.0, "y": (y0 + y1) / 2.0,
                   "width": x1 - x0, "height": y1 - y0}
            for lay in LAYERS:
                f = self.f_solid[lay]
                for j in range(j0, j1 + 1):
                    py = self.y0 + j * STEP
                    base = j * self.nx
                    for i in range(i0, i1 + 1):
                        d = rect_distance(self.x0 + i * STEP, py, box)
                        if d < f.d[base + i]:
                            f.d[base + i] = d
        for (cx, cy, dia) in EXTRA_CIRCLES:
            r = dia / 2.0
            i0, i1, j0, j1 = self._cells(cx - r - M, cy - r - M,
                                         cx + r + M, cy + r + M)
            for lay in LAYERS:
                f = self.f_solid[lay]
                for j in range(j0, j1 + 1):
                    py = self.y0 + j * STEP
                    base = j * self.nx
                    for i in range(i0, i1 + 1):
                        d = math.hypot(self.x0 + i * STEP - cx, py - cy) - r
                        if d < f.d[base + i]:
                            f.d[base + i] = d
        for v in self.vias:
            if v.get("net") == net:
                continue
            r = (v.get("diameter") or VIA_D) / 2.0
            i0, i1, j0, j1 = self._cells(v["x"] - r - M, v["y"] - r - M,
                                         v["x"] + r + M, v["y"] + r + M)
            for lay in LAYERS:
                fs = self.f_solid[lay]
                for j in range(j0, j1 + 1):
                    py = self.y0 + j * STEP
                    base = j * self.nx
                    for i in range(i0, i1 + 1):
                        d = math.hypot(self.x0 + i * STEP - v["x"], py - v["y"]) - r
                        if d < fs.d[base + i]:
                            fs.d[base + i] = d

    def pad_cells(self, pad, lay):
        """Grid cells whose centre lies inside the pad rectangle."""
        hw = (pad.get("width") or 0) / 2.0
        hh = (pad.get("height") or 0) / 2.0
        i0, i1, j0, j1 = self._cells(pad["x"] - hw, pad["y"] - hh,
                                     pad["x"] + hw, pad["y"] + hh)
        out = []
        for j in range(j0, j1 + 1):
            py = self.y0 + j * STEP
            for i in range(i0, i1 + 1):
                px = self.x0 + i * STEP
                if abs(px - pad["x"]) <= hw + 1e-9 and abs(py - pad["y"]) <= hh + 1e-9:
                    out.append((i, j))
        if not out:
            i = int(round((pad["x"] - self.x0) / STEP))
            j = int(round((pad["y"] - self.y0) / STEP))
            out.append((i, j))
        return [(i, j) for i, j in out
                if 0 <= i < self.nx and 0 <= j < self.ny]

    def slack(self, lay, i, j):
        """Half-width the corridor at this cell still allows."""
        k = j * self.nx + i
        return min(self.f_track[lay].d[k] - CLR_TRACK,
                   self.f_solid[lay].d[k] - CLR_SOLID,
                   self.f_edge.d[k] - CLR_EDGE)

    def free(self, lay, i, j, r, safety=SAFETIES[0]):
        k = j * self.nx + i
        if not self.inside[k]:
            return False
        if self.f_track[lay].d[k] < r + CLR_TRACK + safety:
            return False
        if self.f_solid[lay].d[k] < r + CLR_SOLID + safety:
            return False
        if self.f_edge.d[k] < r + CLR_EDGE + safety:
            return False
        return True

    def xy(self, i, j):
        return self.x0 + i * STEP, self.y0 + j * STEP

    def cell_of(self, px, py):
        return (int(round((px - self.x0) / STEP)),
                int(round((py - self.y0) / STEP)))


def astar(board, sources, goals, r, safety=SAFETIES[0]):
    """Multi-source / multi-goal A*.

    `sources` is a set of (layer, i, j) seeds (already-connected copper);
    `goals` is a set of (i, j) cells on layer 1 (inside the target pad).
    """
    nx, ny = board.nx, board.ny
    goal_set = set(goals)
    gx0 = min(i for i, _ in goal_set); gx1 = max(i for i, _ in goal_set)
    gy0 = min(j for _, j in goal_set); gy1 = max(j for _, j in goal_set)

    def h(i, j):
        dx = max(gx0 - i, 0, i - gx1)
        dy = max(gy0 - j, 0, j - gy1)
        a, b = max(dx, dy), min(dx, dy)
        return (a - b) * STEP + b * STEP * math.sqrt(2)

    free_cache = {}

    def is_free(lay, i, j):
        if not (0 <= i < nx and 0 <= j < ny):
            return False
        key = (lay, i, j)
        v = free_cache.get(key)
        if v is None:
            v = board.free(lay, i, j, r, safety)
            free_cache[key] = v
        return v

    start_nodes = []
    for (lay, i, j) in sources:
        if is_free(lay, i, j):
            start_nodes.append((lay, i, j))
    if not start_nodes:
        return None

    r2 = STEP * math.sqrt(2)
    dist = {}
    prev = {}
    pq = []
    for k, (lay, i, j), in enumerate(start_nodes):
        dist[(lay, i, j)] = 0.0
        heapq.heappush(pq, (h(i, j), 0.0, lay, i, j))

    target = None
    expanded = 0
    nbr = [(1, 0, STEP), (0, 1, STEP), (-1, 0, STEP), (0, -1, STEP),
           (1, 1, r2), (1, -1, r2), (-1, 1, r2), (-1, -1, r2)]
    while pq:
        f, g, lay, i, j = heapq.heappop(pq)
        key = (lay, i, j)
        if g > dist.get(key, 1e18) + 1e-9:
            continue
        if lay == 1 and (i, j) in goal_set:
            target = key
            break
        expanded += 1
        if expanded > MAX_EXPAND:
            return None
        slack = board.slack(lay, i, j) - r
        bias = 1.0 + WALL_PULL * max(0.0, 14.0 - slack) / 14.0
        for di, dj, clen in nbr:
            ni, nj = i + di, j + dj
            if not is_free(lay, ni, nj):
                continue
            ng = g + clen * bias
            nk = (lay, ni, nj)
            if ng < dist.get(nk, 1e18) - 1e-9:
                dist[nk] = ng
                prev[nk] = key
                heapq.heappush(pq, (ng + h(ni, nj), ng, lay, ni, nj))
        for other in LAYERS:
            if other == lay:
                continue
            if not board.via_ok(i, j, safety):
                continue
            nk = (other, i, j)
            ng = g + VIA_COST
            if ng < dist.get(nk, 1e18) - 1e-9:
                dist[nk] = ng
                prev[nk] = key
                heapq.heappush(pq, (ng + h(i, j), ng, other, i, j))
    if target is None:
        return None
    path = []
    k = target
    while k is not None:
        path.append(k)
        k = prev.get(k)
    path.reverse()
    return path


def _via_ok(self, i, j, safety=SAFETIES[0]):
    if (i, j) in self.seed_cells:
        return True
    r = VIA_D / 2.0
    for lay in LAYERS:
        k = j * self.nx + i
        if self.f_solid[lay].d[k] < r + CLR_SOLID + safety + VIA_EXTRA:
            return False
        if self.f_track[lay].d[k] < r + CLR_TRACK + safety + VIA_EXTRA:
            return False
        if self.f_edge.d[k] < r + CLR_EDGE + safety + VIA_EXTRA:
            return False
    return True


Board.via_ok = _via_ok


def smooth(board, path, r):
    """String-pull an 8-connected path: keep the furthest reachable vertex."""
    out = [path[0]]
    n = len(path)
    i = 0
    while i < n - 1:
        best = i + 1
        for j in range(min(n - 1, i + 90), i, -1):
            if path[j][0] != path[i][0]:
                continue
            if straight_ok(board, path[i], path[j], r):
                best = j
                break
        out.append(path[best])
        i = best
    return out


def straight_ok(board, a, b, r):
    lay, i0, j0 = a
    _, i1, j1 = b
    x0, y0 = board.xy(i0, j0)
    x1, y1 = board.xy(i1, j1)
    L = math.hypot(x1 - x0, y1 - y0)
    n = max(2, int(L / (STEP * 0.5)) + 1)
    for k in range(n + 1):
        u = k / n
        px = x0 + u * (x1 - x0)
        py = y0 + u * (y1 - y0)
        i = int(round((px - board.x0) / STEP))
        j = int(round((py - board.y0) / STEP))
        if not (0 <= i < board.nx and 0 <= j < board.ny):
            return False
        if not _line_free(board, lay, i, j, r):
            return False
    return True


def _line_free(board, lay, i, j, r):
    k = j * board.nx + i
    lim = r + FINAL_SAFETY
    if board.f_track[lay].d[k] < lim + CLR_TRACK:
        return False
    if board.f_solid[lay].d[k] < lim + CLR_SOLID:
        return False
    if board.f_edge.d[k] < lim + CLR_EDGE:
        return False
    return True


def grade(board, a, b, cap):
    """Widest ladder width whose edges still clear along the straight run a->b."""
    lay, i0, j0 = a
    _, i1, j1 = b
    x0, y0 = board.xy(i0, j0)
    x1, y1 = board.xy(i1, j1)
    L = math.hypot(x1 - x0, y1 - y0)
    n = max(2, int(L / (STEP * 0.5)) + 1)
    worst = 1e9
    for k in range(n + 1):
        u = k / n
        px = x0 + u * (x1 - x0)
        py = y0 + u * (y1 - y0)
        i = int(round((px - board.x0) / STEP))
        j = int(round((py - board.y0) / STEP))
        kk = j * board.nx + i
        worst = min(worst,
                    board.f_track[lay].d[kk] - CLR_TRACK,
                    board.f_solid[lay].d[kk] - CLR_SOLID,
                    board.f_edge.d[kk] - CLR_EDGE)
    allow = 2.0 * (worst - FINAL_SAFETY)
    for w in LADDER:
        if w <= cap and w <= allow:
            return w
    return WIDTH_LADDER[-1]


def terminal_pads(g, net):
    out = []
    for c, p in geom.iter_pads(g["components"]):
        if p.get("net") == net:
            out.append((c["designator"], p))
    return out


def main():
    net = sys.argv[1] if len(sys.argv) > 1 else "SYS"
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    global LADDER
    max_w = None
    if "--max-width" in sys.argv:
        max_w = float(sys.argv[sys.argv.index("--max-width") + 1])
    if max_w is not None:
        LADDER = [w for w in WIDTH_LADDER if w <= max_w] or [WIDTH_LADDER[-1]]
    geom_path = None
    if "--geom" in sys.argv:
        geom_path = sys.argv[sys.argv.index("--geom") + 1]
    g = geom.load(geom_path)
    board = Board(g, net)
    print(f"grid {board.nx}x{board.ny} step {STEP} mil, layers {LAYERS}")

    terms = terminal_pads(g, net)
    for d, p in terms:
        cells = board.pad_cells(p, p.get("layer"))
        best = max((board.slack(p.get("layer") if p.get("layer") in LAYERS else 1, i, j)
                    for i, j in cells), default=-1)
        print(f"  {d}.{p.get('padNumber')} ({p['x']:.1f},{p['y']:.1f}) "
              f"cells={len(cells)} best-halfwidth={best:.1f} "
              f"-> max width {2*best:.1f} mil")

    # Prim MST over terminals: always attach the nearest remaining pad.
    # nearest-neighbour (Prim) over pad centres
    order = [0]
    remaining = [k for k in range(len(terms)) if k != 0]
    edges = []
    while remaining:
        best = None
        for ti in remaining:
            for oi in order:
                dist = math.hypot(terms[ti][1]["x"] - terms[oi][1]["x"],
                                  terms[ti][1]["y"] - terms[oi][1]["y"])
                if best is None or dist < best[0]:
                    best = (dist, ti, oi)
        _, ti, oi = best
        edges.append((oi, ti))
        order.append(ti)
        remaining.remove(ti)
    print(f"\nMST edges: {[(terms[a][0], terms[b][0]) for a, b in edges]}")

    track_segs = []
    via_pts = []
    tree = {(1, i, j) for (i, j) in board.pad_cells(terms[0][1], 1)}
    for a, b in edges:
        da, pa = terms[a]
        db, pb = terms[b]
        goals = set(board.pad_cells(pb, 1))
        used_w = None
        used_s = None
        path = None
        for w in LADDER:
            r = w / 2.0
            for safety in SAFETIES:
                src = {(lay, i, j) for (lay, i, j) in tree
                       if board.free(lay, i, j, r, safety)}
                goal = {(i, j) for (i, j) in goals if board.free(1, i, j, r, safety)}
                if not src or not goal:
                    continue
                p = astar(board, src, goal, r, safety)
                if p:
                    used_w, used_s, path = w, safety, p
                    break
            if path:
                break
        if path is None:
            print(f"  !! {da} -> {db}: NO PATH at any width")
            continue
        sm = smooth(board, path, used_w / 2.0)
        print(f"  {da} -> {db}: width {used_w} mil (safety {used_s}), "
              f"{len(path)} nodes, {len(sm)} after smoothing")
        # emit — a vertex sitting on a reused via keeps that via's exact coordinate
        coords = []
        for (lay, i, j) in sm:
            seed = board.seed_cells.get((i, j))
            coords.append((lay, i, j, seed[0] if seed else None,
                           seed[1] if seed else None))
        for k in range(len(coords) - 1):
            lay0, i0, j0, sx0, sy0 = coords[k]
            lay1, i1, j1, sx1, sy1 = coords[k + 1]
            x0, y0 = board.xy(i0, j0) if sx0 is None else (sx0, sy0)
            x1, y1 = board.xy(i1, j1) if sx1 is None else (sx1, sy1)
            if lay0 != lay1:
                vx, vy = board.seed_cells.get((i0, j0), board.xy(i0, j0))
                via_pts.append((vx, vy))
                for L in LAYERS:
                    tree.add((L, i0, j0))
                continue
            w = grade(board, sm[k], sm[k + 1], used_w)
            track_segs.append({"x1": round(x0, 2), "y1": round(y0, 2),
                               "x2": round(x1, 2), "y2": round(y1, 2),
                               "layer": lay0, "width": w, "net": net})
            tree.add((lay0, i0, j0))
            tree.add((lay1, i1, j1))

    # de-duplicate vias
    seen = set()
    uniq = []
    for x, y in via_pts:
        key = (round(x, 1), round(y, 1))
        if key not in seen:
            seen.add(key)
            uniq.append({"x": round(x, 2), "y": round(y, 2),
                         "net": net, "diameter": VIA_D, "hole": VIA_HOLE})

    plan = {"net": net, "tracks": track_segs, "vias": uniq}
    import collections as _c
    hist = _c.Counter(t["width"] for t in track_segs)
    print("\nemitted widths:", dict(hist))
    print("emitted vias:", len(uniq))
    total = sum(math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"]) for t in track_segs)
    print(f"total copper length {total/1000*25.4:.1f} mm")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False, indent=1)
        print("wrote", out_path)


if __name__ == "__main__":
    main()

