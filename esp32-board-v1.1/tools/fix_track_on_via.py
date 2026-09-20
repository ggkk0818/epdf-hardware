"""Snap track geometry onto via centres (MD Final DFM Plan Phase E).

    python tools/fix_track_on_via.py --drc routing/drc_phaseE.json [--apply]

Reads the `track_not_centered_on_via` violations from a DRC report and fixes
the *geometry*, never the rule:

  * a track that stops next to the via is re-drawn so that this end lands on
    the via centre (the other end never moves),
  * a track that merely passes over the via is split exactly at the via centre
    (identical copper, two centred ends).

Every edit is re-checked with the router's own clearance engine before it is
written, and the file is only written with --apply.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"

POS = re.compile(r"@\(([-\d.]+),([-\d.]+)\)")
LEN = re.compile(r"length ([-\d.]+) mm")


def seg_dist(seg, x, y):
    x0, y0 = seg["start"]
    x1, y1 = seg["end"]
    vx, vy = x1 - x0, y1 - y0
    den = vx * vx + vy * vy
    t = 0.0 if den == 0 else max(0.0, min(1.0, ((x - x0) * vx
                                               + (y - y0) * vy) / den))
    return math.hypot(x0 + t * vx - x, y0 + t * vy - y)


def track_ok(sess, net, layer, x0, y0, x1, y1, width):
    walk = sess.rtr.masks(net, width / 2.0,
                          R.net_params(net)["clearance"])[layer][0]
    n = max(5, int(math.hypot(x1 - x0, y1 - y0) / 0.05))
    for t in range(n + 1):
        x = x0 + (x1 - x0) * t / n
        y = y0 + (y1 - y0) * t / n
        i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
        if not (0 <= i < R.W and 0 <= j < R.H) or not walk[j, i]:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drc", default=str(ROOT / "routing" / "drc_phaseE.json"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=lambda *a: None)
    segs = data["segments"]

    drc = json.loads(Path(args.drc).read_text(encoding="utf-8"))
    cases = [v for v in drc["violations"]
             if v["type"] == "track_not_centered_on_via"]
    print(f"track_not_centered_on_via cases: {len(cases)}")

    edits = []
    for v in cases:
        tr, vi = v["items"]
        tnet = tr["description"].split("[")[1].split("]")[0]
        tlayer = "F.Cu" if "on F.Cu" in tr["description"] else (
            "B.Cu" if "on B.Cu" in tr["description"] else (
                "In2.Cu" if "on In2.Cu" in tr["description"] else "In1.Cu"))
        tlen = float(LEN.search(tr["description"]).group(1))
        vx, vy = float(vi["pos"]["x"]), float(vi["pos"]["y"])
        cands = [s for s in segs
                 if s["net"] == tnet and s["layer"] == tlayer
                 and abs(math.hypot(s["end"][0] - s["start"][0],
                                    s["end"][1] - s["start"][1]) - tlen) < 0.01
                 and seg_dist(s, vx, vy) < 0.30]
        if len(cands) != 1:
            print(f"  {tnet}: cannot match the reported track "
                  f"({len(cands)} candidates) - skipped")
            continue
        s = cands[0]
        ends = [("start", s["start"]), ("end", s["end"])]
        ends.sort(key=lambda e: math.hypot(e[1][0] - vx, e[1][1] - vy))
        near_name, near = ends[0]
        far = s["end"] if near_name == "start" else s["start"]
        d = math.hypot(near[0] - vx, near[1] - vy)
        w = s["width"]
        if d > 0.05 and seg_dist(s, vx, vy) < 0.02:
            # the via sits in the middle of the track -> split it there
            if not (track_ok(sess, tnet, tlayer, far[0], far[1], vx, vy, w)
                    and track_ok(sess, tnet, tlayer, vx, vy, near[0], near[1],
                                 w)):
                print(f"  {tnet}: split at the via fails the clearance check "
                      f"- skipped")
                continue
            edits.append(("split", s, (vx, vy)))
            print(f"  {tnet} {tlayer} w{w}: split the track at the via "
                  f"({vx},{vy}) (copper unchanged)")
        else:
            if not track_ok(sess, tnet, tlayer, far[0], far[1], vx, vy, w):
                print(f"  {tnet}: snapping {near} -> ({vx},{vy}) fails the "
                      f"clearance check - skipped")
                continue
            edits.append(("snap", s, (vx, vy)))
            print(f"  {tnet} {tlayer} w{w}: snap ({near[0]:.3f},{near[1]:.3f})"
                  f" -> ({vx:.3f},{vy:.3f})  (move {d:.3f} mm)")

    if not args.apply:
        return 0
    for (kind, s, p) in edits:
        if kind == "split":
            a, b = s["start"], s["end"]
            segs.remove(s)
            segs.append(dict(s, start=[round(a[0], 4), round(a[1], 4)],
                             end=[round(p[0], 4), round(p[1], 4)]))
            segs.append(dict(s, start=[round(p[0], 4), round(p[1], 4)],
                             end=[round(b[0], 4), round(b[1], 4)]))
        else:
            near = min((s["start"], s["end"]),
                       key=lambda e: math.hypot(e[0] - p[0], e[1] - p[1]))
            if near is s["start"]:
                s["start"] = [round(p[0], 4), round(p[1], 4)]
            else:
                s["end"] = [round(p[0], 4), round(p[1], 4)]
    shutil.copyfile(ROUTING, ROUTING.with_name("_pre_track_on_via.json"))
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name} ({len(edits)} geometry fixes, "
          f"backup: _pre_track_on_via.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
