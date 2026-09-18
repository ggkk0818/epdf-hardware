"""Read-only GND copper component map (MD Checkpoint M).

    python tools/gnd_components.py

Rasterises every piece of GND copper on the router grid - tracks, vias, pads and
the *filled* polygons of the GND pours - labels the connected components and
prints one line per component: layers, bbox, area, how many pads / vias / tracks
it holds, whether it reaches the In1 GND plane (MAIN_GND) and how far it is from
MAIN_GND.  Nothing is modified.
"""

from __future__ import annotations

import json
import math
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pcbnew  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"
LAY = {pcbnew.F_Cu: "F.Cu", pcbnew.In1_Cu: "In1.Cu",
       pcbnew.In2_Cu: "In2.Cu", pcbnew.B_Cu: "B.Cu"}


def pour_cells():
    """(layer, polygon, zone name) of every filled GND pour."""
    board = pcbnew.LoadBoard(str(PCB))
    out = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND":
            continue
        for lid, name in LAY.items():
            if not z.IsOnLayer(lid):
                continue
            ps = z.GetFilledPolysList(lid)
            for k in range(ps.OutlineCount()):
                o = ps.Outline(k)
                pts = [(o.CPoint(t).x / 1e6, o.CPoint(t).y / 1e6)
                       for t in range(o.PointCount())]
                if len(pts) >= 3:
                    out.append((name, pts, z.GetZoneName()))
    return out


def poly_cells(poly):
    m = np.zeros((R.H, R.W), bool)
    ys = [q[1] for q in poly]
    j0 = max(0, int(min(ys) / R.PITCH))
    j1 = min(R.H - 1, int(max(ys) / R.PITCH) + 1)
    edges = [(poly[k][1], poly[(k + 1) % len(poly)][1],
              poly[k][0], poly[(k + 1) % len(poly)][0])
             for k in range(len(poly))]
    for j in range(j0, j1 + 1):
        y = j * R.PITCH
        xs = sorted(x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    for (y0, y1, x0, x1) in edges if (y0 > y) != (y1 > y))
        for k in range(0, len(xs) - 1, 2):
            i0 = max(0, int(math.ceil(xs[k] / R.PITCH)))
            i1 = min(R.W - 1, int(xs[k + 1] / R.PITCH))
            if i1 >= i0:
                m[j, i0:i1 + 1] = True
    return m


