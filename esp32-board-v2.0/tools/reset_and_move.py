"""Delete the stubs of given pins and translate given parts (with stub cleanup)."""

import argparse
import json
import subprocess
import sys

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


def call(args):
    res = subprocess.run([EASYEDA] + args, capture_output=True, text=True, encoding="utf-8")
    out = res.stdout
    i = out.find("{")
    if i < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(out[i:])
    except Exception:
        return None
    return data


def snapshot(doc, project):
    d = call(["sch", "list", "--page", doc, "--include-pins", "--include-wires",
              "--project", project])
    r = (d or {}).get("result", {})
    coords, parts = {}, {}
    for c in r.get("components", []):
        if c.get("componentType") != "part":
            continue
        parts[c.get("designator")] = c
        for p in c.get("pins") or []:
            coords["{}:{}".format(c.get("designator"), p.get("pinNumber"))] = (
                p.get("x"), p.get("y"))
    return r.get("wires") or [], coords, parts


def delete_stubs(pins, doc, project):
    wires, coords, _ = snapshot(doc, project)
    ids = set()
    for pin in pins:
        xy = coords.get(pin)
        for w in wires:
            if (w["x0"], w["y0"]) == xy or (w["x1"], w["y1"]) == xy:
                ids.add(w["primitiveId"])
    ids = sorted(ids)
    if ids:
        call(["sch", "prim-delete", "--ids", ",".join(ids), "--doc", doc, "--project", project])
    print("deleted stubs:", len(ids), "for", len(pins), "pins")
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--pins", default="")
    ap.add_argument("--moves", default="[]",
                    help='JSON [{"ref":"C12","pins":["C12:1","C12:2"],"dx":90,"dy":0}]')
    args = ap.parse_args()

    pins = [p for p in args.pins.split(",") if p]
    moves = json.loads(args.moves)

    for mv in moves:
        pins.extend(mv["pins"])
    pins = sorted(set(pins))
    delete_stubs(pins, args.doc, args.project)

    for mv in moves:
        _, _, parts = snapshot(args.doc, args.project)
        comp = parts.get(mv["ref"])
        if not comp:
            print("MISSING PART", mv["ref"])
            continue
        nx = comp.get("x") + mv.get("dx", 0)
        ny = comp.get("y") + mv.get("dy", 0)
        res = call(["sch", "modify", "--id", comp["primitiveId"], "--x", str(nx),
                    "--y", str(ny), "--doc", args.doc, "--project", args.project])
        print("move", mv["ref"], "->", (nx, ny), "ok" if (res and res.get("ok")) else "FAILED")


if __name__ == "__main__":
    main()
