"""Build lib/esp32-board-v1.1.pretty/X05B20U24T.kicad_mod from vendor data.

Sources (both kept in ``datasheets/``):

* ``X05B20U24T.pdf`` - XKB's own drawing.  The "RECOMMENDED PCB LAYOUT" view
  gives the pad sizes: 0.30 x 1.60 mm signal pads on 0.50 mm pitch and
  2.40 x 3.50 mm mounting pads.
* ``X05B20U24T_easyeda.json`` - LCSC's official CAD data for C437036 (fetched
  with ``easyeda.com/api/products/C437036/components``).  It is the cross-check
  for the *positions*: the signal row spans 11.50 mm (23 x 0.5) and the two
  mounting pads sit 7.40 mm either side of the row centre, 2.35 mm behind it.
  EasyEDA works in 10 mil units (1 unit = 0.254 mm) and its x axis is mirrored
  relative to the drawing, so the conversion flips x - that also puts pin 1 on
  the left, matching the manufacturer's pin-1 dot and the footprint this board
  used before (so the J2 net-to-pad mapping is unchanged).

Run:  python tools/import_xkb_fpc.py
"""

import json
import math
import re
import uuid
from pathlib import Path

ROOT = Path("C:/Code/epdf-hardware/esp32-board-v1.1")
SRC = ROOT / "datasheets" / "X05B20U24T_easyeda.json"
OUT = ROOT / "lib" / "esp32-board-v1.1.pretty" / "X05B20U24T.kicad_mod"

PITCH = 0.5
PAD_W, PAD_L = 0.30, 1.60          # vendor recommended layout
MOUNT_W, MOUNT_L = 2.40, 3.50
N_PINS = 24


def u():
    return str(uuid.uuid4())


def fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def vendor_offsets():
    """Pull the two geometry cross-checks out of the LCSC CAD data."""
    data = json.loads(SRC.read_text(encoding="utf-8"))
    fp = data["result"]["packageDetail"]["dataStr"]
    u_mm = 0.254
    ox, oy = fp["head"]["x"], fp["head"]["y"]
    pins, mounts = [], []
    for shape in fp["shape"]:
        if not shape.startswith("PAD~"):
            continue
        f = shape.split("~")
        num, pts = f[8], [float(v) for v in f[10].split()]
        xs, ys = pts[0::2], pts[1::2]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        # mirror x (EasyEDA is mirrored w.r.t. the drawing), flip y (EasyEDA y
        # grows the other way), then bring to mm
        p = (-(cx - ox) * u_mm, -(cy - oy) * u_mm)
        (pins if num.isdigit() and int(num) <= N_PINS else mounts).append((num, p))
    return pins, mounts


