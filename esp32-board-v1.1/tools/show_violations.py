"""Print the DRC violations (type, description and the items involved).

    python tools/show_violations.py [drc.json] [type]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "drc.json")
    only = sys.argv[2] if len(sys.argv) > 2 else None
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    for v in d["violations"]:
        if only and v["type"] != only:
            continue
        print(f"{v['type']:<18s} {v['description']}")
        for i in v["items"]:
            print(f"      {i.get('description')}  {i.get('pos')}")


if __name__ == "__main__":
    main()
