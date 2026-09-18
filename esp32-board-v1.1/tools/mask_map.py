"""Text map of the router's own legality masks, for one window.

    python tools/mask_map.py <net> x0 y0 x1 y1 [--track 0.15] [--via 0.4/0.2]

Prints one character per router cell:
    '#'  a via of the requested size may be centred here
    '+'  a track of the requested width may be centred here
    '.'  neither
Read-only: it uses the same clearance engine the router uses, so anything the
map allows is legal for DRC as well.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("net")
    ap.add_argument("x0", type=float)
    ap.add_argument("y0", type=float)
    ap.add_argument("x1", type=float)
    ap.add_argument("y1", type=float)
    ap.add_argument("--track", default="0.15")
    ap.add_argument("--via", default="0.4/0.2")
    ap.add_argument("--layer", default="F.Cu")
    a = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=lambda *x: None)
    clear = R.net_params(a.net)["clearance"]

    walk = sess.rtr.masks(a.net, float(a.track) / 2.0, clear)[a.layer][0]
    dia, drill = (float(v) for v in a.via.split("/"))
    vias = sess.rtr.via_mask(a.net, dia / 2.0, drill / 2.0, clear)

    i0, i1 = int(a.x0 / R.PITCH), int(a.x1 / R.PITCH)
    j0, j1 = int(a.y0 / R.PITCH), int(a.y1 / R.PITCH)
    hdr = "        " + "".join(f"{i * R.PITCH % 10:3.0f}"
                               for i in range(i0, i1 + 1, 5))
    print(f"net {a.net} layer {a.layer} track {a.track} via {a.via} "
          f"clearance {clear}")
    print("         " + "".join(f"{i * R.PITCH:6.1f}"
                                for i in range(i0, i1 + 1, 5)))
    for j in range(j0, j1 + 1):
        row = []
        for i in range(i0, i1 + 1):
            if vias[j, i]:
                row.append("#")
            elif walk[j, i]:
                row.append("+")
            else:
                row.append(".")
        print(f"{j * R.PITCH:7.2f}  " + "".join(row))


if __name__ == "__main__":
    main()
