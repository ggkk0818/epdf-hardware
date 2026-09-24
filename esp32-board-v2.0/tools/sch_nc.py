"""Mark every authoritative no-net pin on both pages with an explicit NC flag.

    python tools/sch_nc.py --dry-run
    python tools/sch_nc.py

The pin list comes from design/model.json (pads without a net) via the same
pin-map resolution used for the connections, so the NC set can never drift from
the netlist the board was built against.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402
import sch_audit  # noqa: E402
import sch_reconnect  # noqa: E402

ROOT = geom.ROOT
AUDIT = os.path.join(ROOT, "work", "audit")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    want = sch_audit.authoritative()
    audit = json.load(open(os.path.join(AUDIT, "audit.json"),
                           encoding="utf-8"))["pages"]
    for page in ("P1", "P2"):
        data = sch_audit.live_read(page)
        live = sch_audit.live_pins(data)
        nc = [p for p in want if want[p] is None and p in live
              and not live[p]]
        by_ref = {}
        for key in nc:
            ref, num = key.split(".")
            by_ref.setdefault(ref, []).append(num)
        print(f"== {page}: {len(nc)} pins without a net ==")
        for ref, nums in sorted(by_ref.items()):
            cmd = ["sch", "no-connect", "--doc", page, "--designator", ref,
                   "--pin", ",".join(nums)]
            if args.dry_run:
                print("   would run:", " ".join(cmd))
                continue
            r = sch_reconnect.call(cmd)
            print(f"   {ref:<6} {','.join(nums):<24} "
                  f"{'ok' if r.get('ok') else 'FAIL'}")
            if not r.get("ok"):
                print("      ", json.dumps(r.get("error"), ensure_ascii=False)[:160])
            time.sleep(0.2)


if __name__ == "__main__":
    main()
