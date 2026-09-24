"""Print every pad / track / via inside a window, to explain a routing failure."""

import math
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402
import sys_router as route_sys  # noqa: E402


def main():
    cx, cy, rad = (float(v) for v in sys.argv[1:4])
    g = geom.load()
    print(f"--- pads within {rad} mil of ({cx},{cy}) ---")
    rows = []
    for c, p in geom.iter_pads(g["components"]):
        d = math.hypot(p["x"] - cx, p["y"] - cy)
        if d <= rad:
            rows.append((d, f"{c['designator']}.{p.get('padNumber')}", p))
    for d, name, p in sorted(rows):
        print(f"  {d:7.1f} {name:<10} ({p['x']:8.1f},{p['y']:8.1f}) "
              f"{p.get('width')}x{p.get('height')} net={p.get('net')} L{p.get('layer')}")
    print(f"--- tracks within {rad} mil ---")
    rows = []
    for t in g["tracks"]:
        d = route_sys.seg_distance(cx, cy, t["startX"], t["startY"],
                                   t["endX"], t["endY"])
        if d <= rad:
            rows.append((d, t))
    for d, t in sorted(rows, key=lambda r: r[0]):
        print(f"  {d:7.1f} w={t['lineWidth']:>5} L{t['layer']:<3} "
              f"({t['startX']:8.1f},{t['startY']:8.1f})->({t['endX']:8.1f},{t['endY']:8.1f}) "
              f"{t.get('net')}")
    print(f"--- vias within {rad} mil ---")
    for v in g["vias"]:
        d = math.hypot(v["x"] - cx, v["y"] - cy)
        if d <= rad:
            print(f"  {d:7.1f} ({v['x']:8.1f},{v['y']:8.1f}) d={v.get('diameter')} "
                  f"{v.get('net')}")


if __name__ == "__main__":
    main()
