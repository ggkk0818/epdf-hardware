"""Delete a net's copper inside a box (local rip-up).

    python tools/rip_local.py <net> x0 y0 x1 y1 [--dry-run]

Used when a short piece of one net blocks another and has to be re-routed.
The net is left disconnected inside the box on purpose - re-route it with
tools/bridge_net.py right afterwards.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def inside(p, box):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("net")
    ap.add_argument("box", help="x0,y0,x1,y1")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    box = tuple(float(v) for v in args.box.split(","))

    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    keep, gone = [], []
    for s in data["segments"]:
        if s["net"] != args.net:
            keep.append(s)
            continue
        # a segment is ripped only when it lies *entirely* inside the box, so
        # the copper outside the box keeps its shape
        if inside(s["start"], box) and inside(s["end"], box):
            gone.append(s)
        else:
            keep.append(s)
    vgone = []
    for key in ("vias", "gnd_vias"):
        rest = []
        for v in data.get(key, []):
            if v["net"] == args.net and inside((v["x"], v["y"]), box):
                vgone.append(v)
            else:
                rest.append(v)
        data[key] = rest
    for s in gone:
        print(f"  rip {s['layer']} {s['start']} -> {s['end']} w{s['width']}")
    for v in vgone:
        print(f"  rip via ({v['x']},{v['y']}) {v['dia']}/{v['drill']}")
    print(f"ripped {len(gone)} segments and {len(vgone)} vias of {args.net}")
    if args.dry_run or not (gone or vgone):
        return 0
    data["segments"] = keep
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
