"""Report the board-edge overhang of the mechanically constrained connectors."""

import math
import pathlib
import re
import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from kicad_fp import split_children

PCB = pathlib.Path("C:/Code/epdf-hardware/esp32-board-v1.1/esp32-board-v1.1.kicad_pcb")
BOARD_H = 84.0


def footprint_block(ref):
    t = PCB.read_text(encoding="utf-8")
    i = t.index(f'(property "Reference" "{ref}"')
    j = t.rfind("(footprint ", 0, i)
    depth = 0
    m = j
    while m < len(t):
        if t[m] == "(":
            depth += 1
        elif t[m] == ")":
            depth -= 1
            if depth == 0:
                break
        m += 1
    return t[j : m + 1]


def report(ref):
    blk = footprint_block(ref)
    at = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk)
    x, y, rot = float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)
    th = math.radians(rot)
    co, si = math.cos(th), math.sin(th)

    def to_board(px, py):
        return (x + px * co + py * si, y - px * si + py * co)

    print(f"--- {ref} at ({x}, {y}) rot {rot}")
    for lname in ("F.CrtYd", "F.Fab"):
        xs, ys = [], []
        for c in split_children(blk)[1]:
            if f'"{lname}"' not in c:
                continue
            for cm in re.finditer(r"\((?:start|end|center)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", c):
                px, py = to_board(float(cm.group(1)), float(cm.group(2)))
                xs.append(px)
                ys.append(py)
        if xs:
            print(f"   {lname:8s} X {min(xs):7.2f}..{max(xs):7.2f}   Y {min(ys):7.2f}..{max(ys):7.2f}"
                  f"   (south overhang {max(ys) - BOARD_H:+.2f} mm)")
    ymin, ymax = 1e9, -1e9
    for c in split_children(blk)[1]:
        if not c.startswith("(pad"):
            continue
        a = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", c)
        s = re.search(r"\(size ([-\d.]+) ([-\d.]+)\)", c)
        px, py = to_board(float(a.group(1)), float(a.group(2)))
        h = float(s.group(2))
        ymin = min(ymin, py - h / 2)
        ymax = max(ymax, py + h / 2)
    print(f"   copper   Y {ymin:7.2f}..{ymax:7.2f}   (south overhang {ymax - BOARD_H:+.2f} mm,"
          f" edge clearance {BOARD_H - ymax:+.2f} mm)")


for r in sys.argv[1:] or ["J1", "J3"]:
    report(r)
