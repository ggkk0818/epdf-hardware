"""Delete the GND track/via primitives that sit too close to other nets' pads.

GND is backed by the Inner1 plane plus stitching, so removing a stray GND stub or
via that violates clearance does not break the net — it just removes the offender.
"""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def call(args):
    r = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
    t = r.stdout
    i = t.find("{")
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(t[i:])[0]
    except Exception:
        return None


def main():
    drc_path, doc, project = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(drc_path, encoding="utf-8") as fh:
        t = fh.read()
    i = t.find("{")
    d, _ = json.JSONDecoder().raw_decode(t[i:])
    r = d.get("result", d)

    track_ids = {w["primitiveId"] for w in
                 (call(["pcb", "track-list", "--doc", doc, "--project", project])
                  or {}).get("result", {}).get("lines", [])}
    via_ids = {v["primitiveId"] for v in
               (call(["pcb", "via-list", "--doc", doc, "--project", project])
                or {}).get("result", {}).get("vias", [])}

    kill_tracks, kill_vias = set(), set()
    for x in r.get("violations") or []:
        if x.get("rule") != "Clearance Error":
            continue
        msg = x.get("message") or ""
        if "(GND)" not in msg:
            continue
        # the message reads "(NET_A): objA to (NET_B): objB" — take the GND side
        idx = 0 if msg.lstrip().startswith("(GND)") else 1
        objs = x.get("objs") or []
        if len(objs) <= idx:
            continue
        cand = objs[idx]
        if cand in track_ids:
            kill_tracks.add(cand)
        elif cand in via_ids:
            kill_vias.add(cand)

    print("GND offenders: tracks", len(kill_tracks), "vias", len(kill_vias))
    for ids, cmd in ((sorted(kill_tracks), "track-delete"), (sorted(kill_vias), "via-delete")):
        for k in range(0, len(ids), 20):
            chunk = ids[k:k + 20]
            res = call(["pcb", cmd, "--ids", ",".join(chunk), "--doc", doc,
                        "--project", project])
            print(f"  {cmd}: {'ok' if (res and res.get('ok')) else 'FAILED'} ({len(chunk)})")


if __name__ == "__main__":
    main()
