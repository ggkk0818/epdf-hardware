"""Cross-check the v2 board against the requirement document's mechanical table.

    python tools/mech_crosscheck.py

The board is 55 x 84 mm with the EasyEDA/Gerber origin at the bottom-left and
Y up, so a requirement coordinate (X, Y_down from the top edge) maps to
(X, 84 - Y_down). The doc's H1-H4 rows pin that mapping down; J4/J3/J1 then
show whether each connector sits where section 3-5 says.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
MIL = 0.0254
BOARD_H = 84.0


def dump():
    txt = open(os.path.join(ROOT, "work", "audit", "pcb-dump.json"),
               encoding="utf-8").read()
    d = json.loads(txt[txt.find("{"):])
    return d.get("result", d)


def main():
    r = dump()
    comps = {(c.get("designator") or c.get("ref")): c
             for c in r.get("components") or []}

    def pads(ref):
        out = {}
        for p in comps[ref].get("pads") or []:
            out.setdefault(p.get("padNumber"), p)
        return out

    def mm(v):
        return v * MIL

    print("doc section 3/5 reference points -> v2 measured (mm, doc frame):")
    # J4 Pin1 should be (8.400, 61.375); J5 Pin1 (8.400, 71.375)
    for ref, pad, want in (("J4", "1", (8.400, 61.375)),
                           ("J5", "1", (8.400, 71.375))):
        p = pads(ref).get(pad)
        got = (mm(p["x"]), BOARD_H - mm(p["y"]))
        print(f"  {ref}.{pad}: measured {got[0]:.3f}, {got[1]:.3f} | "
              f"doc {want[0]:.3f}, {want[1]:.3f} | "
              f"delta {got[0]-want[0]:+.3f}, {got[1]-want[1]:+.3f}")
    # J3 pad row: pads 1..9 all at Y = 67.475, pin1 X = 42.775
    j3 = pads("J3")
    row = [p for k, p in j3.items() if k and k.isdigit() and int(k) <= 9]
    ys = sorted({round(BOARD_H - mm(p["y"]), 3) for p in row})
    print(f"  J3 pads 1-9 row Y: measured {ys} | doc 67.475")
    p1 = j3.get("1")
    print(f"  J3.1: measured {mm(p1['x']):.3f}, {BOARD_H-mm(p1['y']):.3f} | "
          f"doc 42.775, 67.475")
    # J1: signal pad row centre Y = 77.650, row X 20.800-27.200
    j1 = [p for k, p in pads("J1").items() if k and k[0] in "AB"]
    xs = sorted(mm(p["x"]) for p in j1)
    ys = sorted({round(BOARD_H - mm(p["y"]), 3) for p in j1})
    print(f"  J1 signal pads: {len(xs)} pads, X {xs[0]:.3f} .. {xs[-1]:.3f} "
          f"(doc 20.800 .. 27.200), row Y {ys} (doc 77.650)")
    print("   (v1.1/GCT footprint has 16 physical contacts; the merged GND/VBUS "
          "pairs are single pads in the EasyEDA symbol)")
    # J2: pad column X = 2.100, pin1 Y = 47.750, pin24 Y = 36.250
    j2 = pads("J2")
    col = [p for k, p in j2.items() if k.isdigit() and 1 <= int(k) <= 24]
    cxs = sorted({round(mm(p["x"]), 3) for p in col})
    p1j2, p24 = j2.get("1"), j2.get("24")
    print(f"  J2 pad column X: {cxs} (doc 2.100)")
    print(f"  J2.1  {mm(p1j2['x']):.3f}, {BOARD_H - mm(p1j2['y']):.3f} (doc 2.100, 47.750)")
    print(f"  J2.24 {mm(p24['x']):.3f}, {BOARD_H - mm(p24['y']):.3f} (doc 2.100, 36.250)")
    # J3 full row
    print(f"  J3.9 {mm(j3['9']['x']):.3f}, {BOARD_H - mm(j3['9']['y']):.3f} (doc 34.125, 67.475)")
    # SW3/SW4/SW5 anchors and pad rows
    for sw, anchor in (("SW3", 15.000), ("SW4", 42.000), ("SW5", 69.000)):
        swp = pads(sw)
        ys2 = sorted(round(BOARD_H - mm(p["y"]), 3) for p in swp.values())
        xs2 = sorted(round(mm(p["x"]), 3) for p in swp.values())
        print(f"  {sw}: pads Y {ys2} (doc {anchor-1.7:.3f} / {anchor+1.7:.3f}), "
              f"X {xs2} (doc 52.850)")
    # J1 shield slots + locating holes from the drill/gko exports
    print()
    print("NPTH drill (work/fab/Drill_NPTH_Through.DRL):")
    for line in open(os.path.join(ROOT, "work", "fab",
                                  "Drill_NPTH_Through.DRL"), encoding="utf-8"):
        if line.startswith("X"):
            x, y = line[1:].split("Y")
            print(f"   hole at ({float(x):.3f}, {BOARD_H-float(y):.3f}) mm in doc frame")
    print("   doc 5.1 locating holes: (21.110, 78.725) and (26.890, 78.725)")


if __name__ == "__main__":
    main()
