"""Build the authoritative schematic pin -> net map (from design/model.json +
design/pin-map.json), diff it against the live pages and emit the list of
`sch connect` / `sch no-connect` calls needed.

    python tools/sch_plan_connect.py            # report only
    python tools/sch_plan_connect.py --emit work/sch-connect-plan.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

ROOT = geom.ROOT


def authoritative():
    model = json.load(open(os.path.join(ROOT, "design", "model.json"), encoding="utf-8"))
    pm = json.load(open(os.path.join(ROOT, "design", "pin-map.json"), encoding="utf-8"))
    resolved = pm["resolved"]
    want, nc = {}, []
    for c in model["components"]:
        ref = c["ref"]
        for p in c["pads"]:
            src = str(p["num"])
            dev = (resolved.get(ref) or {}).get(src) or [src]
            for d in dev:
                key = f"{ref}.{d}"
                if p.get("net"):
                    want[key] = p["net"]
                else:
                    nc.append(key)
    return want, sorted(set(nc))


def live(page):
    r = geom.call(["sch", "read", "--doc", page])["result"]
    comps = [c.get("designator") for c in r["components"]
             if c.get("componentType") == "part"]
    floating = set(r["floatingPinCount"] and r["floatingPins"] or [])
    nets = {n["net"]: set(n["pins"]) for n in r["nets"]}
    return set(comps), floating, nets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit")
    args = ap.parse_args()
    want, nc = authoritative()
    print(f"authoritative: {len(want)} pin->net entries, {len(nc)} explicit-NC pins")

    pages = {}
    for page in ("P1", "P2"):
        comps, floating, nets = live(page)
        pages[page] = (comps, floating, nets)
        print(f"  {page}: {len(comps)} parts, {len(floating)} floating, "
              f"{len(nets)} nets")

    plan = []
    for page, (comps, floating, nets) in pages.items():
        for pin in sorted(floating):
            ref = pin.split(".")[0]
            if ref not in comps:
                continue
            net = want.get(pin)
            if net:
                plan.append({"page": page, "op": "connect", "pin": pin, "net": net})
            else:
                plan.append({"page": page, "op": "nc", "pin": pin})
    print(f"\nplan: {len(plan)} operations "
          f"({sum(1 for p in plan if p['op']=='connect')} connect, "
          f"{sum(1 for p in plan if p['op']=='nc')} nc)")
    bynet = {}
    for p in plan:
        if p["op"] == "connect":
            bynet.setdefault(p["net"], []).append(p["pin"])
    for net, pins in sorted(bynet.items(), key=lambda kv: -len(kv[1]))[:12]:
        print(f"   {net:<16} {len(pins):>3} pins")
    missing = [k for k in want if k.split(".")[0] in
               set().union(*(c for c, _, _ in pages.values())) and
               all(k not in pins for _, _, nets2 in pages.values() for pins in nets2.values())
               and all(k != p["pin"] for p in plan)]
    print(f"\npins the authoritative map wants but neither wired nor planned: {len(missing)}")
    print("   sample:", missing[:10])
    if args.emit:
        with open(args.emit, "w", encoding="utf-8") as fh:
            json.dump({"plan": plan, "want": want, "nc": nc}, fh,
                      ensure_ascii=False, indent=1)
        print("wrote", args.emit)


if __name__ == "__main__":
    main()
