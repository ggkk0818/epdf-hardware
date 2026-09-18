"""Dump every copper object inside a window of the board file.

    python tools/inspect_area.py x0 y0 x1 y1 [--pour NET px,py ...]

Read-only helper: prints pads, tracks, vias and (optionally) whether a point
falls inside a filled pour, straight out of esp32-board-v1.1.kicad_pcb.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"


def mm(v):
    return v / 1e6


def main():
    x0, y0, x1, y1 = (float(a) for a in sys.argv[1:5])
    board = pcbnew.LoadBoard(str(PCB))
    inside = lambda x, y: x0 <= x <= x1 and y0 <= y <= y1

    print("== pads ==")
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            x, y = mm(p.GetPosition().x), mm(p.GetPosition().y)
            if not inside(x, y):
                continue
            sz = p.GetSize()
            print(f"  {ref}.{p.GetNumber():<3s} ({x:7.3f},{y:7.3f}) "
                  f"{mm(sz.x):.2f}x{mm(sz.y):.2f} {p.GetShape()} "
                  f"net={p.GetNetname() or '-'}")

    print("== tracks ==")
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        s, e = t.GetStart(), t.GetEnd()
        if not (inside(mm(s.x), mm(s.y)) or inside(mm(e.x), mm(e.y))):
            continue
        print(f"  {board.GetLayerName(t.GetLayer()):<6s} "
              f"({mm(s.x):7.3f},{mm(s.y):7.3f})->({mm(e.x):7.3f},{mm(e.y):7.3f}) "
              f"w{mm(t.GetWidth()):.4f} net={t.GetNetname() or '-'}")

    print("== vias ==")
    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T:
            continue
        c = t.GetPosition()
        x, y = mm(c.x), mm(c.y)
        if not inside(x, y):
            continue
        print(f"  ({x:7.3f},{y:7.3f}) dia {mm(t.GetWidth(pcbnew.F_Cu)):.2f}/"
              f"{mm(t.GetDrillValue()):.2f} net={t.GetNetname() or '-'}")

    if "--pour" in sys.argv:
        i = sys.argv.index("--pour")
        net = sys.argv[i + 1]
        print(f"== pour {net} ==")
        for a in sys.argv[i + 2:]:
            x, y = (float(v) for v in a.split(","))
            hits = []
            for z in board.Zones():
                if z.GetIsRuleArea() or z.GetNetname() != net:
                    continue
                for lyr in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu,
                            pcbnew.B_Cu):
                    if not z.IsOnLayer(lyr):
                        continue
                    ps = z.GetFilledPolysList(lyr)
                    if ps.Contains(pcbnew.VECTOR2I(int(x * 1e6),
                                                   int(y * 1e6))):
                        hits.append(board.GetLayerName(lyr))
            print(f"  ({x},{y}) -> {hits if hits else 'not in any pour'}")

    if "--pourmap" in sys.argv:
        i = sys.argv.index("--pourmap")
        net = sys.argv[i + 1]
        px0, py0, px1, py1 = (float(a) for a in sys.argv[i + 2:i + 6])
        step = float(sys.argv[i + 6]) if len(sys.argv) > i + 6 else 0.5
        polys = []
        for z in board.Zones():
            if z.GetIsRuleArea() or z.GetNetname() != net:
                continue
            for lyr in (pcbnew.F_Cu, pcbnew.B_Cu):
                if z.IsOnLayer(lyr):
                    polys.append((board.GetLayerName(lyr),
                                  z.GetFilledPolysList(lyr)))
        row_hdr = "        " + "".join(
            f"{px0 + k * step:6.2f}" for k in range(
                int((px1 - px0) / step) + 1))
        print(f"== pour map {net} (F=front B=back . none) ==")
        print(row_hdr)
        y = py0
        while y <= py1 + 1e-9:
            cells = []
            x = px0
            while x <= px1 + 1e-9:
                pt = pcbnew.VECTOR2I(int(round(x * 1e6)),
                                     int(round(y * 1e6)))
                mark = "."
                for name, ps in polys:
                    if ps.Contains(pt):
                        mark = name[0]
                        break
                cells.append(f"{mark:>6s}")
                x += step
            print(f"{y:7.2f} " + "".join(cells))
            y += step


if __name__ == "__main__":
    main()
