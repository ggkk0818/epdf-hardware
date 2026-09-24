"""Summarise a saved DRC JSON: counts, and designators for keep-out violations."""

import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    path = sys.argv[1]
    t = open(path, encoding="utf-8").read()
    i = t.find("{")
    d, _ = json.JSONDecoder().raw_decode(t[i:])
    r = d.get("result", d)
    print("passed", r.get("passed"), "total", r.get("total"))
    print(json.dumps(r.get("counts"), ensure_ascii=False))
    v = r.get("violations") or []
    print(Counter(x.get("objType") for x in v).most_common(8))

    ids_path = os.path.join(ROOT, "design", "pcb-ids.json")
    rev = {}
    if os.path.exists(ids_path):
        rev = {v["primitiveId"]: k
               for k, v in json.load(open(ids_path, encoding="utf-8")).items()}
    for x in v:
        if x.get("objType") == "Device to Prohibited Region":
            objs = x.get("objs") or []
            print("  keepout:", " ".join(rev.get(o, o) for o in objs),
                  (x.get("x"), x.get("y")), x.get("message"))


if __name__ == "__main__":
    main()
