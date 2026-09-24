"""Execute an autoconnect dry-run plan deterministically.

autoconnect's batch planner simulates the whole page, so its dry-run says "all N
safe"; the mutating run re-plans per connection against the growing live state and
fails on pins whose lead-out got consumed. Replaying the planned direction/offset
with the low-level `sch connect` reproduces exactly the geometry the planner
validated, so every pin that the plan accepted gets its stub + net flag.
"""

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-connected", action="store_true",
                    help="read live pin nets first and skip pins already on the target net")
    args = ap.parse_args()

    with open(args.plan, encoding="utf-8") as fh:
        plan = json.load(fh)

    live_nets = {}
    if args.skip_connected:
        res = run(["sch", "list", "--page", args.doc, "--include-pins",
                   "--project", args.project])
        for c in (res or {}).get("result", {}).get("components", []):
            if c.get("componentType") != "part":
                continue
            ref = c.get("designator")
            for p in c.get("pins") or []:
                live_nets[f"{ref}:{p.get('pinNumber')}"] = p.get("net") or ""

    todo = []
    for c in plan.get("connections") or []:
        sel = c.get("selected") or {}
        if not c.get("pin") or not sel.get("direction"):
            continue
        if args.skip_connected and live_nets.get(c["pin"]) == c["net"]:
            continue
        todo.append({
            "pin": c["pin"], "net": c["net"], "kind": c["kind"],
            "direction": sel["direction"], "offset": sel["offset"],
            "endPoint": sel.get("endPoint"),
        })
    if args.limit:
        todo = todo[: args.limit]

    done, failed = [], []
    for i, item in enumerate(todo, 1):
        res = run([
            "sch", "connect",
            "--pin", item["pin"],
            "--kind", item["kind"],
            "--net", item["net"],
            "--direction", item["direction"],
            "--offset", str(item["offset"]),
            "--doc", args.doc,
            "--project", args.project,
        ])
        ok = bool(res and res.get("ok"))
        if ok:
            done.append(item["pin"])
        else:
            failed.append({"pin": item["pin"], "net": item["net"],
                           "error": (res or {}).get("error", {}).get("message", "no response")})
        if i % 20 == 0:
            print(f"  {i}/{len(todo)} (ok={len(done)} fail={len(failed)})", flush=True)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump({"doc": args.doc, "planned": len(todo), "done": done,
                   "failed": failed}, fh, ensure_ascii=False, indent=1)
    print(f"{args.doc}: {len(done)}/{len(todo)} connected, {len(failed)} failed")
    for f in failed[:20]:
        print("  FAIL", f)


if __name__ == "__main__":
    main()