def main():
    pins, mounts = vendor_offsets()
    row_y = sum(p[1] for _, p in pins) / len(pins)
    mount_y = sum(p[1] for _, p in mounts) / len(mounts)
    mount_x = sorted(p[0] for _, p in mounts)
    print(f"vendor pad row y = {row_y:+.3f} mm, mounting y = {mount_y:+.3f} mm, "
          f"mounting x = {mount_x[0]:+.3f} / {mount_x[-1]:+.3f} mm")

    half = (N_PINS - 1) * PITCH / 2.0            # 5.75 mm
    mx = (abs(mount_x[0]) + abs(mount_x[-1])) / 2.0

    body_x = 17.60 / 2.0                          # DIM=A for 24 poles
    lines = []
    lines.append('(footprint "X05B20U24T"')
    lines.append("\t(version 20260206)")
    lines.append('\t(generator "kicad-footprint-generator")')
    lines.append('\t(layer "F.Cu")')
    lines.append('\t(descr "XKB X05B20U24T FFC/FPC connector, 24 pins, 0.5 mm pitch, '
                 'top contact, slide lock, horizontal SMT. Pad sizes from the XKB '
                 'recommended PCB layout, pad positions cross-checked against the LCSC '
                 'CAD data for C437036.")')
    lines.append('\t(tags "FPC FFC connector 0.5mm top contact slide lock")')
    lines.append("\t(attr smd)")
    lines.append(f'\t(property "Reference" "J"')
    lines.append(f"\t\t(at 0 {fmt(-2.6)} 0)")
    lines.append('\t\t(layer "F.SilkS")')
    lines.append("\t\t(uuid \"%s\")" % u())
    lines.append("\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)")
    lines.append("\t)")
    lines.append(f'\t(property "Value" "X05B20U24T"')
    lines.append(f"\t\t(at 0 {fmt(4.0)} 0)")
    lines.append('\t\t(layer "F.Fab")')
    lines.append("\t\t(uuid \"%s\")" % u())
    lines.append("\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)")
    lines.append("\t)")
    lines.append('\t(property "Footprint" ""')
    lines.append("\t\t(at 0 0 0)")
    lines.append('\t\t(layer "F.Fab")')
    lines.append("\t\t(hide yes)")
    lines.append("\t\t(uuid \"%s\")" % u())
    lines.append("\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)")
    lines.append("\t)")
    lines.append('\t(property "Datasheet" "https://item.szlcsc.com/434884.html"')
    lines.append("\t\t(at 0 0 0)")
    lines.append('\t\t(layer "F.Fab")')
    lines.append("\t\t(hide yes)")
    lines.append("\t\t(uuid \"%s\")" % u())
    lines.append("\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)")
    lines.append("\t)")

    # ---- body outline: fabrication layer + a simple silk front edge ----------
    body = (-body_x, mount_y - MOUNT_L / 2 - 0.15, body_x, mount_y + MOUNT_L / 2 + 0.15)
    for a, b in (((body[0], body[1]), (body[2], body[1])),
                 ((body[2], body[1]), (body[2], body[3])),
                 ((body[2], body[3]), (body[0], body[3])),
                 ((body[0], body[3]), (body[0], body[1]))):
        lines.append("\t(fp_line\n"
                     f"\t\t(start {fmt(a[0])} {fmt(a[1])})\n"
                     f"\t\t(end {fmt(b[0])} {fmt(b[1])})\n"
                     "\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type solid)\n\t\t)\n"
                     '\t\t(layer "F.Fab")\n'
                     f'\t\t(uuid "{u()}")\n\t)')
    silk_y = row_y - PAD_L / 2 - 0.25
    lines.append("\t(fp_line\n"
                 f"\t\t(start {fmt(-body_x)} {fmt(silk_y)})\n"
                 f"\t\t(end {fmt(body_x)} {fmt(silk_y)})\n"
                 "\t\t(stroke\n\t\t\t(width 0.12)\n\t\t\t(type solid)\n\t\t)\n"
                 '\t\t(layer "F.SilkS")\n'
                 f'\t\t(uuid "{u()}")\n\t)')
    for sx in (-body_x, body_x):
        lines.append("\t(fp_line\n"
                     f"\t\t(start {fmt(sx)} {fmt(silk_y)})\n"
                     f"\t\t(end {fmt(sx)} {fmt(-PAD_L / 2 + row_y + 0.2)})\n"
                     "\t\t(stroke\n\t\t\t(width 0.12)\n\t\t\t(type solid)\n\t\t)\n"
                     '\t\t(layer "F.SilkS")\n'
                     f'\t\t(uuid "{u()}")\n\t)')
    lines.append("\t(fp_circle\n\t\t(center %s %s)\n\t\t(end %s %s)\n"
                 "\t\t(stroke\n\t\t\t(width 0.12)\n\t\t\t(type solid)\n\t\t)\n"
                 '\t\t(fill no)\n\t\t(layer "F.SilkS")\n'
                 '\t\t(uuid "%s")\n\t)'
                 % (fmt(-half), fmt(silk_y - 0.45), fmt(-half + 0.15), fmt(silk_y - 0.45), u()))

    # ---- courtyard ---------------------------------------------------------
    cy0 = row_y - PAD_L / 2 - 0.25
    cy1 = mount_y + MOUNT_L / 2 + 0.25
    cx1 = mx + MOUNT_W / 2 + 0.25
    for a, b in (((-cx1, cy0), (cx1, cy0)), ((cx1, cy0), (cx1, cy1)),
                 ((cx1, cy1), (-cx1, cy1)), ((-cx1, cy1), (-cx1, cy0))):
        lines.append("\t(fp_line\n"
                     f"\t\t(start {fmt(a[0])} {fmt(a[1])})\n"
                     f"\t\t(end {fmt(b[0])} {fmt(b[1])})\n"
                     "\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n"
                     '\t\t(layer "F.CrtYd")\n'
                     f'\t\t(uuid "{u()}")\n\t)')

    # ---- pads --------------------------------------------------------------
    for n in range(N_PINS):
        x = -half + n * PITCH
        lines.append(f'\t(pad "{n + 1}" smd rect\n'
                     f"\t\t(at {fmt(x)} {fmt(row_y)})\n"
                     f"\t\t(size {fmt(PAD_W)} {fmt(PAD_L)})\n"
                     '\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n'
                     f'\t\t(uuid "{u()}")\n\t)')
    for n, x in ((25, -mx), (26, mx)):
        lines.append(f'\t(pad "{n}" smd rect\n'
                     f"\t\t(at {fmt(x)} {fmt(mount_y)})\n"
                     f"\t\t(size {fmt(MOUNT_W)} {fmt(MOUNT_L)})\n"
                     '\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n'
                     f'\t\t(uuid "{u()}")\n\t)')
    lines.append("\t(embedded_fonts no)")
    lines.append(")")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
