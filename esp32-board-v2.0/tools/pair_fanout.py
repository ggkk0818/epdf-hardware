"""Close a coupled pair's ends onto their pads (the fan-out the router omits).

    python tools/pair_fanout.py --plan work/pair-usb0.json --layer 2 \
        --pos USB_DP_CONN --neg USB_DN_CONN \
        --pos-start 935,264 --neg-start 954.7,264 \
        --pos-end 610,2370.3 --neg-end 650,2370.3 --out work/fan-usb0.json

The planner emits a centreline +/- offset, so a trace ends a few mil away from
its pad (and on the inner layer).  This finds each chain's free ends, assigns
them to the nearest given pad and adds a validated (<=3 segment) link: an
in-pad via plus a short top-layer stub when a layer change is needed.
"""

import argparse
import collections
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clearance  # noqa: E402
import geom  # noqa: E402

ROOT = geom.ROOT
VIA = {"diameter": 24, "hole": 12}


def chain_ends(tracks):
    """Free ends of a polyline chain: endpoints used exactly once."""
    cnt = collections.Counter()
    for t in tracks:
        cnt[(round(t["x1"], 1), round(t["y1"], 1))] += 1
        cnt[(round(t["x2"], 1), round(t["y2"], 1))] += 1
    return [p for p, c in cnt.items() if c == 1]


def paths(pad, target):
    px, py = pad
    tx, ty = target
    cands = [[(px, py), (tx, py), (tx, ty)], [(px, py), (px, ty), (tx, ty)],
             [(px, py), (tx, ty)]]
    # 45-degree doglegs first: they step clear of the same-row neighbour pads
    L = math.hypot(tx - px, ty - py)
    if L > 1:
        ux, uy = (tx - px) / L, (ty - py) / L
        for k in (20.0, 30.0, 40.0, 60.0):
            for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                kx, ky = px + sx * k, py + sy * k
                cands.append([(px, py), (kx, ky), (tx, ky), (tx, ty)])
                cands.append([(px, py), (kx, ky), (kx, ty), (tx, ty)])
    return cands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--width", type=float, default=9.449)
    ap.add_argument("--pads", default=None,
                    help="JSON {net: [[x,y] start, [x,y] end]}")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    plan = json.load(open(args.plan, encoding="utf-8"))
    pads = json.loads(args.pads)
    geom.dump(os.path.join(ROOT, "work", "geom.json"))
    g = geom.load(os.path.join(ROOT, "work", "geom.json"))

    out = {"tracks": list(plan.get("tracks") or []),
           "vias": list(plan.get("vias") or [])}
    layers = {}
    for t in plan["tracks"]:
        layers.setdefault(t["net"], t["layer"])
    for net, entry in pads.items():
        if isinstance(entry, dict):
            ps, pe = entry.get("start"), entry.get("end")
        else:
            ps, pe = entry[0], entry[1]
        ts = [t for t in plan["tracks"] if t["net"] == net]
        ends = chain_ends(ts)
        lane_layer = layers.get(net, args.layer)
        # The pair's two traces swap sides at the ends, so a fan-out that stays
        # on the lane layer has to cross its partner.  Instead: via at the lane
        # end, then fan out on the PAD layer (L1), where the partner's L2 lane
        # is simply not an obstacle.
        layer = 1
        # the net's own pads are the destination, not obstacles
        own = set()
        for c in g["components"]:
            for p in c.get("pads") or []:
                if p.get("net") == net and p.get("primitiveId"):
                    own.add(p["primitiveId"])
        for t in geom.load()["tracks"]:
            if t.get("net") == net:
                own.add(t["primitiveId"])
        oracle = clearance.Oracle(net=net, ignore=own)
        for target in (tuple(ps), tuple(pe)):
            if not ends:
                continue
            # nearest free end to this pad
            end = min(ends, key=lambda e: math.hypot(e[0] - target[0],
                                                     e[1] - target[1]))
            ends.remove(end)
            d0 = math.hypot(end[0] - target[0], end[1] - target[1])
            best = None
            for pts in paths(end, target):
                worst, who = 1e9, "none"
                for a, b in zip(pts, pts[1:]):
                    if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.5:
                        continue
                    mm, ww = oracle.seg_margin(a[0], a[1], b[0], b[1],
                                               args.width, layer)
                    if mm < worst:
                        worst, who = mm, ww
                if worst >= 3.0:
                    best, m = pts, worst
                    break
                if worst > (best[1] if isinstance(best, tuple) else -99):
                    pass
            if not best:
                print(f"  ! {net} end {end} -> pad {target}: no clear path")
                continue
            if lane_layer != layer:
                out["vias"].append({"x": round(end[0], 2), "y": round(end[1], 2),
                                    "net": net, **VIA})
            for a, b in zip(best, best[1:]):
                if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.5:
                    continue
                out["tracks"].append({"x1": round(a[0], 2), "y1": round(a[1], 2),
                                      "x2": round(b[0], 2), "y2": round(b[1], 2),
                                      "layer": layer, "width": args.width,
                                      "net": net})
            out["vias"].append({"x": round(target[0], 2), "y": round(target[1], 2),
                                "net": net, **VIA})
            print(f"  {net:<13} end {end} -> pad {target} d={d0:.1f} "
                  f"{len(best)-1} seg(s) + in-pad via margin={m:.2f}")
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    print(f"tracks {len(out['tracks'])}, vias {len(out['vias'])} -> {args.out}")


if __name__ == "__main__":
    main()
