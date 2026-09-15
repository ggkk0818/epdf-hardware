"""Print, in board coordinates, every pad of the given placed footprints."""

import math
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from kicad_fp import split_children

PCB = pathlib.Path("C:/Code/epdf-hardware/esp32-board-v1.1/esp32-board-v1.1.kicad_pcb")
NET = pathlib.Path("C:/Code/epdf-hardware/esp32-board-v1.1/current.net")


def netmap():
    root = ET.parse(NET).getroot()
    out = {}
    for n in root.iter("net"):
        name = n.get("name")
        for node in n.findall("node"):
            out[(node.get("ref"), node.get("pin"))] = name
    return out


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


def main():
    nets = netmap()
    refs = sys.argv[1:]
    for ref in refs:
        blk = block(ref)
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk)
        x, y, rot = float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)
        th = math.radians(rot)
        co, si = math.cos(th), math.sin(th)
        print(f"--- {ref}  at ({x}, {y}) rot {rot}")
        rows = []
        for c in split_children(blk)[1]:
            if not c.startswith("(pad"):
                continue
            num = re.match(r'\(pad "([^"]*)"', c).group(1)
            a = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", c)
            px, py = float(a.group(1)), float(a.group(2))
            bx = x + px * co + py * si
            by = y - px * si + py * co
            rows.append((by, bx, num, nets.get((ref, num), "")))
        for by, bx, num, net in sorted(rows):
            print(f"    pad {num:>6s}  board ({bx:7.2f}, {by:7.2f})  {net}")


if __name__ == "__main__":
    main()
