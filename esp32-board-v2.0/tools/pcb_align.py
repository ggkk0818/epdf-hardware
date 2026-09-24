"""Snap the mechanically-constrained parts onto their required pad positions."""

import argparse
import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
MM = 39.37007874015748
BOARD_H = 3307.0866141732283


def call(args):
    res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    if i < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(out[i:])
    except Exception:
        return None
    return data


# ref -> (pad selection, required position in requirement mm)
#   "mean"  : mean of the given pad numbers
#   "pad:N" : that pad
TARGETS = {
    "J1": ("mean", ["A5", "A6", "A7", "A8", "B5", "B6", "B7", "B8"], (24.000, 77.650)),
    "J2": ("pad:1", None, (2.100, 47.750)),
    "J3": ("pad:1", None, (42.775, 67.475)),
    "J4": ("pad:1", None, (8.400, 61.375)),
    "J5": ("pad:1", None, (8.400, 71.375)),
    "SW3": ("mean", ["1", "2"], (52.850, 15.000)),
    "SW4": ("mean", ["1", "2"], (52.850, 42.000)),
    "SW5": ("mean", ["1", "2"], (52.850, 69.000)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    d = call(["pcb", "list", "--doc", args.doc, "--project", args.project,
              "--include-pads", "--include-bbox"])
    comps = {c.get("designator"): c for c in (d or {}).get("result", {}).get("components", [])}

    out = []
    for ref, (mode, pads, (rx, ry)) in TARGETS.items():
        c = comps.get(ref)
        if not c:
            print("missing", ref)
            continue
        by_num = {}
        for p in c.get("pads") or []:
            by_num.setdefault(str(p.get("padNumber")), []).append(p)
        if mode == "mean":
            pts = [p for n in pads for p in by_num.get(n, [])]
            if not pts:
                print("no pads for", ref)
                continue
            cx = sum(p["x"] for p in pts) / len(pts)
            cy = sum(p["y"] for p in pts) / len(pts)
        else:
            num = mode.split(":", 1)[1]
            pts = by_num.get(num)
            if not pts:
                print("no pad", num, "on", ref)
                continue
            cx, cy = pts[0]["x"], pts[0]["y"]
        tx = rx * MM
        ty = BOARD_H - ry * MM
        dx, dy = tx - cx, ty - cy
        print(f"{ref}: current pad ({cx:.2f},{cy:.2f}) target ({tx:.2f},{ty:.2f}) delta ({dx:.2f},{dy:.2f})")
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            out.append({"ref": ref, "status": "already"})
            continue
        patch = json.dumps({"x": round(c["x"] + dx, 3), "y": round(c["y"] + dy, 3)})
        res = call(["pcb", "modify", "--id", c["primitiveId"], "--patch", patch,
                    "--doc", args.doc, "--project", args.project])
        ok = bool(res and res.get("ok"))
        out.append({"ref": ref, "delta": [dx, dy], "status": "moved" if ok else "failed"})
        print("   ", "moved" if ok else "FAILED")

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
