"""Extract authoritative source data from the v1.1 final KiCad PCB."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpr


SRC = r"C:\Code\epdf-hardware\esp32-board-v1.1\esp32-board-v1.1_final_drc_20260920.kicad_pcb"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source-board.json")


def num(node, name, idx=1, default=0.0):
    c = sexpr.child(node, name)
    if not c:
        return default
    vals = sexpr.atoms(c)
    try:
        return float(vals[idx])
    except (IndexError, ValueError):
        return default


def parse_pad(p):
    d = {
        "number": sexpr.atoms(p)[1] if len(sexpr.atoms(p)) > 1 else "",
        "type": sexpr.atoms(p)[2] if len(sexpr.atoms(p)) > 2 else "",
        "shape": sexpr.atoms(p)[3] if len(sexpr.atoms(p)) > 3 else "",
    }
    at = sexpr.child(p, "at")
    if at:
        a = sexpr.atoms(at)
        d["x"] = float(a[1])
        d["y"] = float(a[2])
        d["rot"] = float(a[3]) if len(a) > 3 else 0.0
    size = sexpr.child(p, "size")
    if size:
        a = sexpr.atoms(size)
        d["w"] = float(a[1])
        d["h"] = float(a[2])
    drill = sexpr.child(p, "drill")
    if drill:
        d["drill"] = sexpr.atoms(drill)[1:]
    net = sexpr.child(p, "net")
    if net:
        a = sexpr.atoms(net)
        if len(a) >= 3 and a[1].lstrip("-").isdigit():
            d["net"] = a[2]
        elif len(a) >= 2:
            d["net"] = a[1]
        else:
            d["net"] = ""
    layers = sexpr.child(p, "layers")
    if layers:
        d["layers"] = sexpr.atoms(layers)[1:]
    return d


def main():
    with open(SRC, "r", encoding="utf-8") as fh:
        text = fh.read()
    tree = sexpr.parse(text)

    board = {
        "general": {},
        "components": [],
        "nets": [],
        "edge": [],
        "zones": [],
        "drawings": [],
    }

    gen = sexpr.child(tree, "general")
    if gen:
        th = sexpr.child(gen, "thickness")
        if th:
            board["general"]["thickness"] = float(sexpr.atoms(th)[1])

    tb = sexpr.child(tree, "title_block")
    if tb:
        board["title_block"] = {
            k: " ".join(sexpr.atoms(sexpr.child(tb, k))[1:])
            for k in ("title", "date", "rev", "company")
            if sexpr.child(tb, k)
        }

    for c in sexpr.children(tree, "net"):
        a = sexpr.atoms(c)
        if len(a) >= 3 and a[1].lstrip("-").isdigit():
            board["nets"].append({"code": int(a[1]), "name": a[2]})
        elif len(a) >= 2:
            board["nets"].append({"name": a[1]})

    for fp in sexpr.children(tree, "footprint"):
        comp = {
            "lib": sexpr.atoms(fp)[1] if len(sexpr.atoms(fp)) > 1 else "",
            "pads": [],
        }
        at = sexpr.child(fp, "at")
        if at:
            a = sexpr.atoms(at)
            comp["x"] = float(a[1])
            comp["y"] = float(a[2])
            comp["rot"] = float(a[3]) if len(a) > 3 else 0.0
        layer = sexpr.child(fp, "layer")
        if layer:
            comp["layer"] = sexpr.atoms(layer)[1]
        for prop in sexpr.children(fp, "property"):
            a = sexpr.atoms(prop)
            if len(a) >= 3:
                comp[a[1]] = a[2]
        for p in sexpr.children(fp, "pad"):
            comp["pads"].append(parse_pad(p))
        for g in sexpr.children(fp, "fp_line") + sexpr.children(fp, "fp_rect") + sexpr.children(fp, "fp_poly"):
            pass
        board["components"].append(comp)

    for g in sexpr.children(tree, "gr_line") + sexpr.children(tree, "gr_arc") + sexpr.children(tree, "gr_rect") + sexpr.children(tree, "gr_circle"):
        layer = sexpr.child(g, "layer")
        lay = sexpr.atoms(layer)[1] if layer else ""
        item = {"kind": sexpr.head(g), "layer": lay}
        if sexpr.head(g) == "gr_line":
            s = sexpr.child(g, "start")
            e = sexpr.child(g, "end")
            item["start"] = [float(sexpr.atoms(s)[1]), float(sexpr.atoms(s)[2])]
            item["end"] = [float(sexpr.atoms(e)[1]), float(sexpr.atoms(e)[2])]
        elif sexpr.head(g) == "gr_arc":
            s = sexpr.child(g, "start")
            m = sexpr.child(g, "mid")
            e = sexpr.child(g, "end")
            item["start"] = [float(sexpr.atoms(s)[1]), float(sexpr.atoms(s)[2])]
            item["mid"] = [float(sexpr.atoms(m)[1]), float(sexpr.atoms(m)[2])]
            item["end"] = [float(sexpr.atoms(e)[1]), float(sexpr.atoms(e)[2])]
        elif sexpr.head(g) == "gr_rect":
            s = sexpr.child(g, "start")
            e = sexpr.child(g, "end")
            item["start"] = [float(sexpr.atoms(s)[1]), float(sexpr.atoms(s)[2])]
            item["end"] = [float(sexpr.atoms(e)[1]), float(sexpr.atoms(e)[2])]
        item["width"] = num(g, "width", 1, 0.0)
        board["drawings"].append(item)

    for z in sexpr.children(tree, "zone"):
        net = sexpr.child(z, "net")
        zname = sexpr.child(z, "name")
        keepout = sexpr.child(z, "keepout")
        item = {
            "net": sexpr.atoms(net)[2] if net and len(sexpr.atoms(net)) > 2 else "",
            "name": sexpr.atoms(zname)[1] if zname and len(sexpr.atoms(zname)) > 1 else "",
            "layers": [],
            "polygon": [],
            "keepout": {},
        }
        lay = sexpr.child(z, "layers")
        if lay:
            item["layers"] = sexpr.atoms(lay)[1:]
        if keepout:
            for k in ("tracks", "vias", "pads", "copperpour", "footprints"):
                kk = sexpr.child(keepout, k)
                if kk:
                    item["keepout"][k] = sexpr.atoms(kk)[1] == "not_allowed"
        poly = sexpr.child(z, "polygon")
        if poly:
            pts = sexpr.child(poly, "pts")
            if pts:
                for xy in sexpr.children(pts, "xy"):
                    a = sexpr.atoms(xy)
                    item["polygon"].append([float(a[1]), float(a[2])])
        board["zones"].append(item)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(board, fh, indent=1)

    print("components", len(board["components"]))
    print("nets", len(board["nets"]))
    print("zones", len(board["zones"]))
    print("edge/drawings", len(board["drawings"]))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
