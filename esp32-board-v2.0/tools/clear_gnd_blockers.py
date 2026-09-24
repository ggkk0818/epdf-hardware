"""Free space for the high-current trunks by removing the parallel GND tracks that
block them, then widening those trunk segments.

GND is carried by the Inner1 plane plus the top/bottom pours, so a redundant parallel
GND stub can go. Anything that still fails DRC is reverted by revert_wide.py.
"""

import argparse
import json
import math
import subprocess
import sys
import time

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def call(args, tries=3):
    for k in range(tries):
        r = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
        out = r.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(1.0 + k)
    return None


def seg_dist(a, b):
    (x1, y1), (x2, y2) = a
    (x3, y3), (x4, y4) = b
    if x1 == x2 == x3 == x4:
        return abs(y1 - y3) if max(min(y1, y2), min(y3, y4)) <= min(max(y1, y2), max(y3, y4)) else min(
            math.dist((x1, y1), (x3, y3)), math.dist((x1, y1), (x4, y4)))
    if y1 == y2 == y3 == y4:
        return abs(x1 - x3) if max(min(x1, x2), min(x3, x4)) <= min(max(x1, x2), max(x3, x4)) else min(
            math.dist((x1, y1), (x3, y3)), math.dist((x1, y1), (x4, y4)))
    return min(math.dist((x1, y1), (x3, y3)), math.dist((x1, y1), (x4, y4)),
               math.dist((x2, y2), (x3, y3)), math.dist((x2, y2), (x4, y4)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--nets", required=True)
    ap.add_argument("--min-len", type=float, default=80.0)
    ap.add_argument("--radius", type=float, default=30.0)
    ap.add_argument("--width", type=float, default=20.0)
    args = ap.parse_args()

    nets = set(x for x in args.nets.split(",") if x)
    tracks = (call(["pcb", "track-list", "--doc", args.doc, "--project", args.project])
              or {}).get("result", {}).get("lines", [])

    targets = []
    for w in tracks:
        if w.get("net") not in nets or float(w.get("lineWidth") or 0) > 11:
            continue
        L = math.dist((w["startX"], w["startY"]), (w["endX"], w["endY"]))
        if L >= args.min_len:
            targets.append(w)
    print(f"{len(targets)} thin trunk segment(s) to widen")

    killed = set()
    for w in targets:
        a = ((w["startX"], w["startY"]), (w["endX"], w["endY"]))
        for o in tracks:
            if o.get("net") != "GND" or o.get("layer") != w.get("layer"):
                continue
            b = ((o["startX"], o["startY"]), (o["endX"], o["endY"]))
            if seg_dist(a, b) < args.radius:
                killed.add(o["primitiveId"])
    print(f"  parallel GND blockers to drop: {len(killed)}")
    for k in range(0, len(killed), 20):
        chunk = sorted(killed)[k:k + 20]
        r = call(["pcb", "track-delete", "--ids", ",".join(chunk),
                  "--doc", args.doc, "--project", args.project])
        print("  delete blockers:", "ok" if (r and r.get("ok")) else "FAILED")

    made = 0
    for w in targets:
        call(["pcb", "track-delete", "--ids", w["primitiveId"],
              "--doc", args.doc, "--project", args.project])
        r = call(["pcb", "track",
                  "--x1", str(w["startX"]), "--y1", str(w["startY"]),
                  "--x2", str(w["endX"]), "--y2", str(w["endY"]),
                  "--layer", str(w["layer"]), "--width", str(args.width),
                  "--net", w["net"], "--doc", args.doc, "--project", args.project])
        made += 1 if (r and r.get("ok")) else 0
    print(f"  widened {made}/{len(targets)}")


if __name__ == "__main__":
    main()
