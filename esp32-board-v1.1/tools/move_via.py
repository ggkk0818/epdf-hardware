"""Move one via of a net and re-attach the tracks that ended on it.

    python tools/move_via.py <net> <old_x> <old_y> <new_x> <new_y> [--dry-run]

Every segment endpoint that sat exactly on the old position follows the via, so
the net stays connected.  Segments that collapse to zero length are dropped.
Nothing else is touched - use tools/check_routing.py and DRC to verify.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("net")
    ap.add_argument("old_x", type=float)
    ap.add_argument("old_y", type=float)
    ap.add_argument("new_x", type=float)
    ap.add_argument("new_y", type=float)
    ap.add_argument("--tol", type=float, default=0.02)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    via = None
    for v in data["vias"] + data.get("gnd_vias", []):
        if v["net"] == args.net \
                and math.hypot(v["x"] - args.old_x,
                               v["y"] - args.old_y) <= args.tol:
            via = v
            break
    if via is None:
        print(f"no {args.net} via at ({args.old_x},{args.old_y})")
        return 1
    print(f"via {args.net} {via['dia']}/{via['drill']} "
          f"({via['x']},{via['y']}) -> ({args.new_x},{args.new_y})")
    via["x"], via["y"] = round(args.new_x, 4), round(args.new_y, 4)

    keep = []
    for s in data["segments"]:
        if s["net"] != args.net:
            keep.append(s)
            continue
        for end in ("start", "end"):
            if math.hypot(s[end][0] - args.old_x,
                          s[end][1] - args.old_y) <= args.tol:
                print(f"   re-attach {s['layer']} {s['start']} -> {s['end']}")
                s[end] = [round(args.new_x, 4), round(args.new_y, 4)]
        if math.hypot(s["end"][0] - s["start"][0],
                      s["end"][1] - s["start"][1]) < 1e-6:
            print(f"   drop zero length {s['layer']} at {s['start']}")
            continue
        keep.append(s)
    print(f"segments {len(data['segments'])} -> {len(keep)}")
    if args.dry_run:
        return 0
    data["segments"] = keep
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
