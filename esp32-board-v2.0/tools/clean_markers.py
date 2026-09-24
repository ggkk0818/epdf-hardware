"""Delete the duplicate/redundant net markers that `sch check` suggests."""

import json
import os
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def main():
    check_path, doc, project = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(check_path, encoding="utf-8") as fh:
        txt = fh.read()
    i = txt.find("{")
    data, _ = json.JSONDecoder().raw_decode(txt[i:])
    r = data.get("result", data)

    ids = []
    for f in r.get("findings") or []:
        if f.get("type") in ("duplicate-net-marker", "redundant-net-marker"):
            ids.extend(f.get("suggestDeleteIds") or [])
    ids = sorted(set(ids))
    print("markers to delete:", len(ids))
    for k in range(0, len(ids), 25):
        chunk = ids[k:k + 25]
        res = subprocess.run(
            [EASYEDA, "sch", "prim-delete", "--ids", ",".join(chunk),
             "--doc", doc, "--project", project],
            capture_output=True, text=True, encoding="utf-8")
        ok = '"ok": true' in res.stdout
        print(f"  chunk {k//25 + 1}: {'ok' if ok else 'FAILED'}")


if __name__ == "__main__":
    main()
