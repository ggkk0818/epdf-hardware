"""Apply a surgical copper edit: delete specific primitives, then add tracks/vias.

    python tools/apply_edits.py work/antenna-fix.json [--dry-run]

The edit file looks like::

    {"tracks":     [{"x1":..,"y1":..,"x2":..,"y2":..,"layer":16,"width":10,"net":"3V3_MAIN"}, ...],
     "vias":       [{"x":..,"y":..,"net":"GND","diameter":24,"hole":12}, ...],
     "delete":     {"tracks":["primitiveId", ...], "vias":["primitiveId", ...]},
     "delete_net": ["KEY3_N"]}
"""

import argparse
import json
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def call(args, tries=4):
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
        time.sleep(1.0 + k)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.edit, encoding="utf-8") as fh:
        ed = json.load(fh)

    tids = list((ed.get("delete") or {}).get("tracks") or [])
    vids = list((ed.get("delete") or {}).get("vias") or [])
    for net in ed.get("delete_net") or []:
        tids += [t["primitiveId"] for t in geom.load()["tracks"] if t.get("net") == net]
        vids += [v["primitiveId"] for v in geom.load()["vias"] if v.get("net") == net]

    print(f"delete {len(tids)} track(s), {len(vids)} via(s); "
          f"add {len(ed.get('tracks') or [])} track(s), {len(ed.get('vias') or [])} via(s)")
    if args.dry_run:
        return
    if tids:
        r = call(["pcb", "track-delete", "--ids", ",".join(tids), "--doc", geom.DOC])
        print("  track-delete:", r and r.get("ok"))
    if vids:
        r = call(["pcb", "via-delete", "--ids", ",".join(vids), "--doc", geom.DOC])
        print("  via-delete:", r and r.get("ok"))
    ok_t = ok_v = 0
    for t in ed.get("tracks") or []:
        r = call(["pcb", "track", "--x1", str(t["x1"]), "--y1", str(t["y1"]),
                  "--x2", str(t["x2"]), "--y2", str(t["y2"]),
                  "--layer", str(t["layer"]), "--width", str(t.get("width", 10)),
                  "--net", t["net"], "--doc", geom.DOC])
        ok_t += 1 if (r and r.get("ok")) else 0
    for v in ed.get("vias") or []:
        r = call(["pcb", "via", "--x", str(v["x"]), "--y", str(v["y"]), "--net", v["net"],
                  "--hole", str(v.get("hole", 12)), "--diameter", str(v.get("diameter", 24)),
                  "--doc", geom.DOC])
        ok_v += 1 if (r and r.get("ok")) else 0
    print(f"added {ok_t}/{len(ed.get('tracks') or [])} tracks, "
          f"{ok_v}/{len(ed.get('vias') or [])} vias")


if __name__ == "__main__":
    main()
