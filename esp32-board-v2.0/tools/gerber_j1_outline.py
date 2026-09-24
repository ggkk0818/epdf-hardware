"""Measure J1's drawn outline in the exported Gerbers (mm, origin bottom-left).

    python tools/gerber_j1_outline.py

Compares the drawn connector body / pad extents against requirement doc 5.1:
body F.Fab Y 77.655..85.005 from the top edge  ->  6.345 mm .. -1.005 mm from
the bottom edge; signal pad row 6.350 mm from the bottom edge.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

FAB = os.path.join(geom.ROOT, "work", "fab")
WIN = (16.0, 32.0, -3.0, 12.0)   # x0, x1, y0, y1 in mm


def scan(path, label, window=WIN):
    xs, ys, n = [], [], 0
    fmt = None
    cur = [None, None]
    for raw in open(path, encoding="utf-8", errors="ignore"):
        line = raw.strip()
        if line.startswith("%FSLAX"):
            m = re.match(r"%FSLAX(\d)(\d)Y(\d)(\d)\*%", line)
            if m:
                fmt = (int(m.group(1)), int(m.group(2)))
        m = re.match(r"^(?:G0[123])?(?:X(-?\d+))?(?:Y(-?\d+))?(?:D0([123]))?\*$",
                     line)
        if m:
            if fmt is None:
                continue
            dec = fmt[1]
            if m.group(1) is not None:
                cur[0] = int(m.group(1)) / (10.0 ** dec)
            if m.group(2) is not None:
                cur[1] = int(m.group(2)) / (10.0 ** dec)
            if cur[0] is None or cur[1] is None:
                continue
            if window[0] <= cur[0] <= window[1] and window[2] <= cur[1] <= window[3]:
                xs.append(cur[0])
                ys.append(cur[1])
                n += 1
    if not xs:
        print(f"  {label}: no geometry in window")
        return
    print(f"  {label}: {n} points, X {min(xs):.3f}..{max(xs):.3f}, "
          f"Y {min(ys):.3f}..{max(ys):.3f} mm")


def main():
    files = [("Gerber_TopSilkscreenLayer.GTO", "top silk"),
             ("Gerber_TopLayer.GTL", "top copper (pads)"),
             ("Gerber_TopSolderMaskLayer.GTS", "top mask openings"),
             ("Gerber_DocumentLayer.GDL", "document/fab layer"),
             ("Gerber_BoardOutlineLayer.GKO", "board outline")]
    print("J1 window x 16-32 mm, y -3..12 mm (board bottom edge = y 0):")
    for fn, label in files:
        p = os.path.join(FAB, fn)
        if os.path.exists(p):
            scan(p, f"{label:<22}({fn})")
    print()
    print("board outline (whole layer):")
    scan(os.path.join(FAB, "Gerber_BoardOutlineLayer.GKO"), "GKO", (-50, 100, -50, 150))
    print("doc 5.1: body back edge 6.345 mm, body front -1.005 mm, "
          "signal pad row 6.350 mm, shield slots 5.775 / 1.595 mm")


if __name__ == "__main__":
    main()
