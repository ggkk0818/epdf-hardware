"""Bridge the tiny gaps left between same-net track pieces.

    python tools/bridge_islands.py --net USB_DP_CONN [--net ...] [--tol 6]

After a batched apply (with degenerate/duplicate segments filtered out) a
polyline can end up as several pieces whose endpoints are only a few mil apart.
The DRC reports those as Connection Errors on primitive ids (e"e####"), not on
pads.  This finds endpoint clusters per net/layer and adds a short bridge.
"""

import argparse
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", action="append", required=True)
    ap.add_argument("--tol", type=float, default=6.0)
    ap.add_argument("--width", type=float, default=10.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    geom.dump(os.path.join(ROOT, "work", "geom.json"))
    g = geom.load(os.path.join(ROOT, "work", "geom.json"))
    edits = {"tracks": [], "vias": []}
    for net in args.net:
        tracks = [t for t in g["tracks"] if t.get("net") == net]
        pts = []
        for t in tracks:
            pts.append((t["layer"], t["startX"], t["startY"], t["primitiveId"]))
            pts.append((t["layer"], t["endX"], t["endY"], t["primitiveId"]))
        used = set()
        for i, (l1, x1, y1, id1) in enumerate(pts):
            if i in used:
                continue
            cluster = [(l1, x1, y1, id1)]
            for j in range(i + 1, len(pts)):
                if j in used:
                    continue
                l2, x2, y2, id2 = pts[j]
                if l2 != l1 or id2 == id1:
                    continue
                if math.hypot(x1 - x2, y1 - y2) <= args.tol:
                    cluster.append((l2, x2, y2, id2))
                    used.add(j)
            if len(cluster) > 1:
                for (_, xa, ya, _) in cluster[1:]:
                    # sub-mil gaps are real (the pieces almost touch) but the
                    # platform drops <1 mil tracks, so overshoot by 2 mil along
                    # the gap direction to guarantee a real overlap.
                    dx, dy = xa - x1, ya - y1
                    L = math.hypot(dx, dy)
                    if L > 0.01:
                        ux, uy = dx / L, dy / L
                    else:
                        ux, uy = 1.0, 0.0
                    xe, ye = xa + ux * 2.0, ya + uy * 2.0
                    edits["tracks"].append({"x1": round(x1, 2), "y1": round(y1, 2),
                                            "x2": round(xe, 2), "y2": round(ye, 2),
                                            "layer": l1, "width": args.width,
                                            "net": net})
        print(f"  {net}: {len(tracks)} tracks -> "
              f"{len([t for t in edits['tracks']])} bridges so far")
    path = os.path.join(ROOT, "work", "bridge-islands.json")
    json.dump(edits, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(edits['tracks'])} bridges -> {path}")
    if not args.dry_run and edits["tracks"]:
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "tools", "apply_plan_batch.py"), path,
                        "--batch", "20"], cwd=ROOT)


if __name__ == "__main__":
    main()
