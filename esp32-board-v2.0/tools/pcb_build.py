"""Build the PCB from scratch: outline, stackup, holes, keep-outs, then all parts.

Component positions come from design/pcb-plan.json (requirement frame, mm); every
other part lands on a temporary grid for the module-aware placer to move.
Pad nets are assigned from design/model.json, so the board carries the full netlist
without depending on a resolvable schematic netlist.
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESIGN = os.path.join(ROOT, "design")
EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"

MM = 39.37007874015748
BOARD_W = 55.0 * MM
BOARD_H = 84.0 * MM


def to_mil(x_mm, y_mm):
    return round(x_mm * MM, 3), round(BOARD_H - y_mm * MM, 3)


def call(args, tries=3):
    for k in range(tries):
        res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
        out = res.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(2 + 2 * k)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    with open(os.path.join(DESIGN, "pcb-plan.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    with open(os.path.join(DESIGN, "model.json"), encoding="utf-8") as fh:
        model = json.load(fh)
    with open(os.path.join(DESIGN, "pin-map.json"), encoding="utf-8") as fh:
        pinmap = json.load(fh)["resolved"]

    log = []

    # ---- 1. board outline 55 x 84 mm, R2 corners
    r = call(["pcb", "outline-round", "--rect",
              f"0,0,{BOARD_W:.3f},{BOARD_H:.3f}", "--radius", "78.7402",
              "--doc", args.doc, "--project", args.project])
    print("outline:", "ok" if (r and r.get("ok")) else "FAILED")
    log.append({"step": "outline", "ok": bool(r and r.get("ok"))})

    # ---- 2. 4-layer stackup, Inner1 = plane
    r = call(["pcb", "stackup", "set", "--layers", "4", "--plane", "15",
              "--doc", args.doc, "--project", args.project])
    print("stackup:", "ok" if (r and r.get("ok")) else "FAILED")
    log.append({"step": "stackup", "ok": bool(r and r.get("ok"))})

    # ---- 3. four M2 mounting holes, 3.000 mm from the centre-line edges
    r = call(["pcb", "mount-holes", "--dia", "86.61", "--inset", "123.11",
              "--clearance", "70", "--doc", args.doc, "--project", args.project])
    print("mount holes:", "ok" if (r and r.get("ok")) else "FAILED")
    log.append({"step": "mount-holes", "ok": bool(r and r.get("ok"))})

    # ---- 4. keep-out regions
    def region(name, x0, y0, x1, y1, rules, locked=False):
        a = to_mil(x0, y0)
        b = to_mil(x1, y1)
        rect = f"{min(a[0], b[0]):.2f},{min(a[1], b[1]):.2f},{max(a[0], b[0]):.2f},{max(a[1], b[1]):.2f}"
        cmd = ["pcb", "region", "create", "--rect", rect, "--name", name,
               "--doc", args.doc, "--project", args.project]
        for rule in rules:
            cmd += ["--rule", rule]
        if locked:
            cmd.append("--locked")
        res = call(cmd)
        print(f"region {name}:", "ok" if (res and res.get("ok")) else "FAILED")
        log.append({"step": "region", "name": name, "ok": bool(res and res.get("ok"))})

    # antenna band: no copper anywhere; no components beside the module only
    region("ESP32_ANT_COPPER_KEEPOUT", 16.0, 0.0, 39.0, 6.0,
           ["no-wires", "no-fills", "no-pours"], locked=True)
    region("ANT_NC_LEFT", 16.0, 0.0, 18.5, 6.0, ["no-components"])
    region("ANT_NC_RIGHT", 36.5, 0.0, 39.0, 6.0, ["no-components"])
    # microSD socket keep-outs (J3_SOCKET_KEEP_OUT_1..5)
    for i, (x0, y0, x1, y1) in enumerate([
            (32.775, 67.925, 33.525, 71.175),
            (32.775, 72.375, 33.525, 75.975),
            (33.875, 73.775, 34.575, 81.375),
            (42.925, 82.175, 45.475, 83.525),
            (34.575, 72.475, 43.275, 74.075)], start=1):
        region(f"J3_SOCKET_KEEP_OUT_{i}", x0, y0, x1, y1,
               ["no-wires", "no-fills", "no-pours"])
    # right switch column: components forbidden except SW3/SW4/SW5 and H1-H4
    region("KEY_RIGHT_MECH_KEEP_OUT", 49.0, 0.0, 51.0, 84.0, ["no-components"])

    # ---- 5. components
    grid = plan["grid"]
    fixed = plan["fixed"]
    anchors = plan["anchors"]
    placed_refs = set(fixed) | set(anchors)
    slot = 0
    placed, failed = [], []

    for comp in model["components"]:
        ref = comp["ref"]
        if ref.startswith("H"):
            continue
        if ref in fixed:
            x_mm, y_mm, rot = fixed[ref]
        elif ref in anchors:
            x_mm, y_mm, rot = anchors[ref]
        else:
            col, row = slot % grid["cols"], slot // grid["cols"]
            slot += 1
            x_mm = grid["x0"] + col * grid["pitch_x"]
            y_mm = grid["y0"] + row * grid["pitch_y"]
            rot = 0
        x, y = to_mil(x_mm, y_mm)

        nets = {}
        mapping = pinmap.get(ref, {})
        for p in comp["pads"]:
            net = p.get("net")
            if not net:
                continue
            for t in mapping.get(p["num"]) or [p["num"]]:
                nets[t] = net

        cmd = ["pcb", "add-component",
               "--library", comp["libraryUuid"], "--uuid", comp["deviceUuid"],
               "--designator", ref, "--x", str(x), "--y", str(y),
               "--rotation", str(rot), "--doc", args.doc, "--project", args.project]
        if nets:
            cmd += ["--nets", json.dumps(nets, ensure_ascii=False)]
        res = call(cmd)
        if res and res.get("ok"):
            placed.append(ref)
        else:
            err = ((res or {}).get("error") or {}).get("message", "no response")
            failed.append({"ref": ref, "error": err})
            print(f"  ! {ref} FAILED: {err[:80]}", flush=True)
        if len(placed) % 20 == 0:
            print(f"  placed {len(placed)}/{len(placed) + len(failed)}", flush=True)
        time.sleep(0.4)

    print(f"components placed {len(placed)}, failed {len(failed)}")
    log.append({"step": "components", "placed": len(placed), "failed": failed})
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
