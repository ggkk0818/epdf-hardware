"""Remove the tracks DRC reports as "unconnected end" (track_dangling).

    python tools/drop_dangling.py [drc.json] [--net GND] [--dry-run]

A track with a free end carries no connection (its other end is attached to
the net's copper), so removing it cannot disconnect anything - it only removes
the warning.  Only items that match exactly one segment (layer, length and
endpoint) are touched.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drc", nargs="?", default=str(ROOT / "drc.json"))
    ap.add_argument("--net", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    drc = json.loads(Path(args.drc).read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    wanted = []
    for v in drc["violations"]:
        if v["type"] != "track_dangling":
            continue
        for it in v["items"]:
            desc = it.get("description", "")
            m = re.match(r"Track \[([^\]]*)\] on (\S+), length ([\d.]+)", desc)
            if not m:
                continue
            net, layer, length = m.group(1), m.group(2), float(m.group(3))
            if args.net and net != args.net:
                continue
            pos = it.get("pos") or {}
            if "x" in pos:
                wanted.append((net, layer, length, pos["x"], pos["y"]))

    keep, dropped = [], []
    for s in data["segments"]:
        hit = None
        length = math.hypot(s["end"][0] - s["start"][0],
                            s["end"][1] - s["start"][1])
        for (net, layer, wl, wx, wy) in wanted:
            if s["net"] != net or s["layer"] != layer \
                    or abs(length - wl) > 0.005:
                continue
            if any(math.hypot(c[0] - wx, c[1] - wy) < 0.02
                   for c in (s["start"], s["end"])):
                hit = (net, layer, wl, wx, wy)
                break
        if hit:
            dropped.append(s)
        else:
            keep.append(s)
    for s in dropped:
        print(f"  drop {s['net']} {s['layer']} {s['start']} -> {s['end']} "
              f"w{s['width']} ({s.get('kind', '-')})")
    print(f"dropped {len(dropped)} of {len(data['segments'])} segments")
    if args.dry_run or not dropped:
        return 0
    data["segments"] = keep
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
