"""Classify every mis-netted pin on a page by the physical cause.

    python tools/sch_diagnose.py                # both pages
    python tools/sch_diagnose.py --page P1

For each pin whose live net differs from the authoritative table it prints:
  cause = marker-on-pin      a foreign flag bbox covers the pin
          marker-on-stub     the pin's stub ends on a foreign flag
          stub-into-pin      the stub runs through another part's pin
          no-wire            the pin itself carries the wrong net with no stub
Writes work/audit/diag.json with the full geometry for planning.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
AUDIT = os.path.join(ROOT, "work", "audit")


def load_full(page):
    with open(os.path.join(AUDIT, f"{page.lower()}-full.json"),
              encoding="utf-8") as fh:
        txt = fh.read()
    return json.loads(txt[txt.find("{"):])["result"]


def in_bbox(x, y, bb, eps=1.0):
    return (bb.get("minX") is not None and
            bb["minX"] - eps <= x <= bb["maxX"] + eps and
            bb["minY"] - eps <= y <= bb["maxY"] + eps)


def on_segment(px, py, w, eps=1.0):
    x1, y1, x2, y2 = w["x0"], w["y0"], w["x1"], w["y1"]
    if abs(x1 - x2) <= eps and abs(px - x1) <= eps:
        return min(y1, y2) - eps <= py <= max(y1, y2) + eps
    if abs(y1 - y2) <= eps and abs(py - y1) <= eps:
        return min(x1, x2) - eps <= px <= max(x1, x2) + eps
    return False


def diagnose(page, wrong, extra):
    full = load_full(page)
    comps = full["components"]
    wires = full.get("wires") or []
    parts = [c for c in comps if c.get("componentType") == "part"]
    flags = [c for c in comps
             if c.get("componentType") in ("netflag", "netport")]
    pin_at = {}
    for c in parts:
        for p in c.get("pins") or []:
            pin_at[(p["x"], p["y"])] = f"{c['designator']}.{p['pinNumber']}"
    out = []
    for item in wrong + extra:
        key = item["pin"]
        ref, num = key.split(".", 1)
        comp = next((c for c in parts if c.get("designator") == ref), None)
        pin = next((p for p in (comp or {}).get("pins") or []
                    if p["pinNumber"] == num), None)
        if not pin:
            out.append({"pin": key, "cause": "pin-not-found"})
            continue
        px, py = pin["x"], pin["y"]
        touching = [w for w in wires if on_segment(px, py, w)
                    or (abs(w["x0"] - px) < 1 and abs(w["y0"] - py) < 1)
                    or (abs(w["x1"] - px) < 1 and abs(w["y1"] - py) < 1)]
        on_pin = [f for f in flags if in_bbox(px, py, f.get("bbox") or {})]
        ends = []
        for w in touching:
            for (ex, ey) in ((w["x0"], w["y0"]), (w["x1"], w["y1"])):
                if abs(ex - px) < 1 and abs(ey - py) < 1:
                    continue
                ends.append((ex, ey))
        end_flags = [f for f in flags
                     if any(abs(f["x"] - ex) <= 1 and abs(f["y"] - ey) <= 1
                            or in_bbox(ex, ey, f.get("bbox") or {})
                            for ex, ey in ends)]
        cause = "no-wire"
        if on_pin:
            cause = "marker-on-pin"
        elif end_flags:
            cause = "marker-on-stub"
        elif touching:
            cause = "stub-no-marker"
        out.append({
            "pin": key, "want": item.get("want"), "live": item.get("live"),
            "cause": cause, "x": px, "y": py,
            "wires": [{"id": w["primitiveId"], "x0": w["x0"], "y0": w["y0"],
                       "x1": w["x1"], "y1": w["y1"]} for w in touching],
            "on_pin_flags": [{"id": f["primitiveId"], "name": f.get("name"),
                              "x": f["x"], "y": f["y"], "bbox": f.get("bbox")}
                             for f in on_pin],
            "end_flags": [{"id": f["primitiveId"], "name": f.get("name"),
                           "x": f["x"], "y": f["y"], "bbox": f.get("bbox")}
                          for f in end_flags],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=None)
    args = ap.parse_args()
    audit = json.load(open(os.path.join(AUDIT, "audit.json"),
                           encoding="utf-8"))["pages"]
    diag = {}
    for page, r in audit.items():
        if args.page and page != args.page:
            continue
        rows = diagnose(page, r["wrong"], r["extra"])
        diag[page] = rows
        tally = {}
        for row in rows:
            tally[row["cause"]] = tally.get(row["cause"], 0) + 1
        print(f"== {page}: {len(rows)} mis-netted pins ==")
        print("  causes:", tally)
        for row in rows:
            det = (row["on_pin_flags"] or row["end_flags"])
            desc = ", ".join(f"{d['name']}@{d['x']},{d['y']}" for d in det[:3])
            print(f"  {row['pin']:<12} want {str(row.get('want')):<12} "
                  f"live {str(row.get('live')):<12} {row['cause']:<16} {desc}")
    with open(os.path.join(AUDIT, "diag.json"), "w", encoding="utf-8") as fh:
        json.dump(diag, fh, ensure_ascii=False, indent=1)
    print("wrote work/audit/diag.json")


if __name__ == "__main__":
    main()
