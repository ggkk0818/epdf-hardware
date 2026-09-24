"""Inventory everything inside a window: components+pads, tracks per layer, vias,
and which nets pass through. Used to plan a region redesign."""

import collections
import math
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def main():
    x0, x1, y0, y1 = [float(v) for v in sys.argv[1:5]]
    pad_margin = float(sys.argv[5]) if len(sys.argv) > 5 else 100.0
    g = geom.load()

    print(f"=== components whose anchor is in x[{x0},{x1}] y[{y0},{y1}] ===")
    for c in g["components"]:
        if x0 <= c["x"] <= x1 and y0 <= c["y"] <= y1:
            print(f"  {c['designator']:<6} ({c['x']:7.1f},{c['y']:7.1f}) rot={c['rotation']:>6} "
                  f"{c['device']}")
            for p in c["pads"]:
                print(f"      pad {p['padNumber']:<4} ({p['x']:7.1f},{p['y']:7.1f}) "
                      f"{p['width']}x{p['height']} {p['net']}")

    print("\n=== tracks per layer touching the window (+/- 60 mil) ===")
    per = collections.defaultdict(list)
    for t in g["tracks"]:
        xs = sorted([t["startX"], t["endX"]])
        ys = sorted([t["startY"], t["endY"]])
        if xs[1] < x0 - 60 or xs[0] > x1 + 60 or ys[1] < y0 - 60 or ys[0] > y1 + 60:
            continue
        per[t["layer"]].append(t)
    for lay in sorted(per):
        nets = collections.Counter(t.get("net") for t in per[lay])
        print(f"  L{lay}: {len(per[lay])} tracks; nets {dict(nets)}")

    print("\n=== vias in the window ===")
    for v in g["vias"]:
        if x0 <= v["x"] <= x1 and y0 <= v["y"] <= y1:
            print(f"  ({v['x']:7.1f},{v['y']:7.1f}) d={v.get('diameter')} {v.get('net')}")

    print("\n=== nets with any object in the window ===")
    seen = set()
    for t in g["tracks"]:
        xs = sorted([t["startX"], t["endX"]])
        ys = sorted([t["startY"], t["endY"]])
        if xs[1] < x0 or xs[0] > x1 or ys[1] < y0 or ys[0] > y1:
            continue
        seen.add(t.get("net"))
    for v in g["vias"]:
        if x0 <= v["x"] <= x1 and y0 <= v["y"] <= y1:
            seen.add(v.get("net"))
    for c, p in geom.iter_pads(g["components"]):
        if x0 - pad_margin <= p["x"] <= x1 + pad_margin and \
                y0 - pad_margin <= p["y"] <= y1 + pad_margin:
            seen.add(p.get("net"))
    print("   ", sorted(n for n in seen if n))


if __name__ == "__main__":
    main()
