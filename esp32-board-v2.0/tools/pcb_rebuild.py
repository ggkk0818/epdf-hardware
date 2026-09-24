"""Rebuild esp32s3-board-v2.0 from an empty PCB.

    python tools/pcb_rebuild.py --stage mech     # keep-out regions
    python tools/pcb_rebuild.py --stage place    # 106 components + nets + locks

Component anchors/rotations come from work/ref-last-layout.json (the accepted
previous layout).  J1-J5 and SW1-SW5 are placed with exactly those anchors and
locked; every other part starts from the same floorplan so the proven module
arrangement is preserved, then gets optimised by `pcb auto-place` + legalizer.
Nets are assigned from design/model.json through design/pin-map.json.
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
EASYEDA = geom.EASYEDA
PROJECT = geom.PROJECT
DOC = "PCB1"
MM = 39.37007874015748
BOARD_W, BOARD_H = 55.0 * MM, 84.0 * MM

FIXED = ["J1", "J2", "J3", "J4", "J5", "SW1", "SW2", "SW3", "SW4", "SW5"]


def to_mil(x_mm, y_mm):
    """doc frame (mm, y down) -> editor frame (mil, y up)."""
    return round(x_mm * MM, 3), round(BOARD_H - y_mm * MM, 3)


def call(args, tries=3, timeout=120):
    for k in range(tries):
        r = subprocess.run([EASYEDA] + args + ["--project", PROJECT],
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=timeout)
        out = r.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(1.5 + k)
    return None


def rect_mil(x0, y0, x1, y1):
    a, b = to_mil(x0, y0), to_mil(x1, y1)
    return (f"{min(a[0], b[0]):.2f},{min(a[1], b[1]):.2f},"
            f"{max(a[0], b[0]):.2f},{max(a[1], b[1]):.2f}")


def stage_mech(log):
    """Keep-out regions from PCB_INTERFACE_POSITIONS.md section 6."""

    def region(name, box, rules, layers=(1,), locked=False):
        for layer in layers:
            cmd = ["pcb", "region", "create", "--rect", rect_mil(*box),
                   "--name", f"{name}_L{layer}" if len(layers) > 1 else name,
                   "--layer", str(layer), "--doc", DOC]
            for rule in rules:
                cmd += ["--rule", rule]
            if locked:
                cmd.append("--locked")
            r = call(cmd)
            ok = bool(r and r.get("ok"))
            print(f"  region {name} L{layer}: {'ok' if ok else 'FAILED'}")
            log.append({"step": "region", "name": name, "layer": layer, "ok": ok})

    # ESP32_ANT_KEEP_OUT X16-39 / Y0-6 : no copper on L1, L4 (L3/Inner1 handled
    # after the plane pour, because a PLANE layer cannot be cut by a region)
    region("ESP32_ANT_COPPER_KEEPOUT", (16.0, 0.0, 39.0, 6.0),
           ["no-wires", "no-fills", "no-pours"], layers=(1, 2, 16), locked=True)
    # keep components off the two antenna side lanes (U1's antenna stays inside)
    region("ANT_NC_LEFT", (16.0, 0.0, 17.9, 6.0), ["no-components"])
    region("ANT_NC_RIGHT", (37.1, 0.0, 39.0, 6.0), ["no-components"])
    # J3 socket keep-outs 1..5
    for i, box in enumerate([(32.775, 67.925, 33.525, 71.175),
                             (32.775, 72.375, 33.525, 75.975),
                             (33.875, 73.775, 34.575, 81.375),
                             (42.925, 82.175, 45.475, 83.525),
                             (34.575, 72.475, 43.275, 74.075)], start=1):
        region(f"J3_SOCKET_KEEP_OUT_{i}", box,
               ["no-wires", "no-fills", "no-pours"])
    # right-hand switch column: components forbidden (SW3-5 / H1-H4 already placed)
    region("KEY_RIGHT_MECH_KEEP_OUT", (49.0, 0.0, 51.0, 84.0),
           ["no-components"], locked=True)


def stage_place(log):
    ref = json.load(open(os.path.join(ROOT, "work", "ref-last-layout.json"),
                         encoding="utf-8"))
    pos = {}
    for c in ref["components"]:
        pos[c["designator"]] = (c["x"], c["y"], c.get("rotation") or 0)

    model = json.load(open(os.path.join(ROOT, "design", "model.json"),
                           encoding="utf-8"))
    pinmap = json.load(open(os.path.join(ROOT, "design", "pin-map.json"),
                            encoding="utf-8"))["resolved"]

    placed, failed = [], []
    for comp in model["components"]:
        ref_d = comp["ref"]
        if ref_d not in pos:
            failed.append({"ref": ref_d, "error": "no reference anchor"})
            continue
        x, y, rot = pos[ref_d]
        nets = {}
        mapping = pinmap.get(ref_d, {})
        for p in comp["pads"]:
            if not p.get("net"):
                continue
            for t in mapping.get(p["num"]) or [p["num"]]:
                nets[t] = p["net"]
        cmd = ["pcb", "add-component", "--library", comp["libraryUuid"],
               "--uuid", comp["deviceUuid"], "--designator", ref_d,
               "--x", str(x), "--y", str(y), "--rotation", str(rot), "--doc", DOC]
        if nets:
            cmd += ["--nets", json.dumps(nets, ensure_ascii=False)]
        r = call(cmd)
        if r and r.get("ok"):
            placed.append(ref_d)
        else:
            err = ((r or {}).get("error") or {}).get("message", "no response")
            failed.append({"ref": ref_d, "error": err})
            print(f"  ! {ref_d}: {err[:90]}")
        if len(placed) % 25 == 0 and placed:
            print(f"  placed {len(placed)}", flush=True)
        time.sleep(0.25)
    print(f"placed {len(placed)}, failed {len(failed)}")

    # lock the ten mechanically constrained parts
    r = call(["pcb", "lock", "--ids", ",".join(FIXED), "--doc", DOC])
    print("lock fixed:", "ok" if (r and r.get("ok")) else "FAILED")
    log.append({"step": "place", "placed": len(placed), "failed": failed,
                "locked": FIXED})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["mech", "place"])
    ap.add_argument("--report", default=os.path.join(ROOT, "work",
                                                    "rebuild-report.json"))
    args = ap.parse_args()
    log = []
    if args.stage == "mech":
        stage_mech(log)
    else:
        stage_place(log)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
    print("report ->", args.report)


if __name__ == "__main__":
    main()
