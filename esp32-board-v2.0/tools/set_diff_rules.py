"""Write the differential-pair DRC rule (trace width / intra-pair gap).

Target 90 ohm differential on the reference stackup
(F.Cu - 0.195 mm prepreg, er 4.2 - In1.Cu, 1 oz copper):

    Z0(microstrip, w=0.2286mm, h=0.195mm, t=0.035mm, er=4.2) ~ 65 ohm
    Zdiff = 2*Z0*(1 - 0.48*exp(-0.96*s/h)) with s = 0.127mm  ~ 91 ohm

Run `pcb drc-rules-set --from <out> --dry-run` first to inspect the patch.
"""

import argparse
import json
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def call(args, tries=3):
    for k in range(tries):
        r = subprocess.run([geom.EASYEDA] + args + ["--project", geom.PROJECT],
                           capture_output=True, text=True, encoding="utf-8")
        out = r.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(1.0 + k)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=float, default=0.2286, help="mm")
    ap.add_argument("--gap", type=float, default=0.127, help="mm")
    ap.add_argument("--out", default="work/diff-rules.json")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    r = call(["pcb", "drc-rules"])
    rules = r["result"]["rules"]
    dp = rules["config"]["Physics"]["Differential Pair"]["differentialPair"]
    form = dp["form"]
    print("before: width", json.dumps(form["strokeWidthTables"]["data"], ensure_ascii=False))
    print("        gap  ", json.dumps(form["diffPairSpacingTables"]["data"], ensure_ascii=False))
    form["strokeWidthTables"]["data"]["1"]["defaultValue"] = args.width
    form["strokeWidthTables"]["data"]["1"]["minValue"] = min(
        form["strokeWidthTables"]["data"]["1"].get("minValue") or args.width, args.width)
    form["diffPairSpacingTables"]["data"]["1"]["defaultValue"] = args.gap
    form["diffPairSpacingTables"]["data"]["1"]["minValue"] = args.gap
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rules, fh, ensure_ascii=False)
    print("after : width", json.dumps(form["strokeWidthTables"]["data"], ensure_ascii=False))
    print("        gap  ", json.dumps(form["diffPairSpacingTables"]["data"], ensure_ascii=False))
    print("wrote", args.out)
    if args.apply:
        res = call(["pcb", "drc-rules-set", "--from", args.out])
        print("apply:", res and res.get("ok"))


if __name__ == "__main__":
    main()
