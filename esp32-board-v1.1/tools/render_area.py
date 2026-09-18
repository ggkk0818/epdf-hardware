"""Render one window of the board (copper + pours) to a PNG for eyeballing.

    python tools/render_area.py x0 y0 x1 y1 out.png [--scale 60]

Colours:  F.Cu pour = pale green, F.Cu track = dark green, F.Cu pad = grey,
          B.Cu track = orange, In2.Cu track = pale blue, via = black ring,
          rule area = pink outline.  Read-only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pcbnew
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"


def main():
    x0, y0, x1, y1 = (float(a) for a in sys.argv[1:5])
    out = Path(sys.argv[5]).resolve()
    scale = 60.0
    if "--scale" in sys.argv:
        scale = float(sys.argv[sys.argv.index("--scale") + 1])
    w = int((x1 - x0) * scale) + 1
    h = int((y1 - y0) * scale) + 1
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)

    def P(x, y):
        return ((x - x0) * scale, (y - y0) * scale)

    board = pcbnew.LoadBoard(str(PCB))

    for z in board.Zones():
        for lyr, col in ((pcbnew.F_Cu, (198, 236, 198)),
                         (pcbnew.B_Cu, (250, 226, 196)),
                         (pcbnew.In2_Cu, (214, 226, 250))):
            if not z.IsOnLayer(lyr):
                continue
            name = z.GetZoneName()
            if z.GetIsRuleArea():
                col = (255, 210, 240)
            elif z.GetNetname() != "GND":
                col = (236, 236, 255)
            ps = z.GetFilledPolysList(lyr)
            for k in range(ps.OutlineCount()):
                o = ps.Outline(k)
                pts = [P(o.CPoint(t).x / 1e6, o.CPoint(t).y / 1e6)
                       for t in range(o.PointCount())]
                if len(pts) >= 3:
                    d.polygon(pts, fill=col, outline=(150, 190, 150) if \
                              z.GetNetname() == "GND" and not z.GetIsRuleArea()
                              else None)

    def seg(a, b, half, col, label=None):
        ax, ay = P(a[0], a[1])
        bx, by = P(b[0], b[1])
        hw = max(1.0, half * scale)
        d.line([ax, ay, bx, by], fill=col, width=int(round(2 * hw)))
        if label:
            mx, my = (ax + bx) / 2, (ay + by) / 2
            d.text((mx + 3, my + 3), label, fill=(0, 0, 0))

    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        a = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
        b = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
        if not (x0 - 1 <= a[0] <= x1 + 1 and y0 - 1 <= a[1] <= y1 + 1
                or x0 - 1 <= b[0] <= x1 + 1 and y0 - 1 <= b[1] <= y1 + 1):
            continue
        lay = t.GetLayer()
        net = t.GetNetname()
        col = {pcbnew.F_Cu: (40, 130, 40), pcbnew.B_Cu: (225, 120, 20),
               pcbnew.In2_Cu: (90, 130, 230)}.get(lay, (120, 120, 120))
        if net == "GND":
            col = {pcbnew.F_Cu: (0, 90, 0), pcbnew.B_Cu: (170, 80, 0),
                   pcbnew.In2_Cu: (60, 90, 190)}.get(lay, col)
        seg(a, b, t.GetWidth() / 2e6, col, net if lay == pcbnew.F_Cu else None)

    for fp in board.GetFootprints():
        for p in fp.Pads():
            c = p.GetPosition()
            cx, cy = c.x / 1e6, c.y / 1e6
            sz = p.GetSize()
            pw, ph = sz.x / 2e6, sz.y / 2e6
            if not (x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1):
                continue
            col = (170, 170, 170)
            if p.GetNetname() == "GND":
                col = (110, 110, 110)
            d.rectangle([P(cx - pw, cy - ph), P(cx + pw, cy + ph)], fill=col)
            d.text(P(cx + pw, cy - ph), f"{fp.GetReference()}.{p.GetNumber()} "
                   f"{p.GetNetname()}", fill=(0, 0, 0))

    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T:
            continue
        c = t.GetPosition()
        cx, cy = c.x / 1e6, c.y / 1e6
        if not (x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1):
            continue
        r = t.GetWidth(pcbnew.F_Cu) / 2e6
        d.ellipse([P(cx - r, cy - r), P(cx + r, cy + r)],
                  fill=(255, 255, 255), outline=(0, 0, 0), width=2)
        d.text(P(cx + r, cy + r), t.GetNetname(), fill=(0, 0, 0))

    img.save(out)
    print(f"wrote {out}  ({w}x{h}px, {scale} px/mm)")


if __name__ == "__main__":
    main()
