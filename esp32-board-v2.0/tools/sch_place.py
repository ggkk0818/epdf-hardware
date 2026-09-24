"""Plan and apply collision-free marker placements for schematic pins.

    python tools/sch_place.py --page P1 --jobs work/fix-P1.json --dry-run
    python tools/sch_place.py --page P1 --jobs work/fix-P1.json --apply

Marker geometry (measured from this build's readbacks, schematic units):

    kind          body along stub        body across
    ground        anchor+9.5 .. +19.5    21
    power         anchor+4.5 .. +10.5    11
    net_port_bi   anchor+9.5 .. +40.5    11

The body always extends beyond the anchor in the stub direction. EasyEDA treats
a marker body that touches a foreign wire (or pins inside it) as connected, so
the planner hard-rejects any candidate whose stub or body overlaps a foreign
wire, a foreign pin, or a part body, and penalises marker/text overlaps.
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
import sch_reconnect  # noqa: E402

ROOT = geom.ROOT
AUDIT = os.path.join(ROOT, "work", "audit")
EASYEDA = geom.EASYEDA
PROJECT = geom.PROJECT

BODY = {
    "ground": (9.5, 19.5, 21.0),
    "power": (4.5, 10.5, 11.0),
    "net_port_bi": (9.5, 40.5, 11.0),
}
DIRV = {"right": (1, 0), "left": (-1, 0), "up": (0, 1), "down": (0, -1)}


def jload(path):
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    return json.loads(txt[txt.find("{"):])


def seg_rect(x0, y0, x1, y1, r):
    """Liang-Barsky: does the segment touch the axis-aligned rect?"""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - r[0]), (dx, r[2] - x0),
                 (-dy, y0 - r[1]), (dy, r[3] - y0)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 <= t1


def rects_overlap(a, b, eps=0.0):
    return (a[0] < b[2] - eps and b[0] < a[2] - eps and
            a[1] < b[3] - eps and b[1] < a[3] - eps)


def point_in(r, x, y, eps=0.5):
    return r[0] - eps <= x <= r[2] + eps and r[1] - eps <= y <= r[3] + eps


class Page:
    def __init__(self, page, skip=()):
        self.page = page
        self.skip = set(skip)
        full = jload(os.path.join(AUDIT, f"{page.lower()}-full.json"))["result"]
        self.comps = full["components"]
        self.wires = full.get("wires") or []
        self.parts = [c for c in self.comps if c.get("componentType") == "part"]
        self.flags = [c for c in self.comps
                      if c.get("componentType") in ("netflag", "netport")]
        self.pins = []
        for c in self.parts:
            for p in c.get("pins") or []:
                self.pins.append({"ref": c["designator"], "num": p["pinNumber"],
                                  "x": p["x"], "y": p["y"],
                                  "rot": p.get("rotation"),
                                  "net": p.get("net"), "part": c})

    def pin(self, key):
        ref, num = key.split(":", 1) if ":" in key else key.split(".", 1)
        for p in self.pins:
            if p["ref"] == ref and p["num"] == num:
                return p
        return None

    def exit_dir(self, pin):
        # pin rotation 180 => the pin points left (stub must go left)
        rot = pin["rot"] or 0
        return {0: "right", 180: "left", 90: "up", 270: "down"}.get(int(rot) % 360,
                                                                    "right")

    def wire_rects(self, skip=None):
        skip = set(skip or ()) | self.skip
        out = []
        for w in self.wires:
            if w["primitiveId"] in skip:
                continue
            out.append((min(w["x0"], w["x1"]), min(w["y0"], w["y1"]),
                        max(w["x0"], w["x1"]), max(w["y0"], w["y1"]), w))
        return out

    def marker_rects(self, skip=None):
        skip = set(skip or ()) | self.skip
        out = []
        for f in self.flags:
            if f["primitiveId"] in skip:
                continue
            b = f.get("bbox") or {}
            if b.get("minX") is None:
                continue
            out.append((b["minX"], b["minY"], b["maxX"], b["maxY"], f))
        return out


def body_rect(pin, direction, offset, kind):
    ux, uy = DIRV[direction]
    ax = pin["x"] + ux * offset
    ay = pin["y"] + uy * offset
    off0, off1, across = BODY[kind]
    bx0, bx1 = sorted((ax + ux * off0, ax + ux * off1))
    if ux:
        return (bx0, ay - across / 2.0, bx1, ay + across / 2.0), (ax, ay)
    return (ax - across / 2.0, bx0, ax + across / 2.0, bx1), (ax, ay)


def evaluate(page, pin, net, kind, direction, offset, planned=None, eps=0.75):
    """Return (feasible, cost, detail) for placing the marker at this offset."""
    planned = planned or {"stubs": [], "bodies": [], "texts": []}
    ux, uy = DIRV[direction]
    ax, ay = pin["x"] + ux * offset, pin["y"] + uy * offset
    body, anchor = body_rect(pin, direction, offset, kind)
    stub = (min(pin["x"], ax), min(pin["y"], ay),
            max(pin["x"], ax), max(pin["y"], ay))
    hard = []
    soft = 0.0

    # foreign pins: the stub must not run through them, the body must not cover
    for q in page.pins:
        if q["ref"] == pin["ref"] and q["num"] == pin["num"]:
            continue
        if abs(q["x"] - ax) < eps and abs(q["y"] - ay) < eps:
            hard.append(f"anchor on pin {q['ref']}.{q['num']}")
        if point_in(stub, q["x"], q["y"]) and not (abs(q["x"] - pin["x"]) < eps
                                                   and abs(q["y"] - pin["y"]) < eps):
            # on the axis of the stub and inside its span
            if (ux and abs(q["y"] - pin["y"]) < eps and
                    min(pin["x"], ax) - eps < q["x"] < max(pin["x"], ax) + eps) or \
               (uy and abs(q["x"] - pin["x"]) < eps and
                    min(pin["y"], ay) - eps < q["y"] < max(pin["y"], ay) + eps):
                hard.append(f"stub crosses pin {q['ref']}.{q['num']}")
        if point_in(body, q["x"], q["y"], eps):
            hard.append(f"body covers pin {q['ref']}.{q['num']}")

    # own part body must not be crossed by the stub
    bb = pin["part"].get("bbox") or {}
    if bb.get("minX") is not None:
        own = (bb["minX"], bb["minY"], bb["maxX"], bb["maxY"])
        if seg_rect(stub[0], stub[1], stub[2], stub[3], own):
            # allowed only if the stub leaves through the pin point itself
            hard.append("stub crosses its own part body")

    for r in page.wire_rects(set()):
        if seg_rect(stub[0], stub[1], stub[2], stub[3], r) :
            hard.append(f"stub overlaps wire {r[4]['primitiveId']}")
        if rects_overlap(body, r, -eps):
            hard.append(f"marker body overlaps wire {r[4]['primitiveId']}")

    for r in page.marker_rects(set()):
        if rects_overlap(body, r, -eps):
            if r[4].get("name") == net:
                soft += 1.0
            else:
                soft += 40.0
        if seg_rect(stub[0], stub[1], stub[2], stub[3], r):
            if r[4].get("name") != net:
                hard.append(f"stub crosses marker {r[4]['primitiveId']} "
                            f"({r[4].get('name')})")

    for c in page.parts:
        if c is pin["part"]:
            continue
        b = c.get("bbox") or {}
        if b.get("minX") is None:
            continue
        r = (b["minX"], b["minY"], b["maxX"], b["maxY"])
        if seg_rect(stub[0], stub[1], stub[2], stub[3], r):
            hard.append(f"stub crosses part {c['designator']}")
        if rects_overlap(body, r, -eps):
            soft += 6.0

    # markers/stubs already planned in this pass
    for (sx0, sy0, sx1, sy1, snet) in planned["stubs"]:
        if seg_rect(stub[0], stub[1], stub[2], stub[3],
                    (min(sx0, sx1), min(sy0, sy1), max(sx0, sx1), max(sy0, sy1))):
            hard.append(f"stub overlaps planned stub ({snet})")
        if rects_overlap(body, (min(sx0, sx1), min(sy0, sy1),
                                max(sx0, sx1), max(sy0, sy1)), -eps):
            hard.append(f"body covers planned stub ({snet})")
    for (bx0, by0, bx1, by1, bnet) in planned["bodies"]:
        if seg_rect(stub[0], stub[1], stub[2], stub[3],
                    (bx0, by0, bx1, by1)):
            hard.append(f"stub crosses planned marker ({bnet})")
        if rects_overlap(body, (bx0, by0, bx1, by1), -eps):
            soft += 1.0 if bnet == net else 40.0

    # text band beyond the body (soft: cosmetic, and it also collides visually)
    off0, off1, _ = BODY[kind]
    tlen = max(31.0, 6.0 * len(net))
    tx0 = ax + ux * (off1 + 4)
    tx1 = ax + ux * (off1 + 4 + tlen)
    if ux:
        text = (min(tx0, tx1), ay - 6, max(tx0, tx1), ay + 6)
    else:
        text = (ax - 6, min(tx0, tx1), ax + 6, max(tx0, tx1))
    for r in page.wire_rects(set()):
        if rects_overlap(text, r):
            soft += 3.0
    for r in page.marker_rects(set()):
        if rects_overlap(text, r):
            soft += 3.0
    for c in page.parts:
        b = c.get("bbox") or {}
        if b.get("minX") is None:
            continue
        if rects_overlap(text, (b["minX"], b["minY"], b["maxX"], b["maxY"])):
            soft += 4.0
    cost = offset + soft * 10.0
    return (not hard), cost, {"anchor": [ax, ay], "body": body,
                              "hard": hard[:4], "soft": soft}


def plan_pin(page, pin, net, kind, offsets, planned=None):
    d = page.exit_dir(pin)
    best = None
    for off in offsets:
        ok, cost, det = evaluate(page, pin, net, kind, d, off, planned)
        if ok and (best is None or cost < best[0]):
            best = (cost, d, off, det)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True)
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--off-min", type=float, default=12)
    ap.add_argument("--off-max", type=float, default=300)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--exclude", default=None,
                    help="untangle JSON whose wires/flags will be deleted first")
    args = ap.parse_args()

    jobs = json.load(open(args.jobs, encoding="utf-8"))
    if args.limit:
        jobs = jobs[:args.limit]
    skip = set()
    if args.exclude:
        for r in json.load(open(args.exclude, encoding="utf-8")):
            skip |= set(r["wires"]) | set(r["flags"])
    page = Page(args.page, skip)
    offsets = [float(o) for o in range(int(args.off_min), int(args.off_max) + 1)]
    plan, failed = [], []
    planned = {"stubs": [], "bodies": [], "texts": []}
    for job in jobs:
        key = job["pin"].replace(".", ":")
        pin = page.pin(key)
        if not pin:
            failed.append((key, "pin not found"))
            continue
        kind = sch_reconnect.kind_for(job["net"])
        best = plan_pin(page, pin, job["net"], kind, offsets, planned)
        if not best:
            failed.append((key, "no collision-free candidate"))
            continue
        cost, d, off, det = best
        planned["stubs"].append((pin["x"], pin["y"], det["anchor"][0],
                                 det["anchor"][1], job["net"]))
        planned["bodies"].append((*det["body"], job["net"]))
        plan.append({"pin": key, "net": job["net"], "kind": kind,
                     "direction": d, "offset": off, "cost": cost,
                     "anchor": det["anchor"], "hard": det["hard"],
                     "soft": det["soft"]})
    for p in plan:
        print(f"  {p['pin']:<12} -> {p['net']:<12} {p['kind']:<12} "
              f"{p['direction']:<5} off={p['offset']:<5} cost={p['cost']:.1f} "
              f"soft={p['soft']:.0f} anchor={p['anchor']}")
    for key, why in failed:
        print(f"  {key:<12} FAILED: {why}")
    out = os.path.join(ROOT, "work", f"place-{args.page}.json")
    json.dump(plan, open(out, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    print(f"{len(plan)} planned, {len(failed)} unplaceable -> {out}")

    if not args.apply:
        return
    ok = bad = 0
    for p in plan:
        cmd = ["sch", "connect", "--doc", args.page, "--pin", p["pin"],
               "--kind", p["kind"], "--net", p["net"],
               "--direction", p["direction"], "--offset", str(p["offset"])]
        r = sch_reconnect.call(cmd)
        good = bool(r.get("ok"))
        ok += good
        bad += (not good)
        if not good:
            print(f"  connect {p['pin']} FAILED:",
                  json.dumps(r.get("error"), ensure_ascii=False)[:160])
        else:
            res = r.get("result") or {}
            print(f"  connect {p['pin']:<12} ok  wire={res.get('wirePrimitiveId')}"
                  f" flag={res.get('flagPrimitiveId')}")
        time.sleep(0.2)
    print(f"applied: ok {ok}, fail {bad}")


if __name__ == "__main__":
    main()
