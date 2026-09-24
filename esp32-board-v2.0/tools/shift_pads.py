"""Move components by +dx and drag every track endpoint that lands on their pads.

    python tools/shift_pads.py --refs R1,R25,R29 --dx 5 --edit work/shift-1.json
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", required=True)
    ap.add_argument("--dx", type=float, default=0.0)
    ap.add_argument("--dy", type=float, default=0.0)
    ap.add_argument("--edit", required=True)
    args = ap.parse_args()
    refs = set(args.refs.split(","))

    g = geom.load()
    pads = []
    for c, p in geom.iter_pads(g["components"]):
        if c["designator"] in refs:
            pads.append((p["x"], p["y"]))
    print(f"{len(pads)} pads on {sorted(refs)}")

    dele, keep = [], []
    for t in g["tracks"]:
        hit = False
        for (px, py) in pads:
            if math.hypot(t["startX"] - px, t["startY"] - py) <= 1.5:
                t = dict(t)
                t["startX"] += args.dx
                t["startY"] += args.dy
                hit = True
            if math.hypot(t["endX"] - px, t["endY"] - py) <= 1.5:
                t = dict(t)
                t["endX"] += args.dx
                t["endY"] += args.dy
                hit = True
        if hit:
            for o in g["tracks"]:
                pass
    # second pass: emit delete + shifted add (ids must come from the original list)
    dele, add = [], []
    for t in g["tracks"]:
        nt = dict(t)
        hit = False
        for (px, py) in pads:
            if math.hypot(t["startX"] - px, t["startY"] - py) <= 1.5:
                nt["startX"] += args.dx
                nt["startY"] += args.dy
                hit = True
            if math.hypot(t["endX"] - px, t["endY"] - py) <= 1.5:
                nt["endX"] += args.dx
                nt["endY"] += args.dy
                hit = True
        if hit:
            dele.append(t["primitiveId"])
            add.append({"net": nt.get("net"), "layer": nt["layer"], "width": nt["lineWidth"],
                        "x1": nt["startX"], "y1": nt["startY"],
                        "x2": nt["endX"], "y2": nt["endY"]})
    print(f"tracks touching those pads: {len(add)}")
    with open(args.edit, "w", encoding="utf-8") as fh:
        json.dump({"delete": {"tracks": dele}, "tracks": add}, fh,
                  ensure_ascii=False, indent=1)
    print("wrote", args.edit)


if __name__ == "__main__":
    main()
