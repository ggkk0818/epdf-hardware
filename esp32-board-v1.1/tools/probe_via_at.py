"""Is a via allowed at a point for a net? (debug helper)

    python tools/probe_via_at.py <net> <x> <y> [dia drill ...]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    net = sys.argv[1]
    x, y = float(sys.argv[2]), float(sys.argv[3])
    verbose = "-v" in sys.argv
    args = [a for a in sys.argv[4:] if a != "-v"]
    sizes = [(float(a), float(b)) for a, b in
             (p.split("/") for p in args)] or [(0.6, 0.3)]
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=lambda *a: None)
    i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
    print(f"net {net} at ({i * R.PITCH:.2f},{j * R.PITCH:.2f}) "
          f"clearance {R.net_params(net)['clearance']}")
    for (dia, drill) in sizes:
        m = sess.rtr.via_mask(net, dia / 2.0, drill / 2.0,
                              R.net_params(net)["clearance"])
        print(f"   via {dia}/{drill}: {'OK' if m[j, i] else 'BLOCKED'}")
        if not m[j, i] and verbose:
            rtr, b = sess.rtr, sess.b
            clear = R.net_params(net)["clearance"]
            via_r, drill_r = dia / 2.0, drill / 2.0
            rec = {"lo": via_r + max(clear, 0.15) + R.EPS,
                   "hi": via_r + max(clear, 0.20) + R.EPS,
                   "hole": max(via_r + clear, drill_r + 0.25) + R.EPS,
                   "res": via_r + max(clear, 0.22) + R.EPS}
            px = np.array([i * R.PITCH], np.float32)
            py = np.array([j * R.PITCH], np.float32)
            for lyr in R.ALL_CU:
                for grp in ("lo", "hi", "hole", "res"):
                    f = b.ob.field(lyr, grp, net)
                    if f[j, i] + 1e-6 >= rec[grp]:
                        continue
                    worst = None
                    for s in b.ob.by[lyr][grp]:
                        if s.net == net:
                            continue
                        d = float(s.dist(px, py)[0])
                        if d < rec[grp] and (worst is None or d < worst[0]):
                            worst = (round(d, 3), s.net)
                    print(f"      {lyr} '{grp}': field {f[j, i]:.3f} < "
                          f"{rec[grp]:.3f} worst={worst}")
                own = b.ob.field(lyr, "lo", None, only_net=net)
                own = np.minimum(own, b.ob.field(lyr, "hi", None,
                                                 only_net=net))
                if not (own[j, i] <= 0.001 or own[j, i] >= via_r + 0.12):
                    print(f"      {lyr} own-copper rule: own={own[j, i]:.3f}")
                if b.keepout_dil[lyr][j, i]:
                    print(f"      {lyr} blocked by a rule area")
            for v in b.net_vias.get(net, []):
                need = drill_r + v["drill"] / 2.0 + R.HOLE_TO_HOLE
                d = math.hypot(v["x"] - i * R.PITCH, v["y"] - j * R.PITCH)
                if d < need - R.EPS:
                    print(f"      blocked by own via at ({v['x']},{v['y']}): "
                          f"d={d:.3f} < {need:.3f}")


if __name__ == "__main__":
    main()
