"""ASCII map of the walkable area of a net (debug helper).

    python tools/probe_walk.py <net> x0 y0 x1 y1 [width]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    net = sys.argv[1]
    x0, y0, x1, y1 = (float(a) for a in sys.argv[2:6])
    w = float(sys.argv[6]) if len(sys.argv) > 6 else R.net_params(net)["width"]
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=lambda *a: None)
    m, _, _, _, _ = sess.masks_for(net, w, False)
    step = 2                     # cells per printed character (0.2 mm)
    i0, i1 = int(x0 / R.PITCH), int(x1 / R.PITCH)
    j0, j1 = int(y0 / R.PITCH), int(y1 / R.PITCH)
    print(f"net {net} width {w} - '#' walkable, '.' blocked "
          f"({step * R.PITCH:.1f} mm per char)")
    for lyr in R.ROUTABLE:
        walk = m[lyr][0]
        print(f"-- {lyr}")
        print("      " + "".join(f"{i * R.PITCH:5.1f}"[-5:]
                                 for i in range(i0, i1 + 1, 5 * step)))
        for j in range(j0, j1 + 1, step):
            row = "".join("#" if walk[j, i] else "." for i in range(i0, i1 + 1,
                                                                   step))
            print(f"{j * R.PITCH:6.2f} {row}")


if __name__ == "__main__":
    main()
