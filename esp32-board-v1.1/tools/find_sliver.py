"""Find thin copper necks inside a filled zone.

    python tools/find_sliver.py <zone_name> <layer> [max_width_mm]

Rasterises the fill and reports the places where the copper is narrower than
`max_width_mm` but still connected to larger copper (i.e. a DRC
"connection too narrow" sliver).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pcbnew  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"
STEP = 0.05


def main():
    zone_name = sys.argv[1] if len(sys.argv) > 1 else "GND_POUR_L4"
    layer_name = sys.argv[2] if len(sys.argv) > 2 else "B.Cu"
    maxw = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2
    lid = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu,
           "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}[layer_name]
    board = pcbnew.LoadBoard(str(PCB))
    polys = None
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetZoneName() != zone_name:
            continue
        polys = z.GetFilledPolysList(lid)
    if polys is None:
        print("zone not found")
        return 1
    xs, ys = [], []
    for k in range(polys.OutlineCount()):
        o = polys.Outline(k)
        xs += [o.CPoint(t).x / 1e6 for t in range(o.PointCount())]
        ys += [o.CPoint(t).y / 1e6 for t in range(o.PointCount())]
    x0, x1 = min(xs) - 0.2, max(xs) + 0.2
    y0, y1 = min(ys) - 0.2, max(ys) + 0.2
    W = int((x1 - x0) / STEP) + 1
    H = int((y1 - y0) / STEP) + 1
    grid = np.zeros((H, W), bool)
    xs_g = x0 + np.arange(W) * STEP
    ys_g = y0 + np.arange(H) * STEP
    X, Y = np.meshgrid(xs_g, ys_g)
    pts = np.stack([X.ravel(), Y.ravel()], axis=1)
    inside = np.zeros(pts.shape[0], bool)
    for k in range(polys.OutlineCount()):
        o = polys.Outline(k)
        poly = np.array([[o.CPoint(t).x / 1e6, o.CPoint(t).y / 1e6]
                         for t in range(o.PointCount())])
        n = len(poly)
        c = np.zeros(pts.shape[0], bool)
        for j in range(n):
            p0, p1 = poly[j], poly[(j + 1) % n]
            if p0[1] == p1[1]:
                continue
            cond = ((p0[1] > pts[:, 1]) != (p1[1] > pts[:, 1]))
            with np.errstate(divide="ignore", invalid="ignore"):
                xx = p0[0] + (pts[:, 1] - p0[1]) * (p1[0] - p0[0]) / (p1[1] - p0[1])
            hit = cond & (pts[:, 0] < xx)
            c ^= hit
        inside |= c
    grid = inside.reshape(H, W)
    # distance to the nearest empty cell, by repeated dilation of the outside
    from numpy import roll
    outside = ~grid
    d = np.where(outside, 0, 10 ** 6).astype(np.int32)
    filled = outside.copy()
    for k in range(1, 41):                    # up to 2 mm in 0.05 mm steps
        nb = (filled | np.roll(filled, 1, 0) | np.roll(filled, -1, 0)
              | np.roll(filled, 1, 1) | np.roll(filled, -1, 1)
              | np.roll(np.roll(filled, 1, 0), 1, 1)
              | np.roll(np.roll(filled, 1, 0), -1, 1)
              | np.roll(np.roll(filled, -1, 0), 1, 1)
              | np.roll(np.roll(filled, -1, 0), -1, 1))
        newly = nb & ~filled
        d[newly & grid] = k
        filled = nb
    thin = grid & (2 * d * STEP <= maxw)
    # keep only real necks: thin here, but wide copper a little further along
    # one axis on *both* sides (a plain copper edge is thin on one side only)
    wide = (2 * d * STEP >= 0.30)
    neck = np.zeros_like(thin)
    k = max(1, int(0.4 / STEP))
    for (d1, d2) in (((k, 0), (-k, 0)), ((0, k), (0, -k))):
        a = np.roll(np.roll(wide, d1[0], 0), d1[1], 1)
        b = np.roll(np.roll(wide, d2[0], 0), d2[1], 1)
        neck |= a & b
    thin &= neck
    ys_i, xs_i = np.nonzero(thin)
    print(f"{thin.sum()} thin cells (<= {maxw} mm) in {zone_name} on {layer_name}")
    seen = []
    for j, i in zip(ys_i, xs_i):
        px, py = x0 + i * STEP, y0 + j * STEP
        if all((px - a) ** 2 + (py - b) ** 2 > 0.5 ** 2 for a, b in seen):
            seen.append((px, py))
            print(f"   at ({px:.2f},{py:.2f}) width {2 * d[j, i] * STEP:.3f} mm")


if __name__ == "__main__":
    main()
