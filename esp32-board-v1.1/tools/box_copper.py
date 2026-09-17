"""List every piece of copper inside a box (debug helper).

    python tools/box_copper.py x0 y0 x1 y1 [net]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    x0, y0, x1, y1 = (float(a) for a in sys.argv[1:5])
    only = sys.argv[5] if len(sys.argv) > 5 else None
    model = json.loads((ROOT / "routing" / "model.json").read_text(
        encoding="utf-8"))
    data = json.loads((ROOT / "routing" / "routing.json").read_text(
        encoding="utf-8"))

    def inbox(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1

    print("-- tracks")
    for s in data["segments"]:
        if only and s["net"] != only:
            continue
        if inbox(s["start"]) or inbox(s["end"]):
            print(f"   {s['net']:<14s} {s['layer']:<6s} {s.get('kind', '-'):<7s}"
                  f" w{s['width']:<4} [{s['start'][0]:.2f},{s['start'][1]:.2f}]"
                  f"->[{s['end'][0]:.2f},{s['end'][1]:.2f}]")
    print("-- vias")
    for v in data["vias"] + data.get("gnd_vias", []):
        if only and v["net"] != only:
            continue
        if x0 <= v["x"] <= x1 and y0 <= v["y"] <= y1:
            print(f"   {v['net']:<14s} ({v['x']:.3f},{v['y']:.3f}) "
                  f"{v['dia']}/{v['drill']}")
    print("-- pads")
    for p in model["pads"]:
        if only and p["net"] != only:
            continue
        if x0 <= p["x"] <= x1 and y0 <= p["y"] <= y1:
            print(f"   {p['ref']}.{p['num']:<4s} [{p['net']:<13s}] "
                  f"({p['x']:.2f},{p['y']:.2f}) {p['w']}x{p['h']} "
                  f"rot{p.get('rot')}")


if __name__ == "__main__":
    main()
