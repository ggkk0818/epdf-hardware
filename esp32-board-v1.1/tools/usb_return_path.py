"""USB return-path review (MD Final DFM Plan section 6), read-only.

    python tools/usb_return_path.py

For every USB_DP_CONN / USB_DN_CONN segment it samples the copper and asks
whether the reference plane underneath is solid GND (In1 for F.Cu and In2.Cu,
In2 for B.Cu - the adjacent layers of the 4 layer stack).  It also reports, for
every layer-change via of those nets, the distance to the nearest GND via
(return-current stitching) and to the nearest GND copper.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcbnew  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"
REF = {"F.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In1_Cu, "B.Cu": pcbnew.In2_Cu}


def pours(board, layer, net="GND"):
    out = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsOnLayer(layer):
            continue
        ps = z.GetFilledPolysList(layer)
        for k in range(ps.OutlineCount()):
            o = ps.Outline(k)
            pts = [(o.CPoint(t).x / 1e6, o.CPoint(t).y / 1e6)
                   for t in range(o.PointCount())]
            if len(pts) >= 3:
                out.append(pts)
    return out


def covered(polys, x, y):
    return any(R.point_in_polygon(x, y, p) for p in polys)


def main():
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = pcbnew.LoadBoard(str(PCB))
    cache = {lyr: pours(board, lyr) for lyr in (pcbnew.In1_Cu, pcbnew.In2_Cu)}
    gnd_vias = [(v["x"], v["y"]) for v in data.get("gnd_vias", [])]
    gnd_vias += [(v["x"], v["y"]) for v in data.get("vias", [])
                 if v["net"] == "GND"]

    for net in ("USB_DP_CONN", "USB_DN_CONN"):
        segs = [s for s in data["segments"] if s["net"] == net]
        vias = [v for v in data["vias"] if v["net"] == net]
        total = sum(math.hypot(s["end"][0] - s["start"][0],
                               s["end"][1] - s["start"][1]) for s in segs)
        n = bad = 0
        holes = []
        runs = []
        for s in segs:
            ref = cache[REF[s["layer"]]]
            run = 0
            steps = max(1, int(math.hypot(s["end"][0] - s["start"][0],
                                          s["end"][1] - s["start"][1]) / 0.2))
            for k in range(steps + 1):
                x = s["start"][0] + (s["end"][0] - s["start"][0]) * k / steps
                y = s["start"][1] + (s["end"][1] - s["start"][1]) * k / steps
                n += 1
                if not covered(ref, x, y):
                    bad += 1
                    run += 0.2
                    holes.append((round(x, 2), round(y, 2), s["layer"]))
                elif run:
                    runs.append(run)
                    run = 0
            if run:
                runs.append(run)
        layers = sorted({s["layer"] for s in segs})
        print(f"{net}: {len(segs)} segments / {len(vias)} vias on "
              f"{'+'.join(layers)}, length {total:.1f} mm")
        print(f"  reference plane ({'/'.join(sorted({REF[l] == pcbnew.In1_Cu and 'In1' or 'In2' for l in layers}))}"
              f"): {n - bad}/{n} samples over solid GND copper"
              + (f", longest gap {max(runs):.1f} mm" if runs else ""))
        for h in holes[:8]:
            print(f"    gap at ({h[0]},{h[1]}) on {h[2]}")
        for v in vias:
            dg = min(math.hypot(v["x"] - gx, v["y"] - gy)
                     for (gx, gy) in gnd_vias)
            print(f"  layer-change via ({v['x']:.3f},{v['y']:.3f}): nearest "
                  f"GND via {dg:.2f} mm")


if __name__ == "__main__":
    main()
