"""Plan the schematic: page split, module assignment, placement playbook, connect specs."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESIGN = os.path.join(ROOT, "design")

MODEL = os.path.join(DESIGN, "model.json")

# module cores -> (page, zone)
MODULES = [
    ("USB_INPUT", "J1", "A"),
    ("CHARGER", "U2", "A"),
    ("FUEL_GAUGE", "U4", "A"),
    ("TYPEC_CC", "U5", "A"),
    ("BUCKBOOST", "U3", "A"),
    ("EPD_POWER", "U6", "A"),
    ("EPD_BOOST", "Q1", "B"),
    ("BATTERY", "J4", "A"),
    ("MCU", "U1", "B"),
    ("EPD_CONN", "J2", "B"),
    ("STORAGE", "J3", "B"),
    ("KEYS", "SW3", "B"),
]

# refs that are cores of page B but must not be their own module
EXTRA_CORE = {"SW1", "SW2"}

# functional seeds: parts whose module membership is known from the design intent
SEEDS = {
    "USB_INPUT": ["J1", "F1", "D1", "D2", "D3", "D4", "D5", "R9", "R10", "R11", "C6", "C9"],
    "CHARGER": ["U2", "L1", "C7", "C8", "C10", "C11", "C12", "C13", "C14", "C15", "C16",
                "R13", "R15", "R18", "C2", "C3", "C4", "NTC1", "C24"],
    "FUEL_GAUGE": ["U4", "R19", "R22", "C36", "C17"],
    "TYPEC_CC": ["U5", "R8", "R12", "C28"],
    "BUCKBOOST": ["U3", "L2", "C19", "C20", "C21", "C22", "C23", "R23", "R24", "R25", "R26", "R27", "C5"],
    "EPD_POWER": ["U6", "R29", "C25", "C26", "C34"],
    "EPD_BOOST": ["Q1", "L3", "D6", "D7", "D8", "R30", "R31", "R16", "R17", "R21",
                  "C27", "C29", "C30", "C31", "C32", "C33", "C35", "C37"],
    "BATTERY": ["J4", "J5", "F2", "F3"],
    "MCU": ["U1", "C1", "R2", "R6", "R7", "C38", "R32", "D2", "D3"],
    "EPD_CONN": ["J2", "R33", "R34", "R35"],
    "STORAGE": ["J3", "R36", "C18"],
    "KEYS": ["SW1", "SW2", "SW3", "SW4", "SW5", "R1", "R3", "R4", "R5"],
}


ZONES = {
    "USB_INPUT": "left-bottom",
    "CHARGER": "center",
    "FUEL_GAUGE": "left-top",
    "TYPEC_CC": "right-bottom",
    "BUCKBOOST": "right-top",
    "EPD_POWER": "top",
    "BATTERY": "bottom",
    "MCU": "center",
    "EPD_CONN": "left-bottom",
    "STORAGE": "right-bottom",
    "KEYS": "right-top",
    "EPD_BOOST": "left-top",
}


def main():
    with open(MODEL, encoding="utf-8") as fh:
        model = json.load(fh)

    comps = {c["ref"]: c for c in model["components"]}
    nets = model["nets"]

    # ref -> set(net)
    ref_nets = {r: set() for r in comps}
    for net, pins in nets.items():
        for ref, _pin in pins:
            ref_nets.setdefault(ref, set()).add(net)

    core_of = {core: name for name, core, _ in MODULES}
    page_of_module = {name: page for name, _core, page in MODULES}

    assigned = {}
    module_parts = {name: [] for name, _core, _p in MODULES}

    # 1) functional seeds win, first seed list wins on conflict, only real refs
    for name, _core, _page in MODULES:
        for ref in SEEDS.get(name, []):
            if ref in comps and ref not in assigned:
                assigned[ref] = name
                module_parts[name].append(ref)
    # cores always belong to their own module
    for core, name in core_of.items():
        if core in comps:
            if assigned.get(core) != name:
                for lst in module_parts.values():
                    if core in lst:
                        lst.remove(core)
                assigned[core] = name
                module_parts[name].append(core)

    # 2) affinity: attach each remaining part to the module it shares most nets with
    for ref in sorted(comps):
        if ref in assigned:
            continue
        best, best_score = None, 0
        for name, core, _page in MODULES:
            if core not in comps:
                continue
            shared = len(ref_nets[ref] & ref_nets[core])
            if shared > best_score:
                best, best_score = name, shared
        if best is None:
            best = "MCU"
        assigned[ref] = best
        module_parts[best].append(ref)

    # H1-H4 are PCB-only mounting holes: no schematic symbol
    for ref in [c["ref"] for c in model["components"]]:
        if ref.startswith("H"):
            comps.pop(ref, None)

    pages = {"A": [], "B": []}
    for ref in sorted(comps):
        mod = assigned[ref]
        pages[page_of_module[mod]].append(ref)

    os.makedirs(DESIGN, exist_ok=True)

    # ---- placement playbook: rough grid; autolayout.py will arrange by module
    def grid_positions(refs, pitch_x, pitch_y, x0, y0, cols):
        out = []
        for i, ref in enumerate(refs):
            col, row = i % cols, i // cols
            out.append((ref, x0 + col * pitch_x, y0 + row * pitch_y))
        return out

    playbooks = {}
    for page, refs in pages.items():
        steps = []
        for ref, x, y in grid_positions(refs, 80, 70, 60, 240, 13):
            c = comps[ref]
            steps.append({
                "action": "schematic.component.place",
                "payload": {
                    "libraryUuid": c["libraryUuid"],
                    "uuid": c["deviceUuid"],
                    "x": x,
                    "y": y,
                    "rotation": 0,
                    "designator": ref,
                },
            })
        pname = f"P{1 if page == 'A' else 2}"
        playbooks[page] = {
            "version": 1,
            "meta": {"name": f"place-schematic-{pname}", "doc": pname},
            "steps": steps,
        }
        with open(os.path.join(DESIGN, f"sch-place-{page}.json"), "w", encoding="utf-8") as fh:
            json.dump(playbooks[page], fh, ensure_ascii=False, indent=1)

    # ---- autolayout specs
    for page, refs in pages.items():
        mods = []
        for name, core, p in MODULES:
            if p != page:
                continue
            parts = [r for r in module_parts[name] if r in refs]
            mods.append({"name": name, "zone": ZONES.get(name, "center"), "core": core, "parts": parts})
        spec = {
            "page": f"P{1 if page == 'A' else 2}",
            "sheet": "A4",
            "modules": mods,
            "rules": {
                "avoidTitleBlock": True,
                "preservePinFanout": True,
                "moduleGap": 110,
                "routeChannelGap": 55,
                "preferVerticalPeripheralPlacement": True,
            },
        }
        with open(os.path.join(DESIGN, f"sch-layout-{page}.json"), "w", encoding="utf-8") as fh:
            json.dump(spec, fh, ensure_ascii=False, indent=1)

    # ---- connection specs: one flag per pin
    def kind_for(net):
        if net == "GND":
            return "ground"
        if net in ("3V3_MAIN", "EPD_3V3", "SYS", "BAT_BUS", "BAT1_RAW", "BAT2_RAW",
                   "USB_VBUS_RAW", "USB_VBUS_PROT", "CHG_PMID", "CHG_REGN"):
            return "power"
        return "net_label"

    for page, refs in pages.items():
        conns = []
        refset = set(refs)
        for net, pins in sorted(nets.items()):
            for ref, pin in pins:
                if ref not in refset:
                    continue
                conns.append({"pin": f"{ref}:{pin}", "kind": kind_for(net), "net": net})
        conns.sort(key=lambda c: (c["net"], c["pin"]))
        spec = {"connections": conns, "rules": {"avoidTitleBlock": True, "preferVertical": True}}
        with open(os.path.join(DESIGN, f"sch-connect-{page}.json"), "w", encoding="utf-8") as fh:
            json.dump(spec, fh, ensure_ascii=False, indent=1)

    # ---- no-connect list per page
    ncs = {}
    for page, refs in pages.items():
        items = []
        for ref in refs:
            for p in comps[ref]["pads"]:
                if not p["net"]:
                    items.append({"designator": ref, "pins": [p["num"]]})
        ncs[page] = items
    with open(os.path.join(DESIGN, "sch-nc.json"), "w", encoding="utf-8") as fh:
        json.dump(ncs, fh, ensure_ascii=False, indent=1)

    print("page A parts:", len(pages["A"]))
    print("page B parts:", len(pages["B"]))
    for name, core, page in MODULES:
        print(f"  {page} {name:12s} core={core:4s} parts={len(module_parts[name])}")
    print("connections A:", len(json.load(open(os.path.join(DESIGN, 'sch-connect-A.json'), encoding='utf-8'))["connections"]))
    print("connections B:", len(json.load(open(os.path.join(DESIGN, 'sch-connect-B.json'), encoding='utf-8'))["connections"]))
    print("NC entries:", {k: len(v) for k, v in ncs.items()})


if __name__ == "__main__":
    main()
