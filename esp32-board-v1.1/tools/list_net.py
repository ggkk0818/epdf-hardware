"""Print every track and via of one or more nets (debug helper).

    python tools/list_net.py USB_DP_CONN [USB_DN_CONN ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    nets = set(sys.argv[1:])
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    for s in data["segments"]:
        if not nets or s["net"] in nets:
            print(f"  {s['net']:<14s} {s['layer']:<6s} w{s['width']:<5} "
                  f"{s['start']} -> {s['end']} ({s.get('kind', '-')})")
    for v in data["vias"] + data.get("gnd_vias", []):
        if not nets or v["net"] in nets:
            print(f"  {v['net']:<14s} VIA ({v['x']},{v['y']}) "
                  f"{v['dia']}/{v['drill']}")


if __name__ == "__main__":
    main()
