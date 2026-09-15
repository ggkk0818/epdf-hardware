"""Generate esp32-board-v1.1.kicad_sch (ESP32-S3 + GDEM102T91 e-paper mainboard V1.1).

Design intent for this revision (see SCHEMATIC_NOTES.md):
  * ERC target 0 error / 0 warning (per ESP32S3_GDEM102T91_V1.1_ERC_Guide.md)
  * TPS63070 VOUT7 = power output, VOUT8 = passive -> no bogus power-output clash
  * Reserved ESP32 GPIOs -> real No-Connect (never isolated global labels)
  * Q1 lib_id fixed to Transistor_FET:Q_NMOS_GSD (was mislabelled Device:...)
  * EPD SSD1677 / GDEM102T91 high voltage network locked to the panel typical
    application circuit (GDEM102T91 spec page 20), GDR symbol pin type = Output
  * BQ25895 /CE defaults HIGH (charge disabled) until the MCU configures it
  * Every BOM line carries a Status field (RELEASED / PROVISIONAL)

Connectivity is expressed with global labels, which keeps the netlist unambiguous.
Run: python tools/gen_sch.py  then ERC with kicad-cli.
"""

import re
import uuid
from pathlib import Path

ROOT = Path("C:/Code/epdf-hardware/esp32-board-v1.1")
KICAD_SYM_DIR = Path("C:/Program Files/KiCad/10.0/share/kicad/symbols")
LOCAL_SYM = ROOT / "lib" / "esp32-board-v1.1.kicad_sym"
OUT_SCH = ROOT / "esp32-board-v1.1.kicad_sch"

pin_maps = {}
SHEET_UUID = ""
GRID = 1.27


def snap(v):
    return round(float(v) / GRID) * GRID


def snap_pt(x, y):
    return snap(x), snap(y)


def read_balanced_blocks(text: str, start: int):
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1, text[start : i + 1]
        i += 1
    raise ValueError("unbalanced")


def find_symbol_block(lib_text: str, name: str):
    pat = re.compile(r'(?m)^\s*\(symbol\s+"' + re.escape(name) + r'"\s*$')
    m = pat.search(lib_text)
    if not m:
        return None
    start = m.start()
    paren = lib_text.find("(", start)
    _, block = read_balanced_blocks(lib_text, paren)
    return block


def normalize_symbol_block_for_sch(block: str, lib_id: str) -> str:
    first = block.find('"')
    second = block.find('"', first + 1)
    return block[: first + 1] + lib_id + block[second:]


def parse_pins(block: str):
    """Parse pins per body/unit. Returns dict[(body, unit)] -> list of pin dicts."""
    pins = {}
    for sm in re.finditer(r'(?m)^\s*\(symbol\s+"([^"]+)_([0-9])_([0-9])"\s*$', block):
        body = int(sm.group(2))
        unit = int(sm.group(3))
        start = sm.start()
        paren = block.find("(", start)
        _, sub = read_balanced_blocks(block, paren)
        sub_pins = []
        for pm in re.finditer(r"(?ms)\(pin\b", sub):
            pstart = pm.start()
            paren2 = sub.find("(", pstart)
            _, pinblk = read_balanced_blocks(sub, paren2)
            name_m = re.search(r'\(pin\s+"((?:[^"\\]|\\.)*)"\s+(\w+)', pinblk)
            type_m = re.search(r"\(pin\s+(\w+)(?:\s+line)?", pinblk)
            name_inner = re.search(r'\(name\s+"((?:[^"\\]|\\.)*)"', pinblk)
            at_m = re.search(r"\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d]+)\)", pinblk)
            num_m = re.search(r'\(number\s+"([^"]+)"', pinblk)
            if name_m and at_m and num_m:
                sub_pins.append(
                    {
                        "name": name_m.group(1),
                        "type": name_m.group(2),
                        "x": float(at_m.group(1)),
                        "y": float(at_m.group(2)),
                        "angle": int(at_m.group(3)),
                        "number": num_m.group(1),
                    }
                )
            elif type_m and at_m and num_m:
                sub_pins.append(
                    {
                        "name": "",
                        "type": type_m.group(1),
                        "x": float(at_m.group(1)),
                        "y": float(at_m.group(2)),
                        "angle": int(at_m.group(3)),
                        "number": num_m.group(1),
                    }
                )
            if name_inner and sub_pins:
                sub_pins[-1]["name"] = name_inner.group(1)
        pins[(body, unit)] = sub_pins
    return pins


def pin_pos(symbol_pos, pin):
    x, y, rot = symbol_pos
    px, py = pin["x"], pin["y"]
    if rot == 0:
        return x + px, y - py
    if rot == 90:
        return x - py, y + px
    if rot == 180:
        return x - px, y - py
    if rot == 270:
        return x + py, y - px
    raise ValueError("bad rotation")


def make_uuid():
    return str(uuid.uuid4())


class Schematic:
    def __init__(self):
        self.lib_symbols = []
        self.items = []
        self.uuid = make_uuid()

    def add_lib_symbol(self, block, lib_id):
        self.lib_symbols.append(normalize_symbol_block_for_sch(block, lib_id))

    def add_symbol_instance(self, lib_id, ref, value, footprint, at, unit=1, body=1,
                            status="", mpn="", dnp=False):
        self.items.append(
            {
                "kind": "symbol",
                "lib_id": lib_id,
                "ref": ref,
                "value": value,
                "footprint": footprint,
                "at": at,
                "unit": unit,
                "body": body,
                "status": status,
                "mpn": mpn,
                "dnp": dnp,
            }
        )

    def add_global_label(self, net, pos, shape="input"):
        self.items.append({"kind": "label", "net": net, "pos": pos, "shape": shape})

    def add_power(self, lib_id, ref, net, pos):
        self.items.append({"kind": "power", "lib_id": lib_id, "ref": ref, "net": net, "pos": pos})

    def add_no_connect(self, pos):
        self.items.append({"kind": "no_connect", "pos": pos})

    def add_text(self, text, pos, size=2.0):
        self.items.append({"kind": "text", "text": text, "pos": pos, "size": size})


