"""Add one hand-placed via to routing.json.

    python tools/add_via.py <net> x y dia drill [--dry-run]
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
    ap.add_argument("x", type=float)
    ap.add_argument("y", type=float)
    ap.add_argument("dia", type=float)
    ap.add_argument("drill", type=float)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    v = {"x": round(args.x, 4), "y": round(args.y, 4),
         "dia": args.dia, "drill": args.drill, "net": args.net}
    print(f"  add via {v}")
    if args.dry_run:
        return 0
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    data["vias"].append(v)
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"vias {len(data['vias'])}, wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
