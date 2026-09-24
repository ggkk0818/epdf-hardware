"""Priority step 2: route the four USB data nets, one lane at a time.

    python tools/route_usb.py [--dry-run]

PCB_INTERFACE_POSITIONS.md 7.4 wants the USB pair at 0.24 mm (9.45 mil) and a
90 ohm differential impedance; the maze router's ladder is capped at 10 mil so
the emitted copper lands on the documented width.  Skew is equalised afterwards
by tools/serpentine.py and verified with `pcb report`.
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
PY = sys.executable
# Order matters: USB_DN_CONN has the harder J1 pocket (its two pads straddle the
# DP pad and the antenna keep-out blocks the south side), so it is routed first;
# USB_DP_CONN then works around it.
NETS = ["USB_DN_CONN", "USB_DP_CONN", "USB_DN", "USB_DP"]


def run(args, timeout=1800):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       cwd=ROOT, timeout=timeout)
    return r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    log = []
    for net in NETS:
        run([PY, "-c", "import sys, os, subprocess; sys.path.insert(0,'tools'); "
                       "import geom; subprocess.run([geom.EASYEDA,'pcb','save','--doc',"
                       "'PCB1','--project',geom.PROJECT],capture_output=True); "
                       "subprocess.run([geom.EASYEDA,'doc','reload','PCB1','--project',"
                       "geom.PROJECT],capture_output=True); "
                       "geom.dump(os.path.join(geom.ROOT,'work','geom.json'))"])
        plan = os.path.join(ROOT, "work", f"route-{net}.json")
        out = run([PY, os.path.join(ROOT, "tools", "sys_router.py"), net, plan,
                   "--max-width", "10"])
        ok = os.path.exists(plan)
        widths = [l for l in out.splitlines() if l.startswith("emitted widths")]
        vias = [l for l in out.splitlines() if l.startswith("emitted vias")]
        total = [l for l in out.splitlines() if l.startswith("total copper")]
        print(f"-- {net:<14} plan={'yes' if ok else 'NO'} "
              f"{widths[0] if widths else ''} {vias[0] if vias else ''}")
        if total:
            print("     ", total[0])
        entry = {"net": net, "plan": ok}
        if ok and not args.dry_run:
            out2 = run([PY, os.path.join(ROOT, "tools", "apply_edits.py"), plan])
            print("     ", out2.strip().splitlines()[-1] if out2.strip() else "")
            entry["applied"] = "added" in out2
        log.append(entry)
    json.dump(log, open(os.path.join(ROOT, "work", "route-usb-report.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print("done")


if __name__ == "__main__":
    main()
