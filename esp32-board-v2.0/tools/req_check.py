"""Check the v2 schematic against PCB_INTERFACE_POSITIONS.md and its source design.

    python tools/req_check.py

Three independent comparisons:
  1. pin->net table of the live v2 schematic (design/model.json) vs the frozen
     v1.1 KiCad netlist (the requirement document's declared data source);
  2. the requirement document's own tables (ESP32-S3 GPIO map from 7.2, the
     microSD pin map from 5.5, the FPC pin map from SCHEMATIC_NOTES 4.2 and the
     GDEM102T91 datasheet page 7);
  3. component values against the frozen v1.1 BOM (bom.csv).
"""

import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402

ROOT = geom.ROOT
V11 = os.path.join(os.path.dirname(ROOT), "esp32-board-v1.1")


def v2_pins():
    model = json.load(open(os.path.join(ROOT, "design", "model.json"),
                           encoding="utf-8"))
    pm = json.load(open(os.path.join(ROOT, "design", "pin-map.json"),
                        encoding="utf-8"))["resolved"]
    pins, refs = {}, set()
    for c in model["components"]:
        refs.add(c["ref"])
        for pad in c["pads"]:
            src = str(pad["num"])
            for dev in (pm.get(c["ref"]) or {}).get(src) or [src]:
                pins[f"{c['ref']}.{dev}"] = pad.get("net")
    return pins, refs


def v11_pins():
    tree = ET.parse(os.path.join(V11, "esp32-board-v1.1.net"))
    pins, refs = {}, set()
    for comp in tree.iter("comp"):
        refs.add(comp.get("ref"))
    for net in tree.iter("net"):
        name = net.get("name")
        for node in net.iter("node"):
            pins[f"{node.get('ref')}.{node.get('pin')}"] = name
    return pins, refs


def norm(net):
    return "" if net in (None, "") else net


