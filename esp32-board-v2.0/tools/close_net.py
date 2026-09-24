"""Connect a net's still-open pads to the nearest copper of the same net.

    python tools/close_net.py --net USB_DP_CONN [--net USB_DN] [--dry-run]

A coupled pair is routed as a centreline +/- offset, so at the ends the traces
land between the pads instead of on them.  This closes the last few mil with a
short straight stub per pad, each checked against the exact clearance oracle
before it is written.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clearance  # noqa: E402
import geom  # noqa: E402

ROOT = geom.ROOT
DOC = "PCB1"


def call(args, timeout=180):
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
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", action="append", required=True)
    ap.add_argument("--drc", default=os.path.join(ROOT, "work", "drc-usbfix.json"))
    ap.add_argument("--width", type=float, default=10.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    d = json.load(open(args.drc, encoding="utf-8"))
    items = []

    def walk(n):
        if isinstance(n, dict):
            if n.get("errorType"):
                items.append(n)
            for k in ("list", "violations"):
                if isinstance(n.get(k), list):
                    for c in n[k]:
                        walk(c)
        elif isinstance(n, list):
            for c in n:
                walk(c)
    walk(d.get("result", d))
    open_pads = {}
    for it in items:
        if it.get("errorType") != "Connection Error":
            continue
        for k in ("obj1", "obj2"):
            sfx = (it.get(k) or {}).get("suffix") or ""
            m = re.match(r"\((\w+)\): (\w+)_(.+)$", sfx)
            if m and m.group(1) in args.net:
                open_pads.setdefault(m.group(1), set()).add((m.group(2), m.group(3)))

    call(["pcb", "save", "--doc", DOC])
    call(["doc", "reload", DOC])
    geom.dump(os.path.join(ROOT, "work", "geom.json"))
    g = geom.load(os.path.join(ROOT, "work", "geom.json"))
    pads = {}
    for c, p in geom.iter_pads(g["components"]):
        pads[(c["designator"], str(p.get("padNumber")))] = p

    edits = {"tracks": [], "vias": []}
    for net, pins in open_pads.items():
        segs = [t for t in g["tracks"] if t.get("net") == net]
        oracle = clearance.Oracle(net=net, ignore=set())
        for ref, pin in sorted(pins):
            p = pads.get((ref, pin))
            if not p:
                print(f"  ! {net} {ref}.{pin}: pad not found")
                continue
            px, py, layer = p["x"], p["y"], p.get("layer") or 1
            best = None
            for t in segs:
                ax, ay, bx, by = t["startX"], t["startY"], t["endX"], t["endY"]
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                if L2 == 0:
                    continue
                u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
                qx, qy = ax + u * dx, ay + u * dy
                d0 = math.hypot(px - qx, py - qy)
                if d0 < 0.5 or d0 > 80.0:
                    continue
                if best is None or d0 < best[0]:
                    best = (d0, qx, qy, t["layer"])
            if not best:
                print(f"  ! {net} {ref}.{pin}: no same-net copper within 80 mil")
                continue
            d0, qx, qy, tlay = best
            # the stub runs on the PAD's layer; a via is needed when the nearest
            # same-net copper lives on another copper layer
            # For an SMD pad whose nearest same-net copper is on an INNER/BOTTOM
            # layer, close it with an in-pad via and route the stub ON THAT LAYER:
            # the pad row's interleaved neighbours are all on L1 and stop blocking.
            if tlay != layer:
                m2, who2 = oracle.seg_margin(px, py, qx, qy, args.width, tlay)
                print(f"  {net:<13} {ref}.{pin:<4} -> ({qx:.1f},{qy:.1f}) L{tlay} "
                      f"d={d0:.1f} margin={m2:.2f} in-pad via "
                      f"{'OK' if m2 >= 3.0 else 'REJECT ' + str(who2)}")
                if m2 >= 3.0:
                    edits["tracks"].append({"x1": round(px, 2), "y1": round(py, 2),
                                            "x2": round(qx, 2), "y2": round(qy, 2),
                                            "layer": tlay, "width": args.width,
                                            "net": net})
                    edits["vias"].append({"x": round(px, 2), "y": round(py, 2),
                                          "net": net, "diameter": 24, "hole": 12})
                continue
            # straight first, then two L-shaped doglegs (the direct line often
            # crosses the pair's other pad)
            paths = [[(px, py), (qx, qy)],
                     [(px, py), (qx, py), (qx, qy)],
                     [(px, py), (px, qy), (qx, qy)]]
            chosen, m, who = None, -99.0, "none"
            for pts in paths:
                worst, worst_who = 1e9, "none"
                for a, b in zip(pts, pts[1:]):
                    if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.5:
                        continue
                    mm, ww = oracle.seg_margin(a[0], a[1], b[0], b[1],
                                               args.width, layer)
                    if mm < worst:
                        worst, worst_who = mm, ww
                if worst >= 3.0:
                    chosen, m, who = pts, worst, worst_who
                    break
                if worst > m:
                    m, who = worst, worst_who
            ok = chosen is not None
            need_via = (tlay != layer)
            print(f"  {net:<13} {ref}.{pin:<4} -> ({qx:.1f},{qy:.1f}) L{tlay} "
                  f"d={d0:.1f} margin={m:.2f}"
                  f"{' +via' if need_via else ''} "
                  f"{'OK' if ok else 'REJECT ' + str(who)}"
                  f"{' (L)' if ok and len(chosen) > 2 else ''}")
            if ok:
                for a, b in zip(chosen, chosen[1:]):
                    if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.5:
                        continue
                    edits["tracks"].append({"x1": round(a[0], 2), "y1": round(a[1], 2),
                                            "x2": round(b[0], 2), "y2": round(b[1], 2),
                                            "layer": layer, "width": args.width,
                                            "net": net})
                if need_via:
                    edits["vias"].append({"x": round(qx, 2), "y": round(qy, 2),
                                          "net": net, "diameter": 24, "hole": 12})
    path = os.path.join(ROOT, "work", "close-net.json")
    json.dump(edits, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(edits['tracks'])} stubs -> {path}")
    if not args.dry_run and edits["tracks"]:
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "apply_plan_batch.py"),
                        path, "--batch", "10"], cwd=ROOT)


if __name__ == "__main__":
    main()
