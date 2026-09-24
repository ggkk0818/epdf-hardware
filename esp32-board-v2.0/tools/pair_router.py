"""Coupled differential-pair router.

Routes the pair's CENTRELINE with A* (the band the two traces occupy is
2*width + gap wide, so the centreline needs width + gap/2 of copper clearance),
then offsets it by +/-(width+gap)/2 to produce the positive and negative traces.
Bevel joins keep both offsets inside the routed band, so the A* clearance bound
also holds for the final traces.

    python tools/pair_router.py --pos USB_DP_CONN --neg USB_DN_CONN \
        --start 944.85,330 --end 581.5,2495.5 --probe

`--probe` only reports per-layer feasibility; without it a plan is written for
tools/apply_edits.py.
"""

import argparse
import json
import math
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import clearance  # noqa: E402
import geom       # noqa: E402
import sys_router as SR  # noqa: E402

MITRE_ALLOW = 1.5      # mil — 45-degree mitre overshoot of the outer trace


class PairBoard(SR.Board):
    """Obstacle model that treats BOTH nets as 'own' copper."""

    def __init__(self, g, nets, ignore=()):
        self.nets = set(nets)
        self.extra_ignore = set(ignore)
        super().__init__(g, net=None)

    # SR.Board filters with `t.get("net") == net`; override the three filters.
    def _fill(self):
        keep = self.net
        self.net = None
        saved = self.nets
        SR.Board._fill_orig(self, saved)
        self.net = keep


def _build_orig(self, own_nets):
    net = None
    M = 60.0
    for t in self.tracks:
        if t.get("net") in own_nets or t.get("net") in self.extra_ignore \
                or t["layer"] not in SR.LAYERS:
            continue
        f = self.f_track[t["layer"]]
        r = t["lineWidth"] / 2.0
        i0, i1, j0, j1 = self._cells(
            min(t["startX"], t["endX"]) - r - M, min(t["startY"], t["endY"]) - r - M,
            max(t["startX"], t["endX"]) + r + M, max(t["startY"], t["endY"]) + r + M)
        for j in range(j0, j1 + 1):
            py = self.y0 + j * SR.STEP
            base = j * self.nx
            for i in range(i0, i1 + 1):
                d = SR.seg_distance(self.x0 + i * SR.STEP, py, t["startX"], t["startY"],
                                    t["endX"], t["endY"]) - r
                if d < f.d[base + i]:
                    f.d[base + i] = d
    for c, p in geom.iter_pads(self.comps):
        if p.get("net") in own_nets or p.get("net") in self.extra_ignore \
                or p.get("layer") not in SR.LAYERS:
            continue
        f = self.f_solid[p["layer"]]
        hw = (p.get("width") or 0) / 2.0
        hh = (p.get("height") or 0) / 2.0
        i0, i1, j0, j1 = self._cells(p["x"] - hw - M, p["y"] - hh - M,
                                     p["x"] + hw + M, p["y"] + hh + M)
        for j in range(j0, j1 + 1):
            py = self.y0 + j * SR.STEP
            base = j * self.nx
            for i in range(i0, i1 + 1):
                d = SR.rect_distance(self.x0 + i * SR.STEP, py, p)
                if d < f.d[base + i]:
                    f.d[base + i] = d
    for v in self.vias:
        if v.get("net") in own_nets or v.get("net") in self.extra_ignore:
            continue
        r = (v.get("diameter") or SR.VIA_D) / 2.0
        i0, i1, j0, j1 = self._cells(v["x"] - r - M, v["y"] - r - M,
                                     v["x"] + r + M, v["y"] + r + M)
        for lay in SR.LAYERS:
            fs = self.f_solid[lay]
            for j in range(j0, j1 + 1):
                py = self.y0 + j * SR.STEP
                base = j * self.nx
                for i in range(i0, i1 + 1):
                    d = math.hypot(self.x0 + i * SR.STEP - v["x"], py - v["y"]) - r
                    if d < fs.d[base + i]:
                        fs.d[base + i] = d


SR.Board._fill_orig = _build_orig


