"""Assemble the complete USB0 (connector-side) plan:

    J1 pad escapes (kept) -> fan-in stubs -> coupled pair -> fan-out to R9.1/R10.1

Reads the pair produced by tools/pair_router.py and writes an edit file for
tools/apply_edits.py (verified with tools/verify_edits.py).
"""

import json
import math
import os
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

ROOT = geom.ROOT
PAIR = os.path.join(ROOT, "work", "g2500.json")
OUT = os.path.join(ROOT, "work", "usb0-plan.json")
J1_KEEP_Y = 430.0        # tracks fully below this y are the J1 escapes: keep
WIDTH = 8.0


def main():
    plan = json.load(open(PAIR, encoding="utf-8"))
    g = geom.load()

    keep = set()
    dele = []
    for t in g["tracks"]:
        if t.get("net") not in ("USB_DP_CONN", "USB_DN_CONN", "USB_DP", "USB_DN"):
            continue
        if t["net"] in ("USB_DP", "USB_DN"):
            continue      # MCU-side pair keeps its length-matched routing as-is
        if t["net"] in ("USB_DP_CONN", "USB_DN_CONN") and \
                max(t["startY"], t["endY"]) <= J1_KEEP_Y:
            keep.add(t["primitiveId"])
        else:
            dele.append(t["primitiveId"])
    dvias = []
    for v in g["vias"]:
        if v.get("net") in ("USB_DP_CONN", "USB_DN_CONN") and \
                v.get("primitiveId") not in ("4d1bd460325a37cc", "bf5c79ecd3470863"):
            dvias.append(v["primitiveId"])
    print(f"delete {len(dele)} tracks / {len(dvias)} vias; keep {len(keep)} J1 escapes")

    # pair traces: find the endpoints
    tr = [dict(t) for t in plan["tracks"]
          if math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"]) > 0.5]
    ends = {}
    for net in ("USB_DP_CONN", "USB_DN_CONN"):
        seq = [t for t in tr if t["net"] == net]
        pts = [(seq[0]["x1"], seq[0]["y1"])] + [(t["x2"], t["y2"]) for t in seq]
        ends[net] = (pts[0], pts[-1])
        print(f"  {net}: start {pts[0]} end {pts[-1]}")

    def seg(net, x1, y1, x2, y2):
        return {"net": net, "layer": 2, "width": WIDTH,
                "x1": round(x1, 2), "y1": round(y1, 2),
                "x2": round(x2, 2), "y2": round(y2, 2)}

    extra = []
    # fan-in from the two J1 vias
    p_start, n_start = ends["USB_DP_CONN"][0], ends["USB_DN_CONN"][0]
    extra.append(seg("USB_DP_CONN", 947.4, 321.3, p_start[0], p_start[1]))
    extra.append(seg("USB_DN_CONN", 899.7, 401.9, n_start[0], n_start[1]))
    # fan-out: DP down to R9.1, DN up to R10.1
    _, p_end = ends["USB_DP_CONN"]
    _, n_end = ends["USB_DN_CONN"]
    # diagonal fan-out straight into the two series resistors' connector pads
    extra.append(seg("USB_DP_CONN", p_end[0], p_end[1], 581.5, 2406.9))
    extra.append(seg("USB_DN_CONN", n_end[0], n_end[1], 581.5, 2584.1))

    out = {"comment": "USB0 coupled pair + J1 fan-in + R fan-out",
           "delete": {"tracks": dele, "vias": dvias},
           "tracks": tr + extra, "vias": []}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"wrote {OUT}: {len(tr)+len(extra)} tracks")


if __name__ == "__main__":
    main()
