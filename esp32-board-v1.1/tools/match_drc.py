"""Match DRC violations against routing.json items (debug helper)."""

from __future__ import annotations

import collections
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    kind_filter = sys.argv[1] if len(sys.argv) > 1 else "track_dangling"
    d = json.loads((ROOT / "drc.json").read_text(encoding="utf-8"))
    r = json.loads((ROOT / "routing" / "routing.json").read_text(encoding="utf-8"))
    segs = r["segments"]
    counts = collections.Counter()
    examples = []
    for x in d["violations"]:
        if x["type"] != kind_filter:
            continue
        pos = x["items"][0].get("pos")
        best = None
        for s in segs:
            cx = (s["start"][0] + s["end"][0]) / 2
            cy = (s["start"][1] + s["end"][1]) / 2
            dd = math.hypot(cx - pos["x"], cy - pos["y"])
            if best is None or dd < best[0]:
                best = (dd, s)
        if best and best[0] < 0.2:
            counts[best[1].get("kind")] += 1
            examples.append(best)
        else:
            counts["no match"] += 1
    print(kind_filter, dict(counts))
    for dd, s in examples[:10]:
        print("  {:<12s} {:<6s} {} -> {} w{}  (d={:.3f})".format(
            s["net"], str(s.get("kind")), s["start"], s["end"], s["width"], dd))


if __name__ == "__main__":
    main()
