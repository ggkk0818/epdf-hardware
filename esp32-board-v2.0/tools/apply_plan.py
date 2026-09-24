"""Rip up one net and replay a routed plan (tracks + vias) into the live PCB."""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402

EASYEDA = geom.EASYEDA
ROOT = geom.ROOT


def call(args, tries=4, quiet=False):
    for k in range(tries):
        r = subprocess.run([EASYEDA] + args + ["--project", geom.PROJECT],
                           capture_output=True, text=True, encoding="utf-8")
        out = r.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        if not quiet:
            print("  retry:", out.strip()[:160])
        time.sleep(1.0 + k)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--net")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.plan, encoding="utf-8") as fh:
        plan = json.load(fh)
    net = args.net or plan["net"]

    g = geom.load()
    old_tracks = [t for t in g["tracks"] if t.get("net") == net]
    old_vias = [v for v in g["vias"] if v.get("net") == net]
    print(f"rip up {len(old_tracks)} {net} tracks, {len(old_vias)} vias")
    if args.dry_run:
        return

    ids = ",".join(t["primitiveId"] for t in old_tracks)
    if ids:
        r = call(["pcb", "track-delete", "--ids", ids, "--doc", geom.DOC])
        print("  track-delete ok:", r and r.get("ok"))
    vids = ",".join(v["primitiveId"] for v in old_vias)
    if vids:
        r = call(["pcb", "via-delete", "--ids", vids, "--doc", geom.DOC])
        print("  via-delete ok:", r and r.get("ok"))

    made_v = made_t = 0
    for v in plan["vias"]:
        r = call(["pcb", "via", "--x", str(v["x"]), "--y", str(v["y"]),
                  "--net", net, "--hole", str(v.get("hole") or 12),
                  "--diameter", str(v.get("diameter") or 24), "--doc", geom.DOC],
                 quiet=True)
        made_v += 1 if (r and r.get("ok")) else 0
    for t in plan["tracks"]:
        r = call(["pcb", "track", "--x1", str(t["x1"]), "--y1", str(t["y1"]),
                  "--x2", str(t["x2"]), "--y2", str(t["y2"]),
                  "--layer", str(t["layer"]), "--width", str(t["width"]),
                  "--net", net, "--doc", geom.DOC], quiet=True)
        made_t += 1 if (r and r.get("ok")) else 0
    print(f"placed {made_t}/{len(plan['tracks'])} tracks, "
          f"{made_v}/{len(plan['vias'])} vias")


if __name__ == "__main__":
    main()
