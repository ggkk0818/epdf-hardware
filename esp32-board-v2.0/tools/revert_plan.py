"""Delete the copper a plan file created (match by geometry, not by id).

    python tools/revert_plan.py work/patch-stat.json [--dry-run]

Ids churn after every edit, so a plan is reverted by matching
(layer, net, rounded endpoints, width) for tracks and (x, y, net) for vias.
Used when a plan was validated against a board state that has since changed and
it now collides with another plan.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402


def tkey(layer, net, x1, y1, x2, y2, width=None):
    a = (round(x1, 1), round(y1, 1))
    b = (round(x2, 1), round(y2, 1))
    return (layer, net, min(a, b), max(a, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ed = json.load(open(args.plan, encoding="utf-8"))
    want_t = {tkey(t["layer"], t["net"], t["x1"], t["y1"], t["x2"], t["y2"])
              for t in ed.get("tracks") or []}
    want_v = {(round(v["x"], 1), round(v["y"], 1), v["net"])
              for v in ed.get("vias") or []}

    lines = geom.call(["pcb", "track-list", "--doc", geom.DOC])["result"]["lines"]
    kill_t = [t["primitiveId"] for t in lines
              if tkey(t["layer"], t.get("net"), t["startX"], t["startY"],
                      t["endX"], t["endY"]) in want_t]
    vias = geom.call(["pcb", "via-list", "--doc", geom.DOC])["result"]["vias"]
    kill_v = [v["primitiveId"] for v in vias
              if (round(v["x"], 1), round(v["y"], 1), v.get("net")) in want_v]
    print(f"plan: {len(want_t)} tracks / {len(want_v)} vias; "
          f"matched {len(kill_t)} tracks / {len(kill_v)} vias")
    if args.dry_run:
        return
    for i in range(0, len(kill_t), 20):
        geom.call(["pcb", "track-delete", "--ids", ",".join(kill_t[i:i + 20]),
                   "--doc", geom.DOC])
    for i in range(0, len(kill_v), 20):
        geom.call(["pcb", "via-delete", "--ids", ",".join(kill_v[i:i + 20]),
                   "--doc", geom.DOC])
    geom.call(["pcb", "pour-rebuild", "--doc", geom.DOC])
    geom.call(["pcb", "save", "--doc", geom.DOC])
    print("reverted")


if __name__ == "__main__":
    main()
