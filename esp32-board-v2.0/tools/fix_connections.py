"""Sweep lead-out lengths along a pin's outward direction until the guard accepts."""

import argparse
import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def run(args):
    res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    start = out.find("{")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(out[start:])
    except Exception:
        return None
    return data


def outward_direction(doc, pin, project):
    """Read the pin's outward rotation from a dry-run autoconnect probe."""
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True, help="JSON list of {pin,net,kind,direction}")
    ap.add_argument("--doc", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--min", type=float, default=45)
    ap.add_argument("--max", type=float, default=900)
    ap.add_argument("--step", type=float, default=15)
    args = ap.parse_args()

    with open(args.items, encoding="utf-8") as fh:
        items = json.load(fh)

    ok, bad = [], []
    for item in items:
        got = False
        offsets = []
        o = args.min
        while o <= args.max:
            offsets.append(o)
            o += args.step
        for off in offsets:
            res = run([
                "sch", "connect", "--pin", item["pin"], "--kind", item["kind"],
                "--net", item["net"], "--direction", item["direction"],
                "--offset", str(int(off)), "--doc", args.doc, "--project", args.project,
            ])
            if res and res.get("ok"):
                ok.append({"pin": item["pin"], "net": item["net"], "offset": off})
                print(f"  OK {item['pin']} {item['net']} {item['direction']} {off}", flush=True)
                got = True
                break
        if not got:
            bad.append(item)
            print(f"  GAVE UP {item['pin']} {item['net']}", flush=True)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump({"ok": ok, "failed": bad}, fh, ensure_ascii=False, indent=1)
    print(f"fixed {len(ok)}/{len(items)}; still failing: {[b['pin'] for b in bad]}")


if __name__ == "__main__":
    main()
