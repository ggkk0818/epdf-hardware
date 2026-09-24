"""Print the as-built coordinates of the constrained interfaces, in the
requirement document's frame (origin = board top-left, X right, Y down).

    python tools/mech_measure.py

Board outline is verified as X 0-55 / Y 0-84 mm with y-up in the editor frame,
so doc-frame Y = 84 - editor Y.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
MIL = 0.0254
BOARD_H = 84.0


def main():
    txt = open(os.path.join(ROOT, "work", "audit", "pcb-dump.json"),
               encoding="utf-8").read()
    d = json.loads(txt[txt.find("{"):])
    comps = {(c.get("designator") or c.get("ref")): c
             for c in d.get("result", d).get("components") or []}

    for ref in ("J1", "J3", "J4", "J5", "SW3", "SW4", "SW5", "J2"):
        c = comps.get(ref)
        if not c:
            continue
        ax, ay = c["x"] * MIL, BOARD_H - c["y"] * MIL
        b = c.get("bbox") or {}
        print(f"== {ref}: anchor ({ax:.3f}, {ay:.3f}) rot {c.get('rotation')} "
              f"locked={c.get('locked')}")
        if b.get("minX") is not None:
            print(f"   bbox X {b['minX']*MIL:.3f} .. {b['maxX']*MIL:.3f}   "
                  f"Y {BOARD_H - b['maxY']*MIL:.3f} .. {BOARD_H - b['minY']*MIL:.3f}")
        for p in sorted(c.get("pads") or [],
                        key=lambda q: str(q.get("padNumber"))):
            print(f"   pad {str(p.get('padNumber')):<6} "
                  f"({p['x']*MIL:.3f}, {BOARD_H - p['y']*MIL:.3f})  "
                  f"size {p.get('width', 0)*MIL:.3f} x {p.get('height', 0)*MIL:.3f}"
                  f"  net={p.get('net')}")


if __name__ == "__main__":
    main()
