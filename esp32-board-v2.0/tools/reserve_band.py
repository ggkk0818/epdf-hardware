"""Build an augmented geometry that reserves a corridor for the USB pair, so
other nets can be re-routed around it.

    python tools/reserve_band.py --out work/geom-reserved.json \
        --band 640,900,640,2250 --band 654,900,654,2250 --width 23
"""

import argparse
import json
import os
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--band", action="append", required=True,
                    help="x1,y1,x2,y2 polyline segment of the reserved corridor")
    ap.add_argument("--width", type=float, default=23.0)
    args = ap.parse_args()
    g = geom.load()
    n = len(g["tracks"])
    for k, b in enumerate(args.band):
        x1, y1, x2, y2 = [float(v) for v in b.split(",")]
        g["tracks"].append({"primitiveId": f"reserved-{k}", "startX": x1, "startY": y1,
                            "endX": x2, "endY": y2, "layer": 2,
                            "lineWidth": args.width, "net": "USB_PAIR_RESERVED",
                            "locked": False})
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(g, fh, ensure_ascii=False)
    print(f"{n} tracks + {len(args.band)} reserved -> {args.out}")


if __name__ == "__main__":
    main()
