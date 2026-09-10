import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from gen_sch import KICAD_SYM_DIR, find_symbol_block, parse_pins

TARGETS = [
    ("RF_Module.kicad_sym", "ESP32-S3-WROOM-1"),
    ("Battery_Management.kicad_sym", "BQ25895RTW"),
    ("Connector.kicad_sym", "USB_C_Receptacle_USB2.0_16P"),
    ("Connector_Generic.kicad_sym", "Conn_01x24"),
    ("Connector_Generic.kicad_sym", "Conn_01x12"),
    ("Transistor_FET.kicad_sym", "Q_NMOS_GSD"),
    ("Device.kicad_sym", "D_Schottky"),
    ("Connector.kicad_sym", "TestPoint"),
    ("Connector.kicad_sym", "Micro_SD_Card_Det2"),
    ("Connector.kicad_sym", "USB_C_Receptacle_USB2.0_16P"),
]

for lib, name in TARGETS:
    text = (KICAD_SYM_DIR / lib).read_text(encoding="utf-8")
    block = find_symbol_block(text, name)
    pins = parse_pins(block)
    print("===", name, "===")
    for key, plist in sorted(pins.items()):
        if not plist:
            continue
        print("  body/unit", key)
        for p in plist:
            print("    ", p["number"], p["name"], p["type"])
