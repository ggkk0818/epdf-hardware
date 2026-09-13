"""Report, in board coordinates, where the battery connector points."""

import math
import pathlib
import re
import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from kicad_fp import split_children

PCB = pathlib.Path("C:/Code/epdf-hardware/esp32-board-v1.1/esp32-board-v1.1.kicad_pcb")


def block(ref):
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
    blk = block(ref)
    at = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk)
    x, y, rot = float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)
    th = math.radians(rot)
    co, si = math.cos(th), math.sin(th)

    def tb(px, py):
        return (x + px * co + py * si, y - px * si + py * co)

    print(f"--- {ref}  at ({x}, {y}) rot {rot}")
    # signal pads
    for c in split_children(blk)[1]:
        if not c.startswith("(pad"):
            continue
        num = re.match(r'\(pad "([^"]*)"', c).group(1)
        a = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", c)
        s = re.search(r"\(size ([-\d.]+) ([-\d.]+)\)", c)
        px, py = tb(float(a.group(1)), float(a.group(2)))
        print(f"    pad {num:2s} centre ({px:6.2f}, {py:6.2f})  size {s.group(1)}x{s.group(2)}")
    # silk / fab extents
    for lname in ("F.Fab", "F.SilkS", "F.CrtYd"):
        xs, ys = [], []
        for c in split_children(blk)[1]:
            if f'"{lname}"' not in c:
                continue
            for cm in re.finditer(r"\((?:start|end|center)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", c):
                px, py = tb(float(cm.group(1)), float(cm.group(2)))
                xs.append(px)
                ys.append(py)
        if xs:
            print(f"    {lname:8s} X {min(xs):6.2f}..{max(xs):6.2f}   Y {min(ys):6.2f}..{max(ys):6.2f}")


for r in sys.argv[1:] or ["J4", "J5"]:
    report(r)
