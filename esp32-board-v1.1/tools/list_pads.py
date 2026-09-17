"""List the pads of a net (or all nets) with their coordinates.

    python tools/list_pads.py [net]
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    model = json.loads((ROOT / "routing" / "model.json").read_text(
        encoding="utf-8"))
    net = sys.argv[1] if len(sys.argv) > 1 else None
    if net is None:
        c = collections.Counter(p["net"] for p in model["pads"] if p["net"])
        for k, v in sorted(c.items()):
            print(f"  {v:3d}  {k}")
        return
    for p in model["pads"]:
        if p["net"] != net:
            continue
        print(f"  {p['ref']}.{p['num']:<3s} ({p['x']:6.2f},{p['y']:6.2f}) "
              f"{p['w']}x{p['h']} rot{p.get('rot')} {p['type']}")


if __name__ == "__main__":
    main()
