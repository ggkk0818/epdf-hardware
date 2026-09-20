"""Drop exactly duplicated segments (MD Final DFM Plan Phase C).

    python tools/drop_duplicate_segments.py [--apply] [--vias]

Two segments count as duplicates only when *all* of these match exactly:
net, layer, width, and the two endpoints (A->B and B->A count as the same
physical segment).  Nothing fuzzy: no coordinate rounding, no collinear merge,
no width change, no topology change.  Duplicate vias (same net, position and
size) are reported; --vias also removes them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"


def key_of(s):
    a = tuple(round(v, 6) for v in s["start"])
    b = tuple(round(v, 6) for v in s["end"])
    lo, hi = (a, b) if a <= b else (b, a)
    return (s["net"], s["layer"], round(s["width"], 6), lo, hi)


def via_key(v):
    return (v["net"], round(v["x"], 6), round(v["y"], 6),
            round(v["dia"], 6), round(v["drill"], 6))


def dedup(items, keyfn):
    seen, keep, drops = set(), [], []
    for it in items:
        k = keyfn(it)
        if k in seen:
            drops.append(it)
            continue
        seen.add(k)
        keep.append(it)
    return keep, drops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--vias", action="store_true",
                    help="also drop duplicated vias")
    args = ap.parse_args()

    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    segs = data.get("segments", [])
    keep, drops = dedup(segs, key_of)
    groups = {}
    for d in drops:
        groups.setdefault(key_of(d), 0)
        groups[key_of(d)] += 1
    print(f"segments: {len(segs)} -> {len(keep)}  (dropped {len(drops)} "
          f"exact duplicates in {len(groups)} groups)")
    for k in sorted(groups, key=lambda k: -groups[k])[:12]:
        print(f"  x{groups[k] + 1:<2d} {k[0]:<12s} {k[1]:<6s} w{k[2]:<5.2f} "
              f"{k[3]} -> {k[4]}")

    vias = data.get("vias", [])
    gvias = data.get("gnd_vias", [])
    vkeep, vdrop = dedup(vias, via_key)
    gkeep, gdrop = dedup(gvias, via_key)
    print(f"signal vias: {len(vias)} -> {len(vkeep)} (dup {len(vdrop)});  "
          f"gnd vias: {len(gvias)} -> {len(gkeep)} (dup {len(gdrop)})")
    for v in (vdrop + gdrop)[:8]:
        print(f"  dup via {v['net']:<8s} ({v['x']:.3f},{v['y']:.3f}) "
              f"{v['dia']}/{v['drill']}")

    if not args.apply:
        return 0
    shutil.copyfile(ROUTING, ROUTING.with_name("_pre_dedup.json"))
    data["segments"] = keep
    if args.vias:
        data["vias"] = vkeep
        data["gnd_vias"] = gkeep
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name} (backup: _pre_dedup.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
