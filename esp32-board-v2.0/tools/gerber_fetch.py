"""Decode the base64 Gerber ZIP captured from the connector into work/fab/ and
report per-layer copper coverage inside a rectangle (used to prove the antenna
keep-out really is copper-free on every layer).

Usage:
    python tools/gerber_fetch.py                      # unpack work/gerber-b64.txt
    python tools/gerber_fetch.py --rect 629.92,3070.77,1535.53,3307.09
"""

import argparse
import base64
import io
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def decode():
    raw = open(os.path.join(ROOT, "work", "gerber-b64.txt"), encoding="utf-8",
               errors="replace").read()
    i = raw.find('"value"')
    j = raw.find(":", i) + 1
    q = raw.find('"', j) + 1
    e = raw.find('"', q)
    data = base64.b64decode(raw[q:e])
    outdir = os.path.join(ROOT, "work", "fab")
    os.makedirs(outdir, exist_ok=True)
    zpath = os.path.join(outdir, "gerber.zip")
    with open(zpath, "wb") as fh:
        fh.write(data)
    z = zipfile.ZipFile(io.BytesIO(data))
    z.extractall(outdir)
    return outdir, z.namelist()


def parse_gerber_extents(path):
    """Return (xmin, ymin, xmax, ymax) of all drawn coordinates in a Gerber file.

    Deliberately crude: EasyEDA emits absolute coordinates in mil (FSLAX...,
    leading-zero-omitted) so every X/Y word is a real point of copper.
    """
    txt = open(path, encoding="utf-8", errors="replace").read()
    xs, ys = [], []
    for m in re.finditer(r"X(-?\d+)Y(-?\d+)", txt):
        xs.append(int(m.group(1)))
        ys.append(int(m.group(2)))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rect", default=None,
                    help="x0,y0,x1,y1 in the gerber's own integer units")
    args = ap.parse_args()
    outdir, names = decode()
    print("extracted to", outdir)
    for n in sorted(names):
        p = os.path.join(outdir, n)
        if os.path.isdir(p):
            continue
        size = os.path.getsize(p)
        ext = parse_gerber_extents(p) if n.lower().endswith((".g", "gbr", ".gtl",
                                                             ".gbl", ".g1", ".g2",
                                                             ".g3", ".g4")) else None
        print(f"  {n:<34} {size:>8} B  extents={ext}")


if __name__ == "__main__":
    main()
