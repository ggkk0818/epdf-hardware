"""Priority step 1: route the power nets with the maze router, mains first.

    python tools/route_power.py --dry-run
    python tools/route_power.py

Widths follow PCB_INTERFACE_POSITIONS.md 7.8: the high-current rails
(BAT / SYS / USB_VBUS) target 0.80 mm (31.5 mil), the other rails 0.50 mm
(19.69 mil).  Each net is routed against a FRESH geometry snapshot, so the
earlier (higher-priority) nets act as obstacles for the later ones.
GND is deliberately not routed: it gets the Inner1 plane + pours + stitching.
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
PY = sys.executable

# order matters: mains first, then the branch rails
MAINS = ["USB_VBUS_RAW", "USB_VBUS_PROT", "BAT1_RAW", "BAT2_RAW", "BAT_BUS", "SYS"]
BRANCH = ["3V3_MAIN", "EPD_3V3", "CHG_PMID", "CHG_REGN", "CHG_SW", "CHG_BTST",
          "TPS_L1", "TPS_L2", "TPS_VAUX", "EPD_VDD", "EPD_SW", "EPD_X",
          "EPD_VGH", "EPD_VGL", "EPD_VSH1", "EPD_VSH2", "EPD_VSL", "EPD_VCOM"]


def run(args, timeout=1800):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       cwd=ROOT, timeout=timeout)
    return r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default=None, help="comma list to restrict nets")
    ap.add_argument("--report", default=os.path.join(ROOT, "work",
                                                    "route-power-report.json"))
    args = ap.parse_args()

    todo = [(n, 31.5) for n in MAINS] + [(n, 19.69) for n in BRANCH]
    if args.only:
        keep = {s.strip() for s in args.only.split(",")}
        todo = [t for t in todo if t[0] in keep]

    log = []
    for net, width in todo:
        # The daemon caches reads until a reload: without this, the router cannot
        # see the copper added by the previous net and shorts straight through it.
        run([PY, "-c", "import sys; sys.path.insert(0,'tools'); import geom, "
                       "subprocess; subprocess.run([geom.EASYEDA,'pcb','save',"
                       "'--doc','PCB1','--project',geom.PROJECT],capture_output=True); "
                       "subprocess.run([geom.EASYEDA,'doc','reload','PCB1','--project',"
                       "geom.PROJECT],capture_output=True)"])
        # fresh obstacle model for every net: previously routed copper counts
        # NB geom.dump() only writes the snapshot when it is given a path — the
        # router reads work/geom.json, so the path is mandatory here.
        run([PY, "-c", "import sys, os; sys.path.insert(0,'tools'); import geom; "
                       "geom.dump(os.path.join(geom.ROOT,'work','geom.json'))"])
        plan = os.path.join(ROOT, "work", f"route-{net}.json")
        out = run([PY, os.path.join(ROOT, "tools", "sys_router.py"), net, plan,
                   "--max-width", str(width)])
        tail = [l for l in out.splitlines() if l.startswith(("grid", "emitted",
                                                            "total", "MST", "FAILED",
                                                            "no path"))]
        routed = os.path.exists(plan)
        print(f"-- {net:<14} width<={width:<6} plan={'yes' if routed else 'NO'}")
        for l in tail:
            print("     ", l)
        entry = {"net": net, "plan": routed}
        if routed and not args.dry_run:
            out2 = run([PY, os.path.join(ROOT, "tools", "apply_edits.py"), plan])
            print("     ", out2.strip().splitlines()[-1] if out2.strip() else "")
            entry["applied"] = "added" in out2
        log.append(entry)
        time.sleep(0.3)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
    ok = sum(1 for e in log if e.get("plan"))
    print(f"\npower nets planned {ok}/{len(log)}  -> {args.report}")


if __name__ == "__main__":
    main()
