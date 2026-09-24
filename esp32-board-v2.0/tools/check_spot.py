"""Score candidate placements for a component by the escape room on each side."""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
BOARD_W, BOARD_H = 2165.354, 3307.087


def main():
    doc, project, ref = sys.argv[1], sys.argv[2], sys.argv[3]
    cands = json.loads(sys.argv[4])          # [[x, y, rot], ...]

    res = subprocess.run(
        [EASYEDA, "pcb", "list", "--doc", doc, "--project", project, "--include-bbox"],
        capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    comps = [c for c in json.JSONDecoder().raw_decode(out[i:])[0]["result"]["components"]
             if c.get("bbox")]
    me = next(c for c in comps if c.get("designator") == ref)
    others = [c for c in comps if c.get("designator") != ref]
    w = me["bbox"]["maxX"] - me["bbox"]["minX"]
    h = me["bbox"]["maxY"] - me["bbox"]["minY"]
    if int(me.get("rotation") or 0) % 180 == 90:
        w, h = h, w

    print(f"{ref} size {w:.0f}x{h:.0f} mil; scoring {len(cands)} candidate(s)")
    for (x, y, rot) in cands:
        box = {"minX": x - w / 2, "maxX": x + w / 2, "minY": y - h / 2, "maxY": y + h / 2}
        clash = None
        gap = {"left": box["minX"], "right": BOARD_W - box["maxX"],
               "bottom": box["minY"], "top": BOARD_H - box["maxY"]}
        for o in others:
            ob = o["bbox"]
            if box["minX"] < ob["maxX"] and box["maxX"] > ob["minX"] and \
               box["minY"] < ob["maxY"] and box["maxY"] > ob["minY"]:
                clash = o.get("designator")
                break
            if box["minY"] < ob["maxY"] and box["maxY"] > ob["minY"]:
                if ob["maxX"] <= box["minX"]:
                    gap["left"] = min(gap["left"], box["minX"] - ob["maxX"])
                if ob["minX"] >= box["maxX"]:
                    gap["right"] = min(gap["right"], ob["minX"] - box["maxX"])
            if box["minX"] < ob["maxX"] and box["maxX"] > ob["minX"]:
                if ob["maxY"] <= box["minY"]:
                    gap["bottom"] = min(gap["bottom"], box["minY"] - ob["maxY"])
                if ob["minY"] >= box["maxY"]:
                    gap["top"] = min(gap["top"], ob["minY"] - box["maxY"])
        worst = min(gap.values())
        verdict = "OK " if (clash is None and worst >= 35) else "no "
        print(f"  {verdict} centre ({x:7.1f},{y:7.1f}) rot {rot:3d}  "
              f"gaps L{gap['left']:.0f} R{gap['right']:.0f} B{gap['bottom']:.0f} T{gap['top']:.0f}"
              + (f"  OVERLAPS {clash}" if clash else ""))


if __name__ == "__main__":
    main()
