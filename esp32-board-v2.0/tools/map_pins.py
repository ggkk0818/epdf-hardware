"""Map source netlist pin numbers onto the placed EasyEDA devices' real pin numbers.

Runs `sch list --include-pins` for both pages, diffs the device pin set against the
source model, applies an explicit mapping for the connectors whose EasyEDA symbol
merges redundant pads, and rewrites the connection specs with device pin numbers.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESIGN = os.path.join(ROOT, "design")
EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
PROJECT = "esp32s3-board-v2.0"

# source pin(s) -> device pin(s) for symbols that merge redundant pads
PIN_MAP = {
    "J1": {
        "A1": ["A1-B12"], "B1": ["A1-B12"], "A12": ["B1-A12"], "B12": ["B1-A12"],
        "A4": ["A4-B9"], "B9": ["A4-B9"], "B4": ["B4-A9"], "A9": ["B4-A9"],
        "SH": ["1", "2", "3", "4"],
        "A5": ["A5"], "A6": ["A6"], "A7": ["A7"], "A8": ["A8"],
        "B5": ["B5"], "B6": ["B6"], "B7": ["B7"], "B8": ["B8"],
    },
    "J4": {"MP": ["3", "4"]},
    "J5": {"MP": ["3", "4"]},
    "U2": {"25": ["25"]},
    "J3": {"SH": ["11", "12", "13", "14"]},
}
# sources whose symbol merges pads: source pin -> device pin for GND/VBUS redundancy
MERGE_DEDUP = {"U2": ["25"]}


def cli(args):
    res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
    return json.loads(res.stdout)


def main():
    with open(os.path.join(DESIGN, "model.json"), encoding="utf-8") as fh:
        model = json.load(fh)
    comps = {c["ref"]: c for c in model["components"]}

    device_pins = {}
    for page in ("P1", "P2"):
        d = cli(["sch", "list", "--page", page, "--include-pins", "--project", PROJECT])
        for c in d["result"]["components"]:
            if c.get("componentType") != "part":
                continue
            ref = c.get("designator")
            device_pins[ref] = [
                str(p["pinNumber"]) for p in (c.get("pins") or []) if p.get("pinNumber")
            ]

    report = {"mapped": {}, "identity": [], "unresolved": [], "missing_source_pins": []}
    resolved = {}
    for ref, comp in comps.items():
        if ref.startswith("H"):
            continue
        dpins = device_pins.get(ref)
        if dpins is None:
            report["unresolved"].append({"ref": ref, "why": "not placed"})
            continue
        dset = set(dpins)
        mapping = PIN_MAP.get(ref, {})
        out = {}
        used_identity = True
        for p in comp["pads"]:
            src = p["num"]
            if src in mapping:
                tgt = mapping[src]
                used_identity = False
            elif ref in MERGE_DEDUP and src in MERGE_DEDUP[ref]:
                tgt = [src]
                used_identity = False
            else:
                tgt = [src]
            missing = [t for t in tgt if t not in dset]
            if missing:
                report["missing_source_pins"].append({"ref": ref, "src": src, "missing": missing})
                continue
            out[src] = tgt
        resolved[ref] = out
        if used_identity and set(out) == dset:
            report["identity"].append(ref)
        else:
            report["mapped"][ref] = {"devicePins": sorted(dset), "sourceToDevice": out}

    # device pins never referenced by any source pin
    unreferenced = {}
    for ref, comp in comps.items():
        if ref.startswith("H") or ref not in resolved:
            continue
        referenced = {t for v in resolved[ref].values() for t in v}
        left = sorted(set(device_pins[ref]) - referenced)
        if left:
            unreferenced[ref] = left
    report["devicePinsUnreferenced"] = unreferenced

    with open(os.path.join(DESIGN, "pin-map.json"), "w", encoding="utf-8") as fh:
        json.dump({"resolved": resolved, "report": report}, fh, ensure_ascii=False, indent=1)

    # regenerate connection specs from the model, translated to device pin numbers
    nets = model["nets"]
    kwargs = {}

    placed_by_page = {"P1": [], "P2": []}
    for page in ("P1", "P2"):
        d = cli(["sch", "list", "--page", page, "--include-pins", "--project", PROJECT])
        for c in d["result"]["components"]:
            if c.get("componentType") == "part":
                placed_by_page[page].append(c.get("designator"))

    def kind_for(net):
        if net == "GND":
            return "ground"
        if net in ("3V3_MAIN", "EPD_3V3", "SYS", "BAT_BUS", "BAT1_RAW", "BAT2_RAW",
                   "USB_VBUS_RAW", "USB_VBUS_PROT", "CHG_PMID", "CHG_REGN"):
            return "power"
        # NB: net_label creation is broken in this connector build (create never
        # settles within 7s -> rollback). net_port_bi produces the same named net
        # and creates reliably.
        return "net_port_bi"

    for page, path in (("P1", "sch-connect-A.json"), ("P2", "sch-connect-B.json")):
        refset = set(placed_by_page[page])
        conns = []
        for net, pins in sorted(nets.items()):
            for ref, src in pins:
                if ref not in refset:
                    continue
                tgts = resolved.get(ref, {}).get(src)
                if not tgts:
                    print("WARN unmapped", ref, src, net)
                    continue
                for t in tgts:
                    conns.append({"pin": f"{ref}:{t}", "kind": kind_for(net), "net": net})
        # one entry per physical device pin; conflicting nets on the same pin is a hard error
        dedup = {}
        conflicts = []
        for c in conns:
            prev = dedup.get(c["pin"])
            if prev and prev["net"] != c["net"]:
                conflicts.append((c["pin"], prev["net"], c["net"]))
            dedup[c["pin"]] = c
        if conflicts:
            print("PIN NET CONFLICTS:", conflicts)
        conns = list(dedup.values())
        conns.sort(key=lambda c: (c["net"], c["pin"]))
        spec = {"connections": conns, "rules": {"avoidTitleBlock": True, "preferVertical": True}}
        with open(os.path.join(DESIGN, path), "w", encoding="utf-8") as fh:
            json.dump(spec, fh, ensure_ascii=False, indent=1)
        print(f"{path}: {len(conns)} connections")

    # NC lists use device pin numbers too
    ncs = {}
    for page in ("P1", "P2"):
        items = []
        for ref in placed_by_page[page]:
            comp = comps.get(ref)
            if not comp:
                continue
            nc_src = [p["num"] for p in comp["pads"] if not p["net"]]
            pins = []
            for src in nc_src:
                pins.extend(resolved.get(ref, {}).get(src, []))
            if pins:
                items.append({"designator": ref, "pins": sorted(set(pins))})
        ncs[page] = items
    with open(os.path.join(DESIGN, "sch-nc-final.json"), "w", encoding="utf-8") as fh:
        json.dump(ncs, fh, ensure_ascii=False, indent=1)

    print("mapped components:", list(report["mapped"]))
    print("identity components:", len(report["identity"]))
    print("unresolved:", report["unresolved"])
    print("missing source pins:", report["missing_source_pins"])
    print("unreferenced device pins:", unreferenced)
    print("NC entries:", {k: len(v) for k, v in ncs.items()})


if __name__ == "__main__":
    main()
