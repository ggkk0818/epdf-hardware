"""Why can TPS_EN / TPS_VSEL not reach their U3 pad? (debug helper)

    python tools/diag_tps_ctrl.py [net]

Floods the router's walk field from every anchor of the net and reports which
anchor is cut off, together with the foreign copper sitting in the corridor.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def flood(walk, seeds, it=400):
    """plain BFS over a 2-D bool mask, no vias"""
    seen = np.zeros_like(walk)
    from collections import deque
    q = deque()
    for (i, j) in seeds:
        if 0 <= i < walk.shape[1] and 0 <= j < walk.shape[0] and walk[j, i] \
                and not seen[j, i]:
            seen[j, i] = True
            q.append((i, j))
    while q:
        i, j = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < walk.shape[1] and 0 <= b < walk.shape[0] \
                    and walk[b, a] and not seen[b, a]:
                seen[b, a] = True
                q.append((a, b))
    return seen


def main():
    net = sys.argv[1] if len(sys.argv) > 1 else "TPS_VSEL"
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=print)
    params = R.net_params(net)
    pads = board.pads_of.get(net, [])
    print(f"net {net}: params {params}")
    print(f"pads: {[(p['ref'], p['num'], p['x'], p['y']) for p in pads]}")
    for pad in pads:
        key = (pad["ref"], pad["num"])
        sess.mask_cache.clear()
        sess.make_stub(net, pad, params, key)
    print("stubs:", {k: v["tip"] for k, v in sess.stubs.items()})

    for w in R.width_ladder(params):
        sess.mask_cache.clear()
        m, via_ok, via_dia, via_drill, soft = sess.masks_for(net, w, False)
        walk = {lyr: m[lyr][0] for lyr in R.ROUTABLE}
        print(f"-- width {w:.2f} walkable cells "
              f"{ {lyr: int(walk[lyr].sum()) for lyr in R.ROUTABLE} }")
        for pad in pads:
            key = (pad["ref"], pad["num"])
            st = sess.stubs.get(key)
            if st:
                li, i, j = st["tip"]
                lyr = R.ROUTABLE[li]
                print(f"   {pad['ref']}.{pad['num']} stub tip {lyr} "
                      f"({i * R.PITCH:.2f},{j * R.PITCH:.2f}) "
                      f"walk={bool(walk[lyr][j, i])}")
            else:
                cells = [(li, i, j) for li, lyr in enumerate(R.ROUTABLE)
                         for (i, j) in pad["cells"] if lyr in pad["cu_layers"]]
                good = [c for c in cells if walk[R.ROUTABLE[c[0]]][c[2], c[1]]]
                print(f"   {pad['ref']}.{pad['num']} pad cells "
                      f"{len(good)}/{len(cells)} walkable "
                      f"({len(pad['cu_layers'])} cu layers)")
        # connectivity between the two pads
        for lextra, name in ((True, "with vias"),):
            seeds = []
            for pad in pads:
                key = (pad["ref"], pad["num"])
                st = sess.stubs.get(key)
                if st:
                    seeds.append((st["tip"][0], st["tip"][1], st["tip"][2]))
                else:
                    seeds += [(li, i, j) for li, lyr in enumerate(R.ROUTABLE)
                              for (i, j) in pad["cells"]
                              if lyr in pad["cu_layers"]]
            src = seeds[0]
            seen = flood(walk[R.ROUTABLE[src[0]]], [(src[1], src[2])])
            for tgt in seeds[1:]:
                lyr = R.ROUTABLE[tgt[0]]
                print(f"   {name}: from {R.ROUTABLE[src[0]]} seed to "
                      f"{lyr}({tgt[1]},{tgt[2]}) same-layer reach = "
                      f"{bool(seen[tgt[2], tgt[1]])}")
        break

    # what sits in the corridor between U3 and R28 / R26
    x0, y0, x1, y1 = 27.0, 40.0, 34.0, 49.0
    print(f"-- foreign copper in ({x0},{y0})-({x1},{y1})")
    for n, segs in board.net_segments.items():
        if n == net:
            continue
        for s in segs:
            sx, sy = s["start"]
            ex, ey = s["end"]
            if max(sx, ex) < x0 or min(sx, ex) > x1:
                continue
            if max(sy, ey) < y0 or min(sy, ey) > y1:
                continue
            print(f"   {n:<13s} {s['layer']:<6s} {s.get('kind', '-'):<5s} "
                  f"[{sx:.2f},{sy:.2f}]->[{ex:.2f},{ey:.2f}] w{s['width']}")
    for p in model["pads"]:
        if x0 <= p["x"] <= x1 and y0 <= p["y"] <= y1 and p["net"] != net:
            print(f"   PAD {p['ref']}.{p['num']:<3s} [{p['net']:<13s}] "
                  f"({p['x']:.3f},{p['y']:.3f}) {p['w']}x{p['h']}")


if __name__ == "__main__":
    main()
