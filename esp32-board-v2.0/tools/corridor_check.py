"""Score candidate segments against the board's existing tracks and vias."""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def fetch(doc, project):
    def call(args):
        r = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
        o = r.stdout
        i = o.find("{")
        return json.JSONDecoder().raw_decode(o[i:])[0]["result"]

    tr = call(["pcb", "track-list", "--doc", doc, "--project", project]).get("lines") or []
    vs = call(["pcb", "via-list", "--doc", doc, "--project", project]).get("vias") or []
    return tr, vs


def seg_hits(seg, tracks, vias, layer, halfw=5.0, margin=8.0):
    """Count existing copper closer than (halfw + margin) to the candidate segment."""
    (x1, y1), (x2, y2) = seg
    need = halfw + margin
    hits = 0
    detail = []
    for w in tracks:
        if w.get("layer") != layer:
            continue
        a = (w["startX"], w["startY"])
        b = (w["endX"], w["endY"])
        # both horizontal / both vertical / generic: use segment-segment distance via sampling
        n = max(2, int(max(abs(x2 - x1), abs(y2 - y1)) // 10))
        bad = False
        for k in range(n + 1):
            t = k / n
            px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            m = max(2, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) // 10))
            for j in range(m + 1):
                s = j / m
                qx, qy = a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s
                if abs(px - qx) <= need and abs(py - qy) <= need:
                    bad = True
                    break
            if bad:
                break
        if bad:
            hits += 1
            detail.append((w.get("net"), w.get("primitiveId")))
    for v in vias:
        vx, vy = v["x"], v["y"]
        n = max(2, int(max(abs(x2 - x1), abs(y2 - y1)) // 10))
        for k in range(n + 1):
            t = k / n
            px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            if abs(px - vx) <= need + 6 and abs(py - vy) <= need + 6:
                hits += 1
                detail.append(("via:" + str(v.get("net")), v.get("primitiveId")))
                break
    return hits, detail


def main():
    doc, project = sys.argv[1], sys.argv[2]
    cands = json.loads(sys.argv[3])     # [[x1,y1,x2,y2,layer], ...]
    tracks, vias = fetch(doc, project)
    print(f"board has {len(tracks)} tracks, {len(vias)} vias")
    for (x1, y1, x2, y2, layer) in cands:
        hits, detail = seg_hits(((x1, y1), (x2, y2)), tracks, vias, layer)
        print(f"  L{layer:<2} ({x1:7.1f},{y1:7.1f})->({x2:7.1f},{y2:7.1f})  conflicts={hits}"
              + (f"  e.g. {detail[:3]}" if detail else "  CLEAR"))


if __name__ == "__main__":
    main()
