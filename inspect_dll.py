import re


path = r"C:\Program Files\KiCad\10.0\bin\_eeschema.dll"
with open(path, "rb") as f:
    data = f.read()

text = data.decode("latin1", "ignore")

needles = ["lib_id", "placeSymbol", "category", "symbol_name", "placeSymbolPinLabel"]
shown = set()
for needle in needles:
    for match in re.finditer(needle, text):
        start = match.start()
        key = (needle, start)
        if key in shown:
            continue
        shown.add(key)
        print(f"--- {needle} at {start}")
        segment = text[max(0, start - 700):start + 1400]
        clean = "".join(ch if ch.isprintable() else "." for ch in segment)
        print(clean)
        print()
