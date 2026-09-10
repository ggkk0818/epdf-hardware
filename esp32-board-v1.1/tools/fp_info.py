import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from kicad_fp import read_mod, parse_pads, split_children, child_key
import re

# Usage: python fp_info.py [LibNick:Footprint ...]
if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
        lib, name = arg.split(":", 1)
        text = read_mod(lib, name)
        pads = parse_pads(text)
        xs = [p["x"] for p in pads]
        ys = [p["y"] for p in pads]
        print("===", name)
        print("   pads:", len(pads), " pad bbox x", min(xs), "..", max(xs), " y", min(ys), "..", max(ys))
        for p in pads:
            print(f'   {p["number"]:>5s} {p["type"]:>9s} {p["shape"]:>5s} at ({p["x"]:7.3f},{p["y"]:7.3f}) '
                  f'rot {p["rot"]:g} size {p["w"]:g}x{p["h"]:g} drill {p["drill"]:g}')
        _, children = split_children(text)
        for lay in ("F.CrtYd", "F.Fab"):
            xs2, ys2 = [], []
            for ch in children:
                if f'"{lay}"' not in ch:
                    continue
                if child_key(ch) == "fp_circle":
                    c = re.search(r"\(center\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch)
                    e = re.search(r"\(end\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch)
                    cx, cy = float(c.group(1)), float(c.group(2))
                    r = ((float(e.group(1)) - cx) ** 2 + (float(e.group(2)) - cy) ** 2) ** 0.5
                    xs2 += [cx - r, cx + r]
                    ys2 += [cy - r, cy + r]
                    continue
                for cm in re.finditer(r"\((?:start|end|center|mid|xy)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch):
                    xs2.append(float(cm.group(1)))
                    ys2.append(float(cm.group(2)))
            if xs2:
                print(f"    {lay}: x {min(xs2):.2f}..{max(xs2):.2f}  y {min(ys2):.2f}..{max(ys2):.2f}")
    raise SystemExit(0)

TARGETS = [
    ("Connector_USB", "USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal"),
    ("Connector_FFC-FPC", "Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal"),
    ("Connector_Card", "microSD_HC_Hirose_DM3AT-SF-PEJM5"),
    ("Connector_Hirose", "Hirose_DF13-02P-1.25DS_1x02_P1.25mm_Horizontal"),
    ("Button_Switch_SMD", "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm"),
    ("RF_Module", "ESP32-S3-WROOM-1"),
    ("Package_TO_SOT_SMD", "SOT-23-6"),
    ("Package_DFN_QFN", "Texas_RTW_WQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm_ThermalVias"),
]


def layer_extents(name, layer):
    text = None
    for lib_, nm in TARGETS:
        if nm == name:
            text = read_mod(lib_, nm)
    _, children = split_children(text)
    xs, ys = [], []
    for ch in children:
        if layer not in ch:
            continue
        for cm in re.finditer(r"\((?:start|end|center|mid|xy)\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch):
            xs.append(float(cm.group(1)))
            ys.append(float(cm.group(2)))
    if not xs:
        return None
    return (round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2))

for lib, name in TARGETS:
    pads = parse_pads(read_mod(lib, name))
    xs = [p["x"] for p in pads]
    ys = [p["y"] for p in pads]
    print("===", name)
    print("   pads:", len(pads), " x:", min(xs), "..", max(xs), " y:", min(ys), "..", max(ys))
    for p in pads:
        print(f'   {p["number"]:>5s} {p["type"]:>9s} {p["shape"]:>5s} at ({p["x"]:7.3f},{p["y"]:7.3f}) '
              f'size {p["w"]:g}x{p["h"]:g} drill {p["drill"]:g}')
    for lay in ("F.CrtYd", "F.Fab", "Dwgs.User"):
        print("   ", lay, layer_extents(name, lay))