def main():
    v2, v2refs = v2_pins()
    v11, v11refs = v11_pins()

    print("== 1a. v2 schematic vs v1.1 historical netlist export "
          "(esp32-board-v1.1.net, 2026-09-10 — NOT the requirement's data source) ==")
    print("   NOTE: that export predates the frozen V1.6 fixups: it still carries "
          "TP1-TP10 test points, a 16-pin U3 symbol and unnamed single-pad nets.")
    print("   The requirement document declares the v1.1 FINAL PCB as its data "
          "source; see tools/pcb_netlist_check.py for that comparison.")
    only11 = sorted(set(v11) - set(v2))
    only2 = sorted(set(v2) - set(v11))
    diff = sorted(k for k in set(v2) & set(v11) if norm(v2[k]) != norm(v11[k]))
    print(f"   v1.1 pins {len(v11)}, v2 pins {len(v2)}, "
          f"only-in-v1.1 {len(only11)}, only-in-v2 {len(only2)}, "
          f"net differences {len(diff)}")
    for k in only11[:20]:
        print(f"     v1.1 only: {k} = {v11[k]}")
    for k in only2[:20]:
        print(f"     v2 only  : {k} = {v2[k]}")
    for k in diff[:30]:
        print(f"     differs  : {k}: v1.1={v11[k]}  v2={v2[k]}")
    print("   component refs only in v1.1:", sorted(v11refs - v2refs))
    print("   component refs only in v2  :", sorted(v2refs - v11refs))

    # net-level comparison (ignore auto-generated single-pin nets)
    def nets_of(pins):
        out = {}
        for k, n in pins.items():
            out.setdefault(norm(n), set()).add(k)
        return {n: p for n, p in out.items() if n and not n.startswith("unconnected")}

    n11, n2 = nets_of(v11), nets_of(v2)
    print(f"   nets: v1.1 {len(n11)}, v2 {len(n2)}; "
          f"v1.1-only {sorted(set(n11) - set(n2))}; "
          f"v2-only {sorted(set(n2) - set(n11))}")
    for name in sorted(set(n11) & set(n2)):
        if n11[name] != n2[name]:
            print(f"     net {name}: v1.1-only pins {sorted(n11[name] - n2[name])}, "
                  f"v2-only pins {sorted(n2[name] - n11[name])}")

    print()
    print("== 2a. requirement doc 7.2: ESP32-S3 GPIO map (module pin -> net) ==")
    gpio = {4: "KEY1_N", 5: "KEY2_N", 6: "EPD_PWR_EN", 7: "EPD_BUSY",
            8: "KEY3_N", 9: "CHG_INT_N", 10: "TYPEC_INT_N", 11: "I2C_SDA",
            12: "EPD_RST_N", 13: "USB_DN", 14: "USB_DP", 17: "EPD_DC",
            18: "EPD_CS_N", 19: "SPI_MOSI", 20: "SPI_SCLK", 21: "SPI_MISO",
            22: "TF_CS_N", 23: "I2C_SCL", 24: "CHG_CE", 27: "BOOT",
            38: "TF_CD_N", 39: "FG_ALRT_N"}
    bad = 0
    for pin, net in sorted(gpio.items()):
        got = norm(v2.get(f"U1.{pin}"))
        if got != net:
            bad += 1
            print(f"     MISMATCH U1.{pin}: doc {net}, schematic {got or 'NC'}")
    print(f"   {len(gpio) - bad}/{len(gpio)} GPIO assignments match")
    doc_nc = {31: "IO38", 32: "IO39", 36: "IO44/RXD0", 37: "IO43/TXD0"}
    nc_v2 = sorted(int(k.split(".")[1]) for k, v in v2.items()
                   if k.startswith("U1.") and not norm(v)
                   and k.split(".")[1] not in ("25", "26"))
    print(f"   NC pins on U1 in v2: {nc_v2}")
    print(f"   doc names these NC  : {sorted(doc_nc)} (+ GPIO3/35/36/37/40/41/42/45/46/48 per SCHEMATIC_NOTES 3)")

    print()
    print("== 2b. requirement doc 5.5: microSD J3 pin map ==")
    j3 = {1: None, 2: "TF_CS_N", 3: "TF_MOSI", 4: "3V3_MAIN", 5: "TF_SCLK",
          6: "GND", 7: "TF_MISO", 8: None, 9: "TF_CD_N", 10: "GND",
          11: "GND", 12: "GND", 13: "GND", 14: "GND"}
    bad = 0
    for pin, net in sorted(j3.items()):
        got = norm(v2.get(f"J3.{pin}")) or None
        if got != net:
            bad += 1
            print(f"     MISMATCH J3.{pin}: doc {net}, schematic {got}")
    print(f"   {len(j3) - bad}/{len(j3)} J3 pins match")

    print()
    print("== 2c. FPC J2 pin map (SCHEMATIC_NOTES 4.2 / GDEM102T91 p.7) ==")
    j2 = {1: None, 2: "EPD_GDR", 3: "EPD_RESE", 4: None, 5: "EPD_VSH2",
          6: None, 7: None, 8: "GND", 9: "EPD_BUSY", 10: "EPD_RST_N",
          11: "EPD_DC", 12: "EPD_CS_N", 13: "SPI_SCLK", 14: "SPI_MOSI",
          15: "EPD_3V3", 16: "EPD_3V3", 17: "GND", 18: "EPD_VDD",
          19: None, 20: "EPD_VSH1", 21: "EPD_VGH", 22: "EPD_VSL",
          23: "EPD_VGL", 24: "EPD_VCOM"}
    bad = 0
    for pin, net in sorted(j2.items()):
        got = norm(v2.get(f"J2.{pin}")) or None
        if got != net:
            bad += 1
            print(f"     MISMATCH J2.{pin}: doc {net}, schematic {got}")
    print(f"   {len(j2) - bad}/{len(j2)} J2 pins match")

    print()
    print("== 2d. requirement doc 7.4/7.5/7.9: connector & function wiring ==")
    checks = {
        "J1.A5 USB_CC1": ("J1.A5", "USB_CC1"), "J1.B5 USB_CC2": ("J1.B5", "USB_CC2"),
        "J1.A6 USB_DP_CONN": ("J1.A6", "USB_DP_CONN"),
        "J1.A7 USB_DN_CONN": ("J1.A7", "USB_DN_CONN"),
        "J1.A4-B9 USB_VBUS_RAW": ("J1.A4-B9", "USB_VBUS_RAW"),
        "J1.B4-A9 USB_VBUS_RAW": ("J1.B4-A9", "USB_VBUS_RAW"),
        "J1.A1-B12 GND": ("J1.A1-B12", "GND"), "J1.B1-A12 GND": ("J1.B1-A12", "GND"),
        "J4.1 BAT1_RAW": ("J4.1", "BAT1_RAW"), "J4.2 GND": ("J4.2", "GND"),
        "J5.1 BAT2_RAW": ("J5.1", "BAT2_RAW"), "J5.2 GND": ("J5.2", "GND"),
        "U2.1 USB_VBUS_PROT": ("U2.1", "USB_VBUS_PROT"),
        "U2.9 CHG_CE": ("U2.9", "CHG_CE"), "U2.24 CHG_DSEL": ("U2.24", "CHG_DSEL"),
        "U4.2 BAT_BUS (CELL)": ("U4.2", "BAT_BUS"),
        "U3.7 3V3_MAIN (VOUT)": ("U3.7", "3V3_MAIN"),
        "U6.6 EPD_3V3 (VOUT)": ("U6.6", "EPD_3V3"),
        "U6.3 EPD_PWR_EN (ON)": ("U6.3", "EPD_PWR_EN"),
        "SW3.1 KEY1_N": ("SW3.1", "KEY1_N"), "SW4.1 KEY2_N": ("SW4.1", "KEY2_N"),
        "SW5.1 KEY3_N": ("SW5.1", "KEY3_N"),
        "SW1.1 RESET_N": ("SW1.1", "RESET_N"), "SW2.1 BOOT": ("SW2.1", "BOOT"),
    }
    bad = 0
    for label, (pin, net) in checks.items():
        got = norm(v2.get(pin))
        if got != net:
            bad += 1
            print(f"     MISMATCH {label}: schematic {got or 'NC'}")
    print(f"   {len(checks) - bad}/{len(checks)} connector/function pins match")

    print()
    print("== 2e. requirement doc 7.6: CHG_STAT must stay off the MCU ==")
    chg = sorted(k for k, v in v2.items() if norm(v) == "CHG_STAT")
    print("   CHG_STAT pins:", chg)

    print()
    print("== 2f. requirement doc 5.2/5.4/5.5 pin counts per connector ==")
    for ref, want in (("J1", 16), ("J2", 26), ("J3", 14), ("J4", 2), ("J5", 2),
                      ("SW3", 2), ("SW4", 2), ("SW5", 2), ("U1", 41)):
        n = len([k for k in v2 if k.startswith(ref + ".")])
        flag = "" if n == want else "  <-- check"
        print(f"   {ref}: {n} pins (expected {want}){flag}")

    print()
    print("== 3. v1.1 BOM vs v2 parts-map ==")
    pm = json.load(open(os.path.join(ROOT, "design", "parts-map.json"),
                        encoding="utf-8"))["parts"]

    def expand(expr):
        out = []
        for part in expr.split(","):
            part = part.strip()
            m = re.match(r"^([A-Za-z]+)(\d+)-([A-Za-z]*)(\d+)$", part)
            if m:
                pre, a, pre2, b = m.group(1), int(m.group(2)), m.group(3) or m.group(1), int(m.group(4))
                for n in range(a, b + 1):
                    out.append(f"{pre}{n}")
            elif part:
                out.append(part)
        return out

    v11 = {}
    with open(os.path.join(V11, "bom.csv"), encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            for ref in expand(row["Reference"]):
                v11[ref] = {"value": row["Value"], "mpn": row["MPN"],
                            "populate": row["Populate"]}
    missing = sorted(set(v11) - set(pm))
    extra = sorted(set(pm) - set(v11))
    print(f"   refs in v1.1 BOM only: {missing}")
    print(f"   refs in v2 parts only : {extra}")
    print(f"   {'ref':<6}{'v1.1 value':<14}{'v2 value':<12}{'v1.1 MPN':<34}{'v2 MPN':<34}")
    for ref in sorted(set(v11) & set(pm),
                      key=lambda r: (re.match(r"[A-Za-z]+", r).group(0),
                                     int(re.search(r"\d+", r).group(0)))):
        a, b = v11[ref], pm[ref]
        m1 = (a["mpn"] or "").split("（")[0].strip()
        m2 = (b.get("mpn") or "").strip()
        flag = ""
        if a["value"].replace("uF", "uF") != (b.get("value") or "").replace("uF", "uF") \
                and a["value"] not in (b.get("value") or ""):
            flag += "  VALUE"
        if m1 and m2 and m1 != m2:
            flag += "  MPN"
        if a["populate"] == "DNP":
            flag += "  (v1.1 DNP)"
        if flag:
            print(f"   {ref:<6}{a['value']:<14}{str(b.get('value'))[:11]:<12}"
                  f"{m1[:33]:<34}{m2[:33]:<34}{flag}")


if __name__ == "__main__":
    main()
