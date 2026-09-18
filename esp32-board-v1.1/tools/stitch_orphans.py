"""Stitch the orphan GND patches with one via each (MD class B).

    python tools/stitch_orphans.py [--dry-run]

Each orphan patch reported by tools/gnd_components.py is a small F.Cu pour
around real GND pads; one 0.40/0.20 via inside it bonds it to the In1 plane.
The via is placed at the first pad of the patch that has room for it, checked
with the router's own clearance engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"

# from tools/gnd_components.py: one entry per orphan patch -> its pads
ORPHANS = [
    ["R28.1", "SW1.2"], ["C14.2", "C19.2", "SW2.2"], ["C30.2"], ["J2.17"],
    ["C26.2", "C34.2", "C35.2", "U6.2"], ["C31.2"], ["J2.8"], ["R31.2"],
    ["C16.2", "C23.2"], ["R13.2"], ["C13.2"], ["U5.11"], ["U5.10"],
    ["D2.2", "D5.2", "R8.2"], ["U5.5"], ["C7.2", "D3.2", "D4.2", "J1.A1"],
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=print)
    pads = {f"{p['ref']}.{p['num']}": p for p in board.pads_of.get("GND", [])}
    added = []
    for group in ORPHANS:
        vm = sess.rtr.via_mask("GND", 0.2, 0.1, R.net_params("GND")["clearance"])
        ok = None
        for key in group:
            p = pads.get(key)
            if p is None:
                continue
            i, j = int(round(p["x"] / R.PITCH)), int(round(p["y"] / R.PITCH))
            if 0 <= i < R.W and 0 <= j < R.H and vm[j, i]:
                ok = (key, p["x"], p["y"])
                break
        if ok is None:
            print(f"  {group}: no room for a 0.4/0.2 via")
            continue
        added.append({"x": round(ok[1], 4), "y": round(ok[2], 4),
                      "dia": 0.4, "drill": 0.2, "net": "GND", "kind": "pad"})
        print(f"  {group}: via at {ok[0]} ({ok[1]:.3f},{ok[2]:.3f})")
    print(f"placed {len(added)} of {len(ORPHANS)} stitching vias")
    if args.dry_run or not added:
        return 0
    data["gnd_vias"] = list(data.get("gnd_vias", [])) + added
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
