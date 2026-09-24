"""Print the live DRC rule values that routing must respect."""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

KEY = ("clearance", "spacing", "width", "track", "pad", "via", "copper",
       "thickness", "plane", "hole", "edge")


def walk(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                walk(v, f"{path}/{k}")
            elif isinstance(v, (int, float, str)) and any(
                    s in k.lower() for s in KEY):
                print(f"{path}/{k} = {v}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]")


def main():
    r = subprocess.run([geom.EASYEDA, "pcb", "drc-rules", "--doc", "PCB1",
                        "--project", geom.PROJECT], capture_output=True,
                       text=True, encoding="utf-8")
    t = r.stdout
    i = t.find("{")
    d = json.loads(t[i:])
    rules = d.get("result", d)["rules"]
    print("groups:", list(rules.keys()))
    rows = []

    def collect(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    collect(v, f"{path}/{k}")
                else:
                    rows.append((f"{path}/{k}", v))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                collect(v, f"{path}[{i}]")

    collect(rules.get("config") or rules)
    print("leaf count:", len(rows))
    for path, value in rows:
        if any(s in path for s in ("Spacing", "Clearance", "Track", "Pad",
                                   "Via", "Edge", "Thickness", "Line", "Width")):
            print(f"{path:<74} {value}")


if __name__ == "__main__":
    main()
