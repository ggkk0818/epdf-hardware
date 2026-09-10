import re
import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from gen_sch import KICAD_SYM_DIR, find_symbol_block
from gen_sch import parse_pins

for lib, name in [
    ("Device.kicad_sym", "R"),
    ("RF_Module.kicad_sym", "ESP32-S3-WROOM-1"),
    ("Battery_Management.kicad_sym", "BQ25895RTW"),
    ("Connector.kicad_sym", "USB_C_Receptacle_USB2.0_16P"),
]:
    text = (KICAD_SYM_DIR / lib).read_text(encoding="utf-8")
    b = find_symbol_block(text, name)
    print("\n", lib, name, "len", len(b))
    print("subs", re.findall(r'(?m)^\s*\(symbol\s+"([^"]+)"\s*$', b))
    print("pin count", b.count("(pin"))
    print("parse", parse_pins(b))
