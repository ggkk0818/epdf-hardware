"""Close the remaining connectivity gaps of a net with the *minimum* of new copper.

    python tools/bridge_net.py SYS [3V3_MAIN ...] [--dry-run]

How it works
  1. every piece of the net's copper is an item: routed tracks, vias, pads and
     the *filled* pieces of the net's pours (an island outline is not copper -
     the fill can be much smaller, and it can be split in several pieces);
  2. items that really touch each other are merged into components
     (exact copper geometry, not a grid approximation);
  3. the components are joined with an MST, and each MST edge is bridged by the
     router's A*: the copper of one component is the source lattice, the other
     component is the target.  Because the source cells are *inside* real
     copper, a bridge can never start in mid air;
  4. nothing that already exists is moved or re-drawn.

Everything is checked with the router's own clearance engine, so a bridge that
has no legal route is reported and skipped instead of being forced in.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"
LAYER_ID = {"F.Cu": 0, "In1.Cu": 1, "In2.Cu": 2, "B.Cu": 3}
# a bridge to another layer needs a via, so a same-layer gap is worth this much
# more than a cross-layer one (only used to order the bridges - the A* decides
# what is really cheapest)
VIA_PENALTY = 1.0


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def pt_seg(p, a, b):
    v = b - a
    den = float(v @ v)
    t = 0.0 if den <= 1e-12 else float(np.clip((p - a) @ v / den, 0.0, 1.0))
    return float(np.linalg.norm(a + t * v - p))


def seg_seg(a0, a1, b0, b1):
    def cr(u, v):
        return float(u[0] * v[1] - u[1] * v[0])

    d1 = cr(a1 - a0, b0 - a0)
    d2 = cr(a1 - a0, b1 - a0)
    d3 = cr(b1 - b0, a0 - b0)
    d4 = cr(b1 - b0, a1 - b0)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(pt_seg(a0, b0, b1), pt_seg(a1, b0, b1),
               pt_seg(b0, a0, a1), pt_seg(b1, a0, a1))


def inside(pt, poly):
    x, y = pt
    c = False
    n = len(poly)
    for k in range(n):
        x0, y0 = poly[k]
        x1, y1 = poly[(k + 1) % n]
        if (y0 > y) != (y1 > y):
            if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
    return c


class Item:
    """One piece of copper."""

    def __init__(self, kind, layer, **kw):
        self.kind = kind
        self.layer = layer
        self.__dict__.update(kw)
        self.cells = None

    # -- copper-to-copper distance (<= 0 means they touch) -----------------
    def gap(self, other):
        d = self._gap_same_layer(other)
        if self.layer != other.layer:
            return d + VIA_PENALTY if d < math.inf else math.inf
        return d

    def _gap_same_layer(self, other):
        if self.kind == "track":
            a0, a1 = np.array(self.p0, float), np.array(self.p1, float)
            if other.kind == "track":
                d = seg_seg(a0, a1, np.array(other.p0, float),
                            np.array(other.p1, float))
                return d - (self.w + other.w) / 2.0
            if other.kind == "via":
                return pt_seg(np.array([other.x, other.y], float), a0, a1) \
                    - self.w / 2.0 - other.r
            if other.kind == "pad":
                n = max(2, int(np.linalg.norm(a1 - a0) / 0.05))
                pts = np.linspace(a0, a1, n).astype(np.float32)
                return float(other.shape.dist(pts[:, 0], pts[:, 1]).min()) \
                    - self.w / 2.0
            if other.kind == "pour":
                n = max(2, int(np.linalg.norm(a1 - a0) / 0.05))
                for t in range(n + 1):
                    q = a0 + (a1 - a0) * t / n
                    if inside((float(q[0]), float(q[1])), other.poly):
                        return 0.0
                d = min(seg_seg(a0, a1, np.array(other.poly[k], float),
                                np.array(other.poly[(k + 1) % len(other.poly)],
                                         float))
                        for k in range(len(other.poly)))
                return d - self.w / 2.0
        if self.kind == "via":
            p = np.array([self.x, self.y], float)
            if other.kind == "track":
                return other.gap(self)
            if other.kind == "via":
                return float(np.linalg.norm(
                    p - np.array([other.x, other.y], float))) \
                    - self.r - other.r
            if other.kind == "pad":
                return float(other.shape.dist(
                    np.array([self.x], np.float32),
                    np.array([self.y], np.float32))[0]) - self.r
            if other.kind == "pour":
                return 0.0 if inside((self.x, self.y), other.poly) \
                    else min(pt_seg(p, np.array(other.poly[k], float),
                                    np.array(other.poly[(k + 1) % len(other.poly)],
                                             float))
                             for k in range(len(other.poly))) - self.r
        if self.kind == "pad":
            if other.kind == "track":
                return other.gap(self)
            if other.kind == "via":
                return other.gap(self)
            if other.kind == "pad":
                n = max(4, int(max(self.shape.x1 - self.shape.x0,
                                   self.shape.y1 - self.shape.y0) / 0.05))
                xs = np.linspace(self.shape.x0, self.shape.x1, n)
                ys = np.linspace(self.shape.y0, self.shape.y1, n)
                X, Y = np.meshgrid(xs, ys)
                return float(other.shape.dist(X, Y).min())
            if other.kind == "pour":
                # the pad is part of the pour when its centre lies inside the
                # filled polygon (checking the polygon vertices is not enough:
                # a pad sitting in the middle of a pour is nowhere near them)
                if inside((self.shape.x, self.shape.y), other.poly):
                    return 0.0
                edges = []
                for k in range(len(other.poly)):
                    q0 = np.array(other.poly[k], float)
                    q1 = np.array(other.poly[(k + 1) % len(other.poly)], float)
                    n = max(2, int(np.linalg.norm(q1 - q0) / 0.05))
                    edges.append(np.linspace(q0, q1, n).astype(np.float32))
                pts = np.concatenate(edges)
                return float(self.shape.dist(pts[:, 0], pts[:, 1]).min())
        if self.kind == "pour":
            if other.kind == "pour":
                if any(inside(q, other.poly) for q in self.poly) or \
                        any(inside(q, self.poly) for q in other.poly):
                    return 0.0
                return min(seg_seg(np.array(self.poly[k], float),
                                   np.array(self.poly[(k + 1) % len(self.poly)],
                                            float),
                                   np.array(other.poly[t], float),
                                   np.array(other.poly[(t + 1) % len(other.poly)],
                                            float))
                           for k in range(len(self.poly))
                           for t in range(len(other.poly)))
            return other.gap(self)
        return math.inf

    def mark(self, mask, exact=True):
        """Cells that lie inside this copper."""
        if self.kind == "track":
            a = np.array(self.p0, float)
            b = np.array(self.p1, float)
            n = max(1, int(np.linalg.norm(b - a) / R.PITCH))
            for k in range(n + 1):
                q = a + (b - a) * k / n
                i, j = int(round(q[0] / R.PITCH)), int(round(q[1] / R.PITCH))
                if not (0 <= i < R.W and 0 <= j < R.H):
                    continue
                if not exact or pt_seg(np.array([i * R.PITCH, j * R.PITCH]),
                                       a, b) <= self.w / 2.0 - 0.005:
                    mask[j, i] = True
        elif self.kind == "via":
            i0 = int((self.x - self.r) / R.PITCH)
            i1 = int((self.x + self.r) / R.PITCH) + 1
            j0 = int((self.y - self.r) / R.PITCH)
            j1 = int((self.y + self.r) / R.PITCH) + 1
            for j in range(max(0, j0), min(R.H - 1, j1) + 1):
                for i in range(max(0, i0), min(R.W - 1, i1) + 1):
                    if math.hypot(i * R.PITCH - self.x, j * R.PITCH - self.y) \
                            <= self.r - 0.005:
                        mask[j, i] = True
        elif self.kind == "pad":
            for (i, j) in self.pad_cells:
                if 0 <= i < R.W and 0 <= j < R.H:
                    mask[j, i] = True
        elif self.kind == "pour":
            mask |= fill_cells([self.poly])
        return mask


def fill_cells(polys):
    """Grid cells covered by filled polygons."""
    m = np.zeros((R.H, R.W), bool)
    for poly in polys:
        ys = [p[1] for p in poly]
        j0 = max(0, int(min(ys) / R.PITCH))
        j1 = min(R.H - 1, int(max(ys) / R.PITCH) + 1)
        edges = [(poly[k][1], poly[(k + 1) % len(poly)][1],
                  poly[k][0], poly[(k + 1) % len(poly)][0])
                 for k in range(len(poly))]
        for j in range(j0, j1 + 1):
            y = j * R.PITCH
            xs = [x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                  for (y0, y1, x0, x1) in edges if (y0 > y) != (y1 > y)]
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                i0 = max(0, int(math.ceil(xs[k] / R.PITCH)))
                i1 = min(R.W - 1, int(xs[k + 1] / R.PITCH))
                if i1 >= i0:
                    m[j, i0:i1 + 1] = True
    return m


def interior_point(poly):
    """A point well inside a polygon."""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    best, best_d = None, -1.0
    y = min(ys) + 0.1
    while y < max(ys) - 0.1:
        x = min(xs) + 0.1
        while x < max(xs) - 0.1:
            if inside((x, y), poly):
                d = min(pt_seg(np.array([x, y], float),
                               np.array(poly[k], float),
                               np.array(poly[(k + 1) % len(poly)], float))
                        for k in range(len(poly)))
                if d > best_d:
                    best, best_d = (x, y), d
            x += 0.1
        y += 0.1
    return best


def _segs_walkable(segs, walk, net):
    """Would every sample of these segments sit on walkable ground?"""
    for s in segs:
        a = np.array(s["start"], float)
        b = np.array(s["end"], float)
        n = max(2, int(np.linalg.norm(b - a) / 0.05))
        w = walk[R.ROUTABLE.index(s["layer"])]
        for k in range(n + 1):
            q = a + (b - a) * k / n
            i, j = int(round(q[0] / R.PITCH)), int(round(q[1] / R.PITCH))
            if not (0 <= i < R.W and 0 <= j < R.H) or not w[j, i]:
                return False
    return True


# ---------------------------------------------------------------------------
# items of a net
# ---------------------------------------------------------------------------


def net_items(board, model, net, with_pours=True):
    items = []
    for s in board.net_segments.get(net, []):
        if s["layer"] not in R.ROUTABLE:
            continue
        items.append(Item("track", s["layer"], p0=tuple(s["start"]),
                          p1=tuple(s["end"]), w=s["width"], src=s))
    for v in board.net_vias.get(net, []):
        for lyr in R.ROUTABLE:
            items.append(Item("via", lyr, x=v["x"], y=v["y"],
                              r=v["dia"] / 2.0, src=v))
    for p in board.pads_of.get(net, []):
        for lyr in R.ROUTABLE:
            if lyr not in p["cu_layers"]:
                continue
            items.append(Item("pad", lyr, shape=board._shape_from_pad(p),
                              pad_cells=p["cells"], ref=p["ref"], num=p["num"]))
    if with_pours:
        import pcbnew
        pcb = pcbnew.LoadBoard(str(PCB))
        for z in pcb.Zones():
            if z.GetIsRuleArea() or z.GetNetname() != net:
                continue
            for lyr in R.ROUTABLE:
                lid = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu,
                       "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}[lyr]
                if not z.IsOnLayer(lid):
                    continue
                polys = z.GetFilledPolysList(lid)
                for k in range(polys.OutlineCount()):
                    o = polys.Outline(k)
                    pts = [(o.CPoint(t).x / 1e6, o.CPoint(t).y / 1e6)
                           for t in range(o.PointCount())]
                    if len(pts) >= 3:
                        items.append(Item("pour", lyr, poly=pts,
                                          zone=z.GetZoneName()))
    return items


def components(items):
    """Union-find over items that really touch."""
    n = len(items)
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for a in range(n):
        for b in range(a + 1, n):
            if items[a].kind == "via" and items[b].kind == "via" \
                    and items[a].x == items[b].x and items[a].y == items[b].y:
                par[find(a)] = find(b)      # same via on two layers
                continue
            if items[a].gap(items[b]) <= 0.0:
                par[find(a)] = find(b)
    groups = {}
    for k in range(n):
        groups.setdefault(find(k), []).append(k)
    return list(groups.values())


def describe(it):
    if it.kind == "track":
        return f"track {it.layer} [{it.p0[0]:.2f},{it.p0[1]:.2f}]->" \
               f"[{it.p1[0]:.2f},{it.p1[1]:.2f}] w{it.w}"
    if it.kind == "via":
        return f"via {it.layer} ({it.x:.2f},{it.y:.2f})"
    if it.kind == "pad":
        return f"pad {it.ref}.{it.num} ({it.layer})"
    return f"pour {it.zone} on {it.layer} ({len(it.poly)} pts)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nets")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-pours", action="store_true")
    ap.add_argument("--width", default=None,
                    help="preferred track width(s) for the new copper, "
                         "comma separated, tried in order (mm); defaults to "
                         "the net class width ladder")
    ap.add_argument("--list", action="store_true",
                    help="list the copper components of every net and stop")
    ap.add_argument("--verbose", action="store_true",
                    help="print every segment / via a bridge adds")
    ap.add_argument("--expand", type=int, default=550000,
                    help="A* expansion budget per attempt (default 550000)")
    ap.add_argument("--small-via", action="store_true",
                    help="only retry a failed gap with 0.4/0.2 vias")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=print)
    rtr = sess.rtr
    added_segs, added_vias = [], []

    for net in args.nets.split(","):
        if net not in board.pads_of and net not in board.net_segments:
            print(f"{net}: no pads and no copper - skip")
            continue
        params = R.net_params(net)
        widths = R.width_ladder(params)
        if args.width:
            pref = [float(x) for x in args.width.split(",")]
            widths = pref + [w for w in widths if w < min(pref)]
        items = net_items(board, model, net, not args.no_pours)
        groups = components(items)
        print(f"{net}: {len(items)} copper items in {len(groups)} component(s)")
        if args.list:
            for k, grp in enumerate(groups):
                print(f"  component {k + 1}:")
                for kk in grp:
                    print(f"     {describe(items[kk])}")
            continue
        while len(groups) > 1:
            # pair of components with the smallest copper-to-copper gap
            best = None
            for a in range(len(groups)):
                for b in range(a + 1, len(groups)):
                    for ia in groups[a]:
                        for ib in groups[b]:
                            d = items[ia].gap(items[ib])
                            if d < math.inf and (best is None or d < best[0]):
                                best = (d, a, b, ia, ib)
            if best is None:
                print("  no measurable gap between components - stop")
                break
            gap, a, b, ia, ib = best
            A = [items[k] for k in groups[a]]
            B = [items[k] for k in groups[b]]
            print(f"  gap {gap:6.3f} mm: {describe(items[ia])[:52]} || "
                  f"{describe(items[ib])[:52]}")

            # sources: the copper of component A that is close to B
            src = {lyr: np.zeros((R.H, R.W), bool) for lyr in R.ROUTABLE}
            for it in A:
                # compare layer by layer: a source that exists on the same
                # layer as the target must not be dropped just because the
                # via penalty would push it over the limit
                if it._gap_same_layer(items[ib]) <= gap + 1.6:
                    it.mark(src[it.layer], exact=True)
            tree = [(li, i, j) for li, lyr in enumerate(R.ROUTABLE)
                    for (j, i) in np.argwhere(src[lyr])]
            if not tree:
                print("    component A has no cells to start from - stop")
                break

            # target: the copper of B that is near the gap.  Offering *all* of
            # it (not only the single nearest item) lets the maze terminate on
            # an existing via or a neighbouring track instead of dropping a
            # second via right next to the first one.
            tgt = items[ib]
            nearB = [it for it in B
                     if it._gap_same_layer(items[ia]) <= gap + 1.0]
            ref = None
            if tgt.kind == "pour":
                pt = interior_point(tgt.poly)
                ref = (int(round(pt[0] / R.PITCH)), int(round(pt[1] / R.PITCH)))
            elif tgt.kind == "track":
                mid = ((tgt.p0[0] + tgt.p1[0]) / 2, (tgt.p0[1] + tgt.p1[1]) / 2)
                ref = (int(round(mid[0] / R.PITCH)), int(round(mid[1] / R.PITCH)))
            elif tgt.kind == "via":
                ref = (int(round(tgt.x / R.PITCH)), int(round(tgt.y / R.PITCH)))
            else:
                cx = sum(c[0] for c in tgt.pad_cells) / len(tgt.pad_cells)
                cy = sum(c[1] for c in tgt.pad_cells) / len(tgt.pad_cells)
                ref = (int(round(cx)), int(round(cy)))

            done = False
            # first with the net class via, then (only if that fails) with the
            # project's smallest allowed via - a 0.4 mm via fits in pockets a
            # 0.6 mm one cannot enter
            tries = [(w, None) for w in widths]
            if not args.small_via:
                tries += [(w, (0.4, 0.2)) for w in widths]
            for w, via in tries:
                sess.mask_cache.clear()
                m, via_ok, dia, drill, soft = sess.masks_for(net, w, False,
                                                             via=via)
                walk = [m[lyr][0] for lyr in R.ROUTABLE]
                slack = [m[lyr][1] for lyr in R.ROUTABLE]
                target = [None] * len(R.ROUTABLE)
                for it in nearB:
                    li = R.ROUTABLE.index(it.layer)
                    if target[li] is None:
                        target[li] = np.zeros((R.H, R.W), bool)
                    if it.kind == "track":
                        # aim for the track's *ends*: landing in the middle of
                        # an existing run would leave the far end dangling
                        a = np.array(it.p0, float)
                        b = np.array(it.p1, float)
                        for q in (a, b):
                            i, j = (int(round(q[0] / R.PITCH)),
                                    int(round(q[1] / R.PITCH)))
                            r = max(2, int(0.35 / R.PITCH))
                            for jj in range(max(0, j - r), min(R.H - 1, j + r) + 1):
                                for ii in range(max(0, i - r),
                                                min(R.W - 1, i + r) + 1):
                                    if math.hypot(ii * R.PITCH - q[0],
                                                  jj * R.PITCH - q[1]) <= 0.35:
                                        target[li][jj, ii] = True
                    else:
                        it.mark(target[li], exact=(it.kind != "pour"))
                if tgt.kind == "pour":
                    # a pour has to be entered where the copper really is
                    li = R.ROUTABLE.index(tgt.layer)
                    if target[li] is None:
                        target[li] = np.zeros((R.H, R.W), bool)
                    target[li][ref[1], ref[0]] = True
                if net in R.NO_VIA:
                    via_ok = np.zeros_like(via_ok)
                path = rtr.astar(walk, slack, target, tree, via_ok,
                                 ref_ij=ref, slack_slack=R.DIAG_MARGIN,
                                 max_expand=args.expand)
                if path is None:
                    continue
                snap_start = None
                if tgt.kind == "pad" and tgt.layer == R.ROUTABLE[path[-1][0]]:
                    for p in board.pads_of.get(net, []):
                        if (p["ref"], p["num"]) == (tgt.ref, tgt.num):
                            li, i, j = path[-1]
                            off = math.hypot(i * R.PITCH - p["x"],
                                             j * R.PITCH - p["y"])
                            # stretching a long last vertex onto the pad centre
                            # sweeps across whatever sits beside the pad, so
                            # only a short, harmless move is allowed
                            if off <= 0.20:
                                snap_start = (p["x"], p["y"])
                segs2, vias2, _ = R.emit_path(path, w, net,
                                              snap_end=snap_start)
                # the snap is a shortcut, not a guarantee: if it pushed the
                # track into something, keep the un-snapped geometry
                if snap_start is not None:
                    walk = [m[lyr][0] for lyr in R.ROUTABLE]
                    if not _segs_walkable(segs2, walk, net):
                        segs2, vias2, _ = R.emit_path(path, w, net)
                for s in segs2:
                    s["kind"] = "route"
                for v in vias2:
                    v["dia"], v["drill"] = dia, drill
                board.net_segments.setdefault(net, []).extend(segs2)
                board.net_vias.setdefault(net, []).extend(vias2)
                added_segs.extend(segs2)
                added_vias.extend(vias2)
                for s in segs2:
                    items.append(Item("track", s["layer"],
                                      p0=tuple(s["start"]), p1=tuple(s["end"]),
                                      w=s["width"], src=s))
                for v in vias2:
                    for lyr in R.ROUTABLE:
                        items.append(Item("via", lyr, x=v["x"], y=v["y"],
                                          r=v["dia"] / 2.0, src=v))
                print(f"    bridged with {len(segs2)} seg w{w:.2f} + "
                      f"{len(vias2)} via")
                if args.verbose:
                    for s in segs2:
                        print(f"       {s['layer']:<6s} {s['start']} -> "
                              f"{s['end']}")
                    for v in vias2:
                        print(f"       VIA ({v['x']:.3f},{v['y']:.3f}) "
                              f"{v['dia']}/{v['drill']}")
                # the obstacle model has to see the copper we just added -
                # otherwise the *next* net in the same run would be routed
                # straight through it
                sess.b.rebuild_copper()
                sess.mask_cache.clear()
                done = True
                break
            if not done:
                print("    NO LEGAL PATH - leaving this gap open")
                break
            groups = components(items)

    print(f"added {len(added_segs)} segments, {len(added_vias)} vias")
    if args.dry_run or not added_segs:
        return 0
    sess.rebuild_necks()
    segs, vias = board.copper()
    data["segments"] = segs
    data["vias"] = [v for v in vias if "kind" not in v]
    uniq = {}
    for v in vias:
        if "kind" in v:
            uniq[(round(v["x"], 3), round(v["y"], 3), v["net"])] = v
    data["gnd_vias"] = list(uniq.values())
    data["neck_segments"] = [
        {"layer": s["layer"], "net": s["net"], "width": s["width"],
         "class": R.netclass_of(s["net"]), "start": s["start"], "end": s["end"]}
        for s in sess.neck_segments]
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
