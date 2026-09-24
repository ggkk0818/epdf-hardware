"""Sum routed track length per net in a KiCad .kicad_pcb (mm)."""

import re
import sys
from collections import defaultdict
from math import hypot


def main():
    path = sys.argv[1]
    want = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    s = open(path, encoding="utf-8", errors="replace").read()
    totals = defaultdict(float)
    for m in re.finditer(r"\(segment\b(.*?)\n\t\)", s, re.S):
        body = m.group(1)
        st = re.search(r"\(start\s+([-\d.]+)\s+([-\d.]+)\)", body)
        en = re.search(r"\(end\s+([-\d.]+)\s+([-\d.]+)\)", body)
        nt = re.search(r'\(net\s+"?([^")]*)"?\)', body)
        if not (st and en and nt):
            continue
        x1, y1 = float(st.group(1)), float(st.group(2))
        x2, y2 = float(en.group(1)), float(en.group(2))
        totals[nt.group(1)] += hypot(x2 - x1, y2 - y1)
    nets = {}
    for name in totals:
        nets[name] = name
    for num, name in sorted(nets.items(), key=lambda kv: -totals.get(kv[0], 0)):
        if want and name not in want:
            continue
        if totals.get(num):
            print(f"  {name:<18} {totals[num]:7.2f} mm  (net {num})")
    if want:
        print("  --- pairs ---")
        for a, b in (("USB_DP_CONN", "USB_DN_CONN"), ("USB_DP", "USB_DN")):
            la = next((totals[n] for n, nm in nets.items() if nm == a), 0)
            lb = next((totals[n] for n, nm in nets.items() if nm == b), 0)
            if la or lb:
                print(f"  {a} vs {b}: {la:.2f} / {lb:.2f}  skew {abs(la-lb):.2f} mm")


if __name__ == "__main__":
    main()
