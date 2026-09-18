"""Is a point inside a filled pour? (debug helper)

    python tools/pour_hit.py <net> x1,y1 [x2,y2 ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"


def main():
    net = sys.argv[1]
    pts = [tuple(float(v) for v in a.split(",")) for a in sys.argv[2:]]
    board = pcbnew.LoadBoard(str(PCB))
    for (x, y) in pts:
        hits = []
        for z in board.Zones():
            if z.GetIsRuleArea() or z.GetNetname() != net:
                continue
            for lyr in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
                if not z.IsOnLayer(lyr):
                    continue
                ps = z.GetFilledPolysList(lyr)
                if ps.Contains(pcbnew.VECTOR2I(int(x * 1e6), int(y * 1e6))):
                    hits.append(board.GetLayerName(lyr))
        print(f"  ({x},{y}) -> {hits if hits else 'not in any pour'}")


if __name__ == "__main__":
    main()
