"""Prepare an EasyEDA Specctra DSN for Freerouting.

1. Inner1 becomes a power plane (the requirement keeps it a complete GND layer).
2. The four M2 mounting holes are injected as keep-outs on every copper layer —
   EasyEDA exports the milled slots only as small pads, so the router otherwise
   routes straight through them.
"""

import math
import os
import re
import sys

HOLE_CENTRES = [(118.12, 3188.98), (2047.25, 3188.98), (118.12, 118.11), (2047.25, 118.11)]
HOLE_R = 55.0          # mil: 43.3 mil hole radius + clearance
LAYERS = ["TopLayer", "Inner1", "Inner2", "BottomLayer"]


def octagon(cx, cy, r):
    pts = []
    for k in range(8):
        a = math.radians(22.5 + k * 45.0)
        pts += [round(cx + r * math.cos(a), 2), round(cy + r * math.sin(a), 2)]
    pts += [pts[0], pts[1]]
    return " ".join(str(p) for p in pts)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8", errors="replace") as fh:
        t = fh.read()

    t, n = re.subn(r"\(layer Inner1(\s*)\(type signal\)",
                   r"(layer Inner1\1(type power)", t)
    print("Inner1 -> power:", n)

    inject = []
    for i, (cx, cy) in enumerate(HOLE_CENTRES, start=1):
        for layer in LAYERS:
            inject.append(f'    (keepout "mount_hole_{i}_{layer}" (polygon {layer} 0 {octagon(cx, cy, HOLE_R)}))')
    block = "\n".join(inject) + "\n"

    # append the new keep-outs just before the closing paren of the structure block
    idx = t.rfind("\n  )\n")          # end of structure
    if idx < 0:
        idx = t.rfind("\n)")
    t = t[:idx] + "\n" + block + t[idx:]

    with open(dst, "w", encoding="ascii", errors="replace") as fh:
        fh.write(t)
    print("wrote", dst, "with", len(inject), "mounting-hole keep-outs")


if __name__ == "__main__":
    main()
