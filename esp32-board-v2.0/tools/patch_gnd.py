"""Connect orphaned GND pads to the main GND copper tree with a maze router.

    python tools/patch_gnd.py --analyze
    python tools/patch_gnd.py --pads C10.2,C6.2 --out work/gnd-patch.json

The board carries a GND pour on Top/Bottom, but the pour only reaches pads
whose local pocket survives the pour rebuild — a pad sitting in a dense cluster
stays isolated and DRC reports it as a Connection Error. Depending on the pour
for those pads is fragile, so this tool instead:

  1. groups every GND track/via/pad into connected clusters (shapes that touch),
  2. takes the largest cluster as the authoritative GND tree,
  3. maze-routes each orphan pad to the nearest copper of that tree
     (Track<->Track 4.016 mil, Track<->Pad/Via 5.984 mil, Track<->edge 11.8 mil,
      identical to the live DRC rule matrix),
  4. writes a track/via plan for `tools/apply_plan_batch.py`.

Nothing is written to the board here; the plan is applied by the existing
batch applier so a failed batch can be retried without re-planning.
"""

import argparse
import collections
import heapq
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402
import sys_router as SR  # noqa: E402

STEP = SR.STEP
TOUCH = 0.5            # mil — shapes closer than this count as connected
WIDTHS = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0]


# ---------------------------------------------------------------- geometry ---

def seg_seg_dist(a, b):
    (x1, y1, x2, y2), (x3, y3, x4, y4) = a, b
    if _seg_cross(x1, y1, x2, y2, x3, y3, x4, y4):
        return 0.0
    return min(SR.seg_distance(x3, y3, x1, y1, x2, y2),
               SR.seg_distance(x4, y4, x1, y1, x2, y2),
               SR.seg_distance(x1, y1, x3, y3, x4, y4),
               SR.seg_distance(x2, y2, x3, y3, x4, y4))


def _seg_cross(x1, y1, x2, y2, x3, y3, x4, y4):
    def o(ax, ay, bx, by, cx, cy):
        v = (by - ay) * (cx - bx) - (bx - ax) * (cy - by)
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
    o1, o2 = o(x1, y1, x2, y2, x3, y3), o(x1, y1, x2, y2, x4, y4)
    o3, o4 = o(x3, y3, x4, y4, x1, y1), o(x3, y3, x4, y4, x2, y2)
    return o1 != o2 and o3 != o4


def track_of(t):
    return ("T", t["layer"], t["startX"], t["startY"], t["endX"], t["endY"],
            t["lineWidth"])


def shapes_touch(a, b):
    """True when two copper shapes touch/overlap (same or through layer)."""
    ka, la = a[0], a[1]
    kb, lb = b[0], b[1]
    if ka == "V" or kb == "V":                      # vias are through-holes
        via = a if ka == "V" else b
        other = b if ka == "V" else a
        r = (via[2] or 24) / 2.0
        if other[0] == "V":
            return math.hypot(via[3] - other[3], via[4] - other[4]) <= \
                r + (other[2] or 24) / 2.0 + TOUCH
        if other[0] == "T":
            return SR.seg_distance(via[3], via[4], other[2], other[3],
                                   other[4], other[5]) <= r + other[6] / 2.0 + TOUCH
        return _rect_point_dist(other[2], other[3], other[4], other[5],
                                via[3], via[4]) <= r + TOUCH
    if ka == "T" and kb == "T":
        if la != lb:
            return False
        return seg_seg_dist((a[2], a[3], a[4], a[5]),
                            (b[2], b[3], b[4], b[5])) <= \
            a[6] / 2.0 + b[6] / 2.0 + TOUCH
    if ka == "P" and kb == "P":
        if la != lb:
            return False
        return _rect_rect_dist(a, b) <= TOUCH
    pad = a if ka == "P" else b
    trk = b if ka == "P" else a
    if trk[1] != pad[1]:
        return False
    # distance from the pad RECTANGLE to the track (a pad is not a circle:
    # treating a 7.9x19.9 mil QFN pad as radius 13 would fake 5 extra links)
    return _rect_seg_dist(pad, trk) <= trk[6] / 2.0 + TOUCH


