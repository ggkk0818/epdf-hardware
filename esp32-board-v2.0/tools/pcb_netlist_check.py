"""Compare design/model.json with the v1.1 final PCB pad netlist (the
requirement document's declared data source).

    python tools/pcb_netlist_check.py

Two-terminal passives are compared as an unordered net pair, because pin 1/2 of
a passive is a library convention that legitimately differs between KiCad and
EasyEDA. Everything else must match pad-for-pad.
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

PASSIVE = re.compile(r"^(C|R|L|NTC)\d+$")


def parse_pcb(path):
    """Return {ref: {pad: net}} from a .kicad_pcb (balanced-paren scan)."""
    txt = open(path, encoding="utf-8").read()
    out = {}

    def blocks(pat, text):
        for m in re.finditer(pat, text):
            start = m.start()
            depth, i, in_str = 0, start, False
            while i < len(text):
                ch = text[i]
                if in_str:
                    if ch == '"' and text[i - 1] != "\\":
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            yield text[start:i + 1]

    for block in blocks(r"\(footprint ", txt):
        rm = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not rm:
            rm = re.search(r'\(fp_text reference "([^"]+)"', block)
        if not rm:
            continue
        ref = rm.group(1)
        pads = {}
        for chunk in blocks(r"\(pad ", block):
            pm = re.match(r'\(pad "([^"]*)"', chunk)
            if not pm:
                continue
            nm = re.search(r'\(net (?:\d+ )?"([^"]*)"\)', chunk)
            pads[pm.group(1)] = (nm.group(1) if nm else "")
        out[ref] = pads
    return out


def main():
    pcb = parse_pcb(PCB)
    model = json.load(open(os.path.join(ROOT, "design", "model.json"),
                           encoding="utf-8"))
    print(f"v1.1 PCB footprints {len(pcb)}")
    bad = ok = 0
    for comp in model["components"]:
        ref = comp["ref"]
        v2 = {p["num"]: (p.get("net") or "") for p in comp["pads"]}
        v1 = pcb.get(ref)
        if v1 is None:
            print(f"  {ref}: not found in v1.1 PCB")
            bad += 1
            continue
        if PASSIVE.match(ref) and len(v2) == 2 and len(v1) == 2:
            s2 = sorted(x for x in v2.values() if x)
            s1 = sorted(x for x in v1.values() if x)
            same = s2 == s1
        else:
            same = v1 == v2
        if same:
            ok += 1
        else:
            bad += 1
            diffs = sorted(set(v1) | set(v2))
            detail = ", ".join(f"{p}: v1.1={v1.get(p)!r} v2={v2.get(p)!r}"
                               for p in diffs if v1.get(p) != v2.get(p))
            print(f"  {ref}: {detail}")
    print(f"components matching: {ok}, differing: {bad}")
    refs_pcb = set(pcb)
    refs_model = {c["ref"] for c in model["components"]}
    print("in v1.1 PCB only:", sorted(refs_pcb - refs_model))
    print("in model only   :", sorted(refs_model - refs_pcb))


if __name__ == "__main__":
    main()
