"""Show why a pin sits on the wrong net: pin coords, touching wires, nearby flags.

    python tools/sch_probe.py --page P1 C19.1 C21.1 U2.6
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
AUDIT = os.path.join(ROOT, "work", "audit")


def load(page):
    with open(os.path.join(AUDIT, f"{page.lower()}-full.json"),
              encoding="utf-8") as fh:
        txt = fh.read()
    rad = json.loads(txt[txt.find("{"):]).get("result", {})
    return rad["components"], rad, rad.get("wires") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="P1")
    ap.add_argument("--radius", type=float, default=45.0)
    ap.add_argument("pins", nargs="+")
    args = ap.parse_args()

    comps, rad, wires = load(args.page)
    pins = {}
    for c in comps:
        if c.get("componentType") != "part":
            continue
        for p in c.get("pins") or []:
            pins[f"{c['designator']}.{p['pinNumber']}"] = (
                p, c, c.get("bbox"))
    flags = [c for c in rad["components"]
             if c.get("componentType") in ("netflag", "netport")]

    for key in args.pins:
        p, c, bb = pins.get(key, (None, None, None))
        if not p:
            print(f"{key}: not found")
            continue
        px, py = p["x"], p["y"]
        print(f"\n{key}  part {c['designator']} @({c.get('x')},{c.get('y')}) "
              f"net={p.get('net')} noConnected={p.get('noConnected')}")
        print(f"   pin at ({px},{py})  bbox {bb}")
        print("   wires touching:")
        for w in wires:
            for (ax, ay, bx, by) in ((w["x0"], w["y0"], w["x1"], w["y1"]),):
                if (abs(ax - px) < 1 and abs(ay - py) < 1) or \
                   (abs(bx - px) < 1 and abs(by - py) < 1) or \
                   (min(ax, bx) - 1 <= px <= max(ax, bx) + 1 and
                        min(ay, by) - 1 <= py <= max(ay, by) + 1 and
                        (ax == bx or ay == by)):
                    print(f"     {w['primitiveId']} ({ax},{ay})-({bx},{by}) "
                          f"net={w.get('net')!r}")
        print("   nearby flags:")
        for f in flags:
            fbb = f.get("bbox") or {}
            dx = abs(f["x"] - px)
            dy = abs(f["y"] - py)
            inside = (fbb.get("minX") is not None and
                      fbb["minX"] - 1 <= px <= fbb["maxX"] + 1 and
                      fbb["minY"] - 1 <= py <= fbb["maxY"] + 1)
            if dx <= args.radius and dy <= args.radius or inside:
                print(f"     {f.get('componentType'):<8} {f.get('name'):<14} "
                      f"@{f['x']},{f['y']} id={f['primitiveId']} "
                      f"bbox=({fbb.get('minX')},{fbb.get('minY')},"
                      f"{fbb.get('maxX')},{fbb.get('maxY')})"
                      + ("  <== OVERLAPS PIN" if inside else ""))


if __name__ == "__main__":
    main()
