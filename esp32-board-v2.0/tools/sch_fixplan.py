"""Emit the per-page repair job list: every pin that is mis-netted, floating,
part of a bridge tree, or left with an orphan stub.

    python tools/sch_fixplan.py                 # writes work/fix-P1.json / fix-P2.json

Each job is {"pin": "C19:1", "net": "SYS", "why": "wrong"}. The net comes from
the authoritative table (design/model.json + design/pin-map.json).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sch_audit  # noqa: E402

ROOT = sch_audit.ROOT
AUDIT = sch_audit.AUDIT


def bridges(page):
    path = os.path.join(AUDIT, f"{page.lower()}-bridge.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    data = json.loads(txt[txt.find("{"):])["result"]
    return data.get("trees") or []


def main():
    want = sch_audit.authoritative()
    audit = json.load(open(os.path.join(AUDIT, "audit.json"),
                           encoding="utf-8"))["pages"]
    for page, r in audit.items():
        jobs = {}

        def add(pin, why):
            if pin in jobs:
                jobs[pin]["why"] = jobs[pin]["why"] + "+" + why
                return
            net = want.get(pin)
            if net:
                jobs[pin] = {"pin": pin, "net": net, "why": why}
            else:
                jobs[pin] = {"pin": pin, "net": None, "why": why}

        for item in r["wrong"]:
            add(item["pin"], "wrong")
        for item in r["floating"]:
            add(item["pin"], "floating")
        for tree in bridges(page):
            for pin in tree.get("pins") or []:
                add(pin.replace(":", "."), tree["kind"].lower())
        out = [j for j in jobs.values() if j["net"]]
        nop = [j for j in jobs.values() if not j["net"]]
        path = os.path.join(ROOT, "work", f"fix-{page}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print(f"{page}: {len(out)} reconnect jobs -> {path}")
        for j in out:
            print(f"   {j['pin']:<12} -> {j['net']:<14} ({j['why']})")
        if nop:
            print(f"{page}: {len(nop)} pins without an authoritative net "
                  f"(need NC): {[j['pin'] for j in nop]}")


if __name__ == "__main__":
    main()
