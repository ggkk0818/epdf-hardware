"""Verify-driven repair of mis-netted pins.

For each target pin: try candidate (direction, offset) lead-outs; after every attempt
re-read the whole page and accept the attempt only when the pin lands on its target net
AND no other pin's net regressed. Rejected attempts are rolled back by deleting the
stub wire that was just created (found by its pin endpoint).
"""

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


class Page:
    def __init__(self, doc, project):
        self.doc = doc
        self.project = project
        self.pins = {}
        self.coords = {}
        self.wires = []
        self.refresh()

    def refresh(self):
        d = call(["sch", "list", "--page", self.doc, "--include-pins", "--include-wires",
                  "--project", self.project])
        r = (d or {}).get("result", {})
        self.pins = {}
        self.coords = {}
        for c in r.get("components", []):
            if c.get("componentType") != "part":
                continue
            ref = c.get("designator")
            for p in c.get("pins") or []:
                key = f"{ref}:{p.get('pinNumber')}"
                self.pins[key] = p.get("net") or ""
                self.coords[key] = (p.get("x"), p.get("y"))
        self.wires = r.get("wires") or []

    def stub_at(self, key):
        xy = self.coords.get(key)
        if not xy:
            return []
        return [w["primitiveId"] for w in self.wires
                if (w["x0"], w["y0"]) == xy or (w["x1"], w["y1"]) == xy]

    def delete(self, ids):
        if not ids:
            return
        call(["sch", "prim-delete", "--ids", ",".join(ids), "--doc", self.doc,
              "--project", self.project])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--pins", required=True, help="comma separated pin list")
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    with open(args.target, encoding="utf-8") as fh:
        spec = json.load(fh)
    target = {c["pin"]: c["net"] for c in spec["connections"]}
    kinds = {c["pin"]: c["kind"] for c in spec["connections"]}

    page = Page(args.doc, args.project)
    results = []

    for pin in [p for p in args.pins.split(",") if p]:
        net = target[pin]
        kind = kinds[pin]
        # clear any existing (shorting) stub first
        page.refresh()
        page.delete(page.stub_at(pin))
        page.refresh()
        baseline = dict(page.pins)

        fixed = False
        for direction in ("right", "left", "up", "down"):
            for offset in (45, 60, 90, 120, 180, 240, 330, 450):
                res = call(["sch", "connect", "--pin", pin, "--kind", kind, "--net", net,
                            "--direction", direction, "--offset", str(offset),
                            "--doc", args.doc, "--project", args.project])
                if not (res and res.get("ok")):
                    page.refresh()
                    page.delete(page.stub_at(pin))
                    page.refresh()
                    continue
                page.refresh()
                here = page.pins.get(pin, "")
                regress = [k for k, v in target.items()
                           if page.pins.get(k, "") != v and k != pin]
                if here == net and not regress:
                    results.append({"pin": pin, "net": net, "direction": direction,
                                    "offset": offset, "status": "fixed"})
                    print(f"  FIXED {pin} -> {net} {direction} {offset}", flush=True)
                    fixed = True
                    break
                page.delete(page.stub_at(pin))
                page.refresh()
            if fixed:
                break
        if not fixed:
            results.append({"pin": pin, "net": net, "status": "unresolved"})
            print(f"  UNRESOLVED {pin} -> {net}", flush=True)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print("repair summary:", {r["status"]: sum(1 for x in results if x["status"] == r["status"])
                              for r in results})


if __name__ == "__main__":
    main()
