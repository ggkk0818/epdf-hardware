import sys
from pathlib import Path

FP_ROOT = Path("C:/Program Files/KiCad/10.0/share/kicad/footprints")

NEEDED = [
    "RF_Module:ESP32-S3-WROOM-1",
    "Capacitor_SMD:C_0402_1005Metric",
    "Capacitor_SMD:C_0603_1608Metric",
    "Capacitor_SMD:C_0805_2012Metric",
    "Capacitor_SMD:C_1206_3216Metric",
    "Capacitor_SMD:C_1210_3225Metric",
    "Resistor_SMD:R_0402_1005Metric",
    "Resistor_SMD:R_0603_1608Metric",
    "Resistor_SMD:R_0805_2012Metric",
    "Resistor_SMD:R_1206_3216Metric",
    "Fuse:Fuse_0805_2012Metric",
    "Fuse:Fuse_1206_3216Metric",
    "Diode_SMD:D_SOD-323",
    "Diode_SMD:D_SOD-123",
    "Inductor_SMD:L_1008_2520Metric",
    "Inductor_SMD:L_1210_3225Metric",
    "Inductor_SMD:L_Coilcraft_XAL5030",
    "Package_DFN_QFN:Texas_RTW_WQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm_ThermalVias",
    "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.45x1.45mm_ThermalVias",
    "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm",
    "Package_DFN_QFN:Texas_X2QFN-12_1.6x1.6mm_P0.4mm",
    "Package_TO_SOT_SMD:SOT-23-6",
    "Package_TO_SOT_SMD:SOT-23",
    "Package_TO_SOT_SMD:SOT-323_SC-70",
    "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
    "Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal",
    "Connector_FFC-FPC:Hirose_FH34C-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal",
    "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5",
    "Connector_Hirose:Hirose_DF13-02P-1.25DS_1x02_P1.25mm_Horizontal",
    "Connector_Hirose:Hirose_DF13A-2P-1.25H_1x02_P1.25mm_Horizontal",
    "Button_Switch_SMD:SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm",
    "Button_Switch_SMD:SW_SPST_TL3342",
    "TestPoint:TestPoint_Pad_D1.5mm",
    "MountingHole:MountingHole_2.2mm_M2",
]

bad = []
for fp in NEEDED:
    lib, name = fp.split(":", 1)
    p = FP_ROOT / f"{lib}.pretty" / f"{name}.kicad_mod"
    if not p.exists():
        bad.append(fp)
    print(("OK  " if p.exists() else "MISS"), fp)

print()
print("missing:", len(bad))
for b in bad:
    print("  ", b)
