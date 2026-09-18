"""Find the short GND track fragments that DRC reports as unconnected.

    python tools/find_gnd_frag.py [max_length]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    maxlen = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))
    for s in data["segments"]:
        if s["net"] != "GND":
            continue
        length = math.hypot(s["end"][0] - s["start"][0],
                            s["end"][1] - s["start"][1])
        if length <= maxlen:
            print(f"  {s['layer']:<6s} {s.get('kind', '-'):<8s} w{s['width']:<5}"
                  f" {s['start']} -> {s['end']}  L={length:.4f}")


if __name__ == "__main__":
    main()
