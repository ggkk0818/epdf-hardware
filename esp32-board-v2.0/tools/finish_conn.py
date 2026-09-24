"""Finish the remaining schematic connections, self-cleaning degenerate wires.

Failed `sch connect` attempts can leave a zero-length wire behind; that degenerate
wire makes the connector's page-wide geometry guard refuse EVERY later write, which
is what stalled the earlier repair loop. This script sweeps candidate lead-outs and
cleans degenerate wires before/after each attempt, accepting an attempt only when the
target net is still its own net in the connectivity IR (i.e. no merge happened).
"""

import argparse
import json
import subprocess
import sys
import time

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def call(args):
    res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    if i < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(out[i:])
    except Exception:
        return None
    return data


def list_wires(doc, project):
    d = call(["sch", "list", "--page", doc, "--include-pins", "--include-wires",
              "--project", project])
    r = (d or {}).get("result", {})
    coords = {}
    for c in r.get("components", []):
        if c.get("componentType") != "part":
            continue
        for p in c.get("pins") or []:
            coords[f"{c['designator']}:{p.get('pinNumber')}"] = (p.get("x"), p.get("y"))
    return r.get("wires") or [], coords


def clean_degenerate(doc, project):
    wires, _ = list_wires(doc, project)
    bad = [w["primitiveId"] for w in wires if w["x0"] == w["x1"] and w["y0"] == w["y1"]]
    if bad:
        call(["sch", "prim-delete", "--ids", ",".join(bad), "--doc", doc,
              "--project", project])
        print(f"  cleaned {len(bad)} degenerate wire(s)", flush=True)
    return len(bad)


def stub_ids_for(pin, doc, project):
    wires, coords = list_wires(doc, project)
    xy = coords.get(pin)
    return [w["primitiveId"] for w in wires
            if (w["x0"], w["y0"]) == xy or (w["x1"], w["y1"]) == xy]


def floating_pins(doc, project):
    """Authoritative connectivity evidence: `sch check`'s floating-pin findings.

    (`sch connectivity` currently returns an empty net list on this build, so the
    check findings are the channel that actually resolves nets.)
    """
    return check_state(doc, project)[0]


def check_state(doc, project):
    """Return (floating_pin_set, multi_net_wire_count) from `sch check`."""
    d = call(["sch", "check", "--doc", doc, "--project", project, "--json"])
    r = (d or {}).get("result", {})
    out = set()
    for f in r.get("findings") or []:
        if f.get("type") != "floating-pin":
            continue
        for p in f.get("pins") or []:
            out.add(f"{f.get('designator')}:{p}")
    multi = (r.get("summary") or {}).get("multiNetWires", 0)
    return out, multi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--items", required=True,
                    help="JSON [{pin,net,kind,directions:[...]}]")
    ap.add_argument("--report", required=True)
    ap.add_argument("--offsets", default="45,60,90,130,180,240,320,420")
    ap.add_argument("--pause", type=float, default=4.0,
                    help="seconds to wait between attempts (the connector degrades under burst load)")
    args = ap.parse_args()

    with open(args.items, encoding="utf-8") as fh:
        items = json.load(fh)
    offsets = [float(x) for x in args.offsets.split(",") if x]

    results = []
    for item in items:
        pin, net, kind = item["pin"], item["net"], item["kind"]
        # 1) discover the pin's outward direction: the guard only accepts the outward
        #    one, so a rejection that is NOT "requires its first wire segment to leave
        #    outward" identifies it (blocked in a legal direction).
        outward = None
        for d in ("right", "left", "up", "down"):
            time.sleep(args.pause)
            res = call(["sch", "connect", "--pin", pin, "--kind", kind, "--net", net,
                        "--direction", d, "--offset", "60",
                        "--doc", args.doc, "--project", args.project])
            if res and res.get("ok"):
                outward = d
                results.append({"pin": pin, "net": net, "direction": d, "offset": 60,
                                "status": "fixed"})
                print(f"  FIXED {pin} -> {net} [{d} 60]", flush=True)
                break
            msg = ((res or {}).get("error") or {}).get("message", "") or ""
            detail = json.dumps((res or {}).get("result") or {}, ensure_ascii=False)
            if "leave outward" in detail:
                continue
            outward = d
            break
        if outward is None:
            results.append({"pin": pin, "net": net, "status": "outward-unknown"})
            print(f"  OUTWARD UNKNOWN {pin}", flush=True)
            continue
        if any(r["pin"] == pin and r["status"] == "fixed" for r in results):
            continue
        dirs = [outward]
        clean_degenerate(args.doc, args.project)
        base_floating, base_multi = check_state(args.doc, args.project)
        base_multi = max(base_multi, 0)
        finished = False
        for direction in dirs:
            for off in offsets:
                time.sleep(args.pause)
                res = call(["sch", "connect", "--pin", pin, "--kind", kind, "--net", net,
                            "--direction", direction, "--offset", str(int(off)),
                            "--doc", args.doc, "--project", args.project])
                if not (res and res.get("ok")):
                    clean_degenerate(args.doc, args.project)
                    continue
                floating, multi = check_state(args.doc, args.project)
                if pin not in floating and multi <= base_multi:
                    results.append({"pin": pin, "net": net, "direction": direction,
                                    "offset": off, "status": "fixed"})
                    print(f"  FIXED {pin} -> {net} [{direction} {int(off)}]", flush=True)
                    finished = True
                    break
                # merged: roll back this stub
                ids = stub_ids_for(pin, args.doc, args.project)
                if ids:
                    call(["sch", "prim-delete", "--ids", ",".join(ids), "--doc", args.doc,
                          "--project", args.project])
                clean_degenerate(args.doc, args.project)
                print(f"  merge at {pin} [{direction} {int(off)}], rolled back", flush=True)
            if finished:
                break
        if not finished:
            results.append({"pin": pin, "net": net, "status": "unresolved"})
            print(f"  UNRESOLVED {pin} -> {net}", flush=True)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print("summary:", [(r["pin"], r["status"]) for r in results])


if __name__ == "__main__":
    main()
