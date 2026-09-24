"""Print the wire primitive id(s) attached to a pin's coordinate."""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def main():
    doc = sys.argv[1]
    project = sys.argv[2]
    pins = [p for p in sys.argv[3].split(",") if p]

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
            coords[f"{c['designator']}:{p.get('pinNumber')}"] = (p.get("x"), p.get("y"))

    wires = r.get("wires") or []
    out = {}
    for pin in pins:
        xy = coords.get(pin)
        hits = [w for w in wires
                if (w["x0"], w["y0"]) == xy or (w["x1"], w["y1"]) == xy]
        out[pin] = {
            "at": xy,
            "wires": [{"id": w["primitiveId"], "seg": [[w["x0"], w["y0"]], [w["x1"], w["y1"]]],
                       "net": w["net"]} for w in hits],
        }
        print(pin, xy, [h["id"] for h in out[pin]["wires"]])
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "design", "stub-ids.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
