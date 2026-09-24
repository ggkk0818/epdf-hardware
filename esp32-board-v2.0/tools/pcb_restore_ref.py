"""Restore every non-fixed component to the accepted previous layout.

    python tools/pcb_restore_ref.py

Anchors/rotations come from work/ref-last-layout.json. The ten locked parts
(J1-J5, SW1-SW5) are already at those coordinates; everything else is moved back
because the generic auto-place + spiral legalizer scored worse (more ratsnest
crossings) than the layout that was already tuned on this board.
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
EASYEDA = geom.EASYEDA
PROJECT = geom.PROJECT
DOC = "PCB1"
FIXED = {"J1", "J2", "J3", "J4", "J5", "SW1", "SW2", "SW3", "SW4", "SW5"}


def call(args, tries=3):
    for k in range(tries):
        r = subprocess.run([EASYEDA] + args + ["--project", PROJECT],
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
    ref = json.load(open(os.path.join(ROOT, "work", "ref-last-layout.json"),
                         encoding="utf-8"))
    cur = call(["pcb", "dump", "--label", "restore", "--no-silk",
                "--no-rules", "--no-layers", "--doc", DOC])
    comps = {c["designator"]: c for c in (cur or {}).get("components") or []}
    if not comps:
        print("no components read back")
        return
    moved = same = failed = 0
    for c in ref["components"]:
        ref_d = c["designator"]
        if ref_d in FIXED:
            continue
        cur_c = comps.get(ref_d)
        if not cur_c:
            failed += 1
            continue
        if (abs(cur_c["x"] - c["x"]) < 0.01 and abs(cur_c["y"] - c["y"]) < 0.01
                and abs((cur_c.get("rotation") or 0) - (c.get("rotation") or 0)) % 360 < 0.01):
            same += 1
            continue
        patch = json.dumps({"x": c["x"], "y": c["y"],
                            "rotation": c.get("rotation") or 0})
        r = call(["pcb", "modify", "--id", cur_c["primitiveId"],
                  "--patch", patch, "--doc", DOC])
        if r and r.get("ok"):
            moved += 1
        else:
            failed += 1
            print(f"  ! {ref_d} restore failed")
        time.sleep(0.2)
        if (moved + failed) % 25 == 0:
            print(f"  ... {moved} restored", flush=True)
    print(f"restored {moved}, already correct {same}, failed {failed}")


if __name__ == "__main__":
    main()
