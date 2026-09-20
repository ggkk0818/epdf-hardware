"""Append GND stitching vias to routing.json.

    python tools/add_gnd_vias.py --kind usb_return_stitch x,y [x,y ...]

Each point is checked with the router's via mask before it is written, so a
typo cannot create a DRC violation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("points", nargs="+")
    ap.add_argument("--kind", default="stitch")
    ap.add_argument("--dia", type=float, default=0.4)
    ap.add_argument("--drill", type=float, default=0.2)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=lambda *a: None)
    vm = sess.rtr.via_mask("GND", args.dia / 2.0, args.drill / 2.0,
                           R.net_params("GND")["clearance"])
    added = []
    for p in args.points:
        x, y = (float(v) for v in p.split(","))
        i, j = int(round(x / R.PITCH)), int(round(y / R.PITCH))
        ok = 0 <= i < R.W and 0 <= j < R.H and bool(vm[j, i])
        print(f"  GND via ({x:.3f},{y:.3f}) {args.dia}/{args.drill}: "
              f"{'OK' if ok else 'BLOCKED'}")
        if ok:
            added.append({"x": round(x, 4), "y": round(y, 4),
                          "dia": args.dia, "drill": args.drill,
                          "net": "GND", "kind": args.kind})
    if not args.apply or not added:
        return 0
    shutil.copyfile(ROUTING, ROUTING.with_name("_pre_add_gnd.json"))
    data["gnd_vias"] = list(data.get("gnd_vias", [])) + added
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name} (+{len(added)} vias)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
