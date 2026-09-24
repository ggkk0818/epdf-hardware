"""Check whether any Gerber layer draws copper inside a rectangle.

Coordinates are EasyEDA/Excellon-style mm with 5 implied decimals, origin at the
board's lower-left (verified: max X = 54.517 mm, max Y = 83.517 mm ≈ board 55x84).
"""

import argparse
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAB = os.path.join(ROOT, "work", "fab")
SCALE = 1e-5          # mm per gerber integer unit


def seg_hits_rect(x1, y1, x2, y2, r):
    rx0, ry0, rx1, ry1 = r
    if max(x1, x2) < rx0 or min(x1, x2) > rx1 or max(y1, y2) < ry0 or min(y1, y2) > ry1:
        return False

    def inside(px, py):
        return rx0 <= px <= rx1 and ry0 <= py <= ry1
    if inside(x1, y1) or inside(x2, y2):
        return True
    # sample the segment
    n = max(2, int(math.hypot(x2 - x1, y2 - y1) / 2000.0) + 1)
    for k in range(n + 1):
        u = k / n
        if inside(x1 + u * (x2 - x1), y1 + u * (y2 - y1)):
            return True
    return False


def scan(path, rect):
    txt = open(path, encoding="utf-8", errors="replace").read()
    cur = None
    hits = []
    in_region = False
    contour = []
    region_idx = 0
    for m in re.finditer(r"(G36|G37)|(?:X(-?\d+))?(?:Y(-?\d+))?D0([123])\*", txt):
        if m.group(1) == "G36":
            in_region, contour = True, []
            region_idx += 1
            continue
        if m.group(1) == "G37":
            if in_region and _rect_touches_polygon(rect, contour):
                hits.append(("region", region_idx, len(contour)))
            in_region, contour = False, []
            continue
        x = int(m.group(2)) * SCALE if m.group(2) else (cur[0] if cur else None)
        y = int(m.group(3)) * SCALE if m.group(3) else (cur[1] if cur else None)
        op = m.group(4)
        if x is None or y is None:
            continue
        if in_region:
            contour.append((x, y))
        if op == "3":
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                hits.append(("flash", round(x, 3), round(y, 3)))
            cur = (x, y)
        elif op == "2":
            cur = (x, y)
        elif op == "1":
            if cur and seg_hits_rect(cur[0], cur[1], x, y, rect):
                hits.append(("draw", round(cur[0], 3), round(cur[1], 3),
                             round(x, 3), round(y, 3)))
            cur = (x, y)
    return hits


def _point_in_poly(px, py, poly):
    inside = False
    n = len(poly)
    if n < 3:
        return False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xin = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xin:
                inside = not inside
    return inside


def _rect_touches_polygon(rect, poly):
    """True when any sample point of the rectangle lies inside the contour."""
    if len(poly) < 3:
        return False
    for i in range(5):
        for j in range(5):
            px = rect[0] + (rect[2] - rect[0]) * (i / 4.0)
            py = rect[1] + (rect[3] - rect[1]) * (j / 4.0)
            if _point_in_poly(px, py, poly):
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rect", required=True, help="x0,y0,x1,y1 in mil")
    ap.add_argument("--layers", default="G1,G2,GTL,GBL,GKO")
    args = ap.parse_args()
    x0, y0, x1, y1 = [float(v) * 0.0254 for v in args.rect.split(",")]
    rect = (x0, y0, x1, y1)
    print(f"rectangle (mm): x {x0:.3f}..{x1:.3f}  y {y0:.3f}..{y1:.3f}")
    for code in args.layers.split(","):
        p = [f for f in os.listdir(FAB) if f.endswith("." + code)]
        if not p:
            print(f"  {code}: (no file)")
            continue
        hits = scan(os.path.join(FAB, p[0]), rect)
        print(f"  {p[0]:<34} copper items inside rect: {len(hits)}")
        for h in hits[:5]:
            print("      ", h)


if __name__ == "__main__":
    main()
