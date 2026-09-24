"""Place every component on the PCB with its pad nets, directly from the design model.

Uses `pcb add-component` (footprint + pad-net assignment) so the board carries the
full netlist without depending on the schematic's netlist being resolvable.
Positions come from the v1.1 final board (which the requirement document was derived
from), transformed from mm/y-down to EasyEDA mil/y-up.
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
BOARD_H = 3307.0866141732283  # 84 mm in mil


def call(args, retries=2):
    for attempt in range(retries + 1):
        res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
        out = res.stdout
        i = out.find("{")
        if i >= 0:
            try:
                data, _ = json.JSONDecoder().raw_decode(out[i:])
            except Exception:
                data = None
            if data is not None:
                return data
        time.sleep(2 + attempt * 3)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--only", default="", help="comma separated refs to place")
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    with open(os.path.join(DESIGN, "model.json"), encoding="utf-8") as fh:
        model = json.load(fh)
    with open(os.path.join(DESIGN, "pin-map.json"), encoding="utf-8") as fh:
        pinmap = json.load(fh)["resolved"]
    with open(os.path.join(HERE, "source-board.json"), encoding="utf-8") as fh:
        src = json.load(fh)

    src_pos = {}
    for c in src["components"]:
        ref = c.get("Reference")
        if ref:
            src_pos[ref] = c

    only = set(x for x in args.only.split(",") if x)
    placed, failed = [], []
    for comp in model["components"]:
        ref = comp["ref"]
        if ref.startswith("H"):
            continue
        if only and ref not in only:
            continue
        s = src_pos.get(ref, {})
        x_mm, y_mm = s.get("x"), s.get("y")
        rot = s.get("rot", 0.0)
        x = round(x_mm * MM, 3)
        y = round(BOARD_H - y_mm * MM, 3)
        rot_e = (-rot) % 360

        nets = {}
        mapping = pinmap.get(ref, {})
        for p in comp["pads"]:
            net = p.get("net")
            if not net:
                continue
            targets = mapping.get(p["num"]) or [p["num"]]
            for t in targets:
                nets[t] = net

        cmd = ["pcb", "add-component",
               "--library", comp["libraryUuid"], "--uuid", comp["deviceUuid"],
               "--designator", ref, "--x", str(x), "--y", str(y),
               "--rotation", str(rot_e), "--doc", args.doc, "--project", args.project]
        if nets:
            cmd += ["--nets", json.dumps(nets, ensure_ascii=False)]
        res = call(cmd)
        if res and res.get("ok"):
            placed.append(ref)
            print(f"  + {ref:5s} ({x:8.2f},{y:8.2f}) rot={rot_e:5.1f} nets={len(nets)}", flush=True)
        else:
            err = ((res or {}).get("error") or {}).get("message", "no response")
            failed.append({"ref": ref, "error": err})
            print(f"  ! {ref:5s} FAILED: {err[:90]}", flush=True)
        time.sleep(1)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump({"placed": placed, "failed": failed}, fh, ensure_ascii=False, indent=1)
    print(f"placed {len(placed)}/{len(placed) + len(failed)}")


if __name__ == "__main__":
    main()
