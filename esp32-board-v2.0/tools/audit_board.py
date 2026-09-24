"""Compliance audit of the current PCB against PCB_INTERFACE_POSITIONS.md.

Read-only. Reports the items the requirement document constrains, plus the
mechanical keep-out zones, so each gap can be turned into a task.
"""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

MM = 39.3700787  # mil per mm

# requirement §6, converted to EasyEDA mil with y measured from the TOP edge
# (board is 84 mm = 3307.09 mil tall; the doc's Y runs downward from the top)
TOP = 3307.09
KEEPOUTS = {
    "ESP32_ANT_KEEP_OUT": (16.0, 39.0, 0.0, 6.0, "all"),
    "KEY_RIGHT_MECH_KEEP_OUT": (49.0, 51.0, 0.0, 84.0, "components"),
    "RIGHT_SWITCH_COLUMN": (49.0, 55.0, 0.0, 84.0, "components"),
}


def mm2mil(v):
    return v * MM


def y_from_top(mm_from_top):
    return TOP - mm2mil(mm_from_top)


def main():
    g = geom.load()
    comps = g["components"]

    print("== components inside the right-hand keep-out band (X 51-55 mm) ==")
    lo, hi = mm2mil(51.0), mm2mil(55.0)
    allowed = {"SW3", "SW4", "SW5", "H1", "H2", "H3", "H4"}
    bad = [c for c in comps if lo <= c["x"] <= hi and c["designator"] not in allowed]
    print("   ", [c["designator"] for c in bad] or "none")

    print("== components inside the KEY_RIGHT band (X 49-51 mm) ==")
    lo2 = mm2mil(49.0)
    bad2 = [c for c in comps if lo2 <= c["x"] <= hi and c["designator"] not in allowed]
    print("   ", [c["designator"] for c in bad2] or "none")

    print("== components inside the antenna keep-out (X 16-39, top 0-6 mm) ==")
    x0, x1 = mm2mil(16.0), mm2mil(39.0)
    ylo, yhi = y_from_top(6.0), TOP
    for c in comps:
        if x0 <= c["x"] <= x1 and c["y"] >= ylo:
            print(f"    {c['designator']:<6} ({c['x']:.0f},{c['y']:.0f}) "
                  f"bboxY {c['bbox']['minY']:.0f}..{c['bbox']['maxY']:.0f}")

    print("== copper / via / pad inside the antenna keep-out, per layer ==")
    layers = {1: "Top", 2: "Bottom", 15: "Inner1", 16: "Inner2"}
    for lay, name in layers.items():
        n_tr = sum(1 for t in g["tracks"] if t["layer"] == lay and
                   x0 <= t["startX"] <= x1 and t["startY"] >= ylo)
        n_v = sum(1 for v in g["vias"] if x0 <= v["x"] <= x1 and v["y"] >= ylo)
        n_p = sum(1 for _c, p in geom.iter_pads(comps)
                  if p.get("layer") == lay and x0 <= p["x"] <= x1 and p["y"] >= ylo)
        print(f"    L{lay:<3}{name:<7} tracks={n_tr} vias={n_v} pads={n_p}")

    print("== keep-out regions currently defined ==")
    r = geom.call(["pcb", "region", "list"])
    for x in (r or {}).get("result", {}).get("regions", []):
        b = x["bbox"]
        print(f"    L{x['layer']:<3} {','.join(x['ruleTypeNames']):<32} "
              f"x[{b['minX']:.0f},{b['maxX']:.0f}] y[{b['minY']:.0f},{b['maxY']:.0f}]")

    print("== pads per layer (SMD vs through) ==")
    seen = {}
    for _c, p in geom.iter_pads(comps):
        seen[p.get("layer")] = seen.get(p.get("layer"), 0) + 1
    print("   ", seen)

    print("== screw-hole / outline sanity ==")
    o = g.get("outline") or {}
    print("    outline bbox", o.get("bbox"))


if __name__ == "__main__":
    main()
