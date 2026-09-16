"""Query the routing model: pads of a part / net, free area checks.

    python tools/query_model.py ref U2 U3
    python tools/query_model.py net CHG_SW USB_DP_CONN
    python tools/query_model.py footprint
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "routing" / "model.json"


def pad_line(p):
    return (f"   {str(p['num']):>4s} {p['net']:<16s} ({p['x']:8.3f},{p['y']:8.3f}) "
            f"{p['w']:.2f}x{p['h']:.2f} {p['shape']:<9s} rot{p['rot']:6.1f} "
            f"drill{p['drill']:.2f} {p['type']} layers={p['layers']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ref", "net", "footprint", "keepout",
                                     "zone", "nc", "spread"])
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()

    m = json.loads(MODEL.read_text(encoding="utf-8"))
    pads = m["pads"]

    if args.what == "footprint":
        for f in m["footprints"]:
            print(f"{f['ref']:<6s} {f['value']:<28s} ({f['x']:7.3f},{f['y']:7.3f}) "
                  f"rot{f['rot']:6.1f} {f['lib_id']}")
        return

    if args.what == "keepout":
        for k in m["keepouts"]:
            print(f"{k['name']:<28s} layers={k['layers']} {k['keepout']}")
            print("   ", k["polygon"])
        return

    if args.what == "zone":
        for z in m["zones"]:
            print(f"{z['name']:<20s} net={z['net']:<8s} layers={z['layers']}")
        return

    if args.what == "spread":
        by_net = collections.defaultdict(list)
        for p in pads:
            by_net[p["net"]].append(p)
        for n, ps in sorted(by_net.items()):
            if not n:
                continue
            xs = [p["x"] for p in ps]
            ys = [p["y"] for p in ps]
            print(f"{n:<18s} n={len(ps):<3d} bbox x[{min(xs):6.2f},{max(xs):6.2f}] "
                  f"y[{min(ys):6.2f},{max(ys):6.2f}]")
        return

    if args.what == "nc":
        for p in pads:
            if not p["net"]:
                print(pad_line(p))
        return

    if args.what == "ref":
        for ref in args.names:
            fp = next((f for f in m["footprints"] if f["ref"] == ref), None)
            print(f"=== {ref} " + (f"{fp['lib_id']} at ({fp['x']},{fp['y']}) "
                                   f"rot {fp['rot']}" if fp else "(not found)"))
            if fp:
                print("    bbox", fp["bbox"])
            for p in sorted((p for p in pads if p["ref"] == ref),
                            key=lambda p: (p["y"], p["x"])):
                print(pad_line(p))
        return

    if args.what == "net":
        for net in args.names:
            ps = [p for p in pads if p["net"] == net]
            print(f"=== net {net}  ({len(ps)} pads)")
            for p in sorted(ps, key=lambda p: (p["y"], p["x"])):
                print(f"   {p['ref']}.{p['num']:<4s} ({p['x']:8.3f},{p['y']:8.3f}) "
                      f"{p['w']:.2f}x{p['h']:.2f} {p['shape']}")
        return


if __name__ == "__main__":
    sys.exit(main())
