"""Calibrate the obstacle model: recompute the min clearance of every existing
track against foreign copper and print the tightest cases. If the model matches
DRC, the global minimum should sit at the clearance rule (~6 mil)."""

import collections
import math
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom        # noqa: E402
import sys_router as route_sys  # noqa: E402

CELL = 200.0


def bucket_index(items, key):
    """Bucket items into CELL-sized grid cells by their bbox."""
    grid = collections.defaultdict(list)
    for it in items:
        b = key(it)
        i0 = int(math.floor(b[0] / CELL)); i1 = int(math.floor(b[2] / CELL))
        j0 = int(math.floor(b[1] / CELL)); j1 = int(math.floor(b[3] / CELL))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                grid[(i, j)].append(it)
    return grid


def nearby(grid, px, py, r):
    i0 = int(math.floor((px - r) / CELL)); i1 = int(math.floor((px + r) / CELL))
    j0 = int(math.floor((py - r) / CELL)); j1 = int(math.floor((py + r) / CELL))
    seen = set()
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            for it in grid.get((i, j), ()):
                k = id(it)
                if k not in seen:
                    seen.add(k)
                    yield it


def main():
    g = geom.load()
    tracks = g["tracks"]
    vias = g["vias"]
    comps = g["components"]

    print("pad layers:", collections.Counter(
        p.get("layer") for _, p in geom.iter_pads(comps)).most_common())
    print("pad nets blank:", sum(
        1 for _, p in geom.iter_pads(comps) if not p.get("net")))
    print("track layers:", collections.Counter(t["layer"] for t in tracks).most_common())
    print("track nets blank:", sum(1 for t in tracks if not t.get("net")))
    print("via layers sample:", vias[0] if vias else None)

    pads = [(c, p) for c, p in geom.iter_pads(comps)]

    pad_grid = bucket_index(pads, lambda cp: (
        cp[1]["x"] - max(cp[1].get("width") or 0, cp[1].get("height") or 0),
        cp[1]["y"] - max(cp[1].get("width") or 0, cp[1].get("height") or 0),
        cp[1]["x"] + max(cp[1].get("width") or 0, cp[1].get("height") or 0),
        cp[1]["y"] + max(cp[1].get("width") or 0, cp[1].get("height") or 0)))
    track_grid = bucket_index(tracks, lambda t: (
        min(t["startX"], t["endX"]), min(t["startY"], t["endY"]),
        max(t["startX"], t["endX"]), max(t["startY"], t["endY"])))
    via_grid = bucket_index(vias, lambda v: (
        v["x"] - 20, v["y"] - 20, v["x"] + 20, v["y"] + 20))

    worst = []
    for t in tracks:
        own = t.get("net")
        half = t["lineWidth"] / 2.0
        dmin = 1e9
        who = None
        n = max(2, int(geom.seg_len_mil(t) / 8) + 1)
        for k in range(n + 1):
            u = k / n
            px = t["startX"] + u * (t["endX"] - t["startX"])
            py = t["startY"] + u * (t["endY"] - t["startY"])
            R = 200.0
            for c, p in nearby(pad_grid, px, py, R):
                if p.get("net") == own or p.get("layer") != t["layer"]:
                    continue
                d = route_sys.rect_distance(px, py, p) - half
                if d < dmin:
                    dmin, who = d, f"pad {c['designator']}.{p.get('padNumber')}"
            for o in nearby(track_grid, px, py, R):
                if o is t or o.get("net") == own or o["layer"] != t["layer"]:
                    continue
                d = route_sys.seg_distance(px, py, o["startX"], o["startY"],
                                           o["endX"], o["endY"]) - half - o["lineWidth"] / 2.0
                if d < dmin:
                    dmin, who = d, f"track {o['primitiveId']}/{o.get('net')}"
            for v in nearby(via_grid, px, py, R):
                if v.get("net") == own:
                    continue
                d = math.hypot(px - v["x"], py - v["y"]) - half - (v.get("diameter") or 24) / 2.0
                if d < dmin:
                    dmin, who = d, f"via {v['primitiveId']}/{v.get('net')}"
        worst.append((dmin, who, t))

    worst.sort(key=lambda x: x[0])
    print("\ntightest 30 tracks (model clearance in mil):")
    for d, who, t in worst[:30]:
        print(f"  {d:7.2f}  w={t['lineWidth']:>5} L{t['layer']} "
              f"({t['startX']:.1f},{t['startY']:.1f})->({t['endX']:.1f},{t['endY']:.1f}) "
              f"via/obj={who}")
    hist = collections.Counter()
    for d, _, _ in worst:
        hist[int(d)] += 1
    print("\nhistogram of min clearance:", sorted(hist.items())[:15])


if __name__ == "__main__":
    main()
