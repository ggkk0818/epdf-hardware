import re
import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from kicad_fp import read_mod, split_children, child_key

lib, name = sys.argv[1].split(":", 1)
text = read_mod(lib, name)
_, children = split_children(text)
for c in children:
    k = child_key(c)
    if k in ("fp_line", "fp_rect", "fp_circle", "fp_arc"):
        lay = re.search(r'\(layer "([^"]+)"', c)
        pts = re.findall(r"\((?:start|end|center)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", c)
        layname = lay.group(1) if lay else "?"
        print(f"{k:8s} {layname:12s} " + " ".join(f"({a},{b})" for a, b in pts))
    elif k == "fp_text":
        lay = re.search(r'\(layer "([^"]+)"', c)
        tx = re.search(r'\(fp_text \w+ "([^"]*)"', c)
        print(f"text     {lay.group(1) if lay else '?':12s} {tx.group(1) if tx else ''!r}")
