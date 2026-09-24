"""Second-pass width polish: bump every track of a plan up to the widest ladder
width the *exact* clearance oracle still accepts, then let verify_plan confirm."""

import argparse
import json
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import clearance  # noqa: E402

LADDER = [31.5, 28.0, 25.0, 22.0, 20.0, 18.0, 16.0, 14.0, 12.0, 10.0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("out")
    ap.add_argument("--net", default=None)
    ap.add_argument("--margin", type=float, default=1.0)
    args = ap.parse_args()

    with open(args.plan, encoding="utf-8") as fh:
        plan = json.load(fh)
    net = args.net or plan["net"]
    oracle = clearance.Oracle(net=net)

    bumped = 0
    for t in plan["tracks"]:
        cur = t["width"]
        best = cur
        for w in LADDER:
            if w <= cur:
                break
            m, _ = oracle.seg_margin(t["x1"], t["y1"], t["x2"], t["y2"],
                                     w, t["layer"])
            if m >= args.margin:
                best = w
                break
        if best > cur:
            t["width"] = best
            bumped += 1
    print(f"bumped {bumped}/{len(plan['tracks'])} segments")
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
