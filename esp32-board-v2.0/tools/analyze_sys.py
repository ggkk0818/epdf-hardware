"""Report SYS / power-net copper width distribution and local blockers."""

import collections
import json
import math
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

NETS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["SYS"]


def main():
    g = geom.load()
    tracks, vias, comps = g["tracks"], g["vias"], g["components"]
    for net in NETS:
        segs = [t for t in tracks if t.get("net") == net]
        agg = collections.defaultdict(float)
        for t in segs:
            agg[t["lineWidth"]] += geom.seg_len_mm(t)
        total = sum(agg.values())
        print(f"=== {net}: {len(segs)} segments, {total:.1f} mm ===")
        for w in sorted(agg):
            print(f"   {w:>6} mil ({w*0.0254:.3f} mm)  {agg[w]:6.1f} mm")
        # equivalent current estimate (IPC-2221 outer, 1oz, 10C)
        cur = 0.0
        for w, L in agg.items():
            mm = w * 0.0254
            area = mm * 0.035  # 1oz = 35um
            cur += (2.0 * (0.048 * area ** 0.44)) * (L / total) if total else 0
        print(f"   length-weighted equivalent: {cur:.2f} A")
        thin = sorted([t for t in segs if t["lineWidth"] < 20],
                      key=lambda t: -geom.seg_len_mil(t))
        print("   thin (<20 mil) segments:")
        for t in thin:
            print(f"     w={t['lineWidth']:>5} L={geom.seg_len_mil(t):6.1f}mil "
                  f"({t['startX']:.1f},{t['startY']:.1f})->({t['endX']:.1f},{t['endY']:.1f}) "
                  f"L{t['layer']} {t['primitiveId']}")
        print()


if __name__ == "__main__":
    main()