def astar_line(board, start_xy, end_xy, r, layer, safety):
    """Single-layer A* on the grid from one cell to another."""
    si, sj = board.cell_of(*start_xy)
    ei, ej = board.cell_of(*end_xy)
    if not board.free(layer, ei, ej, r, safety):
        # allow the goal to be reached even if its own cell is tight
        pass
    nx, ny = board.nx, board.ny
    r2 = SR.STEP * math.sqrt(2)
    nbr = [(1, 0, SR.STEP), (0, 1, SR.STEP), (-1, 0, SR.STEP), (0, -1, SR.STEP),
           (1, 1, r2), (1, -1, r2), (-1, 1, r2), (-1, -1, r2)]

    def h(i, j):
        dx, dy = abs(i - ei), abs(j - ej)
        a, b = max(dx, dy), min(dx, dy)
        return (a - b) * SR.STEP + b * r2

    dist = {(si, sj): 0.0}
    prev = {}
    pq = [(h(si, sj), 0.0, si, sj)]
    goal = (ei, ej)
    expanded = 0
    cache = {}

    def ok(i, j):
        if not (0 <= i < nx and 0 <= j < ny):
            return False
        key = (i, j)
        v = cache.get(key)
        if v is None:
            v = board.free(layer, i, j, r, safety)
            cache[key] = v
        return v

    while pq:
        f, g, i, j = SR.heapq.heappop(pq)
        if g > dist.get((i, j), 1e18) + 1e-9:
            continue
        if (i, j) == goal:
            path = []
            k = (i, j)
            while k is not None:
                path.append((layer, k[0], k[1]))
                k = prev.get(k)
            path.reverse()
            return path
        expanded += 1
        if expanded > SR.MAX_EXPAND:
            return None
        for di, dj, clen in nbr:
            ni, nj = i + di, j + dj
            if not ok(ni, nj):
                continue
            ng = g + clen
            if ng < dist.get((ni, nj), 1e18) - 1e-9:
                dist[(ni, nj)] = ng
                prev[(ni, nj)] = (i, j)
                SR.heapq.heappush(pq, (ng + h(ni, nj), ng, ni, nj))
    return None


def offset_polyline(board, path, off):
    """Offset a same-layer polyline sideways by `off` (bevel joins)."""
    pts = [(board.xy(i, j)) for (_l, i, j) in path]
    pts = [pts[0]] + [p for k, p in enumerate(pts[1:], 1)
                      if math.hypot(p[0] - pts[k - 1][0], p[1] - pts[k - 1][1]) > 1e-6]
    normals = []
    for k in range(len(pts) - 1):
        dx, dy = pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]
        L = math.hypot(dx, dy) or 1.0
        normals.append((dy / L, -dx / L))
    out = []
    for k in range(len(pts) - 1):
        nx, ny = normals[k]
        out.append((pts[k][0] + nx * off, pts[k][1] + ny * off))
        out.append((pts[k + 1][0] + nx * off, pts[k + 1][1] + ny * off))
    return out


