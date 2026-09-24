"""Back up / restore the whole copper layer set (tracks + vias).

`pcb rip-up` deletes vias as well as tracks, so a track-only dump is not a rollback
point. This stores both and can replay them.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("mode", choices=["save", "restore"])
    ap.add_argument("--file", required=True)
    args = ap.parse_args()

    if args.mode == "save":
        tracks = (call(["pcb", "track-list", "--doc", args.doc, "--project", args.project])
                  or {}).get("result", {}).get("lines", [])
        vias = (call(["pcb", "via-list", "--doc", args.doc, "--project", args.project])
                or {}).get("result", {}).get("vias", [])
        with open(args.file, "w", encoding="utf-8") as fh:
            json.dump({"tracks": tracks, "vias": vias}, fh, ensure_ascii=False, indent=1)
        print(f"saved {len(tracks)} tracks, {len(vias)} vias -> {args.file}")
        return

    with open(args.file, encoding="utf-8") as fh:
        data = json.load(fh)
    call(["pcb", "rip-up", "--doc", args.doc, "--project", args.project])
    made_v = 0
    for v in data["vias"]:
        r = call(["pcb", "via", "--x", str(v["x"]), "--y", str(v["y"]),
                  "--net", v.get("net") or "", "--hole", str(v.get("holeDiameter") or 12),
                  "--diameter", str(v.get("diameter") or 24),
                  "--doc", args.doc, "--project", args.project])
        made_v += 1 if (r and r.get("ok")) else 0
    made_t = 0
    for w in data["tracks"]:
        r = call(["pcb", "track", "--x1", str(w["startX"]), "--y1", str(w["startY"]),
                  "--x2", str(w["endX"]), "--y2", str(w["endY"]),
                  "--layer", str(w["layer"]), "--width", str(w["lineWidth"]),
                  "--net", w.get("net") or "", "--doc", args.doc, "--project", args.project])
        made_t += 1 if (r and r.get("ok")) else 0
    print(f"restored {made_t}/{len(data['tracks'])} tracks, {made_v}/{len(data['vias'])} vias")


if __name__ == "__main__":
    main()
