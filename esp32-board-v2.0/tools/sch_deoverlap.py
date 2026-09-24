"""Re-place only the markers that `sch check` reports as visually overlapping.

    python tools/sch_deoverlap.py --page P1            # plan files only

Writes work/deoverlap-<page>-jobs.json (pins to re-connect) and
work/deoverlap-<page>-del.json (the exact wire+marker ids to delete first).
Only markers sitting on a simple two-point stub out of a part pin are touched;
anything else is skipped and named.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402
import sch_place  # noqa: E402
import sch_reconnect  # noqa: E402

ROOT = geom.ROOT
AUDIT = os.path.join(ROOT, "work", "audit")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True)
    ap.add_argument("--max", type=int, default=0)
    args = ap.parse_args()

    page = sch_place.Page(args.page)
    check = sch_place.jload(os.path.join(AUDIT, f"{args.page.lower()}-check.json"))
    markers = {}
    for f in (check["result"]["findings"] or []):
        if f.get("type") != "marker-overlap":
            continue
        if f.get("componentType") in ("netflag", "netport"):
            markers[f["primitiveId"]] = f.get("net") or ""
        other = f.get("other") or {}
        if other.get("componentType") in ("netflag", "netport"):
            markers[other["primitiveId"]] = other.get("net") or ""

    by_id = {c["primitiveId"]: c for c in page.flags}
    pins_at = {(p["x"], p["y"]): p for p in page.pins}
    wires_by_point = {}
    for w in page.wires:
        wires_by_point.setdefault((w["x0"], w["y0"]), []).append(w)
        wires_by_point.setdefault((w["x1"], w["y1"]), []).append(w)

    jobs, job_dels, skipped = {}, {}, []
    for fid, net in sorted(markers.items()):
        flag = by_id.get(fid)
        if not flag:
            skipped.append((fid, "marker not on page"))
            continue
        net = flag.get("name") or net
        anchor = (flag["x"], flag["y"])
        stub = None
        for w in wires_by_point.get(anchor, []):
            span = abs(w["x1"] - w["x0"]) + abs(w["y1"] - w["y0"])
            if span > 260:
                continue
            other_end = ((w["x1"], w["y1"]) if (w["x0"], w["y0"]) == anchor
                         else (w["x0"], w["y0"]))
            if other_end in pins_at:
                stub = (w, pins_at[other_end])
                break
        if not stub:
            skipped.append((fid, "not a simple pin stub"))
            continue
        w, pin = stub
        key = f"{pin['ref']}.{pin['num']}"
        want = net or None
        if not want:
            skipped.append((fid, "marker has no net name"))
            continue
        if want != pin.get("net"):
            skipped.append((fid, f"pin {key} live net {pin.get('net')} != {want}"))
            continue
        jobs[key] = {"pin": key.replace(".", ":"), "net": want}
        job_dels[key] = {w["primitiveId"], fid}

    ordered = sorted(jobs.values(), key=lambda j: j["pin"])
    if args.max:
        ordered = ordered[:args.max]
    keep = {j["pin"].replace(":", ".") for j in ordered}
    dels = set()
    for key in keep:
        dels |= job_dels[key]
    print(f"{args.page}: {len(markers)} overlapping markers -> "
          f"{len(ordered)} re-connectable pins, {len(skipped)} skipped")
    for fid, why in skipped:
        print(f"   skip {fid}: {why}")
    jpath = os.path.join(ROOT, "work", f"deoverlap-{args.page}-jobs.json")
    dpath = os.path.join(ROOT, "work", f"deoverlap-{args.page}-del.json")
    json.dump(ordered, open(jpath, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    json.dump({"wires": sorted(dels)}, open(dpath, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("  jobs ->", jpath)
    print("  delete ->", dpath, len(dels), "ids")


if __name__ == "__main__":
    main()
