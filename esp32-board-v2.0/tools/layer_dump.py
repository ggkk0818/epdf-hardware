"""Dump every track/via on one layer inside an x/y window (for corridor surveys)."""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def main():
    layer = int(sys.argv[1])
    x0, x1, y0, y1 = [float(v) for v in sys.argv[2:6]]
    net = sys.argv[6] if len(sys.argv) > 6 else None
    g = geom.load()
    rows = []
    for t in g["tracks"]:
        if t["layer"] != layer:
            continue
        if net and t.get("net") != net:
            continue
        xs = sorted([t["startX"], t["endX"]])
        ys = sorted([t["startY"], t["endY"]])
        if xs[1] < x0 or xs[0] > x1 or ys[1] < y0 or ys[0] > y1:
            continue
        rows.append((min(ys), t))
    print(f"layer {layer}: {len(rows)} track(s) in window "
          f"x[{x0},{x1}] y[{y0},{y1}]")
    for _, t in sorted(rows, key=lambda r: r[0]):
        print(f"   w={t['lineWidth']:>5} ({t['startX']:8.1f},{t['startY']:8.1f})->"
              f"({t['endX']:8.1f},{t['endY']:8.1f})  {t.get('net')}")


if __name__ == "__main__":
    main()