def fmt_pt(x, y):
    return f"{x:.4f} {y:.4f}"


def prop(name, value, x, y, hide=True, justify=None):
    s = [f'\t\t(property "{name}" "{value}"']
    s.append(f"\t\t\t(at {fmt_pt(x, y)} 0)")
    if hide:
        s.append("\t\t\t(hide yes)")
    s.append("\t\t\t(effects")
    s.append("\t\t\t\t(font")
    s.append("\t\t\t\t\t(size 1.27 1.27)")
    s.append("\t\t\t\t)")
    if justify:
        s.append(f"\t\t\t\t(justify {justify})")
    s.append("\t\t\t)")
    s.append("\t\t)")
    return "\n".join(s)


def gen_symbol_instance(item, pin_map):
    lib_id = item["lib_id"]
    at = item["at"]
    if len(at) == 2:
        at = (at[0], at[1], 0)
    body = item.get("body", 0)
    unit = item.get("unit", 1)
    ref = item["ref"]
    value = item["value"]
    footprint = item.get("footprint", "")
    pins = pin_map.get((lib_id, body, unit), [])
    s = []
    s.append("\t(symbol")
    s.append(f'\t\t(lib_id "{lib_id}")')
    s.append(f"\t\t(at {fmt_pt(at[0], at[1])} {at[2]})")
    s.append(f"\t\t(unit {unit})")
    s.append("\t\t(exclude_from_sim no)")
    s.append("\t\t(in_bom yes)")
    s.append("\t\t(on_board yes)")
    s.append(f"\t\t(dnp {'yes' if item.get('dnp') else 'no'})")
    s.append(f'\t\t(uuid "{make_uuid()}")')
    s.append(f'\t\t(property "Reference" "{ref}"')
    s.append(f"\t\t\t(at {fmt_pt(at[0], at[1] - 1.27)} 0)")
    s.append("\t\t\t(effects")
    s.append("\t\t\t\t(font")
    s.append("\t\t\t\t\t(size 1.27 1.27)")
    s.append("\t\t\t\t)")
    s.append("\t\t\t)")
    s.append("\t\t)")
    s.append(f'\t\t(property "Value" "{value}"')
    s.append(f"\t\t\t(at {fmt_pt(at[0], at[1] + 2.54)} 0)")
    s.append("\t\t\t(effects")
    s.append("\t\t\t\t(font")
    s.append("\t\t\t\t\t(size 1.27 1.27)")
    s.append("\t\t\t\t)")
    s.append("\t\t\t)")
    s.append("\t\t)")
    s.append(prop("Footprint", footprint, at[0], at[1]))
    s.append(prop("Datasheet", "", at[0], at[1]))
    if item.get("status"):
        s.append(prop("Status", item["status"], at[0], at[1]))
    if item.get("mpn"):
        s.append(prop("MPN", item["mpn"], at[0], at[1]))
    for p in pins:
        s.append(f'\t\t(pin "{p["number"]}"')
        s.append(f'\t\t\t(uuid "{make_uuid()}")')
        s.append("\t\t)")
    inst_uuid = make_uuid()
    s.append("\t\t(instances")
    s.append('\t\t\t(project "esp32-board-v1.1"')
    s.append(f'\t\t\t\t(path "/{SHEET_UUID}/{inst_uuid}"')
    s.append(f'\t\t\t\t\t(reference "{ref}")')
    s.append(f"\t\t\t\t\t(unit {unit})")
    s.append("\t\t\t\t)")
    s.append("\t\t\t)")
    s.append("\t\t)")
    s.append("\t)")
    return "\n".join(s)


def gen_label(item):
    pos = item["pos"]
    shape = item.get("shape", "input")
    s = []
    s.append(f'\t(global_label "{item["net"]}"')
    s.append(f"\t\t(shape {shape})")
    s.append(f"\t\t(at {fmt_pt(pos[0], pos[1])} 0)")
    s.append("\t\t(effects")
    s.append("\t\t\t(font")
    s.append("\t\t\t\t(size 1.27 1.27)")
    s.append("\t\t\t)")
    s.append("\t\t\t(justify left bottom)")
    s.append("\t\t)")
    s.append(f'\t\t(uuid "{make_uuid()}")')
    s.append("\t)")
    return "\n".join(s)


def gen_power(item):
    pos = item["pos"]
    if len(pos) == 2:
        pos = (pos[0], pos[1], 0)
    s = []
    s.append("\t(symbol")
    s.append(f'\t\t(lib_id "{item["lib_id"]}")')
    s.append(f"\t\t(at {fmt_pt(pos[0], pos[1])} 0)")
    s.append("\t\t(unit 1)")
    s.append("\t\t(exclude_from_sim no)")
    s.append("\t\t(in_bom yes)")
    s.append("\t\t(on_board no)")
    s.append("\t\t(dnp no)")
    s.append(f'\t\t(uuid "{make_uuid()}")')
    s.append(prop("Reference", item["ref"], pos[0], pos[1]))
    s.append(prop("Value", item["net"], pos[0], pos[1], hide=False))
    s.append(prop("Footprint", "", pos[0], pos[1]))
    s.append(prop("Datasheet", "", pos[0], pos[1]))
    s.append('\t\t(pin "1"')
    s.append(f'\t\t\t(uuid "{make_uuid()}")')
    s.append("\t\t)")
    inst_uuid = make_uuid()
    s.append("\t\t(instances")
    s.append('\t\t\t(project "esp32-board-v1.1"')
    s.append(f'\t\t\t\t(path "/{SHEET_UUID}/{inst_uuid}"')
    s.append(f'\t\t\t\t\t(reference "{item["ref"]}")')
    s.append("\t\t\t\t\t(unit 1)")
    s.append("\t\t\t\t)")
    s.append("\t\t\t)")
    s.append("\t\t)")
    s.append("\t)")
    return "\n".join(s)


