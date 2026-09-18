"""Add one hand-placed track to routing.json.

    python tools/add_track.py <net> <layer> <width> x0,y0 x1,y1 [--dry-run]

Used for the small, deliberately hand-shaped pieces (pushing a fan-out aside,
drawing a differential pair) where the automatic router has no freedom left.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("net")
    ap.add_argument("layer")
    ap.add_argument("width", type=float)
    ap.add_argument("p0")
    ap.add_argument("p1")
    ap.add_argument("--kind", default="route")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    a = [round(float(v), 4) for v in args.p0.split(",")]
    b = [round(float(v), 4) for v in args.p1.split(",")]
    seg = {"layer": args.layer, "net": args.net, "width": args.width,
           "start": a, "end": b, "kind": args.kind}
    print(f"  add {seg['net']} {seg['layer']} w{seg['width']} {a} -> {b}")
    if args.dry_run:
        return 0
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    data["segments"].append(seg)
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"segments {len(data['segments'])}, wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
