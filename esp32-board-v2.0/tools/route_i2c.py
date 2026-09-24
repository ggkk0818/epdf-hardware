"""Route the two I2C nets manually.

Freerouting left these two 5-pad nets unrouted. Each net gets its own vertical trunk
(SDA on Bottom, SCL on Inner2) so the branches, which reach both sides of the board,
never cross each other on one layer.
"""

import json
import subprocess
import sys
import time

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
DOC, PROJECT = "PCB1", "esp32s3-board-v2.0"

TOP, BOTTOM, INNER2 = 1, 2, 16

# net -> (trunk layer, trunk x, [ (pad xy, via xy, top stub), ... ], [ (y, x_from, x_to) ])
PLAN = {
    "I2C_SDA": {
        "layer": BOTTOM,
        "trunk_x": 1140.0,
        "ys": [228.4, 620.1, 745.6, 2468.3, 3201.6],
        "vias": [
            (1200.0, 228.4, 1269.7, 228.4),
            (700.0, 620.1, 747.0, 620.1),
            (460.0, 745.6, 502.0, 745.6),
            (700.0, 2468.3, 738.2, 2468.3),
            (1620.0, 3201.6, 1659.2, 3201.6),
        ],
        "branches": [(1200.0, 228.4), (700.0, 620.1), (460.0, 745.6),
                     (700.0, 2468.3), (1620.0, 3201.6)],
    },
    "I2C_SCL": {
        "layer": INNER2,
        "trunk_x": 1140.0,
        "ys": [244.1, 639.8, 800.0, 2170.5, 2267.9],
        "vias": [
            (1240.0, 244.1, 1269.7, 244.1),
            (680.0, 639.8, 747.0, 639.8),
            (521.7, 800.0, 521.7, 745.6),
            (1560.0, 2170.5, 1591.8, 2170.5),
            (1250.0, 2267.9, 1207.7, 2267.9),
        ],
        "branches": [(1240.0, 244.1), (680.0, 639.8), (521.7, 800.0),
                     (1560.0, 2170.5), (1250.0, 2267.9)],
    },
}


def call(args):
    res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(out[i:])[0]
    except Exception:
        return None


def add(cmd):
    r = call(cmd + ["--doc", DOC, "--project", PROJECT])
    ok = bool(r and r.get("ok"))
    if not ok:
        print("   FAILED:", " ".join(cmd), ((r or {}).get("error") or {}).get("message", ""))
    return ok


def main():
    total_ok = 0
    for net, plan in PLAN.items():
        layer = plan["layer"]
        tx = plan["trunk_x"]
        print("==", net, "trunk on layer", layer)
        for (vx, vy, px, py) in plan["vias"]:
            total_ok += add(["pcb", "via", "--x", str(vx), "--y", str(vy), "--net", net])
            total_ok += add(["pcb", "track", "--x1", str(px), "--y1", str(py),
                             "--x2", str(vx), "--y2", str(vy), "--layer", str(TOP),
                             "--width", "10", "--net", net])
        ys = plan["ys"]
        total_ok += add(["pcb", "track", "--x1", str(tx), "--y1", str(min(ys)),
                         "--x2", str(tx), "--y2", str(max(ys)), "--layer", str(layer),
                         "--width", "10", "--net", net])
        for (bx, by) in plan["branches"]:
            total_ok += add(["pcb", "track", "--x1", str(tx), "--y1", str(by),
                             "--x2", str(bx), "--y2", str(by), "--layer", str(layer),
                             "--width", "10", "--net", net])
        time.sleep(1)
    print("primitives added:", total_ok)


if __name__ == "__main__":
    main()