def _rect_seg_dist(pad, trk):
    box = ("x", pad[2], pad[3], pad[4], pad[5])
    x1, y1, x2, y2 = trk[2], trk[3], trk[4], trk[5]
    L = math.hypot(x2 - x1, y2 - y1)
    n = max(2, int(L / 2.0) + 1)
    best = 1e9
    for k in range(n + 1):
        u = k / n
        px = x1 + u * (x2 - x1)
        py = y1 + u * (y2 - y1)
        best = min(best, _rect_point_dist(pad[2], pad[3], pad[4], pad[5], px, py))
    return best


def _rect_point_dist(x, y, w, h, px, py):
    return math.hypot(max(abs(px - x) - w / 2.0, 0.0),
                      max(abs(py - y) - h / 2.0, 0.0))


def _rect_rect_dist(a, b):
    dx = max(abs(a[2] - b[2]) - (a[4] + b[4]) / 2.0, 0.0)
    dy = max(abs(a[3] - b[3]) - (a[5] + b[5]) / 2.0, 0.0)
    return math.hypot(dx, dy)


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def gnd_objects(g, net="GND"):
    """Every track / via / pad of `net` as a shape tuple, with a lookup."""
    objs = []
    ids = []
    for t in g["tracks"]:
        if t.get("net") != net:
            continue
        objs.append(track_of(t))
        ids.append(t["primitiveId"])
    for v in g["vias"]:
        if v.get("net") != net:
            continue
        objs.append(("V", None, v.get("diameter") or 24, v["x"], v["y"]))
        ids.append(v["primitiveId"])
    padindex = {}
    for c, p in geom.iter_pads(g["components"]):
        if p.get("net") != net:
            continue
        lay = p.get("layer")
        if lay not in (1, 2, 16):
            lay = 1
        name = f"{c['designator']}.{p.get('padNumber')}"
        objs.append(("P", lay, p["x"], p["y"], p.get("width") or 0,
                     p.get("height") or 0, name))
        ids.append(p.get("primitiveId") or name)
        padindex[name] = len(objs) - 1
    return objs, ids, padindex


