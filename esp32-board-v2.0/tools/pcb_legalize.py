"""Legalise the PCB placement without ever moving the fixed parts.

`pcb place-constrained` snaps edge connectors to their nearest edge and ignores the
lock, which displaced J2/J3/U1. This pass instead only moves *unlocked* satellites,
searching a spiral of offsets until a part is clear of every other part, of the
board edges and of the mechanical keep-outs.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOARD_W = 2165.354
BOARD_H = 3307.087
MARGIN = 12.0

# mechanical keep-outs that must stay clear of components (mil rect x0,y0,x1,y1)
KEEPOUTS = [
    (1929.13, 0.0, 2007.87, BOARD_H),          # right switch column
    (629.92, 3070.87, 708.66, BOARD_H),        # antenna band, left of the module
    (1466.69, 3070.87, 1535.43, BOARD_H),      # antenna band, right of the module
]


def call(args, tries=3):
    for k in range(tries):
        res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
        out = res.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(1.5 + 1.5 * k)
    return None


def fetch(doc, project):
    d = call(["pcb", "list", "--doc", doc, "--project", project, "--include-bbox"])
    comps = []
    for c in (d or {}).get("result", {}).get("components", []):
        if c.get("bbox"):
            comps.append(c)
    return comps


def boxes_overlap(a, b, gap):
    return (a["minX"] - gap < b["maxX"] and a["maxX"] + gap > b["minX"] and
            a["minY"] - gap < b["maxY"] and a["maxY"] + gap > b["minY"])


def in_keepout(box):
    for (x0, y0, x1, y1) in KEEPOUTS:
        if box["minX"] < x1 and box["maxX"] > x0 and box["minY"] < y1 and box["maxY"] > y0:
            return True
    return False


def on_board(box):
    return (box["minX"] >= MARGIN and box["maxX"] <= BOARD_W - MARGIN and
            box["minY"] >= MARGIN and box["maxY"] <= BOARD_H - MARGIN)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--gap", type=float, default=12.0)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    comps = fetch(args.doc, args.project)
    fixed = [c for c in comps if c.get("locked")]
    movable = [c for c in comps if not c.get("locked")]
    # biggest first: anchors settle before small satellites shuffle around them
    movable.sort(key=lambda c: -((c["bbox"]["maxX"] - c["bbox"]["minX"]) *
                                 (c["bbox"]["maxY"] - c["bbox"]["minY"])))

    placed = list(fixed)
    moved, failed = [], []
    for c in movable:
        box = dict(c["bbox"])
        ok = (not in_keepout(box)) and on_board(box) and \
             not any(boxes_overlap(box, o["bbox"], args.gap) for o in placed)
        if ok:
            placed.append(c)
            continue

        w = box["maxX"] - box["minX"]
        h = box["maxY"] - box["minY"]
        target = None
        for radius in range(40, 2000, 40):
            found = False
            for ang in range(0, 360, 30):
                dx = radius * math.cos(math.radians(ang))
                dy = radius * math.sin(math.radians(ang))
                cand = {"minX": box["minX"] + dx, "maxX": box["maxX"] + dx,
                        "minY": box["minY"] + dy, "maxY": box["maxY"] + dy}
                if not on_board(cand) or in_keepout(cand):
                    continue
                if any(boxes_overlap(cand, o["bbox"], args.gap) for o in placed):
                    continue
                target = cand
                found = True
                break
            if found:
                break
        if not target:
            failed.append(c.get("designator"))
            placed.append(c)
            continue

        dx = target["minX"] - box["minX"]
        dy = target["minY"] - box["minY"]
        patch = json.dumps({"x": round(c["x"] + dx, 3), "y": round(c["y"] + dy, 3)})
        r = call(["pcb", "modify", "--id", c["primitiveId"], "--patch", patch,
                  "--doc", args.doc, "--project", args.project])
        ok = bool(r and r.get("ok"))
        moved.append({"ref": c.get("designator"), "d": [round(dx, 1), round(dy, 1)], "ok": ok})
        print(f"  moved {c.get('designator'):5s} by ({dx:7.1f},{dy:7.1f}) {'ok' if ok else 'FAILED'}",
              flush=True)
        c2 = dict(c)
        c2["bbox"] = target
        placed.append(c2)
        time.sleep(0.5)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump({"moved": moved, "failed": failed}, fh, ensure_ascii=False, indent=1)
    print(f"legalised: moved {len(moved)}, could not place {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
