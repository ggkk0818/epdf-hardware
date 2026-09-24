"""Report how many target pins currently have a wire attached at the pin point."""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def main():
    doc, project, spec_path = sys.argv[1], sys.argv[2], sys.argv[3]
    res = subprocess.run(
        [EASYEDA, "sch", "list", "--page", doc, "--include-pins", "--include-wires",
         "--project", project],
        capture_output=True, text=True, encoding="utf-8")
    r = json.loads(res.stdout)["result"]

    coords = {}
    for c in r["components"]:
        if c.get("componentType") != "part":
            continue
        for p in c.get("pins") or []:
            coords["{}:{}".format(c["designator"], p.get("pinNumber"))] = (p.get("x"), p.get("y"))

    wires = r.get("wires") or []
    ends = set()
    for w in wires:
        ends.add((w["x0"], w["y0"]))
        ends.add((w["x1"], w["y1"]))

    with open(spec_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    targets = {c["pin"]: c["net"] for c in spec["connections"]}

    attached = [p for p in targets if coords.get(p) in ends]
    missing = [p for p in targets if coords.get(p) not in ends]
    print("{}: {} target pins, {} have a wire at the pin point, {} do not".format(
        doc, len(targets), len(attached), len(missing)))
    print("wires on page:", len(wires))
    for m in missing[:25]:
        print("   no stub:", m, targets[m], coords.get(m))


if __name__ == "__main__":
    main()
