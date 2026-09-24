"""Re-apply the corridor-opening edits by matching endpoints (ids change after a
copper restore).  Writes work/reopen-corridor.json for tools/apply_edits.py."""

import json
import os
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

ROOT = geom.ROOT

DEL_TRACKS = [
    ((615.1, 2153.7), (595.9, 2153.7)),
    ((595.9, 2153.7), (588.2, 2153.7)),
    ((595.9, 2153.7), (595.9, 2241.8)),
    ((595.9, 2241.8), (614.5, 2260.4)),
    ((614.5, 2260.4), (597.0, 2277.9)),
    ((597.0, 2277.9), (597.0, 2634.7)),
    ((597.0, 2634.7), (624.7, 2662.4)),
    ((611.4, 2345.2), (620.1, 2345.2)),
    ((620.1, 2345.2), (646.5, 2345.2)),
]
DEL_VIAS = [(620.1, 2345.2)]


def close(a, b, tol=1.2):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def main():
    g = geom.load()
    dele, vias = [], []
    for a, b in DEL_TRACKS:
        for t in g["tracks"]:
            p, q = (t["startX"], t["startY"]), (t["endX"], t["endY"])
            if (close(p, a) and close(q, b)) or (close(p, b) and close(q, a)):
                dele.append(t["primitiveId"])
                break
        else:
            print(f"  !! not found: {a} -> {b}")
    for v in g["vias"]:
        for a in DEL_VIAS:
            if close((v["x"], v["y"]), a):
                vias.append(v["primitiveId"])
    print(f"matched {len(dele)}/{len(DEL_TRACKS)} tracks, {len(vias)}/{len(DEL_VIAS)} vias")

    add = [
        {"net": "EPD_PWR_EN", "layer": 1, "width": 10, "x1": 620.1, "y1": 2153.7,
         "x2": 614.5, "y2": 2260.4},
        {"net": "EPD_PWR_EN", "layer": 2, "width": 10, "x1": 614.5, "y1": 2260.4,
         "x2": 625.0, "y2": 2270.9},
        {"net": "EPD_PWR_EN", "layer": 2, "width": 10, "x1": 625.0, "y1": 2270.9,
         "x2": 625.0, "y2": 2657.0},
        {"net": "EPD_PWR_EN", "layer": 2, "width": 10, "x1": 625.0, "y1": 2657.0,
         "x2": 624.7, "y2": 2662.4},
        {"net": "EPD_RST_N", "layer": 16, "width": 10, "x1": 611.4, "y1": 2345.2,
         "x2": 650.0, "y2": 2345.2},
        {"net": "EPD_RST_N", "layer": 1, "width": 10, "x1": 650.0, "y1": 2345.2,
         "x2": 646.5, "y2": 2345.2},
    ]
    out = {"comment": "re-open the USB pair corridor (EPD_PWR_EN L1 straighten + L2 ->625, "
                      "EPD_RST_N via ->650)",
           "delete": {"tracks": dele, "vias": vias},
           "tracks": add,
           "vias": [{"net": "EPD_RST_N", "x": 650.0, "y": 2345.2,
                     "diameter": 24, "hole": 12}]}
    path = os.path.join(ROOT, "work", "reopen-corridor.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main()
