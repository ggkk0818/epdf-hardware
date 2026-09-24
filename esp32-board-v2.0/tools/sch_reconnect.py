"""Disconnect + re-connect a batch of schematic pins against the authoritative net.

    python tools/sch_reconnect.py --page P1 --jobs work/fix-row990.json --offset-max 30

The job file is a JSON list of {"pin": "C19:1", "net": "SYS"} entries. Each pin
is first disconnected (stub + marker removed, the inverse of sch connect), then
the batch is re-connected with one autoconnect --spec call so the planner sees
the other planned stubs and can stagger the labels.

Marker kind follows the reference plan (design/sch-connect-*.json):
    GND                        -> ground
    rails (3V3_MAIN, SYS ...)  -> power
    anything else              -> net_port_bi
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

RAILS = {"3V3_MAIN", "SYS", "EPD_3V3", "BAT_BUS", "BAT1_RAW", "BAT2_RAW",
         "CHG_PMID", "CHG_REGN", "USB_VBUS_PROT", "USB_VBUS_RAW", "USB_SHIELD"}


def kind_for(net):
    if net == "GND":
        return "ground"
    if net in RAILS:
        return "power"
    return "net_port_bi"


def call(args, timeout=120):
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
    return {"ok": False, "raw": out[-500:], "stderr": r.stderr[-300:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True)
    ap.add_argument("--jobs", required=True, help="JSON list of {pin, net}")
    ap.add_argument("--offset-min", type=float, default=18)
    ap.add_argument("--offset-max", type=float, default=30)
    ap.add_argument("--offset-step", type=float, default=3)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--skip-disconnect", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--spec-out", default=os.path.join(ROOT, "work",
                                                      "sch-fix-spec.json"))
    args = ap.parse_args()

    with open(args.jobs, encoding="utf-8") as fh:
        jobs = json.load(fh)
    print(f"{len(jobs)} pins to re-connect on {args.page}")

    if not args.skip_disconnect and not args.dry_run:
        for job in jobs:
            r = call(["sch", "disconnect", "--doc", args.page, "--pin",
                      job["pin"]])
            flag = "ok" if r.get("ok") else "FAIL"
            extra = ""
            also = (r.get("result") or {}).get("alsoDisconnectedPins") or []
            if also:
                extra = "  also-disconnected: " + ",".join(also)
            print(f"  disconnect {job['pin']:<12} {flag}{extra}")
            time.sleep(0.2)

    spec = {
        "connections": [{"pin": j["pin"], "kind": kind_for(j["net"]),
                         "net": j["net"]} for j in jobs],
        "rules": {
            "avoidTitleBlock": True,
            "avoidPinFanout": True,
            "staggerLabels": True,
            "offsetRange": [args.offset_min, args.offset_max],
            "offsetStep": args.offset_step,
            "minLabelGap": 12,
        },
    }
    with open(args.spec_out, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=1)
    print("spec ->", args.spec_out)

    cmd = ["sch", "autoconnect", "--doc", args.page, "--spec", args.spec_out,
           "--json"]
    if args.strict:
        cmd.append("--strict")
    if args.dry_run:
        cmd.append("--dry-run")
    r = call(cmd, timeout=900)
    res = r.get("result") or r
    print("ok:", res.get("ok"), "| succeeded:",
          len(res.get("succeeded") or []), "| failed:",
          len(res.get("failed") or []))
    for c in res.get("connections") or []:
        sel = c.get("selected") or {}
        warn = "yes" if (c.get("warning") or c.get("tainted")) else "no"
        print(f"  {str(c.get('pin')):<12} {str(c.get('net')):<12} "
              f"{str(c.get('state', 'new')):<18} dir={sel.get('direction')} "
              f"off={sel.get('offset')} end={sel.get('endPoint')} "
              f"score={sel.get('score')} warn={warn}")
        if c.get("error"):
            print("      error:",
                  json.dumps(c["error"], ensure_ascii=False)[:200])
    if res.get("failed"):
        print("failed pins:", res["failed"])


if __name__ == "__main__":
    main()
