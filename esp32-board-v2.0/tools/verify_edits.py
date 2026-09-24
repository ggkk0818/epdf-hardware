"""Verify a surgical edit before replaying it.

Checks (a) every new segment/via against the current board minus the objects the
edit deletes, and (b) that the antenna keep-out rectangle stays copper-free for
the newly added copper.
"""

import json
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import clearance  # noqa: E402
import geom  # noqa: E402

ANT = (629.92, 3070.77, 1535.43, 3307.09)   # ESP32_ANT_KEEP_OUT, mil


def seg_in_rect(t, rect):
    x0, y0, x1, y1 = rect
    pts = [(t["x1"], t["y1"]), (t["x2"], t["y2"])]
    if any(x0 <= px <= x1 and y0 <= py <= y1 for px, py in pts):
        return True
    # coarse: sample the run
    n = max(2, int(((t["x2"] - t["x1"]) ** 2 + (t["y2"] - t["y1"]) ** 2) ** 0.5 / 2) + 1)
    for k in range(n + 1):
        u = k / n
        px = t["x1"] + u * (t["x2"] - t["x1"])
        py = t["y1"] + u * (t["y2"] - t["y1"])
        if x0 <= px <= x1 and y0 <= py <= y1:
            return True
    return False


def main():
    path = sys.argv[1]
    with open(path, encoding="utf-8") as fh:
        ed = json.load(fh)
    ignore = set((ed.get("delete") or {}).get("tracks") or []) | \
        set((ed.get("delete") or {}).get("vias") or [])
    nets = {t["net"] for t in (ed.get("tracks") or [])}
    if "--ignore-net" in sys.argv:
        nets |= set(sys.argv[sys.argv.index("--ignore-net") + 1].split(","))
    # any net named in --ignore-net is skipped wholesale by the Oracle
    oracle = clearance.Oracle(net=nets, ignore=ignore)

    rows = []
    for t in ed.get("tracks") or []:
        m, who = oracle.seg_margin(t["x1"], t["y1"], t["x2"], t["y2"],
                                   t.get("width", 10), t["layer"])
        rows.append((m, "track", t, who))
    for v in ed.get("vias") or []:
        m, who = oracle.point_margin(v["x"], v["y"], v.get("diameter", 24) / 2.0, None)
        rows.append((m, "via", v, who))

    bad = [r for r in rows if r[0] < 0]
    for m, kind, o, who in sorted(rows, key=lambda r: r[0])[:8]:
        xy = (f"({o['x1']:.1f},{o['y1']:.1f})->({o['x2']:.1f},{o['y2']:.1f})"
              if kind == "track" else f"({o['x']:.1f},{o['y']:.1f})")
        print(f"   margin {m:7.2f}  {kind:<5} L{o.get('layer','')} {xy} vs {who}")
    for t in ed.get("tracks") or []:
        if seg_in_rect(t, ANT):
            print(f"   ANTENNA-KEEPOUT HIT: L{t['layer']} "
                  f"({t['x1']:.1f},{t['y1']:.1f})->({t['x2']:.1f},{t['y2']:.1f})")
            bad.append((-1, "keepout", t, "antenna"))
    print("RESULT:", "PASS" if not bad else f"{len(bad)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
