"""Delete duplicated vias (exact same position / net / size).

    python tools/dedupe_vias.py [--dry-run] [--tol 0.001]

`pcb via-stitch` (and any repeated via action) can land the same via twice;
the DRC then reports one `Hole to Hole` Clearance Error per pair even though
there is no real geometry problem. This removes the surplus copies and
verifies the count afterwards. Connectivity is unchanged because the kept
via sits exactly on top of the deleted one.
"""

import argparse
import collections
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402


def key(v, tol):
    q = 1.0 / tol
    return (round(v["x"] * q) / q, round(v["y"] * q) / q,
            v.get("net"), v.get("diameter"), v.get("holeDiameter"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tol", type=float, default=0.001)
    args = ap.parse_args()

    v = geom.call(["pcb", "via-list", "--doc", geom.DOC])
    vias = ((v or {}).get("result") or {}).get("vias") or []
    groups = collections.defaultdict(list)
    for x in vias:
        groups[key(x, args.tol)].append(x["primitiveId"])
    victims = [ids[1:] for ids in groups.values() if len(ids) > 1]
    todo = [i for sub in victims for i in sub]

    print(f"vias on board: {len(vias)}; duplicate groups: {len(victims)}; "
          f"surplus vias: {len(todo)}")
    if not todo:
        return
    if args.dry_run:
        for i in todo:
            print("  would delete", i)
        return

    ok = bad = 0
    for i in range(0, len(todo), 20):
        chunk = todo[i:i + 20]
        r = geom.call(["pcb", "via-delete", "--ids", ",".join(chunk),
                       "--doc", geom.DOC])
        if r and r.get("ok"):
            ok += len(chunk)
        else:
            bad += len(chunk)
            print("   ! batch failed:", (r or {}).get("error"))
        geom.call(["pcb", "save", "--doc", geom.DOC])
        time.sleep(0.4)
    print(f"deleted ok {ok}, fail {bad}")

    geom.call(["pcb", "save", "--doc", geom.DOC])
    geom.call(["doc", "reload", geom.DOC])
    v2 = geom.call(["pcb", "via-list", "--doc", geom.DOC])
    n2 = len(((v2 or {}).get("result") or {}).get("vias") or [])
    print(f"vias after: {n2} (expected {len(vias) - ok})")


if __name__ == "__main__":
    main()
