"""Report which pads each power island covers (debug helper)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    model = json.loads((ROOT / "routing" / "model.json").read_text(encoding="utf-8"))
    for isl in R.ISLANDS:
        cells = set(R.polygon_cells(isl["poly"]))
        hits = []
        for p in model["pads"]:
            if p["net"] != isl["net"]:
                continue
            layers = [R.LAYER_OF_ID.get(l) for l in p["layers"]]
            if isl["layer"] not in layers:
                continue
            i, j = int(round(p["x"] / R.PITCH)), int(round(p["y"] / R.PITCH))
            if (i, j) in cells:
                hits.append(f"{p['ref']}.{p['num']}")
        print(f"{isl['name']:18s} {isl['net']:10s} covers {hits}")


if __name__ == "__main__":
    main()
