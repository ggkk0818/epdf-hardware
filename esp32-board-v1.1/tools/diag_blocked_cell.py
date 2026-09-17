"""What blocks a grid cell for a given net? (debug helper)

    python tools/diag_blocked_cell.py <net> <x> <y> [width]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def main():
    net = sys.argv[1]
    x, y = float(sys.argv[2]), float(sys.argv[3])
    w = float(sys.argv[4]) if len(sys.argv) > 4 else R.net_params(net)["width"]
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
    print(f"net {net} w{w} cell ({i},{j}) = ({i * R.PITCH:.2f},{j * R.PITCH:.2f})")
    params = R.net_params(net)
    half = w / 2.0
    for layer, li in ((lyr, k) for k, lyr in enumerate(R.ROUTABLE)):
        print(f"-- {layer}")
        xs = np.array([x], dtype=np.float32)
        ys = np.array([y], dtype=np.float32)
        for grp, gclear in (("lo", 0.15), ("hi", 0.20)):
            if not hasattr(board.ob, "by"):
                continue
            need = half + max(params["clearance"], gclear) + R.EPS
            for s in board.ob.by[layer][grp]:
                if s.net == net:
                    continue
                d = float(s.dist(xs, ys).min())
                if d < need:
                    print(f"   {grp} need={need:.3f} d={d:.3f} net={s.net!r} "
                          f"box=({s.x0:.2f},{s.y0:.2f})-({s.x1:.2f},{s.y1:.2f})"
                          f" r=({s.a:.2f},{s.b:.2f},{s.r:.2f})")
    print("pad cell list for R28.2:",
          [(p["x"], p["y"], p["w"], p["h"], p["cu_layers"])
           for p in model["pads"] if p["ref"] == "R28"])


if __name__ == "__main__":
    main()
