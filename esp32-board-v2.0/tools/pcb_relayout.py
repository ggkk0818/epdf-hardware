"""Re-plan the board: lock the fixed parts, anchor the ICs, then legalise.

Fixed (never moved): U1 ESP32-S3 module, J1 USB-C, J2 24P FPC, J3 microSD,
J4/J5 battery connectors, SW3/SW4/SW5 right-column keys, H1-H4 holes.
Everything else is re-placed from the schematic's functional grouping.
"""

import argparse
import json
import os
import subprocess
import sys
import time

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN = os.path.join(ROOT, "design")

MM = 39.37007874015748
BOARD_H = 3307.0866141732283

FIXED = ["U1", "J1", "J2", "J3", "J4", "J5", "SW3", "SW4", "SW5"]


def to_mil(x_mm, y_mm):
    return round(x_mm * MM, 3), round(BOARD_H - y_mm * MM, 3)


# functional anchors (requirement mm, y-down from the board's top-left corner)
ANCHORS = {
    "U2": (21.0, 67.0),   # BQ25895 charger: between the battery inlet and USB-C
    "U3": (30.0, 52.0),   # TPS63070 buck-boost: centre, feeds the 3V3 rail
    "U4": (13.5, 66.0),   # MAX17048 fuel gauge: next to the battery connectors
    "U5": (31.5, 78.0),   # TUSB320 CC controller: at the USB-C end
    "U6": (12.0, 35.0),   # TPS22918 EPD load switch: at the FPC end
    "Q1": (11.0, 49.0),   # EPD booster switch: short HV loop at the FPC end
}


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


def snapshot(doc, project):
    d = call(["pcb", "list", "--doc", doc, "--project", project, "--include-bbox"])
    return {c.get("designator"): c for c in (d or {}).get("result", {}).get("components", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    comps = snapshot(args.doc, args.project)
    log = []

    ids = [comps[r]["primitiveId"] for r in FIXED if r in comps]
    res = call(["pcb", "lock", "--ids", ",".join(ids), "--doc", args.doc,
                "--project", args.project])
    print("locked:", len(ids), "ok" if (res and res.get("ok")) else "FAILED")
    log.append({"step": "lock", "refs": FIXED, "ok": bool(res and res.get("ok"))})

    for ref, (x_mm, y_mm) in ANCHORS.items():
        c = comps.get(ref)
        if not c:
            print("missing", ref)
            continue
        x, y = to_mil(x_mm, y_mm)
        patch = json.dumps({"x": x, "y": y})
        r = call(["pcb", "modify", "--id", c["primitiveId"], "--patch", patch,
                  "--doc", args.doc, "--project", args.project])
        ok = bool(r and r.get("ok"))
        print(f"anchor {ref}: ({x:.1f},{y:.1f}) {'ok' if ok else 'FAILED'}")
        log.append({"step": "anchor", "ref": ref, "to": [x, y], "ok": ok})
        time.sleep(1)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
