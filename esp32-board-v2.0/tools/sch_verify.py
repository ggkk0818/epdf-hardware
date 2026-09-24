"""Refresh the live audit and print the schematic repair scoreboard.

    python tools/sch_verify.py            # both pages: read, check, bridge-check, audit
"""

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


def run(args, out=None, timeout=300):
    r = subprocess.run([EASYEDA] + args + ["--project", PROJECT],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(r.stdout)
    return r.stdout


def jload(path):
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    return json.loads(txt[txt.find("{"):])


def main():
    for page in ("P1", "P2"):
        low = page.lower()
        run(["sch", "read", "--doc", page], os.path.join(AUDIT, f"{low}-read.json"))
        run(["sch", "list", "--doc", page, "--include-pins", "--include-bbox",
             "--include-wires"], os.path.join(AUDIT, f"{low}-full.json"))
        run(["sch", "check", "--doc", page, "--json"],
            os.path.join(AUDIT, f"{low}-check.json"))
        run(["sch", "bridge-check", "--doc", page, "--json"],
            os.path.join(AUDIT, f"{low}-bridge.json"))
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sch_audit.py")],
                   check=False)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sch_diagnose.py")],
                   check=False)
    print()
    for page in ("P1", "P2"):
        low = page.lower()
        check = jload(os.path.join(AUDIT, f"{low}-check.json"))["result"]
        br = jload(os.path.join(AUDIT, f"{low}-bridge.json"))["result"]
        print(f"-- {page} check: {check['summary']} passed={check['passed']}")
        print(f"   bridges: {br['summary']}")
        for f in check.get("findings") or []:
            print("   finding:", f.get("level"), f.get("type"),
                  str(f.get("message"))[:70])


if __name__ == "__main__":
    main()
