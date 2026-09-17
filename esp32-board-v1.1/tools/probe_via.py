"""ASCII map of where a via may be dropped for a net (debug helper).

    python tools/probe_via.py <net> <x0> <y0> <x1> <y1> [width]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def main():
    net = sys.argv[1]
    x0, y0, x1, y1 = (float(a) for a in sys.argv[2:6])
    w = float(sys.argv[6]) if len(sys.argv) > 6 else R.net_params(net)["width"]
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=lambda *a: None)
    params = R.net_params(net)
    m, via_ok, dia, drill, soft = sess.masks_for(net, w, False)
    print(f"net {net} w{w} via {dia}/{drill} "
          f"(scale {dia}/{drill} and 0.4/0.2 shown)")
    ok4 = sess.rtr.via_mask(net, 0.2, 0.10, params["clearance"])
    okw = via_ok
    i0, i1 = int(x0 / R.PITCH), int(x1 / R.PITCH)
    j0, j1 = int(y0 / R.PITCH), int(y1 / R.PITCH)
    hdr = "      " + "".join(f"{i * R.PITCH:5.1f}"[-5:]
                             for i in range(i0, i1 + 1, 5))
    print(hdr)
    for j in range(j0, j1 + 1):
        row = "".join("B" if okw[j, i] else "." for i in range(i0, i1 + 1))
        row2 = "".join("b" if ok4[j, i] else "." for i in range(i0, i1 + 1))
        print(f"{j * R.PITCH:6.2f} {row}   {row2}")
    print("B/b = via allowed (net via size / 0.4-0.2)")


if __name__ == "__main__":
    main()