def gen_no_connect(item):
    pos = item["pos"]
    return f'\t(no_connect (at {fmt_pt(pos[0], pos[1])}) (uuid "{make_uuid()}"))'


def gen_text(item):
    pos = item["pos"]
    size = item.get("size", 2.0)
    s = []
    s.append(f'\t(text "{item["text"]}"')
    s.append("\t\t(exclude_from_sim no)")
    s.append(f"\t\t(at {fmt_pt(pos[0], pos[1])} 0)")
    s.append("\t\t(effects")
    s.append("\t\t\t(font")
    s.append(f"\t\t\t\t(size {size} {size})")
    s.append("\t\t\t)")
    s.append("\t\t)")
    s.append(f'\t\t(uuid "{make_uuid()}")')
    s.append("\t)")
    return "\n".join(s)


STD_LIBS = [
    ("Device:R", "Device.kicad_sym", "R"),
    ("Device:C", "Device.kicad_sym", "C"),
    ("Device:L", "Device.kicad_sym", "L"),
    ("Device:D_Schottky", "Device.kicad_sym", "D_Schottky"),
    ("Device:D_TVS", "Device.kicad_sym", "D_TVS"),
    ("Device:Fuse", "Device.kicad_sym", "Fuse"),
    ("Device:Thermistor_NTC", "Device.kicad_sym", "Thermistor_NTC"),
    ("Transistor_FET:Q_NMOS_GSD", "Transistor_FET.kicad_sym", "Q_NMOS_GSD"),
    ("Connector:USB_C_Receptacle_USB2.0_16P", "Connector.kicad_sym",
     "USB_C_Receptacle_USB2.0_16P"),
    ("Connector:Micro_SD_Card_Det2", "Connector.kicad_sym", "Micro_SD_Card_Det2"),
    ("Connector:TestPoint", "Connector.kicad_sym", "TestPoint"),
    ("Connector_Generic:Conn_01x02", "Connector_Generic.kicad_sym", "Conn_01x02"),
    ("Switch:SW_Push", "Switch.kicad_sym", "SW_Push"),
    ("Battery_Management:BQ25895RTW", "Battery_Management.kicad_sym", "BQ25895RTW"),
    ("RF_Module:ESP32-S3-WROOM-1", "RF_Module.kicad_sym", "ESP32-S3-WROOM-1"),
    ("power:GND", "power.kicad_sym", "GND"),
    ("power:PWR_FLAG", "power.kicad_sym", "PWR_FLAG"),
    ("local:TPS63070RNM", "__local__", "TPS63070RNM"),
    ("local:MAX17048", "__local__", "MAX17048"),
    ("local:TUSB320LI", "__local__", "TUSB320LI"),
    ("local:TPS22918", "__local__", "TPS22918"),
    ("local:EPD_FPC24", "__local__", "EPD_FPC24"),
    ("local:CONN_01X02_PICO", "__local__", "CONN_01X02_PICO"),
]

RELEASED = "RELEASED"
PROVISIONAL = "PROVISIONAL"


class Builder:
    def __init__(self, sch):
        self.sch = sch
        self.power_count = 0
        self.ref_counts = {}

    def pwr_ref(self):
        self.power_count += 1
        return f"#PWR{self.power_count:04d}"

    def next_ref(self, prefix):
        n = self.ref_counts.get(prefix, 0) + 1
        self.ref_counts[prefix] = n
        return f"{prefix}{n}"

    def connect(self, lib_id, at, pin_nets, unit=1, body=1):
        pins = pin_maps.get((lib_id, body, unit), [])
        if len(at) == 2:
            at = (at[0], at[1], 0)
        for p in pins:
            net = pin_nets.get(p["number"])
            if net is None:
                net = pin_nets.get(p["name"])
            if net is None:
                net = "NC"
            pos = snap_pt(*pin_pos(at, p))
            if net == "NC":
                self.sch.add_no_connect(pos)
            elif net == "GND":
                self.sch.add_power("power:GND", self.pwr_ref(), "GND", pos)
            else:
                self.sch.add_global_label(net, pos)

    def comp(self, lib_id, prefix, value, footprint, at, pin_nets,
             unit=1, body=1, status=RELEASED, mpn="", dnp=False, ref=None):
        at = (snap(at[0]), snap(at[1]), at[2] if len(at) > 2 else 0)
        if (lib_id, body, unit) not in pin_maps and (lib_id, 0, unit) in pin_maps:
            body = 0
        if ref is None:
            ref = self.next_ref(prefix)
        else:
            self.ref_counts[prefix] = max(self.ref_counts.get(prefix, 0), int(re.sub(r"\D", "", ref) or 0))
        self.sch.add_symbol_instance(lib_id, ref, value, footprint, at, unit=unit,
                                     body=body, status=status, mpn=mpn, dnp=dnp)
        self.connect(lib_id, at, pin_nets, unit=unit, body=body)
        return ref

    def pwrflag(self, net, at):
        """Attach a PWR_FLAG (power output) to a net at the same coordinate as a
        net label / power symbol so that "Input Power pin not driven" clears."""
        pos = (snap(at[0]), snap(at[1]))
        if net == "GND":
            self.sch.add_power("power:GND", self.pwr_ref(), "GND", pos)
        else:
            self.sch.add_global_label(net, pos)
        self.sch.add_power("power:PWR_FLAG", self.pwr_ref(), net, pos)


