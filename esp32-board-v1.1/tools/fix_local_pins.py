import re
from pathlib import Path

p = Path(r"C:/Code/epdf-hardware/esp32-board-v1.1/lib/esp32-board-v1.1.kicad_sym")
s = p.read_text(encoding="utf-8")
pattern = re.compile(r'\(pin\s+"([^"]+)"\s+(\w+)')
n = len(pattern.findall(s))
s2 = pattern.sub(r"(pin \2 line", s)
p.write_text(s2, encoding="utf-8")
print("replaced", n)
