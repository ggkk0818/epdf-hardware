"""Authoritative DRC read: save -> doc reload -> drc, then summarise.

    python tools/drc_summary.py [--no-reload] [--top N]

Groups violations by errorType and prints the worst offenders with the
object/net names, so a routing stage can be judged at a glance.
"""

import argparse
import collections
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
DOC = "PCB1"


def call(args, timeout=900):
    r = subprocess.run([geom.EASYEDA] + args + ["--project", geom.PROJECT],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout)
    out = r.stdout
    i = out.find("{")
    if i >= 0:
        try:
            return json.JSONDecoder().raw_decode(out[i:])[0]
        except Exception:
            pass
    return {"ok": False, "raw": out[-400:]}


def walk(node, out):
    if isinstance(node, dict):
        if node.get("errorType"):
            out.append(node)
        for k in ("list", "violations"):
            if isinstance(node.get(k), list):
                for c in node[k]:
                    walk(c, out)
    elif isinstance(node, list):
        for c in node:
            walk(c, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-reload", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    call(["pcb", "save", "--doc", DOC])
    if not args.no_reload:
        call(["doc", "reload", DOC])
    r = call(["pcb", "drc", "--doc", DOC])
    res = r.get("result", r)
    items = []
    walk(res.get("violations"), items)
    print("DRC passed:", res.get("passed"))
    c = collections.Counter(i.get("errorType") for i in items)
    print("violations by type:", dict(c), " total:", sum(c.values()))
    shown = 0
    for it in items:
        if shown >= args.top:
            break
        ex = (it.get("explanation") or {}).get("errData") or {}
        names = [v for k, v in ex.items() if k.startswith("obj") and
                 isinstance(v, str) and not v.startswith("err")]
        print(f"  {it.get('errorType'):<22} {ex.get('name',''):<20} "
              f"clr={ex.get('clearance')} dist={ex.get('minDistance')} "
              f"{' | '.join(str(n)[:40] for n in names[:3])}")
        shown += 1
    if args.out:
        json.dump(res, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("saved ->", args.out)


if __name__ == "__main__":
    main()
