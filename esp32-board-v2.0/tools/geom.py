"""Shared geometry helpers: dump live copper, build an obstacle model."""

import json
import math
import os
import subprocess
import time

EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = "esp32s3-board-v2.0"
DOC = "PCB1"


def call(args, tries=4):
    for k in range(tries):
        r = subprocess.run([EASYEDA] + args + ["--project", PROJECT],
                           capture_output=True, text=True, encoding="utf-8")
        out = r.stdout
        i = out.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(out[i:])[0]
            except Exception:
                pass
        time.sleep(1.0 + k)
    return None


def dump(path=None):
    t = call(["pcb", "track-list", "--doc", DOC])
    v = call(["pcb", "via-list", "--doc", DOC])
    d = call(["pcb", "dump", "--label", "live", "--no-silk", "--no-rules", "--no-layers"])
    data = {
        "tracks": (t or {}).get("result", {}).get("lines", []),
        "vias": (v or {}).get("result", {}).get("vias", []),
        "components": (d or {}).get("components", []),
        "outline": (d or {}).get("outline"),
    }
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
    return data


def load(path=None):
    path = path or os.path.join(ROOT, "work", "geom.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def seg_len_mil(t):
    return math.hypot(t["endX"] - t["startX"], t["endY"] - t["startY"])


def seg_len_mm(t):
    return seg_len_mil(t) / 1000.0 * 25.4


def point_box_dist(px, py, t):
    """Distance from a point to a segment."""
    x1, y1, x2, y2 = t["startX"], t["startY"], t["endX"], t["endY"]
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    u = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + u * dx), py - (y1 + u * dy))


def pad_radius(pad):
    """Conservative half-extent of a pad in mil."""
    return max(pad.get("width", 0), pad.get("height", 0)) / 2.0


def iter_pads(components):
    for c in components:
        for p in c.get("pads") or []:
            yield c, p
