"""Merge BOM values, chosen library parts and v1.1 board connectivity into one model."""

import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "source-board.json")
PARTS = os.path.join(ROOT, "design", "parts-map.json")
BOM = r"C:\Code\epdf-hardware\esp32-board-v1.1\bom.csv"
OUT = os.path.join(ROOT, "design", "model.json")

# BOM group key -> part-map key
GROUP_TO_PART = {
    "22uF": "C_22uF_0805",
    "10uF": "C_10uF_0805",
    "1uF": "C_1uF_0603",
    "0.1uF": "C_100nF_0603",
    "1nF": "C_1nF_0603",
    "4.7uF/10V": "C_4u7uF_0805",
    "47nF": "C_47nF_0603",
    "470pF": "C_470pF_0603",
    "100nF": "C_100nF_0603",
    "4.7uF/25V": "C_4u7uF_0805",
    "1uF/25V": "C_1uF_0603",
    "TVS 5.6V": "D1",
    "ESD": "D23",
    "MBR0530": "D6",
    "2A PTC": "F",
    "USB-C 2.0 Sink": "J1",
    "GDEM102T91 24P FPC": "J2",
    "MicroSD": "J3",
    "BAT1": "J4",
    "BAT2": "J4",
    "1.0uH": "L1",
    "1.2uH": "L2",
    "47uH": "L3",
    "10k B3435": "NTC1",
    "Si1304BDL": "Q1",
    "10k": "R_10k_0603",
    "4.7k": "R_4k7_0603",
    "0": "R_0R_0603",
    "22": "R_22R_0603",
    "900k": "R_900k_0603",
    "180": "R_180R_0603",
    "5.23k": "R_5k23_0603",
    "30.1k": "R_30k1_0603",
    "100k": "R_100k_0603",
    "470k": "R_470k_0603",
    "150k": "R_150k_0603",
    "1M": "R_1M_0603",
    "2.2": "R_2R2_0805",
    "RESET": "SW",
    "BOOT": "SW",
    "KEY1": "SW",
    "KEY2": "SW",
    "KEY3": "SW",
    "ESP32-S3-WROOM-1-N16R8": "U1",
    "BQ25895RTW": "U2",
    "TPS63070RNMT": "U3",
    "MAX17048": "U4",
    "TUSB320LI": "U5",
    "TPS22918": "U6",
}

# group-value overrides: ESD group is two different parts in v1.1
REF_PART_OVERRIDE = {
    "D4": "D45",
    "D5": "D45",
    "C16": "C_470pF_0603",
    "C36": "C_1uF_25V_0805",
    "C34": "C_1uF_0603",
    "C35": "C_1uF_0603",
}


def expand_refs(cell):
    out = []
    for token in cell.split(","):
        token = token.strip()
        if not token:
            continue
        m = re.fullmatch(r"([A-Za-z]+)(\d+)-([A-Za-z]+)(\d+)", token)
        if m and m.group(1) == m.group(3):
            for n in range(int(m.group(2)), int(m.group(4)) + 1):
                out.append(f"{m.group(1)}{n}")
        else:
            out.append(token)
    return out


def main():
    with open(PARTS, encoding="utf-8") as fh:
        parts = json.load(fh)["parts"]

    bom = {}
    with open(BOM, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            for ref in expand_refs(row["Reference"]):
                bom[ref] = {
                    "group": row["Value"],
                    "bom_footprint": row["Footprint"],
                    "mpn": row["MPN"],
                    "populate": row["Populate"],
                }

    with open(SRC, encoding="utf-8") as fh:
        board = json.load(fh)

    components = []
    unknown = []
    for comp in board["components"]:
        ref = comp.get("Reference")
        if not ref:
            continue
        key = REF_PART_OVERRIDE.get(ref)
        if key is None:
            b = bom.get(ref)
            if not b:
                unknown.append(ref)
                continue
            key = GROUP_TO_PART.get(b["group"])
            if not key:
                unknown.append(f"{ref}:{b['group']}")
                continue
        part = parts.get(key)
        if not part:
            unknown.append(f"{ref}->{key}")
            continue
        pads = []
        for p in comp["pads"]:
            if not p["number"]:
                continue
            pads.append({
                "num": p["number"],
                "net": p.get("net") or "",
                "x": p["x"],
                "y": p["y"],
                "w": p.get("w"),
                "h": p.get("h"),
                "type": p["type"],
                "shape": p["shape"],
                "rot": p.get("rot", 0.0),
                "layers": p.get("layers", []),
            })
        bomrow = bom.get(ref, {})
        components.append({
            "ref": ref,
            "part_key": key,
            "value": part["value"],
            "mpn": part["mpn"],
            "lcsc": part["lcsc"],
            "libraryUuid": part["libraryUuid"],
            "deviceUuid": part["uuid"],
            "footprint": part["fp"],
            "populate": bomrow.get("populate", "FIT"),
            "src_footprint": comp.get("lib", ""),
            "src_x": comp.get("x"),
            "src_y": comp.get("y"),
            "src_rot": comp.get("rot", 0.0),
            "pads": pads,
        })

    nets = {}
    seen = set()
    for c in components:
        for p in c["pads"]:
            if p["net"]:
                key = (p["net"], c["ref"], p["num"])
                if key in seen:
                    continue
                seen.add(key)
                nets.setdefault(p["net"], []).append([c["ref"], p["num"]])

    model = {
        "_doc": "Connectivity + part model for esp32s3-board-v2.0; nets come from the v1.1 final board pads.",
        "board": {"thickness_mm": board["general"].get("thickness", 1.2)},
        "components": components,
        "nets": {k: v for k, v in sorted(nets.items())},
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(model, fh, ensure_ascii=False, indent=1)

    print("components:", len(components))
    print("nets:", len(nets))
    print("total pins with net:", sum(len(v) for v in nets.values()))
    if unknown:
        print("UNMAPPED:", sorted(set(unknown)))
    for name in ("GND", "3V3_MAIN", "GPI", "USB_DP", "USB_DN"):
        if name in nets:
            print(f"  net {name}: {len(nets[name])} pins")


if __name__ == "__main__":
    main()
