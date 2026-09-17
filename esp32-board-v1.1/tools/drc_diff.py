"""Compare two DRC reports (unconnected items + violations).

    python tools/drc_diff.py <old.json> [new.json]
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def items(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for u in d.get("unconnected_items", []):
        out.append(tuple(sorted(i.get("description", "") for i in u["items"])))
    return out, d


def nets_of(desc):
    out = set()
    for s in desc:
        m = re.search(r"\[([^\]]+)\]", s)
        if m:
            out.add(m.group(1))
        z = re.search(r"Zone '([^']+)'", s)
        if z:
            out.add(z.group(1))
    return out


def main():
    old = sys.argv[1]
    new = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "drc.json")
    a, da = items(old)
    b, db = items(new)
    print(f"violations {len(da['violations'])} -> {len(db['violations'])}")
    print(f"unconnected {len(a)} -> {len(b)}")
    ca, cb = collections.Counter(da["violations"] and
                                 [v["type"] for v in da["violations"]] or []), \
        collections.Counter(v["type"] for v in db["violations"])
    if ca != cb:
        print("  violation types", dict(ca), "->", dict(cb))
    sa, sb = set(a), set(b)
    print("--- fixed")
    for x in sorted(sa - sb):
        print("   ", x)
    print("--- new")
    for x in sorted(sb - sa):
        print("   ", x)
    c = collections.Counter()
    for it in b:
        for n in nets_of(it):
            c[n] += 1
    print("--- remaining unconnected per net")
    for k, v in c.most_common():
        print(f"    {v:3d}  {k}")


if __name__ == "__main__":
    main()
