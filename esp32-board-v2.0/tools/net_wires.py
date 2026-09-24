"""Map given wire primitive ids to the pins at their endpoints."""

import json
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def main():
    doc, project = sys.argv[1], sys.argv[2]
    ids = set(x for x in sys.argv[3].split(",") if x)

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
            key = "{}:{}".format(c.get("designator"), p.get("pinNumber"))
            coords[(p.get("x"), p.get("y"))] = key

    for w in r.get("wires") or []:
        if w["primitiveId"] not in ids:
            continue
        a = (w["x0"], w["y0"])
        b = (w["x1"], w["y1"])
        print(w["primitiveId"], "net=", repr(w.get("net")), a, "->", b,
              "| pins:", coords.get(a), coords.get(b))


if __name__ == "__main__":
    main()
