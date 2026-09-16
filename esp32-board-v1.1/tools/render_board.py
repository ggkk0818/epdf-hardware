"""Render the routing model (pads / nets / keepouts / tracks) to PNG.

    python tools/render_board.py --scale 24 --out routing/view_all.png
    python tools/render_board.py --region 8,30,32,50 --scale 60 --out routing/view_pwr.png

Runs with either interpreter (numpy + PIL only).
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "routing" / "model.json"

HALF_W, HALF_H = 55.0 / 2, 84.0 / 2


def net_color(net: str):
    if net in ("", None):
        return (140, 140, 140)
    h = 0
    for ch in net:
        h = (h * 131 + ord(ch)) % 100000
    hue = (h % 997) / 997.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
    return (int(r * 255), int(g * 255), int(b * 255))


class View:
    def __init__(self, region, scale, flip_y=False):
        x0, y0, x1, y1 = region
        self.x0, self.y0, self.scale = x0, y0, scale
        self.w = int(round((x1 - x0) * scale))
        self.h = int(round((y1 - y0) * scale))
        self.ox = (x0 + x1) / 2.0
        self.oy = (y0 + y1) / 2.0
        self.flip_y = flip_y

    def px(self, x, y):
        sx = self.w / 2 + (x - self.ox) * self.scale
        sy = self.h / 2 + (y - self.oy) * self.scale * (-1 if self.flip_y else 1)
        return sx, sy

    def rect(self, x0, y0, x1, y1):
        a = self.px(x0, y0)
        b = self.px(x1, y1)
        return [min(a[0], b[0]), min(a[1], b[1]),
                max(a[0], b[0]), max(a[1], b[1])]


def rot_rect(cx, cy, w, h, rot_deg):
    a = math.radians(rot_deg)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return pts


def build(model, args):
    region = args.region or (0.0, 0.0, 55.0, 84.0)
    view = View(region, args.scale, flip_y=args.flip_y)
    img = Image.new("RGB", (view.w, view.h), (16, 16, 20) if args.dark else (250, 250, 248))
    dr = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("arial.ttf", max(9, int(args.scale * 0.55)))
        small = ImageFont.truetype("arial.ttf", max(7, int(args.scale * 0.38)))
    except OSError:
        font = ImageFont.load_default()
        small = font

    # board outline
    if model["board"]["outline"]:
        pts = [view.px(x, y) for x, y in model["board"]["outline"]]
        dr.polygon(pts, outline=(90, 200, 90), width=2)

    # keepout areas
    for ko in model["keepouts"]:
        if ko["polygon"]:
            pts = [view.px(x, y) for x, y in ko["polygon"]]
            dr.polygon(pts, outline=(200, 60, 60), fill=(200, 60, 60, 40))
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            if args.labels:
                dr.text((cx, cy), ko["name"], fill=(220, 90, 90), font=small, anchor="mm")

    # courtyard outlines
    for fp in model["footprints"]:
        for ring in fp["courtyard"]:
            pts = [view.px(x, y) for x, y in ring]
            dr.polygon(pts, outline=(120, 120, 130, 160))

    # tracks / vias if present
    routing = None
    if args.routing:
        routing = json.loads(Path(args.routing).read_text(encoding="utf-8"))
    layers_shown = set(args.layers.split(",")) if args.layers else None
    track_list = list(model.get("tracks", []))
    via_list = list(model.get("vias", []))
    if routing:
        track_list += routing.get("segments", [])
        via_list += [v for v in routing.get("vias", []) if v.get("dia")]
    for tr in track_list:
        if layers_shown and tr["layer"] not in layers_shown:
            continue
        col = {"F.Cu": (200, 40, 40), "In2.Cu": (230, 220, 60), "B.Cu": (60, 120, 240),
               "In1.Cu": (60, 200, 160)}.get(tr["layer"], (255, 0, 255))
        if args.by_net:
            col = net_color(tr["net"])
        a = view.px(*tr["start"])
        b = view.px(*tr["end"])
        w = max(1, int(tr["width"] * view.scale))
        dr.line([a, b], fill=col + (220,), width=w)
    for v in via_list:
        a = view.px(v["x"], v["y"])
        r = max(1.5, v["dia"] * view.scale / 2)
        dr.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r],
                   fill=(255, 255, 255), outline=(30, 30, 30))

    # pads
    for pad in model["pads"]:
        x, y = pad["x"], pad["y"]
        if not (region[0] - 1 <= x <= region[2] + 1 and region[1] - 1 <= y <= region[3] + 1):
            continue
        col = net_color(pad["net"])
        pts = rot_rect(x, y, pad["w"], pad["h"], pad["rot"])
        ppts = [view.px(px, py) for px, py in pts]
        dr.polygon(ppts, fill=col, outline=(20, 20, 20))
        if pad["drill"]:
            a = view.px(x, y)
            r = max(1.0, pad["drill"] * view.scale / 2)
            dr.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r],
                       fill=(16, 16, 20) if args.dark else (250, 250, 248))

    if args.labels:
        for fp in model["footprints"]:
            if not (region[0] - 3 <= fp["x"] <= region[2] + 3
                    and region[1] - 3 <= fp["y"] <= region[3] + 3):
                continue
            a = view.px(fp["x"], fp["y"])
            dr.text(a, fp["ref"], fill=(20, 20, 20) if not args.dark else (240, 240, 240),
                    font=font, anchor="mm", stroke_width=3,
                    stroke_fill=(250, 250, 248) if not args.dark else (16, 16, 20))
        if args.pad_numbers:
            for pad in model["pads"]:
                a = view.px(pad["x"], pad["y"])
                if 0 <= a[0] < view.w and 0 <= a[1] < view.h:
                    dr.text(a, str(pad["num"]), fill=(10, 10, 10), font=small,
                            anchor="mm", stroke_width=2, stroke_fill=(250, 250, 248))

    # coordinate ruler every 5 mm
    step = 5
    for gx in range(0, 56, step):
        a = view.px(gx, region[1])
        b = view.px(gx, region[3])
        dr.line([a, b], fill=(150, 150, 150, 70))
        dr.text((a[0] + 2, 2), str(gx), fill=(120, 120, 120), font=small)
    for gy in range(0, 85, step):
        a = view.px(region[0], gy)
        b = view.px(region[2], gy)
        dr.line([a, b], fill=(150, 150, 150, 70))
        dr.text((2, a[1] + 1), str(gy), fill=(120, 120, 120), font=small)

    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(MODEL))
    ap.add_argument("--region", help="x0,y0,x1,y1 in mm")
    ap.add_argument("--scale", type=float, default=24.0, help="pixels per mm")
    ap.add_argument("--out", default=str(ROOT / "routing" / "view.png"))
    ap.add_argument("--no-labels", dest="labels", action="store_false")
    ap.add_argument("--pad-numbers", action="store_true")
    ap.add_argument("--flip-y", action="store_true")
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--routing", help="routing.json overlay")
    ap.add_argument("--layers", help="comma separated layers to draw")
    ap.add_argument("--by-net", action="store_true", help="colour tracks by net")
    args = ap.parse_args()
    if args.region:
        args.region = tuple(float(v) for v in args.region.split(","))
    model = json.loads(Path(args.model).read_text(encoding="utf-8"))
    img = build(model, args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    print("wrote", args.out, img.size)


if __name__ == "__main__":
    sys.exit(main())
