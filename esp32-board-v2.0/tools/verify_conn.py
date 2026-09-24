"""Compare live schematic pin nets against the target connection spec."""

import argparse
import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--project", required=True)
    args = ap.parse_args()

    res = subprocess.run(
        [EASYEDA, "sch", "list", "--page", args.doc, "--include-pins",
         "--project", args.project],
        capture_output=True, text=True, encoding="utf-8")
    d = json.loads(res.stdout)
    live = {}
    for c in d["result"]["components"]:
        if c.get("componentType") != "part":
            continue
        ref = c.get("designator")
        for p in c.get("pins") or []:
            live[f"{ref}:{p.get('pinNumber')}"] = p.get("net") or ""

    with open(args.spec, encoding="utf-8") as fh:
        spec = json.load(fh)

    want = {c["pin"]: c["net"] for c in spec["connections"]}
    missing, wrong = [], []
    for pin, net in sorted(want.items()):
        got = live.get(pin, "")
        if not got:
            missing.append({"pin": pin, "want": net})
        elif got != net:
            wrong.append({"pin": pin, "want": net, "got": got})
    print(f"{args.doc}: target {len(want)}, connected {len(want) - len(missing) - len(wrong)}, "
          f"missing {len(missing)}, wrong {len(wrong)}")
    for m in missing:
        print("  MISSING", m)
    for w in wrong:
        print("  WRONG  ", w)


if __name__ == "__main__":
    main()
