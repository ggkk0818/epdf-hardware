"""Where may a via legally go? (debug helper)

    python tools/find_via_spot.py <net> x0 y0 x1 y1 [dia] [drill]

Scans the box on the router grid and prints the legal via spots grouped into
clusters (one line per cluster) - handy to find room near a crowded pad.
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
    dia = float(sys.argv[6]) if len(sys.argv) > 6 else 0.4
    drill = float(sys.argv[7]) if len(sys.argv) > 7 else 0.2
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=lambda *a: None)
    clear = R.net_params(net)["clearance"]
    m = sess.rtr.via_mask(net, dia / 2.0, drill / 2.0, clear)
    hits = set()
    for j in range(int(y0 / R.PITCH), int(y1 / R.PITCH) + 1):
        for i in range(int(x0 / R.PITCH), int(x1 / R.PITCH) + 1):
            if 0 <= i < R.W and 0 <= j < R.H and m[j, i]:
                hits.add((i, j))
    print(f"{net}: {len(hits)} legal {dia}/{drill} via cells in "
          f"({x0},{y0})-({x1},{y1})")
    seen = set()
    for cell in sorted(hits):
        if cell in seen:
            continue
        stack, cl = [cell], []
        while stack:
            a, b = stack.pop()
            if (a, b) in seen or (a, b) not in hits:
                continue
            seen.add((a, b))
            cl.append((a, b))
            for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                stack.append((a + da, b + db))
        xs = [c[0] for c in cl]
        ys = [c[1] for c in cl]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        print(f"   cluster {len(cl):3d} cells  centre "
              f"({cx * R.PITCH:.2f},{cy * R.PITCH:.2f})  "
              f"x {min(xs) * R.PITCH:.2f}..{max(xs) * R.PITCH:.2f} "
              f"y {min(ys) * R.PITCH:.2f}..{max(ys) * R.PITCH:.2f}")


if __name__ == "__main__":
    main()
