"""Find free cells on a schematic page for relocating congested small parts."""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def main():
    doc, project, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
    res = subprocess.run(
        [EASYEDA, "sch", "list", "--page", doc, "--include-bbox", "--project", project],
        capture_output=True, text=True, encoding="utf-8")
    r = json.loads(res.stdout)["result"]
    boxes = []
    for c in r["components"]:
        if c.get("componentType") != "part":
            continue
        b = c.get("bbox")
        if b:
            boxes.append(b)

    CW, CH = 160, 130          # cell size
    MARGIN = 30
    W, H = 1655, 1170
    title = {"minX": 953, "minY": 0, "maxX": 1655, "maxY": 198}  # A3 title block

    def free(cx, cy):
        x0, y0 = cx - CW / 2 - MARGIN, cy - CH / 2 - MARGIN
        x1, y1 = cx + CW / 2 + MARGIN, cy + CH / 2 + MARGIN
        if x0 < 20 or y0 < 220 or x1 > W - 20 or y1 > H - 20:
            return False
        for b in boxes + [title]:
            if b["minX"] < x1 and b["maxX"] > x0 and b["minY"] < y1 and b["maxY"] > y0:
                return False
        return True

    spots = []
    for cy in range(300, H - 100, CH):
        for cx in range(100, W - 100, CW):
            if free(cx, cy):
                spots.append((cx, cy))
    # prefer lower rows (bottom of the sheet) to stay clear of the modules
    spots.sort(key=lambda p: (p[1], p[0]))
    chosen = spots[:count]
    print(json.dumps(chosen))


if __name__ == "__main__":
    main()
