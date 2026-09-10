import re
import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from gen_sch import KICAD_SYM_DIR, find_symbol_block, parse_pins

t = (KICAD_SYM_DIR / "RF_Module.kicad_sym").read_text(encoding="utf-8")
b = find_symbol_block(t, "ESP32-S3-WROOM-1")
print("len", len(b))
print("children", re.findall(r'(?m)^\s*\(symbol\s+"([^"]+)"', b)[:20])
print("--- head ---")
print(b[:1200])
print("--- parse_pins keys/lens ---")
p = parse_pins(b)
for k, v in p.items():
    print(k, len(v), v[:2])
print("--- ESP32 body1 unit1 pins ---")
for pin in p.get((1, 1), []):
    print(pin["number"], pin["name"], pin["type"], pin["x"], pin["y"], pin["angle"])
print("--- PWR_FLAG / GND pins ---")
for name in ("PWR_FLAG", "GND"):
    b = find_symbol_block((KICAD_SYM_DIR / "power.kicad_sym").read_text(encoding="utf-8"), name)
    pp = parse_pins(b)
    for k, v in pp.items():
        for pin in v:
            print(name, k, pin)
print("--- local symbol pins ---")
lt = (__import__("pathlib").Path("C:/Code/epdf-hardware/esp32-board-v1.1/lib/esp32-board-v1.1.kicad_sym")).read_text(encoding="utf-8")
for name in ("TUSB320LI", "TPS63070", "MAX17048", "TPS22918"):
    b = find_symbol_block(lt, name)
    pp = parse_pins(b)
    for k, v in pp.items():
        for pin in v:
            print(name, k, pin["number"], pin["name"], pin["type"], pin["x"], pin["y"], pin["angle"])
print("--- BQ25895RTW pins ---")
b = find_symbol_block((KICAD_SYM_DIR / "Battery_Management.kicad_sym").read_text(encoding="utf-8"), "BQ25895RTW")
pp = parse_pins(b)
for k, v in pp.items():
    for pin in v:
        print(k, pin["number"], pin["name"], pin["type"], pin["x"], pin["y"], pin["angle"])