U1_PINS = {
    "1": "GND", "2": "3V3_MAIN", "3": "RESET_N",
    "4": "KEY1_N", "5": "KEY2_N", "6": "EPD_PWR_EN", "7": "EPD_BUSY", "8": "KEY3_N",
    "9": "CHG_INT_N", "10": "TYPEC_INT_N", "11": "I2C_SDA", "12": "EPD_RST_N",
    "13": "USB_DN", "14": "USB_DP",
    "15": "NC", "16": "NC", "26": "NC",
    "17": "EPD_DC", "18": "EPD_CS_N", "19": "SPI_MOSI", "20": "SPI_SCLK",
    "21": "SPI_MISO", "22": "TF_CS_N", "23": "I2C_SCL",
    "24": "CHG_CE",
    "25": "NC",
    "27": "BOOT",
    "28": "NC", "29": "NC", "30": "NC",
    # No test points on this revision: spare GPIOs and the debug UART are left
    # deliberately unconnected (explicit No Connect, never an isolated label).
    "31": "NC", "32": "NC",
    "33": "NC", "34": "NC", "35": "NC",
    "36": "NC", "37": "NC", "38": "TF_CD_N", "39": "FG_ALRT_N",
    "40": "GND", "41": "GND",
}

USB_PINS = {
    "A1": "GND", "A4": "USB_VBUS_RAW", "A5": "USB_CC1", "A6": "USB_DP_CONN",
    "A7": "USB_DN_CONN", "A8": "NC", "A9": "USB_VBUS_RAW", "A12": "GND",
    "B1": "GND", "B4": "USB_VBUS_RAW", "B5": "USB_CC2", "B6": "USB_DP_CONN",
    "B7": "USB_DN_CONN", "B8": "NC", "B9": "USB_VBUS_RAW", "B12": "GND",
    "SH": "USB_SHIELD",
}

TUSB_PINS = {
    "1": "USB_CC1", "2": "USB_CC2", "3": "GND", "4": "USB_VBUS_DET",
    "5": "GND", "6": "TYPEC_INT_N", "7": "I2C_SDA", "8": "I2C_SCL",
    "9": "NC", "10": "GND", "11": "GND", "12": "3V3_MAIN",
}

BQ_PINS = {
    "1": "USB_VBUS_PROT", "2": "NC", "3": "NC", "4": "CHG_STAT",
    "5": "I2C_SCL", "6": "I2C_SDA", "7": "CHG_INT_N", "8": "CHG_OTG",
    "9": "CHG_CE", "10": "CHG_ILIM", "11": "CHG_TS", "12": "NC",
    "13": "BAT_BUS", "14": "BAT_BUS", "15": "SYS", "16": "SYS",
    "17": "GND", "18": "GND", "19": "CHG_SW", "20": "CHG_SW",
    "21": "CHG_BTST", "22": "CHG_REGN", "23": "CHG_PMID", "24": "CHG_DSEL",
    "25": "GND",
}

MAX_PINS = {
    "1": "GND",
    "2": "BAT_BUS",
    "3": "BAT_BUS",
    "4": "GND",
    "5": "FG_ALRT_N",
    "6": "GND",
    "7": "I2C_SCL",
    "8": "I2C_SDA",
    "9": "GND",
}

TPS_PINS = {
    "1": "TPS_PS_SYNC", "2": "TPS_PG", "3": "TPS_VAUX", "4": "GND",
    "5": "TPS_FB", "6": "NC", "7": "3V3_MAIN", "8": "3V3_MAIN",
    "9": "TPS_L2", "10": "GND", "11": "TPS_L1", "12": "SYS",
    "13": "SYS", "14": "TPS_EN", "15": "TPS_VSEL",
}

TPS22918_PINS = {
    "1": "3V3_MAIN", "2": "GND", "3": "EPD_PWR_EN",
    "4": "NC", "5": "NC", "6": "EPD_3V3",
}

EPD_PINS = {
    "1": "NC",
    "2": "EPD_GDR",
    "3": "EPD_RESE",
    "4": "NC",
    "5": "EPD_VSH2",
    "6": "NC",
    "7": "NC",
    "8": "GND",
    "9": "EPD_BUSY",
    "10": "EPD_RST_N",
    "11": "EPD_DC",
    "12": "EPD_CS_N",
    "13": "SPI_SCLK",
    "14": "SPI_MOSI",
    "15": "EPD_3V3",
    "16": "EPD_3V3",
    "17": "GND",
    "18": "EPD_VDD",
    "19": "NC",
    "20": "EPD_VSH1",
    "21": "EPD_VGH",
    "22": "EPD_VSL",
    "23": "EPD_VGL",
    "24": "EPD_VCOM",
}

SD_PINS = {
    "1": "NC",
    "2": "TF_CS_N",
    "3": "TF_MOSI",
    "4": "3V3_MAIN",
    "5": "TF_SCLK",
    "6": "GND",
    "7": "TF_MISO",
    "8": "NC",
    "9": "TF_CD_N",
    "10": "GND",
    "SH": "GND",
}


