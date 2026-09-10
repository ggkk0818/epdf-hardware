import sys

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from gen_sch import (
    Schematic,
    KICAD_SYM_DIR,
    find_symbol_block,
    parse_pins,
    render_schematic,
    pin_pos,
    pin_maps,
)

sch = Schematic()
text = (KICAD_SYM_DIR / "Device.kicad_sym").read_text(encoding="utf-8")
block = find_symbol_block(text, "R")
sch.add_lib_symbol(block, "Device:R")
pin_maps.clear()
parsed = parse_pins(block)
for key, val in parsed.items():
    pin_maps[("Device:R",) + key] = val

at = (100, 100, 0)
sch.add_symbol_instance("Device:R", "R1", "10k", "Resistor_SMD:R_0603_1608Metric", at)
for p in pin_maps[("Device:R", 1, 1)]:
    pos = pin_pos(at, p)
    sch.add_global_label("N1" if p["number"] == "1" else "N2", pos)

out = render_schematic(sch)
path = "C:/Code/epdf-hardware/esp32-board-v1.1/test_min.kicad_sch"
open(path, "w", encoding="utf-8").write(out)
print("wrote", path)
