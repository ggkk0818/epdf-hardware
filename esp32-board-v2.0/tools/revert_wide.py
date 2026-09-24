"""Revert only the widened segments that the DRC says no longer fit.

Loops: run DRC -> find every target-net track that appears in a violation -> delete it
and re-create the same geometry at the original width. Repeat until no target-net track
is among the offenders (or the iteration cap is hit).
"""

import argparse
import json
import os
import subprocess
import sys
import time

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def call(args, tries=3):
    for k in range(tries):
        r = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
        out = r.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(1.0 + k)
    return None


def drc(doc, project):
    d = call(["pcb", "drc", "--doc", doc, "--project", project, "--json"])
    return (d or {}).get("result", d or {}).get("violations") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--nets", required=True)
    ap.add_argument("--narrow-width", type=float, default=10.0)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    nets = set(x for x in args.nets.split(",") if x)
    log = []
    for rnd in range(1, args.rounds + 1):
        tracks = (call(["pcb", "track-list", "--doc", args.doc, "--project", args.project])
                  or {}).get("result", {}).get("lines", [])
        mine = {w["primitiveId"]: w for w in tracks if w.get("net") in nets}
        viol = drc(args.doc, args.project)
        offenders = set()
        for v in viol:
            for o in v.get("objs") or []:
                if o in mine:
                    offenders.add(o)
        print(f"round {rnd}: DRC {len(viol)} violations, {len(offenders)} widened segment(s) implicated")
        log.append({"round": rnd, "drc": len(viol), "offenders": len(offenders)})
        if not offenders:
            print("clean: no widened segment is implicated")
            break
        for oid in offenders:
            w = mine[oid]
            call(["pcb", "track-delete", "--ids", oid, "--doc", args.doc, "--project", args.project])
            call(["pcb", "track",
                  "--x1", str(w["startX"]), "--y1", str(w["startY"]),
                  "--x2", str(w["endX"]), "--y2", str(w["endY"]),
                  "--layer", str(w["layer"]), "--width", str(args.narrow_width),
                  "--net", w["net"], "--doc", args.doc, "--project", args.project])
        call(["pcb", "pour-rebuild", "--doc", args.doc, "--project", args.project])
        call(["pcb", "save", "--doc", args.doc, "--project", args.project])
        call(["doc", "reload", args.doc, "--project", args.project])
        time.sleep(2)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
