"""Move every endpoint of a net that sits on one point to another point.

    python tools/move_endpoint.py <net> fx fy tx ty [--dry-run]

Handy for trimming a stub back to the junction it is really connected at.
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
    ap.add_argument("fx", type=float)
    ap.add_argument("fy", type=float)
    ap.add_argument("tx", type=float)
    ap.add_argument("ty", type=float)
    ap.add_argument("--tol", type=float, default=0.02)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    keep, n = [], 0
    for s in data["segments"]:
        if s["net"] == args.net:
            for end in ("start", "end"):
                if math.hypot(s[end][0] - args.fx,
                              s[end][1] - args.fy) <= args.tol:
                    print(f"   {s['layer']} {s['start']} -> {s['end']} : "
                          f"{end} {s[end]} -> [{args.tx}, {args.ty}]")
                    s[end] = [round(args.tx, 4), round(args.ty, 4)]
                    n += 1
        if math.hypot(s["end"][0] - s["start"][0],
                      s["end"][1] - s["start"][1]) < 1e-6:
            print(f"   drop zero length {s['layer']} at {s['start']}")
            continue
        keep.append(s)
    print(f"moved {n} endpoints, segments {len(data['segments'])} -> {len(keep)}")
    if args.dry_run or not n:
        return 0
    data["segments"] = keep
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