def analyse(with_candidates=False):
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)

    mask = {lyr: np.zeros((R.H, R.W), bool) for lyr in R.ALL_CU}
    # copper only changes layer inside a via (or a plated through hole) - the
    # V1 solver linked any two layers that happened to overlap in XY, which is
    # not a physical connection (MD GND Connectivity Solver V2 §2)
    via_like = np.zeros((R.H, R.W), bool)
    owner = {lyr: {} for lyr in R.ALL_CU}      # cell -> item label

    def mark(lyr, cells, half_w, label):
        """exact rasterisation: a cell belongs to the copper only when its
        centre is really inside (mark_cells dilates and would merge pieces)"""
        m = np.zeros((R.H, R.W), bool)
        d = int(math.ceil((half_w + 0.001) / R.PITCH))
        for (_, i, j) in cells:
            for jj in range(max(0, j - d), min(R.H - 1, j + d) + 1):
                for ii in range(max(0, i - d), min(R.W - 1, i + d) + 1):
                    if math.hypot((ii - i) * R.PITCH, (jj - j) * R.PITCH) \
                            <= half_w + 1e-9:
                        m[jj, ii] = True
        mask[lyr] |= m
        ys, xs = np.nonzero(m)
        for j, i in zip(ys, xs):
            owner[lyr].setdefault((i, j), label)

    for s in board.net_segments.get("GND", []):
        if s["layer"] not in R.ALL_CU:
            continue
        a, b = s["start"], s["end"]
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / R.PITCH))
        cells = [(0, int(round((a[0] + (b[0] - a[0]) * t / n) / R.PITCH)),
                  int(round((a[1] + (b[1] - a[1]) * t / n) / R.PITCH)))
                 for t in range(n + 1)]
        mark(s["layer"], cells, s["width"] / 2.0, f"track@{a}")
    for v in board.net_vias.get("GND", []):
        for lyr in R.ALL_CU:
            i, j = int(round(v["x"] / R.PITCH)), int(round(v["y"] / R.PITCH))
            mark(lyr, [(0, i, j)], v["dia"] / 2.0, f"via@{v['x']},{v['y']}")
        r = v["dia"] / 2.0
        d = int(math.ceil((r + 0.001) / R.PITCH))
        ci, cj = int(round(v["x"] / R.PITCH)), int(round(v["y"] / R.PITCH))
        for jj in range(max(0, cj - d), min(R.H - 1, cj + d) + 1):
            for ii in range(max(0, ci - d), min(R.W - 1, ci + d) + 1):
                if math.hypot((ii - ci) * R.PITCH,
                              (jj - cj) * R.PITCH) <= r + 1e-9:
                    via_like[jj, ii] = True
    for p in board.pads_of.get("GND", []):
        for lyr in [l for l in R.ALL_CU if l in p["cu_layers"]]:
            mark(lyr, [(0, i, j) for (i, j) in p["cells"]], 0.001,
                 f"pad@{p['ref']}.{p['num']}")
        if p["type"] == "pth":
            for (i, j) in p["cells"]:
                via_like[j, i] = True
    pours = pour_cells()
    pour_cell_sets = {}
    for (lyr, poly, zname) in pours:
        m = poly_cells(poly)
        mask[lyr] |= m
        key = (lyr, zname, round(min(q[0] for q in poly), 2),
               round(min(q[1] for q in poly), 2))
        pour_cell_sets[key] = m
        ys, xs = np.nonzero(m)
        for j, i in zip(ys, xs):
            owner[lyr].setdefault((i, j), f"pour@{zname}")

    # label components across layers (a via is marked on every layer, so the
    # layers join through it automatically)
    lab = np.zeros((len(R.ALL_CU), R.H, R.W), np.int32)
    nxt = 0
    for li, lyr in enumerate(R.ALL_CU):
        m = mask[lyr]
        ys, xs = np.nonzero(m)
        for j, i in zip(ys, xs):
            if lab[li, j, i]:
                continue
            nxt += 1
            q = deque([(li, i, j)])
            lab[li, j, i] = nxt
            while q:
                L, x, y = q.popleft()
                for dL in range(len(R.ALL_CU)) if via_like[y, x] else ():
                    if dL == L or not mask[R.ALL_CU[dL]][y, x] \
                            or lab[dL, y, x]:
                        continue
                    lab[dL, y, x] = nxt
                    q.append((dL, x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < R.W and 0 <= ny < R.H \
                            and mask[R.ALL_CU[L]][ny, nx] \
                            and not lab[L, ny, nx]:
                        lab[L, ny, nx] = nxt
                        q.append((L, nx, ny))
    print(f"GND copper components: {nxt}")
    plane = None
    for li, lyr in enumerate(R.ALL_CU):
        ys, xs = np.nonzero(mask[lyr])
        if lyr == "In1.Cu" and len(ys):
            plane = lab[li, ys[0], xs[0]]
            break
    vmask = None
    if with_candidates:
        import route as _R
        sess = _R.Session(board, log=lambda *a: None)
        vmask = sess.rtr.via_mask("GND", 0.2, 0.1,
                                  _R.net_params("GND")["clearance"])
    for k in range(1, nxt + 1):
        cells = np.argwhere(lab == k)
        if not len(cells):
            continue
        lys = sorted({R.ALL_CU[li] for li, _, _ in cells})
        js, xs_ = cells[:, 1], cells[:, 2]
        area = sum(int((lab[li] == k).sum()) for li in range(len(R.ALL_CU)))
        items = set()
        for li, j, i in cells:
            t = owner[R.ALL_CU[li]].get((i, j))
            if t:
                items.add(t)
        pads = sorted(t[4:] for t in items if t.startswith("pad@"))
        vias = sum(1 for t in items if t.startswith("via@"))
        tracks = sum(1 for t in items if t.startswith("track@"))
        name = "MAIN_GND" if (plane and k == plane) else f"ORPHAN_{k:03d}"
        print(f"  {name:<12s} layers={','.join(lys):<22s} "
              f"bbox=({xs_.min() * R.PITCH:.1f},{js.min() * R.PITCH:.1f})-"
              f"({xs_.max() * R.PITCH:.1f},{js.max() * R.PITCH:.1f}) "
              f"cells={area} tracks={tracks} vias={vias} pads={len(pads)}")
        if pads:
            print(f"      pads: {' '.join(pads[:12])}"
                  f"{' ...' if len(pads) > 12 else ''}")
        if with_candidates and not (plane and k == plane):
            cands = []
            for li, j, i in cells:
                if R.ALL_CU[li] != "F.Cu" or not vmask[j, i]:
                    continue
                # margin = distance to the nearest cell that is *not* in this
                # patch (a big margin means a roomy spot, away from the edges)
                m = 0
                while m < 8:
                    r = m + 1
                    ok = all(0 <= i + a < R.W and 0 <= j + b < R.H
                             and lab[li, j + b, i + a] == k
                             for a, b in ((r, 0), (-r, 0), (0, r), (0, -r)))
                    if not ok:
                        break
                    m = r
                cands.append((m * R.PITCH, i * R.PITCH, j * R.PITCH))
            cands.sort(reverse=True)
            print(f"      off-pad via candidates (margin, x, y): "
                  f"{[(round(c[0], 2), round(c[1], 2), round(c[2], 2)) for c in cands[:4]]}")


def main():
    analyse()


if __name__ == "__main__":
    main()
