"""Round 21 - close the last two GND records around U5.

    python tools/fix_u5_gnd_round21.py [--dry-run]

The two remaining DRC records are two pockets of GND copper inside the U5
fanout that no via can reach:

  * U5.10 + U5.11 (bridged on the north row): the only 0.4/0.2 via spot in
    reach sits at (29.5, 68.675) - between the two pads - but the 0.8 mm
    BAT_BUS trunk on B.Cu runs straight through it (y 67.8-68.6).  The trunk's
    middle is therefore lifted 0.45 mm north over U5 (45 deg ramps, width kept
    at 0.8 mm), the endpoints stay where they were, so nothing downstream moves.

  * U5.5: its stub ends inside the sealed pocket; the only legal via spot is
    (29.8, 71.1), which needs the 3V3_MAIN In2 trunk to keep the 0.5 mm neck a
    little further south (it went back to 0.85/1.2 mm at y = 71.2).

Both new vias are 0.4/0.2 - the board minimum - and both land on the In1 GND
plane.  The script only edits routing/routing.json; tools/apply_routing.py
then rebuilds the board (it writes a .bak of the json first).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"

# --- 3V3_MAIN In2 trunk: keep the existing 0.5 mm neck 1.4 mm longer ---------
NECK_OLD = [
    {"layer": "In2.Cu", "net": "3V3_MAIN", "width": 0.85,
     "start": [30.6, 71.2], "end": [30.6, 71.55]},
    {"layer": "In2.Cu", "net": "3V3_MAIN", "width": 1.2,
     "start": [30.6, 71.55], "end": [30.6, 75.1]},
]
NECK_NEW = [
    {"layer": "In2.Cu", "net": "3V3_MAIN", "width": 0.5,
     "start": [30.6, 71.2], "end": [30.6, 72.6]},
    {"layer": "In2.Cu", "net": "3V3_MAIN", "width": 1.2,
     "start": [30.6, 72.6], "end": [30.6, 75.1]},
]

# --- BAT_BUS B.Cu trunk: 0.45 mm north detour over the U5 north row ----------
HUMP_OLD = [
    {"layer": "B.Cu", "net": "BAT_BUS", "width": 0.8,
     "start": [31.1, 68.2], "end": [24.5, 68.2]},
]
HUMP_NEW = [
    {"layer": "B.Cu", "net": "BAT_BUS", "width": 0.8,
     "start": [31.1, 68.2], "end": [30.45, 68.2]},
    {"layer": "B.Cu", "net": "BAT_BUS", "width": 0.8,
     "start": [30.45, 68.2], "end": [30.0, 67.75]},
    {"layer": "B.Cu", "net": "BAT_BUS", "width": 0.8,
     "start": [30.0, 67.75], "end": [28.9, 67.75]},
    {"layer": "B.Cu", "net": "BAT_BUS", "width": 0.8,
     "start": [28.9, 67.75], "end": [28.45, 68.2]},
    {"layer": "B.Cu", "net": "BAT_BUS", "width": 0.8,
     "start": [28.45, 68.2], "end": [24.5, 68.2]},
]

# --- GND: two stitching vias + one stub to reach the U5.5 via ---------------
NEW_VIAS = [
    {"x": 29.5, "y": 68.675, "dia": 0.4, "drill": 0.2, "net": "GND",
     "kind": "u5_bridge"},
    {"x": 29.8, "y": 71.1, "dia": 0.4, "drill": 0.2, "net": "GND",
     "kind": "u5_pad5"},
]
NEW_SEGS = [
    {"layer": "F.Cu", "net": "GND", "width": 0.15,
     # starts inside the U5.5 stub (29.7343, 70.325-70.6934) so the two pieces
     # overlap instead of merely touching
     "start": [29.7343, 70.66], "end": [29.7343, 71.1], "kind": "u5_pad5"},
    {"layer": "F.Cu", "net": "GND", "width": 0.15,
     "start": [29.7343, 71.1], "end": [29.8, 71.1], "kind": "u5_pad5"},
]


def same(seg, want):
    return (seg.get("layer") == want["layer"] and seg.get("net") == want["net"]
            and abs(seg.get("width", 0) - want["width"]) < 1e-9
            and all(abs(a - b) < 1e-6
                    for a, b in ((seg["start"][0], want["start"][0]),
                                 (seg["start"][1], want["start"][1]),
                                 (seg["end"][0], want["end"][0]),
                                 (seg["end"][1], want["end"][1]))))


def replace(segments, olds, news, what):
    for old in olds:
        hits = [s for s in segments if same(s, old)]
        if len(hits) != 1:
            raise SystemExit(f"{what}: expected exactly one {old}, found "
                             f"{len(hits)}")
        segments.remove(hits[0])
    for new in news:
        segments.append(dict(new))
    print(f"  {what}: {len(olds)} segment(s) -> {len(news)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    segs = data["segments"]
    if any(v.get("kind", "").startswith("u5_") for v in data.get("gnd_vias", [])):
        raise SystemExit("the U5 round-21 vias are already in routing.json")

    replace(segs, NECK_OLD, NECK_NEW, "3V3_MAIN In2 neck")
    replace(segs, HUMP_OLD, HUMP_NEW, "BAT_BUS trunk detour")
    segs.extend(dict(s) for s in NEW_SEGS)
    data["gnd_vias"] = list(data.get("gnd_vias", [])) + [dict(v)
                                                         for v in NEW_VIAS]
    print(f"  GND: +{len(NEW_VIAS)} vias, +{len(NEW_SEGS)} stub segments")
    if args.dry_run:
        return 0
    shutil.copyfile(ROUTING, ROUTING.with_name("_pre_round21.json"))
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name} (backup: _pre_round21.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
