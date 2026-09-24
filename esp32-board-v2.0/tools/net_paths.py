"""Print the routed path of one or more nets (per layer, longest first)."""

import collections
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def main():
    g = geom.load()
    for net in sys.argv[1].split(","):
        ts = [t for t in g["tracks"] if t.get("net") == net]
        tot = sum(geom.seg_len_mm(t) for t in ts)
        per = collections.defaultdict(float)
        for t in ts:
            per[t["layer"]] += geom.seg_len_mm(t)
        print(f"=== {net}: {len(ts)} segments, {tot:.2f} mm  "
              f"per-layer {dict((k, round(v,1)) for k,v in sorted(per.items()))}")
        for t in sorted(ts, key=lambda t: -geom.seg_len_mm(t)):
            print(f"   L{t['layer']:<3} w={t['lineWidth']:>5} {geom.seg_len_mm(t):6.2f}mm "
                  f"({t['startX']:8.1f},{t['startY']:8.1f})->"
                  f"({t['endX']:8.1f},{t['endY']:8.1f})")
        vias = [v for v in g["vias"] if v.get("net") == net]
        print(f"   vias: {[(round(v['x'],1), round(v['y'],1)) for v in vias]}")
        print()


if __name__ == "__main__":
    main()
