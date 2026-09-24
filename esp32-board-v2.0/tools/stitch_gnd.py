"""Close the remaining GND connection errors with a local stitching via per pad.

    python tools/stitch_gnd.py --dry-run
    python tools/stitch_gnd.py

Reads work/drc-final-turn.json for the GND Connection Errors, resolves each
"DESIGNATOR_PIN" to a pad in the live dump, then places a GND via in the first
free spot around that pad (checked against the sys_router obstacle model, i.e.
foreign copper / pads / slots / keep-outs) and a stub track from pad to via.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402
import sys_router as SR  # noqa: E402

ROOT = geom.ROOT
PY = sys.executable
DOC = "PCB1"
VIA_D = 24.0
VIA_HOLE = 12.0


def call(args, timeout=120):
    r = subprocess.run([geom.EASYEDA] + args + ["--project", geom.PROJECT],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout)
    out = r.stdout
    i = out.find("{")
    if i >= 0:
        try:
            return json.JSONDecoder().raw_decode(out[i:])[0]
        except Exception:
            pass
    return {"ok": False, "raw": out[-300:]}


def gnd_error_pins(drc_path):
    d = json.load(open(drc_path, encoding="utf-8"))
    items = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("errorType"):
                items.append(node)
            for k in ("list", "violations"):
                if isinstance(node.get(k), list):
                    for c in node[k]:
                        walk(c)
        elif isinstance(node, list):
            for c in node:
                walk(c)
    walk(d.get("result", d))
    pins = set()
    for it in items:
        if it.get("errorType") != "Connection Error":
            continue
        for k in ("obj1", "obj2"):
            sfx = (it.get(k) or {}).get("suffix") or ""
            m = re.match(r"\(GND\): (\w+)_(.+)$", sfx)
            if m:
                pins.add((m.group(1), m.group(2)))
    return sorted(pins)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--drc", default=os.path.join(ROOT, "work",
                                                 "drc-final-turn.json"))
    args = ap.parse_args()

    pins = gnd_error_pins(args.drc)
    print(f"GND connection errors: {len(pins)} pads")
    if not pins:
        return

    call(["pcb", "save", "--doc", DOC])
    call(["doc", "reload", DOC])
    geom.dump(os.path.join(ROOT, "work", "geom.json"))
    g = geom.load(os.path.join(ROOT, "work", "geom.json"))
    board = SR.Board(g, "GND")
    pads = {}
    for c, p in geom.iter_pads(g["components"]):
        pads.setdefault((c["designator"], str(p.get("padNumber"))), p)

    edits = {"tracks": [], "vias": []}
    existing_vias = [(v["x"], v["y"]) for v in g["vias"]]
    for ref, pin in pins:
        p = pads.get((ref, str(pin))) or pads.get((ref, pin.lstrip("0")))
        if not p:
            print(f"  ! {ref}.{pin}: pad not found")
            continue
        px, py = p["x"], p["y"]
        if any(math.hypot(px - vx, py - vy) < 45.0 for vx, vy in existing_vias):
            print(f"  {ref}.{pin:<5} already stitched nearby — skip")
            continue
        hw = (p.get("width") or 10) / 2.0
        hh = (p.get("height") or 10) / 2.0
        chosen = None
        for r in (hh + 26.0, hh + 40.0, hh + 60.0, hw + 40.0, hw + 70.0):
            for ang in (90, 270, 0, 180, 45, 135, 225, 315):
                vx = px + r * math.cos(math.radians(ang))
                vy = py + r * math.sin(math.radians(ang))
                i = int(round((vx - board.x0) / SR.STEP))
                j = int(round((vy - board.y0) / SR.STEP))
                if not (0 <= i < board.nx and 0 <= j < board.ny):
                    continue
                if not board.inside[j * board.nx + i]:
                    continue
                # need VIA_D/2 + clearance on every layer the via passes
                ok = all(board.slack(L, i, j) >= VIA_D / 2.0 + 2.5
                         for L in SR.LAYERS)
                if ok:
                    chosen = (vx, vy)
                    break
            if chosen:
                break
        if not chosen:
            # No room for a via: a plain stub into the copper pour is enough,
            # the pour merges with the track and the pad becomes connected.
            best = None
            for r in (hw + 22.0, hh + 22.0, hw + 34.0, hh + 34.0):
                for ang in (0, 90, 180, 270, 45, 135, 225, 315):
                    sx = px + r * math.cos(math.radians(ang))
                    sy = py + r * math.sin(math.radians(ang))
                    i = int(round((sx - board.x0) / SR.STEP))
                    j = int(round((sy - board.y0) / SR.STEP))
                    if not (0 <= i < board.nx and 0 <= j < board.ny):
                        continue
                    if not board.inside[j * board.nx + i]:
                        continue
                    s = min(board.slack(L, i, j) for L in SR.LAYERS)
                    if s >= 7.5 and (best is None or s > best[0]):
                        best = (s, sx, sy)
                if best:
                    break
            if not best:
                print(f"  ! {ref}.{pin}: no free via spot and no stub room")
                continue
            _, sx, sy = best
            edits["tracks"].append({"x1": round(px, 2), "y1": round(py, 2),
                                    "x2": round(sx, 2), "y2": round(sy, 2),
                                    "layer": 1, "width": 10, "net": "GND"})
            print(f"  {ref}.{pin:<5} pad ({px:.1f},{py:.1f}) -> pour stub "
                  f"({sx:.1f},{sy:.1f})")
            continue
        vx, vy = chosen
        edits["tracks"].append({"x1": round(px, 2), "y1": round(py, 2),
                                "x2": round(vx, 2), "y2": round(vy, 2),
                                "layer": p.get("layer") if p.get("layer") in
                                (1, 2, 16) else 1,
                                "width": 10, "net": "GND"})
        edits["vias"].append({"x": round(vx, 2), "y": round(vy, 2),
                              "net": "GND", "diameter": VIA_D, "hole": VIA_HOLE})
        print(f"  {ref}.{pin:<5} pad ({px:.1f},{py:.1f}) -> via "
              f"({vx:.1f},{vy:.1f})")

    path = os.path.join(ROOT, "work", "gnd-stitch.json")
    json.dump(edits, open(path, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    print(f"{len(edits['vias'])} vias + {len(edits['tracks'])} stubs -> {path}")
    if not args.dry_run and edits["vias"]:
        out = subprocess.run([PY, os.path.join(ROOT, "tools", "apply_edits.py"),
                              path], capture_output=True, text=True,
                             encoding="utf-8", cwd=ROOT)
        print(out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out)


if __name__ == "__main__":
    main()
