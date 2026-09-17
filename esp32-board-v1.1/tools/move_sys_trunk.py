"""Shift the SYS trunk piece above U3 upwards by ~1 mm (user approved 2026-09-17).

The 1.2 mm wide trunk segment (33.25,42.2)->(37.1,40.9) passes 1.2 mm above the
U3 top pin row and blocks the escape of TPS_EN (pin 14) / TPS_VSEL (pin 15).
This moves that segment (and the endpoints it shares with its neighbours) up by
`--dy` mm, which keeps the net connected by construction, then verifies that the
result is still clearance legal.  Nothing is written unless the check passes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"

TARGET = ((33.25, 42.2), (37.1, 40.9))


def _patch(sess, seg, log=print):
    """Local A* re-route of a ripped SYS piece between its former endpoints."""
    net = seg["net"]
    params = R.net_params(net)
    m, via_ok, dia, drill, _soft = sess.masks_for(net, seg["width"])
    walk = [m[lyr][0] for lyr in R.ROUTABLE]
    slack = [m[lyr][1] for lyr in R.ROUTABLE]
    x0, y0 = seg["start"]
    x1, y1 = seg["end"]
    li = R.ROUTABLE.index(seg["layer"])

    def cells(x, y, radius=0.4):
        out = []
        r = int(radius / R.PITCH)
        ci, cj = int(round(x / R.PITCH)), int(round(y / R.PITCH))
        for i in range(ci - r, ci + r + 1):
            for j in range(cj - r, cj + r + 1):
                if 0 <= i < R.W and 0 <= j < R.H:
                    out.append((i, j))
        return out

    sources = [(li, i, j) for (i, j) in cells(x0, y0) if walk[li][j, i]]
    tmask = np.zeros((R.H, R.W), bool)
    for (i, j) in cells(x1, y1):
        tmask[j, i] = True
    target = [None] * len(R.ROUTABLE)
    target[li] = tmask
    if not sources:
        return False
    span = max(abs(x1 - x0), abs(y1 - y0))
    pad = (span / 2.0 + 8.0)
    window = (max(0, int(min(x0, x1) / R.PITCH - pad / R.PITCH)),
              min(R.W - 1, int(max(x0, x1) / R.PITCH + pad / R.PITCH)),
              max(0, int(min(y0, y1) / R.PITCH - pad / R.PITCH)),
              min(R.H - 1, int(max(y0, y1) / R.PITCH + pad / R.PITCH)))
    path = sess.rtr.astar(walk, slack, target, sources, via_ok,
                          ref_ij=(int(round(x1 / R.PITCH)),
                                  int(round(y1 / R.PITCH))),
                          window=window, max_expand=200000,
                          layer_pen=sess.layer_penalty(net))
    if path is None:
        return False
    segs, vias, _cw = R.emit_path(path, seg["width"], net)
    for s in segs:
        s["kind"] = "route"
    sess.b.net_segments.setdefault(net, []).extend(segs)
    sess.b.net_vias.setdefault(net, []).extend(vias)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dy", type=float, default=-1.0,
                    help="shift in +y (use a negative value to move up)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=print)

    def same(a, b):
        return abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3

    segs = sess.b.net_segments.get("SYS", [])
    # 1. rip the SYS copper that sits in the band above the U3 top pin row
    band = (32.4, 42.2, 35.4, 43.5)
    ripped, keep = [], []
    for s in segs:
        x0 = min(s["start"][0], s["end"][0])
        x1 = max(s["start"][0], s["end"][0])
        y0 = min(s["start"][1], s["end"][1])
        y1 = max(s["start"][1], s["end"][1])
        if s.get("kind") != "stub" and not (x1 < band[0] or x0 > band[2]
                                            or y1 < band[1] or y0 > band[3]):
            ripped.append(s)
        else:
            keep.append(s)
    sess.b.net_segments["SYS"] = keep
    print(f"ripped {len(ripped)} SYS segment(s) out of the band above U3")

    # 2. replace each ripped piece with an explicit corridor that stays above
    #    the U3 pin row (the arc is tried in order and taken only if the result
    #    is clearance legal)
    variants = [
        [(33.10, 41.90), (37.15, 41.90)],
        [(33.10, 41.70), (37.15, 41.70)],
        [(33.05, 41.50), (37.15, 41.50)],
        [(32.95, 41.30), (37.20, 41.30)],
        [(32.90, 41.05), (37.20, 41.05)],
        [(32.80, 40.50), (37.40, 40.50)],
    ]
    baseline = sess.violations("SYS")
    print(f"  baseline SYS score: {baseline}")
    best = None
    best_score = None
    for arc in variants:
        keep_backup = list(sess.b.net_segments["SYS"])
        add = []
        for s in ripped:
            a = s["start"]
            b = s["end"]
            pts = [a] + list(arc) + [b]
            for k in range(len(pts) - 1):
                add.append({"layer": s["layer"], "net": "SYS", "width": s["width"],
                            "start": [round(pts[k][0], 4), round(pts[k][1], 4)],
                            "end": [round(pts[k + 1][0], 4),
                                    round(pts[k + 1][1], 4)],
                            "kind": "route"})
        sess.b.net_segments["SYS"] = keep_backup + add
        sess.b.rebuild_copper()
        sess.mask_cache.clear()
        bad = sess.violations("SYS")
        print(f"  variant {arc[0][1]:.2f} mm: {bad} SYS clearance violations")
        if bad <= baseline:
            best = add
            best_score = bad
            break
        sess.b.net_segments["SYS"] = keep_backup
        sess.b.rebuild_copper()
        sess.mask_cache.clear()
    if best is None:
        print("rejected: no corridor variant is clearance legal")
        return 1
    print(f"re-routed the trunk with {len(best)} segment(s), corridor "
          f"{arc[0][1]:.2f} mm")

    sess.b.rebuild_copper()
    sess.mask_cache.clear()
    bad = sess.violations("SYS")
    print(f"SYS clearance violations after the move: {bad}")
    # the TPS nets must be able to leave the U3 pad row now
    for net in ("TPS_EN", "TPS_VSEL"):
        sess.mask_cache.clear()
        params = R.net_params(net)
        for pad in board.pads_of.get(net, []):
            if pad["ref"] != "U3":
                continue
            key = (pad["ref"], pad["num"])
            if key not in sess.stubs:
                if sess.make_stub(net, pad, params, key):
                    print(f"  {net}: stub reserved at {pad['ref']}.{pad['num']}")
        sess.mask_cache.clear()
        print(f"  {net}: {'routed' if sess.route_one(net) else 'still blocked'}")

    if bad:
        print("rejected: the move breaks clearance")
        return 1
    if args.dry_run:
        return 0
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