def reach_report(board, start_xy, end_xy, r, layer, safety):
    """BFS flood from the start; report how far it gets toward the goal."""
    import collections
    si, sj = board.cell_of(*start_xy)
    ei, ej = board.cell_of(*end_xy)
    if not board.free(layer, si, sj, r, safety):
        return None
    seen = {(si, sj)}
    q = collections.deque([(si, sj)])
    best = None
    while q:
        i, j = q.popleft()
        d = math.hypot(i - ei, j - ej)
        if best is None or d < best[0]:
            best = (d, i, j)
        for di, dj, _c in ((1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0),
                           (1, 1, 0), (1, -1, 0), (-1, 1, 0), (-1, -1, 0)):
            ni, nj = i + di, j + dj
            if (ni, nj) in seen:
                continue
            if not board.free(layer, ni, nj, r, safety):
                continue
            seen.add((ni, nj))
            q.append((ni, nj))
    bx, by = board.xy(best[1], best[2])
    return {"cells": len(seen), "closest": (bx, by), "dist": best[0] * SR.STEP,
            "goal": (ei, ej)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", required=True)
    ap.add_argument("--neg", required=True)
    ap.add_argument("--start", required=True, help="pair centreline start x,y")
    ap.add_argument("--end", required=True, help="pair centreline end x,y")
    ap.add_argument("--width", type=float, default=9.0)
    ap.add_argument("--gap", type=float, default=5.0)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--reach", action="store_true")
    ap.add_argument("--ignore-net", action="append", default=[],
                    help="treat this net as absent (what-if analysis)")
    ap.add_argument("--pad-clearance", type=float, default=0.0,
                    help="inflate the clearance used by the A* so the emitted "
                         "traces keep a margin against grid quantisation")
    ap.add_argument("--out")
    args = ap.parse_args()

    sx, sy = [float(v) for v in args.start.split(",")]
    ex, ey = [float(v) for v in args.end.split(",")]
    half = args.width + args.gap / 2.0
    r = half + MITRE_ALLOW
    g = geom.load()
    if args.pad_clearance:
        SR.CLR_TRACK += args.pad_clearance
        SR.CLR_SOLID += args.pad_clearance
    board = PairBoard(g, {args.pos, args.neg}, args.ignore_net)
    print(f"pair band {2*args.width+args.gap:.1f} mil wide "
          f"(centreline radius {r:.1f} + clearance)")
    if args.reach:
        for lay in SR.LAYERS:
            rep = reach_report(board, (sx, sy), (ex, ey), r, lay, 1.2)
            if rep is None:
                print(f"  layer {lay:<3} start cell not free at r={r}")
                continue
            print(f"  layer {lay:<3} reachable {rep['cells']:>7} cells, "
                  f"closest to goal {rep['dist']:7.1f} mil at "
                  f"({rep['closest'][0]:.0f},{rep['closest'][1]:.0f}) "
                  f"goal=({ex:.0f},{ey:.0f})")
        return
    best = None
    for lay in SR.LAYERS:
        for safety in SR.SAFETIES:
            p = astar_line(board, (sx, sy), (ex, ey), r, lay, safety)
            if p:
                L = sum(math.hypot(board.xy(p[k + 1][1], p[k + 1][2])[0] - board.xy(p[k][1], p[k][2])[0],
                                   board.xy(p[k + 1][1], p[k + 1][2])[1] - board.xy(p[k][1], p[k][2])[1])
                        for k in range(len(p) - 1))
                print(f"  layer {lay:<3} safety {safety}: path {len(p)} nodes, "
                      f"{L:.0f} mil")
                if best is None:
                    best = (lay, safety, p)
                break
        else:
            print(f"  layer {lay:<3} no path")
    if args.probe or best is None:
        return
    lay, safety, path = best
    sm = SR.smooth(board, path, r)
    print(f"chosen layer {lay}, safety {safety}, {len(sm)} vertices after smoothing")
    oracle = clearance.Oracle(net={args.pos, args.neg})
    traces = {}
    for name, off in ((args.pos, -half), (args.neg, +half)):
        poly = offset_polyline(board, sm, off)
        worst, who = 1e9, None
        for k in range(len(poly) - 1):
            m, w = oracle.seg_margin(poly[k][0], poly[k][1], poly[k + 1][0],
                                     poly[k + 1][1], args.width, lay)
            if m < worst:
                worst, who = m, w
        length = sum(math.hypot(poly[k + 1][0] - poly[k][0], poly[k + 1][1] - poly[k][1])
                     for k in range(len(poly) - 1))
        traces[name] = (poly, worst, who, length)
        print(f"  {name:<14} {len(poly)-1} segs, {length:.1f} mil, "
              f"worst margin {worst:.2f} mil vs {who}")
    d = abs(traces[args.pos][3] - traces[args.neg][3])
    print(f"  skew between the two traces: {d:.2f} mil")
    if args.out:
        tracks = []
        for name, (poly, _w, _x, _l) in traces.items():
            for k in range(len(poly) - 1):
                tracks.append({"x1": round(poly[k][0], 2), "y1": round(poly[k][1], 2),
                               "x2": round(poly[k + 1][0], 2),
                               "y2": round(poly[k + 1][1], 2),
                               "layer": lay, "width": args.width, "net": name})
        plan = {"tracks": tracks, "vias": [],
                "delete": {"tracks": [t["primitiveId"] for t in g["tracks"]
                                      if t.get("net") in (args.pos, args.neg)],
                           "vias": [v["primitiveId"] for v in g["vias"]
                                    if v.get("net") in (args.pos, args.neg)]}}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False, indent=1)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
