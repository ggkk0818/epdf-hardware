"""Exact clearance check (and optional local repair) for a routed plan.

    python tools/verify_plan.py work/sys-plan.json SYS
    python tools/verify_plan.py work/sys-plan.json SYS --repair work/sys-plan-fixed.json

Repair moves a marginal via within a small neighbourhood (keeping the two
adjacent tracks attached) and picks the site with the largest exact margin.
"""

import collections
import json
import math
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import clearance  # noqa: E402


def worst(plan, oracle):
    rows = []
    for t in plan["tracks"]:
        m, who = oracle.seg_margin(t["x1"], t["y1"], t["x2"], t["y2"],
                                   t["width"], t["layer"])
        rows.append((m, "track", t, who))
    for v in plan["vias"]:
        m, who = oracle.point_margin(v["x"], v["y"], v["diameter"] / 2.0, None)
        rows.append((m, "via", v, who))
    return rows


def repair(plan, oracle, need=0.6, radius=14.0, step=0.5):
    fixed = {"net": plan["net"],
             "tracks": [dict(t) for t in plan["tracks"]],
             "vias": [dict(v) for v in plan["vias"]]}
    moves = 0
    for vi, v in enumerate(fixed["vias"]):
        m, _ = oracle.point_margin(v["x"], v["y"], v["diameter"] / 2.0, None)
        if m >= need:
            continue
        best = (m, v["x"], v["y"])
        k = int(radius / step)
        for di in range(-k, k + 1):
            for dj in range(-k, k + 1):
                px = v["x"] + di * step
                py = v["y"] + dj * step
                mm, _ = oracle.point_margin(px, py, v["diameter"] / 2.0, None)
                # prefer closer moves when margins tie
                score = mm - 0.004 * math.hypot(px - v["x"], py - v["y"])
                bs = best[0] - 0.004 * math.hypot(best[1] - v["x"], best[2] - v["y"])
                if score > bs:
                    best = (mm, px, py)
        if best[0] > m:
            ox, oy = v["x"], v["y"]
            nx, ny = best[1], best[2]
            for t in fixed["tracks"]:
                if abs(t["x1"] - ox) < 0.75 and abs(t["y1"] - oy) < 0.75:
                    t["x1"], t["y1"] = round(nx, 2), round(ny, 2)
                if abs(t["x2"] - ox) < 0.75 and abs(t["y2"] - oy) < 0.75:
                    t["x2"], t["y2"] = round(nx, 2), round(ny, 2)
            v["x"], v["y"] = round(nx, 2), round(ny, 2)
            moves += 1
            print(f"  via {vi}: ({ox:.1f},{oy:.1f}) -> ({nx:.1f},{ny:.1f}) "
                  f"margin {m:.2f} -> {best[0]:.2f}")
    print(f"repaired {moves} via/vias")
    return fixed


def main():
    path = sys.argv[1]
    net = sys.argv[2] if len(sys.argv) > 2 else "SYS"
    out = None
    if "--repair" in sys.argv:
        out = sys.argv[sys.argv.index("--repair") + 1]
    with open(path, encoding="utf-8") as fh:
        plan = json.load(fh)
    oracle = clearance.Oracle(net=net)

    rows = worst(plan, oracle)
    hist = collections.Counter()
    for t in plan["tracks"]:
        hist[t["width"]] += 1
    print(f"plan: {len(plan['tracks'])} tracks {dict(sorted(hist.items()))}, "
          f"{len(plan['vias'])} vias")
    bad = [r for r in rows if r[0] < 0]
    print(f"worst margins: tracks {min(r[0] for r in rows if r[1]=='track'):.2f} mil, "
          f"vias {min([r[0] for r in rows if r[1]=='via'], default=float('nan')):.2f} mil")
    for m, kind, obj, who in sorted(rows, key=lambda r: r[0])[:6]:
        tag = f"w={obj['width']} L{obj['layer']}" if kind == "track" else "via"
        xy = (f"({obj['x1']:.1f},{obj['y1']:.1f})->({obj['x2']:.1f},{obj['y2']:.1f})"
              if kind == "track" else f"({obj['x']:.1f},{obj['y']:.1f})")
        print(f"   {m:7.2f} {tag} {xy} vs {who}")
    if not bad:
        print("RESULT: PASS")
        return 0
    print(f"RESULT: {len(bad)} violation(s)")
    if out:
        fixed = repair(plan, oracle)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(fixed, fh, ensure_ascii=False, indent=1)
        rows2 = worst(fixed, oracle)
        bad2 = [r for r in rows2 if r[0] < 0]
        print(f"after repair: {len(bad2)} violation(s), worst "
              f"{min(r[0] for r in rows2):.2f} mil -> {out}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
