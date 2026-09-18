"""List the rule areas / keepouts of the board model (debug helper)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    model = json.loads((ROOT / "routing" / "model.json").read_text(
        encoding="utf-8"))
    for k in model["keepouts"]:
        xs = [q[0] for q in k["polygon"]]
        ys = [q[1] for q in k["polygon"]]
        ko = k.get("keepout", {})
        print(f"  {k.get('name', '?')}: layers {k['layers']} "
              f"bbox x {min(xs):.2f}..{max(xs):.2f} y {min(ys):.2f}.."
              f"{max(ys):.2f} tracks={ko.get('tracks')} vias={ko.get('vias')} "
              f"pads={ko.get('pads')}")


if __name__ == "__main__":
    main()
