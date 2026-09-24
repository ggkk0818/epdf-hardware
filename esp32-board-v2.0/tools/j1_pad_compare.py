"""Compare the J1 (USB-C) footprint pads between the v1.1 final PCB and the v2 board.

    python tools/j1_pad_compare.py

Checks the mechanical structure the requirement document 5.1 specifies: the
16-contact signal row (0.60 x 1.15 and 0.30 x 1.15 mm, 0.5 mm pitch, 6.40 mm
span), the four oval shield slots (1.00 x 1.80 / 1.00 x 2.10 mm, 8.64 x 4.18 mm
apart) and the two 0.65 mm NPTH locating holes.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
V11 = os.path.join(os.path.dirname(ROOT), "esp32-board-v1.1")
PCB = os.path.join(V11, "esp32-board-v1.1_final_drc_20260920.kicad_pcb")
MIL = 0.0254


def block_at(txt, start):
    depth, i, instr = 0, start, False
    while i < len(txt):
        ch = txt[i]
        if instr:
            if ch == '"' and txt[i - 1] != "\\":
                instr = False
        elif ch == '"':
            instr = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return txt[start:i + 1]
        i += 1
    return txt[start:]


def v11_j1():
    txt = open(PCB, encoding="utf-8").read()
    for m in re.finditer(r"\(footprint ", txt):
        blk = block_at(txt, m.start())
        if re.search(r'\(property "Reference" "J1"', blk):
            out = []
            for pm in re.finditer(r"\(pad ", blk):
                pad = block_at(blk, pm.start())
                head = re.match(r'\(pad "([^"]*)" (\S+)', pad)
                at = re.search(r"\(at ([-\d.]+) ([-\d.]+)", pad)
                sz = re.search(r"\(size ([\d.]+) ([\d.]+)\)", pad)
                dr = re.search(r"\(drill ([^)]*)\)", pad)
                net = re.search(r'\(net "([^"]*)"\)', pad)
                out.append({
                    "num": head.group(1), "type": head.group(2),
                    "x": float(at.group(1)) if at else None,
                    "y": float(at.group(2)) if at else None,
                    "w": float(sz.group(1)) * MIL if sz else None,
                    "h": float(sz.group(2)) * MIL if sz else None,
                    "drill": dr.group(1) if dr else None,
                    "net": net.group(1) if net else "",
                })
            return out
    return []


def v2_j1():
    txt = open(os.path.join(ROOT, "work", "audit", "pcb-dump.json"),
               encoding="utf-8").read()
    d = json.loads(txt[txt.find("{"):])
    r = d.get("result", d)
    for c in r.get("components") or []:
        if (c.get("designator") or c.get("ref")) == "J1":
            return [{"num": p.get("padNumber"), "net": p.get("net"),
                     "x": p.get("x"), "y": p.get("y"),
                     "w": (p.get("width") or 0) * MIL,
                     "h": (p.get("height") or 0) * MIL,
                     "layer": p.get("layer")} for p in c.get("pads") or []]
    return []


def summarize(name, pads):
    sig = [p for p in pads if p["w"] and p["h"] and p["h"] < 2.0 and
           p["w"] < 2.0 and (p.get("layer") in (1, None))]
    thru = [p for p in pads if p.get("layer") not in (1, None)]
    sizes = sorted({(round(p["w"], 3), round(p["h"], 3)) for p in pads if p["w"]})
    print(f"== {name}: {len(pads)} pads, sizes(mm)={sizes}")
    if sig:
        xs = sorted(p["x"] for p in sig)
        print(f"   signal row: {len(sig)} pads, span {xs[-1] - xs[0]:.3f} mm, "
              f"pitch {sorted(round(b - a, 3) for a, b in zip(xs, xs[1:]))}")
    if thru:
        xs = sorted({p["x"] for p in thru})
        ys = sorted({p["y"] for p in thru})
        print(f"   through-hole slots: {len(thru)} pads, "
              f"x spread {xs[-1] - xs[0]:.3f} mm, y spread {ys[-1] - ys[0]:.3f} mm")
    nph = [p for p in pads if p.get("drill") or (p.get("layer") not in (1, None)
                                                 and p["h"] and p["h"] < 1.0)]
    print(f"   small/NPTH holes: {len(nph)}")
    return sig, thru


def main():
    a = v11_j1()
    b = v2_j1()
    summarize("v1.1 final PCB", a)
    summarize("v2 board", b)
    print("\n要求文档 5.1 规定：")
    print("  信号焊盘 16 个（0.60x1.15 / 0.30x1.15 mm），单元间距 0.5 mm")
    print("  屏蔽固定孔 4 个 1.00x1.80 与 1.00x2.10 mm（X 间距 8.64 / Y 间距 4.18 mm）")
    print("  定位柱孔 2 个 D0.65 mm NPTH，间距 5.780 mm")


if __name__ == "__main__":
    main()
