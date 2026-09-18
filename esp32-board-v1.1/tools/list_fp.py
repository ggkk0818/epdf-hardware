"""Print the pads of one footprint (debug helper).

    python tools/list_fp.py J1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ref = sys.argv[1]
    model = json.loads((ROOT / "routing" / "model.json").read_text(
        encoding="utf-8"))
    pads = [p for p in model["pads"] if p["ref"] == ref]
    for p in sorted(pads, key=lambda p: (p["y"], p["x"])):
        print(f"  {p['num']:<4s} [{p['net']:<14s}] ({p['x']:.3f},{p['y']:.3f})"
              f" {p['w']}x{p['h']} rot{p.get('rot')}")


if __name__ == "__main__":
    main()
