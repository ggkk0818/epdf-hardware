"""Apply an edit plan in small batches, dropping degenerate/duplicate segments.

    python tools/apply_plan_batch.py work/pair-usb0.json [--batch 25] [--dry-run]

The platform refuses (or silently drops) some tiny/duplicated segments when a
large plan is pushed in one go; batching + de-duplication makes the apply
complete, which is what the USB pair plans need.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT


def call(args, tries=3):
    for k in range(tries):
        r = subprocess.run([geom.EASYEDA] + args + ["--project", geom.PROJECT],
                           capture_output=True, text=True, encoding="utf-8")
        out = r.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(0.8 + k)
    return None


def key(t):
    a = (round(t["x1"], 1), round(t["y1"], 1))
    b = (round(t["x2"], 1), round(t["y2"], 1))
    return (t["layer"], t["net"], min(a, b), max(a, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ed = json.load(open(args.plan, encoding="utf-8"))
    seen, tracks, dropped = set(), [], 0
    for t in ed.get("tracks") or []:
        if math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"]) < 1.0:
            dropped += 1
            continue
        k = key(t)
        if k in seen:
            dropped += 1
            continue
        seen.add(k)
        tracks.append(t)
    vias = ed.get("vias") or []
    print(f"{os.path.basename(args.plan)}: {len(tracks)} tracks "
          f"(dropped {dropped} degenerate/duplicate), {len(vias)} vias")
    if args.dry_run:
        return

    ok = bad = 0
    for i in range(0, len(tracks), args.batch):
        chunk = tracks[i:i + args.batch]
        for t in chunk:
            r = call(["pcb", "track", "--x1", str(t["x1"]), "--y1", str(t["y1"]),
                      "--x2", str(t["x2"]), "--y2", str(t["y2"]),
                      "--layer", str(t["layer"]), "--width", str(t.get("width", 10)),
                      "--net", t["net"], "--doc", "PCB1"])
            if r and r.get("ok"):
                ok += 1
            else:
                bad += 1
                err = ((r or {}).get("error") or {}).get("message", "no response")
                print(f"   ! {t['net']} ({t['x1']},{t['y1']})->({t['x2']},{t['y2']}): "
                      f"{err[:70]}")
        print(f"   batch {i//args.batch+1}: ok {ok}, fail {bad}", flush=True)
        # let the platform settle between batches
        call(["pcb", "save", "--doc", "PCB1"])
        time.sleep(0.5)
    for v in vias:
        r = call(["pcb", "via", "--x", str(v["x"]), "--y", str(v["y"]),
                  "--net", v["net"], "--hole", str(v.get("hole", 12)),
                  "--diameter", str(v.get("diameter", 24)), "--doc", "PCB1"])
        if r and r.get("ok"):
            ok += 1
        else:
            bad += 1
    print(f"applied ok {ok}, fail {bad}")


if __name__ == "__main__":
    main()
