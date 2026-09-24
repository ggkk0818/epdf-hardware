"""Report (and optionally delete) degenerate wires and pin-less stub fragments."""

import argparse
import json
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def call(args):
    res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    if i < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(out[i:])
    except Exception:
        return None
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--shrink", type=float, default=2.0,
                    help="shrink part bboxes by this many units before testing")
    args = ap.parse_args()

    d = call(["sch", "list", "--page", args.doc, "--include-pins", "--include-wires",
              "--include-bbox",
              "--project", args.project])
    r = (d or {}).get("result", {})
    pins = set()
    for c in r.get("components", []):
        if c.get("componentType") != "part":
            continue
        for p in c.get("pins") or []:
            pins.add((p.get("x"), p.get("y")))

    boxes = []
    for c in r.get("components", []):
        if c.get("componentType") != "part":
            continue
        b = c.get("bbox")
        if not b:
            continue
        boxes.append((c.get("designator"), b))

    wires = r.get("wires") or []
    degenerate, orphans = [], []
    ends_of = {}
    for w in wires:
        a = (w["x0"], w["y0"])
        b = (w["x1"], w["y1"])
        ends_of[w["primitiveId"]] = (a, b)
        if a == b:
            degenerate.append(w["primitiveId"])
    for w in wires:
        a, b = ends_of[w["primitiveId"]]
        if a in pins or b in pins:
            continue
        orphans.append(w["primitiveId"])

    def seg_in_box(a, b, box, k):
        minx, miny = box["minX"] + k, box["minY"] + k
        maxx, maxy = box["maxX"] - k, box["maxY"] - k
        if minx >= maxx or miny >= maxy:
            return False
        x0, y0 = a
        x1, y1 = b
        if x0 == x1:
            return minx < x0 < maxx and max(min(y0, y1), miny) < min(max(y0, y1), maxy)
        if y0 == y1:
            return miny < y0 < maxy and max(min(x0, x1), minx) < min(max(x0, x1), maxx)
        return False

    crossing = []
    if boxes:
        for w in wires:
            a, b = ends_of[w["primitiveId"]]
            for ref, box in boxes:
                if seg_in_box(a, b, box, args.shrink):
                    crossing.append((w["primitiveId"], ref, a, b))
                    break

    print(f"{args.doc}: wires={len(wires)} degenerate={len(degenerate)} pinless={len(orphans)} "
          f"crossing-bodies={len(crossing)}")
    for wid, ref, a, b in crossing[:15]:
        print(f"   crosses {ref}: {wid} {a}->{b}")
    for wid in degenerate[:10]:
        print("   degenerate", wid, ends_of[wid])
    for wid in orphans[:15]:
        print("   pinless   ", wid, ends_of[wid])

    if args.apply:
        targets = sorted(set(degenerate + orphans + [c[0] for c in crossing]))
        for k in range(0, len(targets), 25):
            call(["sch", "prim-delete", "--ids", ",".join(targets[k:k + 25]),
                  "--doc", args.doc, "--project", args.project])
        print("deleted", len(targets))


if __name__ == "__main__":
    main()