class Layout:
    def __init__(self, x0, y0, dx=16.51, dy=13.97, cols=8):
        self.x0, self.y0, self.dx, self.dy, self.cols = x0, y0, dx, dy, cols
        self.n = 0

    def cell(self):
        x = self.x0 + (self.n % self.cols) * self.dx
        y = self.y0 + (self.n // self.cols) * self.dy
        self.n += 1
        return (x, y)


def build_schematic():
    global pin_maps
    sch = Schematic()

    for lib_id, filename, name in STD_LIBS:
        if filename == "__local__":
            block = find_symbol_block(LOCAL_SYM.read_text(encoding="utf-8"), name)
        else:
            block = find_symbol_block((KICAD_SYM_DIR / filename).read_text(encoding="utf-8"), name)
        if block is None:
            raise RuntimeError(f"missing symbol {lib_id}")
        sch.add_lib_symbol(block, lib_id)
        for (body, unit), plist in parse_pins(block).items():
            pin_maps[(lib_id, body, unit)] = plist

    b = Builder(sch)

    FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
    FP_R0805 = "Resistor_SMD:R_0805_2012Metric"
    FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
    FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"

    sch.add_text("ESP32-S3 + GDEM102T91 e-Paper Mainboard V1.1", (25.4, 25.4), 4.0)
    sch.add_text(
        "Status=PROVISIONAL marks candidate MPNs that still need procurement review "
        "before Gerber release.  Net names are frozen per the V1.1 design document.",
        (25.4, 31.75), 2.0)

    # ---- 01 ESP32-S3 core -------------------------------------------------
    sch.add_text("01  ESP32-S3-WROOM-1-N16R8 core, reset, boot, keys, I2C pull-ups",
                 (25.4, 45.72), 2.5)
    b.comp("RF_Module:ESP32-S3-WROOM-1", "U", "ESP32-S3-WROOM-1-N16R8",
           # project copy of the vendor land pattern: its 48 x 21 mm RF keep-out
           # courtyard overlaps the two upper locating holes on a 55 mm board, so
           # the board uses a local footprint whose courtyard is the module body
           # and whose top silkscreen no longer crosses Edge.Cuts.  Using a local
           # copy keeps the board consistent with the library (review item 14).
           "esp32-board-v1.1:ESP32-S3-WROOM-1_EPDF", (76.2, 88.9, 0), U1_PINS,
           mpn="ESP32-S3-WROOM-1-N16R8", ref="U1")

    lay = Layout(27.94, 127.0)
    core_passives = [
        ("Device:C", "C", "22uF", FP_C0805, {"1": "3V3_MAIN", "2": "GND"}, RELEASED),
        ("Device:C", "C", "10uF", FP_C0805, {"1": "3V3_MAIN", "2": "GND"}, RELEASED),
        ("Device:C", "C", "1uF", FP_C0603, {"1": "3V3_MAIN", "2": "GND"}, RELEASED),
        ("Device:C", "C", "0.1uF", FP_C0603, {"1": "3V3_MAIN", "2": "GND"}, RELEASED),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "RESET_N"}, RELEASED),
        ("Device:C", "C", "1uF", FP_C0603, {"1": "RESET_N", "2": "GND"}, RELEASED),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "BOOT"}, RELEASED),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "KEY1_N"}, RELEASED),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "KEY2_N"}, RELEASED),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "KEY3_N"}, RELEASED),
        ("Device:R", "R", "4.7k", FP_R0603, {"1": "3V3_MAIN", "2": "I2C_SDA"}, RELEASED),
        ("Device:R", "R", "4.7k", FP_R0603, {"1": "3V3_MAIN", "2": "I2C_SCL"}, RELEASED),
    ]
    for lib, prefix, val, fp, nets, status in core_passives:
        b.comp(lib, prefix, val, fp, lay.cell(), nets, status=status)

    lay = Layout(27.94, 156.21)
    for name, net in [("RESET", "RESET_N"), ("BOOT", "BOOT"), ("KEY1", "KEY1_N"),
                      ("KEY2", "KEY2_N"), ("KEY3", "KEY3_N")]:
        b.comp("Switch:SW_Push", "SW", name,
               "Button_Switch_SMD:SW_SPST_B3U-1000P",
               lay.cell(), {"1": net, "2": "GND"}, status=PROVISIONAL,
               mpn="Omron B3U-1000P")

    # ---- 02 USB-C + TUSB320LI --------------------------------------------
    sch.add_text("02  USB-C 2.0 sink, VBUS protection, TUSB320LI current advertisement",
                 (25.4, 211.46), 2.5)
    b.comp("Connector:USB_C_Receptacle_USB2.0_16P", "J", "USB-C 2.0 Sink",
           "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
           (76.2, 260.35, 0), USB_PINS, status=PROVISIONAL,
           mpn="GCT USB4105-15-A-120", ref="J1")

    lay = Layout(27.94, 302.26)
    usb_parts = [
        ("Device:Fuse", "F", "2A PTC", "Fuse:Fuse_0805_2012Metric",
         {"1": "USB_VBUS_RAW", "2": "USB_VBUS_PROT"}, PROVISIONAL, ""),
        ("Device:D_TVS", "D", "TVS 5.6V", "Diode_SMD:D_SOD-323",
         {"1": "USB_VBUS_PROT", "2": "GND"}, PROVISIONAL, ""),
        ("Device:D_TVS", "D", "ESD", "Diode_SMD:D_SOD-323",
         {"1": "USB_DP_CONN", "2": "GND"}, PROVISIONAL, ""),
        ("Device:D_TVS", "D", "ESD", "Diode_SMD:D_SOD-323",
         {"1": "USB_DN_CONN", "2": "GND"}, PROVISIONAL, ""),
        ("Device:D_TVS", "D", "ESD", "Diode_SMD:D_SOD-323",
         {"1": "USB_CC1", "2": "GND"}, PROVISIONAL, ""),
        ("Device:D_TVS", "D", "ESD", "Diode_SMD:D_SOD-323",
         {"1": "USB_CC2", "2": "GND"}, PROVISIONAL, ""),
        ("Device:C", "C", "1uF", FP_C0603, {"1": "USB_VBUS_PROT", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "1nF", FP_C0603, {"1": "USB_SHIELD", "2": "GND"}, RELEASED, ""),
        ("Device:R", "R", "0", FP_R0603, {"1": "USB_SHIELD", "2": "GND"}, RELEASED, ""),
        ("Device:R", "R", "22", FP_R0603, {"1": "USB_DP_CONN", "2": "USB_DP"}, RELEASED, ""),
        ("Device:R", "R", "22", FP_R0603, {"1": "USB_DN_CONN", "2": "USB_DN"}, RELEASED, ""),
        ("Device:R", "R", "900k", FP_R0603, {"1": "USB_VBUS_RAW", "2": "USB_VBUS_DET"}, RELEASED, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "TYPEC_INT_N"}, RELEASED, ""),
        ("Device:C", "C", "0.1uF", FP_C0603, {"1": "3V3_MAIN", "2": "GND"}, RELEASED, ""),
    ]
    for lib, prefix, val, fp, nets, status, mpn in usb_parts:
        b.comp(lib, prefix, val, fp, lay.cell(), nets, status=status, mpn=mpn)

    b.comp("local:TUSB320LI", "U", "TUSB320LI",
           "Package_DFN_QFN:Texas_X2QFN-12_1.6x1.6mm_P0.4mm",
           (182.88, 260.35, 0), TUSB_PINS, status=RELEASED,
           mpn="TUSB320LIRWBR", ref="U5")

    # ---- 03 BQ25895 -------------------------------------------------------
    sch.add_text("03  BQ25895 NVDC charger / power path (/CE defaults HIGH = charge disabled)",
                 (236.22, 45.72), 2.5)
    # V1.3 design note (review list 2.2 / 2.3): the connector is not changed, the
    # current is constrained in firmware, and the charger stays off until the MCU
    # has written and verified its configuration.  Placed above the section title
    # so it does not collide with the BQ25895 symbol or its pin labels.
    for i, line in enumerate([
        "Charge policy (V1.3, review list 2.2 / 2.3)",
        "ICHG default = 896 mA (14 x 64 mA) - keeps the Molex 53261-0271 connector, 26 AWG harness and terminals inside their thermal budget.",
        "/CE = CHG_CE (GPIO47), 10k pull-up to 3V3_MAIN -> charge DISABLED at power-up.",
        "Start-up: MCU boot -> I2C init -> write ICHG / IINLIM / ITERM / VREG -> read back and verify -> drive /CE LOW -> charging enabled.",
        "Bench test at peak load (Wi-Fi TX + EPD refresh + TF card + CPU) required: measure J4/J5 peak current and connector /",
        "terminal / harness temperature rise; limit concurrent load in firmware if the design target is exceeded.",
    ]):
        sch.add_text(line, (236.22, 20.5 + 4.3 * i), 1.6)
    b.comp("Battery_Management:BQ25895RTW", "U", "BQ25895RTW",
           "Package_DFN_QFN:Texas_RTW_WQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm_ThermalVias",
           (287.02, 88.9, 0), BQ_PINS, mpn="BQ25895RTWT", ref="U2")

    lay = Layout(236.22, 127.0)
    bq_parts = [
        ("Device:C", "C", "1uF", FP_C0603, {"1": "USB_VBUS_PROT", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "4.7uF/10V", FP_C0805, {"1": "CHG_REGN", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "47nF", FP_C0603, {"1": "CHG_BTST", "2": "CHG_SW"}, RELEASED, ""),
        ("Device:C", "C", "10uF", FP_C0805, {"1": "BAT_BUS", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "22uF", FP_C0805, {"1": "SYS", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "22uF", FP_C0805, {"1": "SYS", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "10uF", FP_C0805, {"1": "CHG_PMID", "2": "GND"}, RELEASED, ""),
        ("Device:L", "L", "1.0uH", "Inductor_SMD:L_Coilcraft_XAL5030-XXX",
         {"1": "CHG_SW", "2": "SYS"}, PROVISIONAL, "Coilcraft XAL5030 / Isat>=4.5A"),
        ("Device:R", "R", "180", FP_R0603, {"1": "CHG_ILIM", "2": "GND"}, PROVISIONAL, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "CHG_INT_N", "2": "3V3_MAIN"}, RELEASED, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "CHG_STAT", "2": "3V3_MAIN"}, RELEASED, ""),
        ("Device:R", "R", "5.23k", FP_R0603, {"1": "CHG_REGN", "2": "CHG_TS"}, RELEASED, ""),
        ("Device:R", "R", "30.1k", FP_R0603, {"1": "CHG_TS", "2": "GND"}, RELEASED, ""),
        ("Device:Thermistor_NTC", "NTC", "10k 103AT", FP_R0603,
         {"1": "CHG_TS", "2": "GND"}, PROVISIONAL, "103AT-2 class NTC"),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "CHG_CE"}, RELEASED, ""),
        ("Device:R", "R", "100k", FP_R0603, {"1": "CHG_OTG", "2": "GND"}, RELEASED, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "CHG_DSEL"}, RELEASED, ""),
        # SW snubber: DNP footprint, fitted only if EMI measurements require it.
        ("Device:R", "R", "2.2 DNP", FP_R0805, {"1": "CHG_SW", "2": "CHG_SNUB"}, RELEASED, ""),
        ("Device:C", "C", "470pF DNP", FP_C0603, {"1": "CHG_SNUB", "2": "GND"}, RELEASED, ""),
    ]
    for lib, prefix, val, fp, nets, status, mpn in bq_parts:
        b.comp(lib, prefix, val.replace(" DNP", ""), fp, lay.cell(), nets,
               status=status, mpn=mpn, dnp=("DNP" in val))

    # ---- 04 battery + fuel gauge -----------------------------------------
    sch.add_text("04  Battery inputs (either or both) + MAX17048 fuel gauge",
                 (236.22, 180.34), 2.5)
    # local symbol: the generic Conn_01x02 footprint filter (Connector*:*_1x??_*)
    # rejects the Molex land pattern name, so the battery connectors use a local
    # symbol whose ki_fp_filters also accepts Connector_Molex:*1x02*
    b.comp("local:CONN_01X02_PICO", "J", "BAT1",
           "Connector_Molex:Molex_PicoBlade_53261-0271_1x02-1MP_P1.25mm_Horizontal",
           (269.24, 213.36, 0), {"1": "BAT1_RAW", "2": "GND"},
           status=RELEASED, mpn="Molex 53261-0271", ref="J4")
    b.comp("local:CONN_01X02_PICO", "J", "BAT2",
           "Connector_Molex:Molex_PicoBlade_53261-0271_1x02-1MP_P1.25mm_Horizontal",
           (269.24, 243.84, 0), {"1": "BAT2_RAW", "2": "GND"},
           status=RELEASED, mpn="Molex 53261-0271", ref="J5")
    b.comp("local:MAX17048", "U", "MAX17048",
           "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm",
           (320.04, 213.36, 0), MAX_PINS, mpn="MAX17048G+T10", ref="U4")

    lay = Layout(236.22, 251.46, cols=4)
    bat_parts = [
        ("Device:Fuse", "F", "2A PTC", "Fuse:Fuse_0805_2012Metric",
         {"1": "BAT1_RAW", "2": "BAT_BUS"}, PROVISIONAL, ""),
        ("Device:Fuse", "F", "2A PTC", "Fuse:Fuse_0805_2012Metric",
         {"1": "BAT2_RAW", "2": "BAT_BUS"}, PROVISIONAL, ""),
        ("Device:C", "C", "0.1uF", FP_C0603, {"1": "BAT_BUS", "2": "GND"}, RELEASED, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "FG_ALRT_N"}, RELEASED, ""),
    ]
    for lib, prefix, val, fp, nets, status, mpn in bat_parts:
        b.comp(lib, prefix, val, fp, lay.cell(), nets, status=status, mpn=mpn)

    # ---- 05 TPS63070 ------------------------------------------------------
    sch.add_text("05  TPS63070 3V3 buck-boost (VOUT8 = Passive, no power-output clash)",
                 (419.1, 45.72), 2.5)
    b.comp("local:TPS63070RNM", "U", "TPS63070RNMT",
           "esp32-board-v1.1:RNM0015A",
           (469.9, 88.9, 0), TPS_PINS, mpn="TPS63070RNMT", ref="U3")

    lay = Layout(419.1, 127.0, cols=7)
    tps_parts = [
        ("Device:L", "L", "1.2uH", "Inductor_SMD:L_Coilcraft_XAL4030-XXX",
         {"1": "TPS_L1", "2": "TPS_L2"}, PROVISIONAL, "Coilcraft XAL4030 / Isat>=3A"),
        ("Device:C", "C", "10uF", FP_C0805, {"1": "SYS", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "10uF", FP_C0805, {"1": "SYS", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "10uF", FP_C0805, {"1": "3V3_MAIN", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "22uF", FP_C0805, {"1": "3V3_MAIN", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "22uF", FP_C0805, {"1": "3V3_MAIN", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "22uF", FP_C0805, {"1": "3V3_MAIN", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "100nF", FP_C0603, {"1": "TPS_VAUX", "2": "GND"}, RELEASED, ""),
        ("Device:R", "R", "470k", FP_R0603, {"1": "3V3_MAIN", "2": "TPS_FB"}, RELEASED, ""),
        ("Device:R", "R", "150k", FP_R0603, {"1": "TPS_FB", "2": "GND"}, RELEASED, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "TPS_PG"}, RELEASED, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "SYS", "2": "TPS_EN"}, RELEASED, ""),
        # PS/SYNC pulled to VIN (SYS) = PWM/PFM power-save mode for good light-load
        # efficiency on battery.  Fit 0R to GND instead for forced PWM if EMI needs it.
        ("Device:R", "R", "100k", FP_R0603, {"1": "SYS", "2": "TPS_PS_SYNC"}, RELEASED, ""),
        ("Device:R", "R", "100k", FP_R0603, {"1": "GND", "2": "TPS_VSEL"}, RELEASED, ""),
    ]
    for lib, prefix, val, fp, nets, status, mpn in tps_parts:
        b.comp(lib, prefix, val, fp, lay.cell(), nets, status=status, mpn=mpn)

    # ---- 06 EPD -----------------------------------------------------------
    sch.add_text("06  EPD GDEM102T91 24P FPC + SSD1677 HV network "
                 "(locked to panel typical application circuit)", (419.1, 180.34), 2.5)
    b.comp("local:EPD_FPC24", "J", "GDEM102T91 24P FPC",
           "Connector_FFC-FPC:Amphenol_F32Q-1A7x1-11024_1x24-1MP_P0.5mm_Horizontal",
           (431.8, 245.11, 0), EPD_PINS, status=PROVISIONAL,
           mpn="Amphenol F32Q-1A7x1-11024 (24P 0.5mm TOP contact)", ref="J2")
    b.comp("local:TPS22918", "U", "TPS22918",
           "Package_TO_SOT_SMD:SOT-23-6", (533.4, 245.11, 0), TPS22918_PINS,
           mpn="TPS22918", ref="U6")

    lay = Layout(419.1, 280.67)
    epd_parts = [
        ("Device:R", "R", "100k", FP_R0603, {"1": "EPD_PWR_EN", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "10uF", FP_C0805, {"1": "EPD_3V3", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "0.1uF", FP_C0603, {"1": "EPD_3V3", "2": "GND"}, RELEASED, ""),
        ("Device:L", "L", "47uH", "Inductor_SMD:L_Taiyo-Yuden_NR-40xx",
         {"1": "EPD_3V3", "2": "EPD_SW"}, PROVISIONAL, "47uH >=500mA, low profile"),
        ("Transistor_FET:Q_NMOS_GSD", "Q", "Si1304BDL", "Package_TO_SOT_SMD:SOT-23",
         {"G": "EPD_GDR", "D": "EPD_SW", "S": "EPD_RESE"}, PROVISIONAL,
         "Si1304BDL / Si1308EDL or compatible"),
        ("Device:R", "R", "1M", FP_R0603, {"1": "EPD_GDR", "2": "GND"}, RELEASED, ""),
        ("Device:R", "R", "2.2", FP_R0805, {"1": "EPD_RESE", "2": "GND"}, RELEASED, ""),
        ("Device:D_Schottky", "D", "MBR0530", "Diode_SMD:D_SOD-123",
         {"2": "EPD_SW", "1": "EPD_VGH"}, PROVISIONAL, "MBR0530"),
        ("Device:D_Schottky", "D", "MBR0530", "Diode_SMD:D_SOD-123",
         {"2": "EPD_X", "1": "GND"}, PROVISIONAL, "MBR0530"),
        ("Device:D_Schottky", "D", "MBR0530", "Diode_SMD:D_SOD-123",
         {"2": "EPD_VGL", "1": "EPD_X"}, PROVISIONAL, "MBR0530"),
        ("Device:C", "C", "4.7uF/25V", FP_C0805, {"1": "EPD_3V3", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "4.7uF/25V", FP_C0805, {"1": "EPD_VGH", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "4.7uF/25V", FP_C0805, {"1": "EPD_SW", "2": "EPD_X"}, RELEASED, ""),
        ("Device:C", "C", "4.7uF/25V", FP_C0805, {"1": "EPD_VGL", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "4.7uF/25V", FP_C0805, {"1": "EPD_VSH2", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "4.7uF/25V", FP_C0805, {"1": "EPD_VSH1", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "4.7uF/25V", FP_C0805, {"1": "EPD_VSL", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "1uF/25V", FP_C0603, {"1": "EPD_3V3", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "1uF/25V", FP_C0603, {"1": "EPD_VDD", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "1uF/25V", FP_C0805, {"1": "EPD_VCOM", "2": "GND"}, RELEASED, ""),
    ]
    for lib, prefix, val, fp, nets, status, mpn in epd_parts:
        b.comp(lib, prefix, val, fp, lay.cell(), nets, status=status, mpn=mpn)

    # ---- 07 MicroSD -------------------------------------------------------
    sch.add_text("07  MicroSD (SPI, shared SCLK/MOSI with EPD, independent CS)",
                 (236.22, 299.72), 2.5)
    b.comp("Connector:Micro_SD_Card_Det2", "J", "MicroSD",
           # project copy of the vendor land pattern (keeps board and library
           # identical, review item 14)
           "esp32-board-v1.1:microSD_DM3AT-SF-PEJM5_EPDF",
           (287.02, 340.36, 0), SD_PINS, status=PROVISIONAL,
           mpn="Hirose DM3AT-SF-PEJM5", ref="J3")

    lay = Layout(236.22, 374.65, cols=7)
    sd_parts = [
        ("Device:C", "C", "10uF", FP_C0805, {"1": "3V3_MAIN", "2": "GND"}, RELEASED, ""),
        ("Device:C", "C", "0.1uF", FP_C0603, {"1": "3V3_MAIN", "2": "GND"}, RELEASED, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "TF_CS_N"}, RELEASED, ""),
        ("Device:R", "R", "0", FP_R0603, {"1": "SPI_SCLK", "2": "TF_SCLK"}, RELEASED, ""),
        ("Device:R", "R", "0", FP_R0603, {"1": "SPI_MOSI", "2": "TF_MOSI"}, RELEASED, ""),
        ("Device:R", "R", "0", FP_R0603, {"1": "SPI_MISO", "2": "TF_MISO"}, RELEASED, ""),
        ("Device:R", "R", "10k", FP_R0603, {"1": "3V3_MAIN", "2": "TF_CD_N"}, RELEASED, ""),
    ]
    for lib, prefix, val, fp, nets, status, mpn in sd_parts:
        b.comp(lib, prefix, val, fp, lay.cell(), nets, status=status, mpn=mpn)

    # ---- 08 PWR_FLAG -------------------------------------------------------
    # This revision has no test points (user requirement), so no TP symbols are
    # emitted.  PWR_FLAGs are still required to mark the nets that have no real
    # power-output pin as driven.
    sch.add_text("08  PWR_FLAG (no test points on this revision)", (419.1, 316.23), 2.5)
    lay = Layout(419.1, 321.31, cols=8)
    # Only nets without a real power-output pin need a PWR_FLAG.  3V3_MAIN (TPS63070
    # VOUT7), EPD_3V3 (TPS22918 VOUT) and CHG_PMID (BQ25895 PMID) are already driven.
    for net in ["GND", "USB_VBUS_RAW", "USB_VBUS_PROT", "BAT_BUS", "SYS"]:
        b.pwrflag(net, lay.cell())

    return sch


def render_schematic(sch: Schematic) -> str:
    global SHEET_UUID
    SHEET_UUID = sch.uuid
    lines = []
    lines.append("(kicad_sch")
    lines.append("\t(version 20250610)")
    lines.append('\t(generator "eeschema")')
    lines.append('\t(generator_version "9.99")')
    lines.append(f'\t(uuid "{sch.uuid}")')
    lines.append('\t(paper "A2")')
    lines.append("\t(title_block")
    lines.append('\t\t(title "ESP32-S3 GDEM102T91 Mainboard")')
    lines.append('\t\t(date "2026-09-10")')
    lines.append('\t\t(rev "V1.1")')
    lines.append('\t\t(company "EPDF Hardware")')
    lines.append("\t)")
    lines.append("\t(lib_symbols")
    for block in sch.lib_symbols:
        lines.append(block)
    lines.append("\t)")
    kind_order = ["symbol", "power", "label", "no_connect", "text"]
    for kind in kind_order:
        for item in sch.items:
            if item["kind"] != kind:
                continue
            if kind == "symbol":
                lines.append(gen_symbol_instance(item, pin_maps))
            elif kind == "power":
                lines.append(gen_power(item))
            elif kind == "label":
                lines.append(gen_label(item))
            elif kind == "no_connect":
                lines.append(gen_no_connect(item))
            elif kind == "text":
                lines.append(gen_text(item))
    lines.append(")")
    return "\n".join(lines)


if __name__ == "__main__":
    sch = build_schematic()
    out = render_schematic(sch)
    OUT_SCH.write_text(out, encoding="utf-8")
    print("wrote", OUT_SCH, len(out), "bytes")

