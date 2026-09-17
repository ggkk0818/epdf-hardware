"""How big is the walkable pocket around a cell for a net? (debug helper)

    python tools/probe_pocket.py <net> <x> <y> [width]
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    net = sys.argv[1]
    x, y = float(sys.argv[2]), float(sys.argv[3])
    w = float(sys.argv[4]) if len(sys.argv) > 4 else R.net_params(net)["width"]
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=lambda *a: None)
    m, _, _, _, _ = sess.masks_for(net, w, False)
    for lyr in R.ROUTABLE:
        walk = m[lyr][0]
        i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
        if not walk[j, i]:
            print(f"{lyr}: start cell blocked")
            continue
        seen = np.zeros_like(walk)
        q = deque([(i, j)])
        seen[j, i] = True
        n = 0
        while q:
            a, b = q.popleft()
            n += 1
            for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p, r = a + da, b + db
                if 0 <= p < R.W and 0 <= r < R.H and walk[r, p] \
                        and not seen[r, p]:
                    seen[r, p] = True
                    q.append((p, r))
        ys, xs = np.nonzero(seen)
        print(f"{lyr}: pocket {n} cells, bbox x {xs.min() * R.PITCH:.1f}.."
              f"{xs.max() * R.PITCH:.1f}  y {ys.min() * R.PITCH:.1f}.."
              f"{ys.max() * R.PITCH:.1f}")


if __name__ == "__main__":
    main()
