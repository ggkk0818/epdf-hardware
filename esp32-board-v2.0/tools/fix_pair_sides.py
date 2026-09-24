"""Fix a coupled pair whose two trace labels are swapped at the pads.

    python tools/fix_pair_sides.py --plan work/pair-usb0.json \
        --pads '{"USB_DP_CONN":[[935,264],[610,2370.3]], ...}' [--row-y 2400]

The planner offsets the centreline by +/- (w+gap)/2; depending on the arriving
direction "positive" can end up on either side, so the DP trace may land next to
the DN pad.  Both traces are parallel and identical in length, so relabelling the
two nets fixes the assignment without touching a single coordinate.
"""

import argparse
import collections
import json
import math
import sys


def ends(tracks):
    cnt = collections.Counter()
    for t in tracks:
        cnt[(round(t["x1"], 1), round(t["y1"], 1))] += 1
        cnt[(round(t["x2"], 1), round(t["y2"], 1))] += 1
    return [p for p, c in cnt.items() if c == 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--pads", required=True)
    ap.add_argument("--row-y", type=float, required=True,
                    help="y of the pad row used to decide the side")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    plan = json.load(open(args.plan, encoding="utf-8"))
    pads = json.loads(args.pads)
    nets = list(pads.keys())
    if len(nets) != 2:
        raise SystemExit("need exactly two nets")
    pos, neg = nets

    def row_end(net):
        e = ends([t for t in plan["tracks"] if t["net"] == net])
        return min(e, key=lambda p: abs(p[1] - args.row_y))

    ep, en = row_end(pos), row_end(neg)
    # which pad does each trace sit next to, in x?
    def nearer_pad(pt):
        d = {}
        for net, (srow, erow) in pads.items():
            for pad in (srow, erow):
                if abs(pad[1] - args.row_y) > 60:
                    continue
                d[net] = abs(pad[0] - pt[0])
        return min(d, key=d.get) if d else None

    pos_seen, neg_seen = nearer_pad(ep), nearer_pad(en)
    print(f"{pos} end {ep} sits next to pad of {pos_seen}; "
          f"{neg} end {en} sits next to pad of {neg_seen}")
    swapped = (pos_seen == neg) or (neg_seen == pos)
    if swapped:
        for t in plan["tracks"]:
            if t["net"] == pos:
                t["net"] = neg
            elif t["net"] == neg:
                t["net"] = pos
        print(f"-> labels swapped: {pos} <-> {neg}")
    else:
        print("-> labels already correct")
    json.dump(plan, open(args.out, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)


if __name__ == "__main__":
    main()
