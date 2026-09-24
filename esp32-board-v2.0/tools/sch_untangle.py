"""Find every electrically merged wire/marker cluster and emit a repair plan.

    python tools/sch_untangle.py --page P1            # report
    python tools/sch_untangle.py --page P1 --delete   # prim-delete the trees

Connectivity model that matches what the platform actually merges:

    wire   <-> wire    shared endpoint, or collinear overlapping span
    wire   <-> marker  marker anchor on the wire, or marker body over the wire
    wire   <-> pin     pin point on the wire
    marker <-> pin     marker body covering the pin, or anchor on the pin

Every cluster carrying more than one net name (or carrying a pin whose live net
differs from the authoritative one) is reported with the exact primitive IDs, so
its wires and markers can be deleted as a unit and each pin re-connected with a
collision-free placement.
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402
import sch_place  # noqa: E402
import sch_reconnect  # noqa: E402

ROOT = geom.ROOT
AUDIT = os.path.join(ROOT, "work", "audit")


class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def analyse(page_name):
    page = sch_place.Page(page_name)
    wires = page.wires
    flags = page.flags
    n = len(wires) + len(flags)
    dsu = DSU(n)

    def wi(i):
        return i

    def fi(i):
        return len(wires) + i

    # wire <-> wire
    for i, a in enumerate(wires):
        for j in range(i + 1, len(wires)):
            b = wires[j]
            ends_a = {(a["x0"], a["y0"]), (a["x1"], a["y1"])}
            ends_b = {(b["x0"], b["y0"]), (b["x1"], b["y1"])}
            if ends_a & ends_b:
                dsu.union(wi(i), wi(j))
                continue
            if (a["y0"] == a["y1"] == b["y0"] == b["y1"] and
                    min(a["x0"], a["x1"]) < max(b["x0"], b["x1"]) and
                    min(b["x0"], b["x1"]) < max(a["x0"], a["x1"])):
                dsu.union(wi(i), wi(j))
            elif (a["x0"] == a["x1"] == b["x0"] == b["x1"] and
                    min(a["y0"], a["y1"]) < max(b["y0"], b["y1"]) and
                    min(b["y0"], b["y1"]) < max(a["y0"], a["y1"])):
                dsu.union(wi(i), wi(j))

    # wire <-> marker
    for i, w in enumerate(wires):
        seg = (min(w["x0"], w["x1"]), min(w["y0"], w["y1"]),
               max(w["x0"], w["x1"]), max(w["y0"], w["y1"]))
        for k, f in enumerate(flags):
            b = f.get("bbox") or {}
            if b.get("minX") is None:
                continue
            body = (b["minX"], b["minY"], b["maxX"], b["maxY"])
            # the marker is attached when its anchor sits on the wire, or when
            # its rendered body covers part of the wire (the silent merge)
            if sch_place.seg_rect(w["x0"], w["y0"], w["x1"], w["y1"], body) or \
                    sch_place.seg_rect(w["x0"], w["y0"], w["x1"], w["y1"],
                                       (f["x"], f["y"], f["x"], f["y"])):
                dsu.union(wi(i), fi(k))

    # pins
    pins_in = {}
    for idx, p in enumerate(page.pins):
        for i, w in enumerate(wires):
            if sch_place.seg_rect(w["x0"], w["y0"], w["x1"], w["y1"],
                                  (p["x"], p["y"], p["x"], p["y"])):
                pins_in.setdefault(dsu.find(wi(i)), set()).add(idx)
        for k, f in enumerate(flags):
            b = f.get("bbox") or {}
            if b.get("minX") is None:
                continue
            if sch_place.point_in((b["minX"], b["minY"], b["maxX"], b["maxY"]),
                                  p["x"], p["y"]):
                pins_in.setdefault(dsu.find(fi(k)), set()).add(idx)

    clusters = {}
    for i in range(len(wires)):
        clusters.setdefault(dsu.find(wi(i)), {"wires": [], "flags": []})["wires"].append(i)
    for k in range(len(flags)):
        clusters.setdefault(dsu.find(fi(k)), {"wires": [], "flags": []})["flags"].append(k)
    for root, c in clusters.items():
        c["pins"] = sorted(pins_in.get(root, set()))
    return page, clusters


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True)
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--jobs-out", default=None)
    args = ap.parse_args()

    page, clusters = analyse(args.page)

    model = json.load(open(os.path.join(ROOT, "design", "model.json"),
                           encoding="utf-8"))
    pm = json.load(open(os.path.join(ROOT, "design", "pin-map.json"),
                        encoding="utf-8"))["resolved"]
    want_map = {}
    for comp in model["components"]:
        for pad in comp["pads"]:
            src = str(pad["num"])
            for dev in (pm.get(comp["ref"]) or {}).get(src) or [src]:
                want_map[f"{comp['ref']}.{dev}"] = pad.get("net") or None

    repairs = []
    for root, c in sorted(clusters.items()):
        names = {page.flags[k].get("name") for k in c["flags"]}
        pins = [page.pins[i] for i in c["pins"]]
        keys = [f"{p['ref']}.{p['num']}" for p in pins]
        # a cluster is defective when it merges several nets, is a nameless
        # orphan stub, or holds a pin that belongs on another net (or on none)
        hit = [k for k in keys
               if want_map.get(k) is None or want_map.get(k) not in names]
        defective = (len(names) > 1 or bool(hit)
                     or (not names and c["wires"]))
        if defective:
            wires = [page.wires[i]["primitiveId"] for i in c["wires"]]
            flags = [page.flags[k]["primitiveId"] for k in c["flags"]]
            repairs.append({"root": root, "names": sorted(names),
                            "wires": wires, "flags": flags, "pins": keys,
                            "flagged": hit})
    print(f"{args.page}: {len(clusters)} clusters, {len(repairs)} need repair")
    for r in repairs:
        print(f"  nets={r['names']} pins={r['pins']} flagged={r['flagged']}")
        print(f"     wires={r['wires']} flags={r['flags']}")

    out = os.path.join(ROOT, "work", f"untangle-{args.page}.json")
    json.dump(repairs, open(out, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    print("  ->", out)

    if args.jobs_out:
        jobs = {}
        for r in repairs:
            for key in r["pins"]:
                if want_map.get(key):
                    jobs[key] = {"pin": key.replace(".", ":"),
                                 "net": want_map[key]}
        json.dump(list(jobs.values()), open(args.jobs_out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"  {len(jobs)} reconnect jobs -> {args.jobs_out}")

    if args.delete:
        ids = []
        for r in repairs:
            ids += r["wires"] + r["flags"]
        for i in range(0, len(ids), 40):
            chunk = ids[i:i + 40]
            res = sch_reconnect.call(["sch", "prim-delete", "--doc", args.page,
                                      "--ids", ",".join(chunk)])
            print("  delete", len(chunk), "->",
                  json.dumps(res.get("result") or res.get("error"),
                             ensure_ascii=False)[:160])


if __name__ == "__main__":
    main()
