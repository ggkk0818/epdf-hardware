"""Insert a 45-degree accordion serpentine into an existing straight track, to
add a precise amount of length for differential-pair skew matching.

    python tools/serpentine.py --net USB_DP_CONN \
        --seg 644.5,2260.4,644.5,624.2 --span 460,972 \
        --ampl 32 --teeth 8 --width 10 --layer 2 --out work/serp-dpconn.json

Emits an edit file for tools/apply_edits.py and verifies every new segment
against the exact clearance oracle before writing it.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import clearance  # noqa: E402
import geom       # noqa: E402
import subprocess  # noqa: E402


def build(x1, y1, x2, y2, span, ampl, teeth, width):
    L = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    vx, vy = uy, -ux
    t0, t1 = span
    footprint = 2.0 * ampl * teeth
    if t1 - t0 < footprint - 1e-6:
        raise SystemExit(f"span {t1-t0:.0f} < footprint {footprint:.0f}")
    pad = (t1 - t0 - footprint) / 2.0
    sx = x1 + ux * (t0 + pad)
    sy = y1 + uy * (t0 + pad)
    pts = [(sx, sy)]
    cx, cy = sx, sy
    for _ in range(teeth):
        cx += ux * ampl + vx * ampl
        cy += uy * ampl + vy * ampl
        pts.append((cx, cy))
        cx += ux * ampl - vx * ampl
        cy += uy * ampl - vy * ampl
        pts.append((cx, cy))
    poly = [(x1, y1)] + pts + [(x2, y2)]
    poly = _dedupe(poly)
    added = teeth * 2 * (ampl * math.sqrt(2) - ampl)
    return poly, added


def _dedupe(pts):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return out


def search(args):
    """Slide a serpentine window along a run and report the feasible placements."""
    x1, y1, x2, y2 = [float(v) for v in args.seg.split(",")]
    L = math.hypot(x2 - x1, y2 - y1)
    g = geom.load()
    target = None
    for t in g["tracks"]:
        if t.get("net") != args.net or t["layer"] != args.layer:
            continue
        a = (round(t["startX"], 1), round(t["startY"], 1))
        b = (round(t["endX"], 1), round(t["endY"], 1))
        if {a, b} == {(round(x1, 1), round(y1, 1)), (round(x2, 1), round(y2, 1))}:
            target = t
            break
    if target is None:
        raise SystemExit("segment not found")
    oracle = clearance.Oracle(net=args.net, ignore={target["primitiveId"]})
    print(f"search on {L:.0f} mil run, need +{args.need:.0f} mil, width {args.width}")
    for ampl in args.amplitudes:
        teeth = max(1, round(args.need / (2 * ampl * (math.sqrt(2) - 1))))
        foot = 2 * ampl * teeth
        added = teeth * 2 * (ampl * math.sqrt(2) - ampl)
        best = None
        t0 = 0.0
        while t0 + foot <= L + 1e-6:
            poly, _ = build(x1, y1, x2, y2, (t0, t0 + foot), ampl, teeth, args.width)
            worst = 1e9
            for k in range(len(poly) - 1):
                m, _w = oracle.seg_margin(poly[k][0], poly[k][1], poly[k + 1][0],
                                          poly[k + 1][1], args.width, args.layer)
                worst = min(worst, m)
            if best is None or worst > best[0]:
                best = (worst, t0)
            t0 += 10.0
        if best:
            print(f"  ampl {ampl:5.1f} teeth {teeth} footprint {foot:6.1f} "
                  f"added {added:6.1f}  best window t0={best[0+1]:7.1f} "
                  f"margin {best[0]:6.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", required=True)
    ap.add_argument("--seg", required=True, help="x1,y1,x2,y2 of the track to replace")
    ap.add_argument("--span", required=True, help="t0,t1 distance from segment start")
    ap.add_argument("--ampl", type=float, required=True)
    ap.add_argument("--teeth", type=int, required=True)
    ap.add_argument("--width", type=float, default=10.0)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--search", action="store_true",
                    help="scan placements instead of emitting an edit")
    ap.add_argument("--need", type=float, default=212.0)
    ap.add_argument("--amplitudes", type=float, nargs="*",
                    default=[24, 28, 32, 36, 40, 44])
    args = ap.parse_args()

    if args.search:
        search(args)
        return

    x1, y1, x2, y2 = [float(v) for v in args.seg.split(",")]
    t0, t1 = [float(v) for v in args.span.split(",")]
    poly, added = build(x1, y1, x2, y2, (t0, t1), args.ampl, args.teeth, args.width)

    g = geom.load()
    target = None
    for t in g["tracks"]:
        if t.get("net") != args.net or t["layer"] != args.layer:
            continue
        a = (round(t["startX"], 1), round(t["startY"], 1))
        b = (round(t["endX"], 1), round(t["endY"], 1))
        if (a == (round(x1, 1), round(y1, 1)) and b == (round(x2, 1), round(y2, 1))) or \
           (b == (round(x1, 1), round(y1, 1)) and a == (round(x2, 1), round(y2, 1))):
            target = t
            break
    if target is None:
        raise SystemExit("target track not found")

    oracle = clearance.Oracle(net=args.net, ignore={target["primitiveId"]})
    segs = []
    worst = 1e9
    who = None
    for k in range(len(poly) - 1):
        m, w = oracle.seg_margin(poly[k][0], poly[k][1], poly[k + 1][0],
                                 poly[k + 1][1], args.width, args.layer)
        if m < worst:
            worst, who = m, w
        segs.append({"x1": round(poly[k][0], 2), "y1": round(poly[k][1], 2),
                     "x2": round(poly[k + 1][0], 2), "y2": round(poly[k + 1][1], 2),
                     "layer": args.layer, "width": args.width, "net": args.net})
    old_len = math.hypot(x2 - x1, y2 - y1)
    new_len = sum(math.hypot(s["x2"] - s["x1"], s["y2"] - s["y1"]) for s in segs)
    print(f"replace {old_len:.1f} mil run with {new_len:.1f} mil  "
          f"(+{new_len-old_len:.1f} mil, expected +{added:.1f})")
    print(f"worst clearance margin {worst:.2f} mil vs {who}")
    print(f"segments emitted: {len(segs)}")
    if worst < 0:
        raise SystemExit("ABORT: clearance violation in serpentine")
    edit = {"delete": {"tracks": [target["primitiveId"]]}, "tracks": segs}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(edit, fh, ensure_ascii=False, indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