def clusters(objs):
    grid = collections.defaultdict(list)
    CELL = 220.0
    for k, o in enumerate(objs):
        if o[0] == "T":
            x0, x1 = sorted((o[2], o[4]))
            y0, y1 = sorted((o[3], o[5]))
        elif o[0] == "V":
            x0 = x1 = o[3]
            y0 = y1 = o[4]
        else:
            x0, x1 = o[2] - o[4] / 2, o[2] + o[4] / 2
            y0, y1 = o[3] - o[5] / 2, o[3] + o[5] / 2
        for i in range(int((x0 - CELL) // CELL), int((x1 + CELL) // CELL) + 1):
            for j in range(int((y0 - CELL) // CELL), int((y1 + CELL) // CELL) + 1):
                grid[(i, j)].append(k)
    uf = UF(len(objs))
    for cell, ks in grid.items():
        for a in range(len(ks)):
            for b in range(a + 1, len(ks)):
                if uf.find(ks[a]) != uf.find(ks[b]) and shapes_touch(objs[ks[a]],
                                                                     objs[ks[b]]):
                    uf.union(ks[a], ks[b])
    groups = collections.defaultdict(list)
    for k in range(len(objs)):
        groups[uf.find(k)].append(k)
    return uf, groups


# ------------------------------------------------------------------ router ---

def route(board, src_cells, goal_cells, r, safety, goal_layers):
    """A* over (layer,i,j) from src cells to any goal cell on goal layer."""
    nx, ny = board.nx, board.ny
    needle = {(i, j) for i, j in goal_cells}
    free = {}

    def is_free(lay, i, j):
        if not (0 <= i < nx and 0 <= j < ny):
            return False
        k = (lay, i, j)
        v = free.get(k)
        if v is None:
            v = board.free(lay, i, j, r, safety)
            free[k] = v
        return v

    def is_goal(lay, i, j):
        if lay not in goal_layers:
            return False
        if (i, j) in needle:
            return True
        return any((i + di, j + dj) in needle
                   for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    starts = [(lay, i, j) for (lay, i, j) in src_cells if is_free(lay, i, j)]
    if not starts:
        return None
    gx = [i for i, _ in needle]
    gy = [j for _, j in needle]
    gx0, gx1, gy0, gy1 = min(gx), max(gx), min(gy), max(gy)

    def h(i, j):
        dx = max(gx0 - i, 0, i - gx1)
        dy = max(gy0 - j, 0, j - gy1)
        a, b = max(dx, dy), min(dx, dy)
        return (a - b) * STEP + b * STEP * math.sqrt(2)

    dist, prev, pq = {}, {}, []
    for (lay, i, j) in starts:
        dist[(lay, i, j)] = 0.0
        heapq.heappush(pq, (h(i, j), 0.0, lay, i, j))
    r2 = STEP * math.sqrt(2)
    nbr = [(1, 0, STEP), (0, 1, STEP), (-1, 0, STEP), (0, -1, STEP),
           (1, 1, r2), (1, -1, r2), (-1, 1, r2), (-1, -1, r2)]
    limit = 4000000
    seen = 0
    while pq:
        f, g, lay, i, j = heapq.heappop(pq)
        key = (lay, i, j)
        if g > dist.get(key, 1e18) + 1e-9:
            continue
        if lay in goal_layers and (i, j) in needle and (lay, i, j) not in starts:
            path = []
            k = key
            while k is not None:
                path.append(k)
                k = prev.get(k)
            path.reverse()
            return path
        seen += 1
        if seen > limit:
            return None
        for di, dj, c in nbr:
            ni, nj = i + di, j + dj
            if not is_free(lay, ni, nj):
                continue
            nk = (lay, ni, nj)
            ng = g + c
            if ng < dist.get(nk, 1e18) - 1e-9:
                dist[nk] = ng
                prev[nk] = key
                heapq.heappush(pq, (ng + h(ni, nj), ng, lay, ni, nj))
        for other in SR.LAYERS:
            if other == lay or not board.via_ok(i, j, safety):
                continue
            nk = (other, i, j)
            ng = g + SR.VIA_COST
            if ng < dist.get(nk, 1e18) - 1e-9:
                dist[nk] = ng
                prev[nk] = key
                heapq.heappush(pq, (ng + h(i, j), ng, other, i, j))
    return None


def obj_cells(board, o):
    """Grid cells covered by a copper shape (used as A* goals)."""
    if o[0] == "P":
        lay = o[1]
        pad = {"x": o[2], "y": o[3], "width": o[4], "height": o[5]}
        return [(lay, i, j) for (i, j) in board.pad_cells(pad, lay)]
    if o[0] == "V":
        i, j = board.cell_of(o[3], o[4])
        return [(lay, i, j) for lay in SR.LAYERS]
    x1, y1, x2, y2 = o[2], o[3], o[4], o[5]
    L = math.hypot(x2 - x1, y2 - y1)
    n = max(2, int(L / STEP) + 1)
    out = []
    for k in range(n + 1):
        u = k / n
        out.append((o[1],) + board.cell_of(x1 + u * (x2 - x1),
                                           y1 + u * (y2 - y1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geom", default=None)
    ap.add_argument("--net", default="GND")
    ap.add_argument("--pads", default="")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--radius", type=float, default=520.0,
                    help="search radius (mil) for a main-tree landing point")
    args = ap.parse_args()

    g = geom.load(args.geom)
    objs, ids, padindex = gnd_objects(g, args.net)
    uf, groups = clusters(objs)
    sizes = sorted(((len(v), k) for k, v in groups.items()), reverse=True)
    main = set(groups[sizes[0][1]])
    print(f"{args.net} shapes: {len(objs)}; clusters: {len(groups)}; "
          f"main cluster: {len(main)} shapes; next: "
          f"{[s for s, _ in sizes[1:6]]}")

    if args.analyze:
        for size, k in sizes[:12]:
            names = [objs[n][6] if objs[n][0] == "P" else objs[n][0]
                     for n in groups[k][:6]]
            xs = [objs[n][2] if objs[n][0] != "V" else objs[n][3]
                  for n in groups[k]]
            ys = [objs[n][3] if objs[n][0] != "V" else objs[n][4]
                  for n in groups[k]]
            print(f"  cluster {size:>4} shapes around ({sum(xs)/len(xs):.0f},"
                  f"{sum(ys)/len(ys):.0f}) e.g. {names}")
        return

    board = SR.Board(g, args.net)
    # The stock Board.via_ok only knows the copper rules; the live DRC also
    # enforces hole-to-hole (0.3 mm = 11.8 mil between drill holes, rule
    # "otherClearance"). Without this a new via can land 6 mil from an existing
    # one and still pass the copper model — which is exactly how the first
    # USB_DP_CONN fanout produced a Hole to Hole error.
    sr_via_ok = board.via_ok
    via_list = [(v["x"], v["y"], (v.get("diameter") or 24) / 2.0,
                 (v.get("holeDiameter") or 12) / 2.0) for v in g["vias"]]

    def via_ok(i, j, safety=SR.SAFETIES[0]):
        if not sr_via_ok(i, j, safety):
            return False
        px, py = board.xy(i, j)
        for vx, vy, _vr, hr in via_list:
            if math.hypot(px - vx, py - vy) < 6.0 + hr + 11.8:
                return False
        return True

    board.via_ok = via_ok
    main_cells = []
    for k in main:
        main_cells.extend(obj_cells(board, objs[k]))

    plan = {"tracks": [], "vias": []}
    missed = []
    for name in [p for p in args.pads.split(",") if p.strip()]:
        name = name.strip()
        idx = padindex.get(name)
        if idx is None:
            missed.append((name, "not a GND pad"))
            continue
        pad = objs[idx]
        px, py = pad[2], pad[3]
        near = [c for c in main_cells
                if math.hypot(board.xy(c[1], c[2])[0] - px,
                              board.xy(c[1], c[2])[1] - py) <= args.radius]
        if not near:
            missed.append((name, f"no main-tree copper within {args.radius} mil"))
            continue
        padobj = {"x": px, "y": py, "width": pad[4], "height": pad[5]}
        src_cells = [(pad[1], i, j) for (i, j) in board.pad_cells(padobj, pad[1])]
        done = False
        for w in WIDTHS:
            for safety in (3.0, 2.0, 1.2):
                path = route(board, src_cells, [(c[1], c[2]) for c in near],
                             w / 2.0, safety, {c[0] for c in near})
                if not path:
                    continue
                sm = SR.smooth(board, path, w / 2.0)
                segs, vias = [], []
                for k in range(len(sm) - 1):
                    lay0, i0, j0 = sm[k]
                    lay1, i1, j1 = sm[k + 1]
                    x0, y0 = board.xy(i0, j0)
                    x1, y1 = board.xy(i1, j1)
                    if lay0 != lay1:
                        vias.append((round(x0, 2), round(y0, 2)))
                        continue
                    segs.append({"x1": round(x0, 2), "y1": round(y0, 2),
                                 "x2": round(x1, 2), "y2": round(y1, 2),
                                 "layer": lay0, "width": w, "net": args.net})
                plan["tracks"].extend(segs)
                plan["vias"].extend({"x": vx, "y": vy, "net": args.net,
                                     "diameter": SR.VIA_D, "hole": SR.VIA_HOLE}
                                    for vx, vy in vias)
                total = sum(math.hypot(s["x2"] - s["x1"], s["y2"] - s["y1"])
                            for s in segs)
                print(f"  {name}: width {w} mil, {len(segs)} segs, "
                      f"{total:.0f} mil, {len(vias)} via(s), safety {safety}")
                done = True
                break
            if done:
                break
        if not done:
            missed.append((name, "no path at any width"))
    print(f"planned {len(plan['tracks'])} tracks, {len(plan['vias'])} vias")
    for m in missed:
        print("  !! missed", m)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False, indent=1)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
