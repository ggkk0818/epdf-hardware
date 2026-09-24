"""Find a placement spot on the PCB for one component, clear of parts and keep-outs."""

import argparse
import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
BOARD_W, BOARD_H = 2165.354, 3307.087

KEEPOUTS = [
    (1929.13, 0.0, 2007.87, BOARD_H),        # right switch column
    (629.92, 3070.87, 703.0, BOARD_H),       # antenna band left of module
    (1462.0, 3070.87, 1535.43, BOARD_H),     # antenna band right of module
    (1295.35, 509.92, 1324.88, 637.87),      # J3 socket keep-outs
    (1295.35, 320.94, 1324.88, 462.68),
    (1336.46, 107.75, 1361.02, 406.58),
    (1689.96, 23.0, 1790.35, 76.15),
    (1361.02, 394.85, 1703.74, 457.84),
]


def main():
    doc, project, ref = sys.argv[1], sys.argv[2], sys.argv[3]
    margin = float(sys.argv[4]) if len(sys.argv) > 4 else 45.0

    res = subprocess.run(
        [EASYEDA, "pcb", "list", "--doc", doc, "--project", project, "--include-bbox"],
        capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    d, _ = json.JSONDecoder().raw_decode(out[i:])
    comps = [c for c in d["result"]["components"] if c.get("bbox")]
    target = next(c for c in comps if c.get("designator") == ref)
    b = target["bbox"]
    w, h = b["maxX"] - b["minX"], b["maxY"] - b["minY"]
    others = [c for c in comps if c.get("designator") != ref]

    def clash(box):
        if (box["minX"] < margin or box["maxX"] > BOARD_W - margin or
                box["minY"] < margin or box["maxY"] > BOARD_H - margin):
            return True
        for (x0, y0, x1, y1) in KEEPOUTS:
            if box["minX"] < x1 + margin and box["maxX"] > x0 - margin and \
               box["minY"] < y1 + margin and box["maxY"] > y0 - margin:
                return True
        for o in others:
            ob = o["bbox"]
            if box["minX"] < ob["maxX"] + margin and box["maxX"] > ob["minX"] - margin and \
               box["minY"] < ob["maxY"] + margin and box["maxY"] > ob["minY"] - margin:
                return True
        return False

    cx0, cy0 = (b["minX"] + b["maxX"]) / 2, (b["minY"] + b["maxY"]) / 2
    best = []
    step = 40.0
    y = margin + h / 2
    while y < BOARD_H - margin:
        x = margin + w / 2
        while x < BOARD_W - margin:
            box = {"minX": x - w / 2, "maxX": x + w / 2,
                   "minY": y - h / 2, "maxY": y + h / 2}
            if not clash(box):
                dist = ((x - cx0) ** 2 + (y - cy0) ** 2) ** 0.5
                best.append((dist, x, y))
            x += step
        y += step
    best.sort()
    print(f"{ref}: bbox {w:.0f}x{h:.0f} mil, current centre ({cx0:.1f},{cy0:.1f})")
    for dist, x, y in best[:8]:
        anchor_x = target["x"] + (x - cx0)
        anchor_y = target["y"] + (y - cy0)
        print(f"   free centre ({x:7.1f},{y:7.1f})  dist {dist:6.1f}  -> anchor ({anchor_x:.2f},{anchor_y:.2f})")


if __name__ == "__main__":
    main()
