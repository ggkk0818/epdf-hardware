"""Audit the live schematic against the authoritative pin->net table.

    python tools/sch_audit.py                 # report from work/audit/*.json
    python tools/sch_audit.py --read          # refresh the live reads first

Classification per pin:
    ok        live net == authoritative net
    floating  live net empty, authoritative net exists
    wrong     live net != authoritative net (both non-empty)
    extra     live net present although the authoritative table says NC
    nc        live empty and NC is wanted (an explicit NC flag is fine)

Extra data: for every bridge tree (sch bridge-check) the endpoints, the pins
and the markers are resolved to real coordinates so the fix can be planned.
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
AUDIT = os.path.join(ROOT, "work", "audit")
EASYEDA = geom.EASYEDA
PROJECT = geom.PROJECT


def live_read(page, refresh=False):
    path = os.path.join(AUDIT, f"{page.lower()}-read.json")
    if refresh or not os.path.exists(path):
        r = subprocess.run([EASYEDA, "sch", "read", "--doc", page,
                            "--project", PROJECT],
                           capture_output=True, text=True, encoding="utf-8")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(r.stdout)
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    return json.loads(txt[txt.find("{"):])["result"]


def authoritative():
    model = json.load(open(os.path.join(ROOT, "design", "model.json"),
                           encoding="utf-8"))
    pm = json.load(open(os.path.join(ROOT, "design", "pin-map.json"),
                        encoding="utf-8"))["resolved"]
    want = {}
    for c in model["components"]:
        ref = c["ref"]
        for p in c["pads"]:
            src = str(p["num"])
            for dev in (pm.get(ref) or {}).get(src) or [src]:
                want[f"{ref}.{dev}"] = p.get("net") or None
    return want


def live_pins(page_data):
    nets = {}
    for c in page_data["components"]:
        if c.get("componentType") != "part":
            continue
        for p in c.get("pins") or []:
            nets[f"{c['designator']}.{p['number']}"] = p.get("net") or None
    return nets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--read", action="store_true", help="refresh live reads")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    want = authoritative()
    report = {"pages": {}}
    for page in ("P1", "P2"):
        data = live_read(page, args.read)
        live = live_pins(data)
        buckets = {"ok": [], "floating": [], "wrong": [], "extra": [], "nc": [],
                   "missing_in_live": []}
        for pin, net in want.items():
            if pin not in live:
                if pin.split(".")[0] in {c.get("designator")
                                         for c in data["components"]}:
                    buckets["missing_in_live"].append(pin)
                continue
            got = live[pin]
            if net is None:
                (buckets["extra"] if got else buckets["nc"]).append(
                    {"pin": pin, "live": got})
            elif got == net:
                buckets["ok"].append(pin)
            elif not got:
                buckets["floating"].append({"pin": pin, "want": net})
            else:
                buckets["wrong"].append({"pin": pin, "want": net, "live": got})
        for pin, net in live.items():
            if pin not in want and net:
                buckets["extra"].append({"pin": pin, "live": net,
                                         "note": "not in authoritative table"})
        report["pages"][page] = {
            "counts": {k: len(v) for k, v in buckets.items()},
            "floating": buckets["floating"],
            "wrong": buckets["wrong"],
            "extra": buckets["extra"],
            "missing_in_live": buckets["missing_in_live"],
            "check_summary": data["check"]["summary"],
            "floatingPins": data["floatingPins"],
            "netCount": data["netCount"],
        }
    if args.json:
        print(json.dumps(report["pages"], ensure_ascii=False, indent=1))
    else:
        for page, r in report["pages"].items():
            print(f"== {page} ==")
            print("  counts:", r["counts"])
            print("  check :", r["check_summary"])
            if r["floating"]:
                print("  floating:")
                for f in r["floating"]:
                    print(f"     {f['pin']:<14} wants {f['want']}")
            if r["wrong"]:
                print("  wrong net:")
                for f in r["wrong"]:
                    print(f"     {f['pin']:<14} live {f['live']:<14} != {f['want']}")
            if r["extra"]:
                print("  extra/unwanted net:")
                for f in r["extra"]:
                    print(f"     {f['pin']:<14} live {f['live']}")
            if r["missing_in_live"]:
                print("  pin not found in live page:", r["missing_in_live"])
    with open(os.path.join(AUDIT, "audit.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print("wrote work/audit/audit.json")


if __name__ == "__main__":
    main()
