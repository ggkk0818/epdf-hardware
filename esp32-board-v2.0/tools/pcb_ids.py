"""Print / save designator -> PCB primitiveId (+ bbox) for the active board."""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    doc, project = sys.argv[1], sys.argv[2]
    res = subprocess.run(
        [EASYEDA, "pcb", "list", "--doc", doc, "--project", project,
         "--include-bbox", "--include-pads"],
        capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    d, _ = json.JSONDecoder().raw_decode(out[i:])
    comps = d["result"]["components"]

    table = {}
    for c in comps:
        ref = c.get("designator")
        table[ref] = {
            "primitiveId": c.get("primitiveId"),
            "x": c.get("x"), "y": c.get("y"),
            "rotation": c.get("rotation"),
            "bbox": c.get("bbox"),
            "pins": len(c.get("pads") or []),
        }
    with open(os.path.join(ROOT, "design", "pcb-ids.json"), "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=1)
    print("components:", len(table))
    for ref in sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else []:
        print(ref, table.get(ref))


if __name__ == "__main__":
    main()
