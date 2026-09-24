"""Build a connection work-list from the live `sch check` floating pins."""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"

# pins that are intentionally not connected (get NC markers instead)
NC = {"J1:A8", "J1:B8", "J4:3", "J4:4", "J5:3", "J5:4", "U2:2", "U2:3", "U2:12",
      "U3:6", "U5:9", "U6:4", "U6:5"}


def main():
    doc, project, spec_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    res = subprocess.run([EASYEDA, "sch", "check", "--doc", doc, "--project", project,
                          "--json"], capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    data, _ = json.JSONDecoder().raw_decode(out[i:])
    r = data.get("result", data)

    with open(spec_path, encoding="utf-8") as fh:
        spec = {c["pin"]: c for c in json.load(fh)["connections"]}

    items, nc_hits = [], []
    for f in r.get("findings") or []:
        if f.get("type") != "floating-pin":
            continue
        ref = f.get("designator")
        for p in f.get("pins") or []:
            key = "{}:{}".format(ref, p)
            if key in NC:
                nc_hits.append(key)
                continue
            c = spec.get(key)
            if not c:
                print("  not in spec:", key)
                continue
            items.append({
                "pin": key, "net": c["net"],
                "kind": "ground" if c["net"] == "GND" else "power",
                "directions": ["right", "left", "up", "down"],
            })

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=1)
    print("{}: floating={} to-connect={} nc={}".format(
        doc, len(items) + len(nc_hits), len(items), len(nc_hits)))
    for it in items:
        print("   connect", it["pin"], it["net"])
    print("   NC", sorted(nc_hits))


if __name__ == "__main__":
    main()
