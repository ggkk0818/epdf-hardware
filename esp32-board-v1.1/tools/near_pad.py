"""List every piece of foreign copper close to a pad (debug helper).

    python tools/near_pad.py 33.275 43.6 [radius]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402


def main():
    x, y = float(sys.argv[1]), float(sys.argv[2])
    radius = float(sys.argv[3]) if len(sys.argv) > 3 else 0.85
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(R.OUT_PATH.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    print(f"copper within {radius} mm of ({x}, {y}):")
    for net, segs in board.net_segments.items():
        for s in segs:
            d = min(math.hypot(s["start"][0] - x, s["start"][1] - y),
                    math.hypot(s["end"][0] - x, s["end"][1] - y))
            if d < radius:
                print(f"   {net:<14s} {s['layer']:<6s} {s.get('kind', '-'):<5s} "
                      f"d={d:.2f} {s['start']} -> {s['end']} w{s['width']}")
    for p in model["pads"]:
        d = math.hypot(p["x"] - x, p["y"] - y)
        if 0.01 < d < radius + 0.3:
            print(f"   PAD {p['ref']}.{p['num']} [{p['net']}] d={d:.2f} "
                  f"({p['x']},{p['y']}) {p['w']}x{p['h']} {p['shape']}")
    for v in data["vias"] + data.get("gnd_vias", []):
        d = math.hypot(v["x"] - x, v["y"] - y)
        if d < radius:
            print(f"   VIA [{v['net']}] d={d:.2f} ({v['x']},{v['y']}) "
                  f"{v['dia']}/{v['drill']}")


if __name__ == "__main__":
    main()
