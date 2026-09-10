import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from gen_sch import KICAD_SYM_DIR, find_symbol_block, parse_pins

for lib, name in [
    ("RF_Module.kicad_sym", "ESP32-S3-WROOM-1"),
    ("Battery_Management.kicad_sym", "BQ25895RTW"),
    ("Connector.kicad_sym", "USB_C_Receptacle_USB2.0_16P"),
]:
    text = (KICAD_SYM_DIR / lib).read_text(encoding="utf-8")
    b = find_symbol_block(text, name)
    pins = parse_pins(b)
    print("\n===", lib, name, "===")
    for key, plist in pins.items():
        if key[0] == 0:
            print(
                "unit",
                key[1],
                [f"{p['number']}:{p['name']}({p['type']})" for p in plist],
            )
