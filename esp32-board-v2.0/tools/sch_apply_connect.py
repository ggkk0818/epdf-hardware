"""Replay the connect plan (work/sch-connect-plan.json) with `sch autoconnect`,
page by page, and mark explicit NC pins.

    python tools/sch_apply_connect.py [--limit N] [--dry-run]
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

ROOT = geom.ROOT


def call(args, tries=3):
    for k in range(tries):
        r = subprocess.run([geom.EASYEDA] + args + ["--project", geom.PROJECT],
                           capture_output=True, text=True, encoding="utf-8")
        out = r.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(1.0 + k)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=os.path.join(ROOT, "work", "sch-connect-plan.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--page", default=None)
    args = ap.parse_args()

    plan = json.load(open(args.plan, encoding="utf-8"))["plan"]
    if args.page:
        plan = [p for p in plan if p["page"] == args.page]
    if args.limit:
        plan = plan[:args.limit]
    print(f"{len(plan)} operations to replay"
          + (" (dry-run)" if args.dry_run else ""))

    ok = bad = 0
    for n, op in enumerate(plan, 1):
        pin = op["pin"].replace(".", ":", 1)
        if op["op"] == "connect":
            a = ["sch", "autoconnect", "--doc", op["page"], "--pin", pin,
                 "--kind", "gnd" if op["net"] == "GND" else "netport",
                 "--net", op["net"], "--offset-min", "30", "--offset-max", "140",
                 "--json"]
        else:
            ref, pn = pin.split(":", 1)
            a = ["sch", "no-connect", "--doc", op["page"], "--designator", ref,
                 "--pin", pn]
        if args.dry_run:
            a.append("--dry-run")
        r = call(a)
        good = bool(r and r.get("ok"))
        if not good and op["op"] == "connect" and not args.dry_run:
            # fall back to the low-level connect with explicit geometry
            for direction in ("up", "down", "left", "right"):
                for off in (40, 80, 140, 220):
                    b = ["sch", "connect", "--doc", op["page"], "--pin", pin,
                         "--kind", "gnd" if op["net"] == "GND" else "netport",
                         "--net", op["net"], "--direction", direction,
                         "--offset", str(off)]
                    if args.dry_run:
                        b.append("--dry-run")
                    r2 = call(b)
                    if r2 and r2.get("ok"):
                        r, good = r2, True
                        break
                if good:
                    break
        ok += good
        bad += (not good)
        if not good and bad <= 8:
            print(f"  FAIL {op['page']} {pin}: {json.dumps(r.get('error'), ensure_ascii=False)[:180] if r else 'no response'}")
        if n % 25 == 0:
            print(f"  ... {n}/{len(plan)} (ok {ok}, fail {bad})")
    print(f"done: ok {ok}, fail {bad}")


if __name__ == "__main__":
    main()
