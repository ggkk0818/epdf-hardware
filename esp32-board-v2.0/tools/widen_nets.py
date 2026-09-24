"""Widen the high-current nets segment by segment.

Dumps every segment of the target nets, deletes them, and re-creates each one at a
larger width. The original geometry is saved so segments that no longer fit can be
restored individually.
"""

import argparse
import json
import os
import subprocess
import sys
import time

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--nets", required=True)
    ap.add_argument("--width", type=float, required=True)
    ap.add_argument("--only", default="", help="restore mode: JSON file with the segment list")
    ap.add_argument("--only-width", type=float, default=0.0,
                    help="only touch segments currently at this width")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    nets = set(x for x in args.nets.split(",") if x)
    dump = call(["pcb", "track-list", "--doc", args.doc, "--project", args.project])
    lines = (dump or {}).get("result", {}).get("lines", [])
    segs = [w for w in lines if w.get("net") in nets]
    if args.only_width:
        segs = [w for w in segs if float(w.get("lineWidth") or 0) == args.only_width]
    print(f"{len(segs)} segment(s) on {sorted(nets)}")

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(segs, fh, ensure_ascii=False, indent=1)

    ids = [w["primitiveId"] for w in segs]
    for k in range(0, len(ids), 20):
        res = call(["pcb", "track-delete", "--ids", ",".join(ids[k:k + 20]),
                    "--doc", args.doc, "--project", args.project])
        ok = bool(res and res.get("ok"))
        print(f"  delete {k//20+1}: {'ok' if ok else 'FAILED'}")

    made = 0
    for w in segs:
        res = call(["pcb", "track",
                    "--x1", str(w["startX"]), "--y1", str(w["startY"]),
                    "--x2", str(w["endX"]), "--y2", str(w["endY"]),
                    "--layer", str(w["layer"]), "--width", str(args.width),
                    "--net", w["net"], "--doc", args.doc, "--project", args.project])
        if res and res.get("ok"):
            made += 1
        else:
            print("  FAILED re-create", w["net"], w["startX"], w["startY"], w["endX"], w["endY"])
    print(f"recreated {made}/{len(segs)} at {args.width} mil")


if __name__ == "__main__":
    main()
