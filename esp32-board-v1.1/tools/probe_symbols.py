import sys
from pathlib import Path

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from gen_sch import (
    Schematic,
    KICAD_SYM_DIR,
    LOCAL_SYM,
    find_symbol_block,
    parse_pins,
    render_schematic,
    pin_maps,
)

ROOT = Path("C:/Code/epdf-hardware/esp32-board-v1.1")
OUT_DIR = ROOT / "probe"
OUT_DIR.mkdir(exist_ok=True)

libs = {
    "Device:R": ("Device.kicad_sym", "R"),
    "Device:C": ("Device.kicad_sym", "C"),
    "Device:L": ("Device.kicad_sym", "L"),
    "Device:D_Schottky": ("Device.kicad_sym", "D_Schottky"),
    "Device:D_TVS": ("Device.kicad_sym", "D_TVS"),
    "Device:Fuse": ("Device.kicad_sym", "Fuse"),
    "Device:Thermistor_NTC": ("Device.kicad_sym", "Thermistor_NTC"),
    "Device:Q_NMOS_GSD": ("Transistor_FET.kicad_sym", "Q_NMOS_GSD"),
    "Connector:USB_C_Receptacle_USB2.0_16P": ("Connector.kicad_sym", "USB_C_Receptacle_USB2.0_16P"),
    "Connector:TestPoint": ("Connector.kicad_sym", "TestPoint"),
    "Connector_Generic:Conn_01x02": ("Connector_Generic.kicad_sym", "Conn_01x02"),
    "Connector_Generic:Conn_01x04": ("Connector_Generic.kicad_sym", "Conn_01x04"),
    "Connector_Generic:Conn_01x24": ("Connector_Generic.kicad_sym", "Conn_01x24"),
    "Connector_Generic:Conn_01x12": ("Connector_Generic.kicad_sym", "Conn_01x12"),
    "Switch:SW_Push": ("Switch.kicad_sym", "SW_Push"),
    "Battery_Management:BQ25895RTW": ("Battery_Management.kicad_sym", "BQ25895RTW"),
    "RF_Module:ESP32-S3-WROOM-1": ("RF_Module.kicad_sym", "ESP32-S3-WROOM-1"),
    "power:GND": ("power.kicad_sym", "GND"),
    "power:PWR_FLAG": ("power.kicad_sym", "PWR_FLAG"),
    "local:TPS63070": ("__local__", "TPS63070"),
    "local:MAX17048": ("__local__", "MAX17048"),
    "local:TUSB320LI": ("__local__", "TUSB320LI"),
    "local:TPS22918": ("__local__", "TPS22918"),
}

local_text = LOCAL_SYM.read_text(encoding="utf-8")

for lib_id, (file, name) in libs.items():
    if file == "__local__":
        block = find_symbol_block(local_text, name)
    else:
        text = (KICAD_SYM_DIR / file).read_text(encoding="utf-8")
        block = find_symbol_block(text, name)
    if block is None:
        print("MISSING", lib_id)
        continue
    sch = Schematic()
    sch.add_lib_symbol(block, lib_id)
    pin_maps.clear()
    parsed = parse_pins(block)
    for key, val in parsed.items():
        pin_maps[(lib_id,) + key] = val
    # pick first body/unit that has pins
    keys = sorted(parsed.keys())
    body, unit = keys[0] if keys else (1, 1)
    sch.add_symbol_instance(lib_id, "U1", name, "", (100, 100, 0), unit=unit, body=body)
    out = render_schematic(sch)
    path = OUT_DIR / f"{lib_id.replace(':','_')}.kicad_sch"
    path.write_text(out, encoding="utf-8")
    print("wrote", path.name)
