# ESP32-S3 + GDEM102T91 V1.1 — PCB 布局说明与状态

> 本文记录 PCB 阶段（placement / stackup / design rules / DRC）的实际执行结果。
> 与 `agent.md`、`SCHEMATIC_NOTES.md` 配套阅读。
> **本轮为竖版 55 × 84 mm 重构版（原 77 × 45 mm 横版作废）。**

---

## 1. 板框与机械

| 项目 | 值 | 状态 |
|---|---|---|
| 外形 | **55.0 (X) × 84.0 (Y) mm**（竖版，长边竖直） | 已实现 |
| 圆角 | R2（4 个角，Edge.Cuts 圆弧） | 已实现 |
| 层数 | 4 层 | 已实现 |
| 成品厚度 | 1.20 ± 0.10 mm | 已实现 |
| 定位孔 | 4 × Ø2.2 mm NPTH，(3,3) (52,3) (3,81) (52,81) | 已实现 |
| 孔心距最近两边 | **3 mm** | 已实现 |
| 贴装面 | 单面 SMT（SMD 全在 L1），插件仅连接器/按键 | 已实现 |
| 测试点 | **无**（本版取消全部测试点） | 已实现 |

坐标系：板左上为 (0, 0)，X 向右 55 mm，Y 向下 84 mm（KiCad 屏幕坐标）。

> **说明**：定位孔没有绘制 F.CrtYd courtyard。原因是 ESP32-S3-WROOM-1 的库封装
> 自带 48 mm × 21 mm 的天线禁布 courtyard，在 55 mm 宽板上必然覆盖两个上角定位孔，
> 保留 courtyard 会产生无法消除的 courtyard 重叠违规。定位孔本身为 NPTH，
> 无铜、无网络，去掉 courtyard 不影响制造。

---

## 2. 叠层（板厂结构图 + 用户给定参数）

```
L1  F.Cu     0.035 mm   （外层成品铜厚 1 oz，按要求代入）
    PP 7628  0.195 mm   Dk = 4.2（按要求统一代入）
L2  In1.Cu   0.035 mm   ← 完整 GND 平面
    CORE     0.63 mm    Dk = 4.2（0.70 mm "含铜" 减去上下各 0.035 mm）
L3  In2.Cu   0.035 mm
    PP 7628  0.195 mm   Dk = 4.2
L4  B.Cu     0.035 mm
```

> 仍建议向板厂复核：7628 半固化片在目标频率下的实际 Dk/Df、外层成品铜厚
> （图纸标注 0.0175 mm 是 Base Copper，成品约 1 oz）、阻焊厚度与 Dk。

---

## 3. 层定义

| 层 | 用途 |
|---|---|
| L1 F.Cu | 器件 + 关键信号（USB、SPI）+ 局部电源铜 |
| L2 In1.Cu | **完整 GND 平面**（已放置整板 GND zone 轮廓） |
| L3 In2.Cu | 电源平面 / 低速信号 |
| L4 B.Cu | 低速信号 + 辅助走线 |

已放置的 zone 轮廓（在 KiCad 中执行一次 "填充所有 zone"）：

- `GND_PLANE_L2`（In1.Cu，整板）
- `GND_POUR_L1`（F.Cu，整板）
- `GND_POUR_L4`（B.Cu，整板）
- `ANTENNA_KEEPOUT`（L1~L4 **禁止铺铜/走线/过孔/焊盘**）

---

## 4. 天线禁布区（真实 DRC 规则区）

模块天线端朝上，模块上边缘与板框上边缘对齐、天线区域外伸出板外。
板内规则区按模块实际宽度收紧为：

```
X 17.0 … 38.0 mm
Y  0.0 …  6.0 mm
tracks / vias / pads / copperpour  not allowed
```

---

## 5. Net Class 与规则（`esp32-board-v1.1.kicad_pro`）

| Net Class | 线宽 | 间距 | Via | 适用网络 |
|---|---|---|---|---|
| Default | 0.20 mm | 0.15 mm | 0.6 / 0.3 | 信号、I2C、SPI、按键 |
| **USB90** | **0.24 mm**（差分间隙 **0.18**） | 0.15 mm | 0.45 / 0.2 | `USB_DP*`, `USB_DN*` |
| POWER | 0.80 mm | 0.20 mm | 0.8 / 0.4 | `USB_VBUS_*`, `BAT*`, `SYS`, `3V3_MAIN`, `CHG_SW`, `EPD_SW` |
| HV_EPD | 0.30 mm | 0.20 mm | 0.6 / 0.3 | `EPD_V*`, `EPD_X`, `EPD_GDR`, `EPD_RESE` |

### 5.1 USB 90 Ω 差分线宽/间距计算

按 "L1 微带线参考 L2 GND"、介质 0.195 mm、Dk = 4.2、外层成品铜 1 oz 计算
（`tools/usb_impedance.py`，Hammerstad 单端模型 + 边耦合差分修正）：

```
目标 Zdiff = 90 Ω
计算解：W = 0.243 mm, S = 0.180 mm      → 取整 W = 0.24 mm, S = 0.18 mm
校验：  W=0.24 S=0.18 → 约 89.7 Ω（-0.3 %）

固定间距时的对应线宽：
  S = 0.15 mm → W = 0.221 mm
  S = 0.18 mm → W = 0.243 mm
  S = 0.20 mm → W = 0.255 mm
  S = 0.25 mm → W = 0.283 mm
```

> 该结果已写入 `USB90` Net Class（track 0.24 / diff_pair 0.24 / gap 0.18）。
> 投板前仍建议由板厂按其实际材料参数复算确认，允许 ±10 %。

设计规则：

```
min track width        0.15 mm
min clearance          0.15 mm
min via                0.40 mm / 0.20 mm drill
min through hole       0.20 mm
min copper-to-edge     0.30 mm
min hole clearance     0.15 mm
solder mask min width  0.05 mm
```

---

## 6. 器件放置（接口约束）

| 要求 | 器件 | 位置 (x, y) | 旋转 | 结果 |
|---|---|---|---|---|
| USB-C 右下、开口向下、**外凸 1 mm** | J1 | (45.5, 81.33) | 0° | 开口朝 +Y；F.Fab 本体前缘 **+1.00 mm** 超出板边，铜箔距板边 0.69 mm |
| 24P FPC 左侧中央、开口向左 | J2 | (4.0, 42.0) | 90° | 开口朝 −X，Y 32.95–51.05（板中心 42） |
| 电池接口左下、开口向左 | J4 / J5 | (5.0, 71.15) / (5.0, 76.45) | 90° | 开口朝 −X，板左下 |
| KEY1/2/3 右侧、**中心距 27 mm** | SW3/SW4/SW5 | (52.85, 15 / 42 / 69) | 90° | 右侧板边，间距 27.00 / 27.00 mm |
| TF 座向板外凸出 | J3 | (20.0, 75.2) | 0° | **未达成 1 mm，见下方说明** |
| BOOT / RESET（自由） | SW2 / SW1 | (31.0, 29.0) / (24.0, 29.0) | 0° | 模块正下方 |

### 6.1 TF（microSD）座外凸说明

`Hirose DM3AT-SF-PEJM5` 的 **两个前部固定焊盘位于本体最前端**
（局部坐标 y 6.4–8.3，本体前缘 y = 8.125），因此座体一旦外凸，焊盘即超出板边。

实测选择：

```
座体前缘距板边    0.675 mm（在板内）
最前铜箔距板边    0.470 mm
插卡后卡片外伸    约 5 mm（远超 1 mm）
```

即：**插拔可达性已满足（卡片外伸约 5 mm），但座体本身没有外凸 1 mm。**
如果结构上必须让座体外凸 1 mm，需要改选前部焊盘后移的型号，或接受 2 个屏蔽焊盘出板
（不推荐）。请确认是否接受当前做法。

---

## 7. DRC 结果（kicad-cli 10.0.5）

```
Errors        : 0
Warnings      : 86      silk_overlap 58 / silk_over_copper 21 /
                        silk_edge_clearance 5 / npth_inside_courtyard 2
Unconnected   : 258     = 尚未布线的飞线（本阶段预期）
Parity        : 0       原理图 ↔ PCB 器件/网络完全一致
```

丝印类告警来自**自动摆放、尚未人工整理丝印**（位号互相压叠、个别位号被板边裁切），
属发布前的人工整理项。`npth_inside_courtyard` 是 2 个上角定位孔落在 ESP32 模块
天线 courtyard 内（都是 warning；定位孔无铜、无网络，无功能影响）。

同一网络内焊盘短路、间距违规、短路、板边间距、阻焊桥、外框成形均为 **0**。

---

## 8. 功能分区

| 区域 | 内容 | 位置 |
|---|---|---|
| ESP32 核心 | U1 + C1–C5、R1、R2 | 上中部，天线朝上 |
| USB 前端 | D1–D5、C6–C8、R8–R12、F1 | 模块右侧 |
| 按键网络 | R3/R4/R5（上拉）+ SW3/SW4/SW5 | 右侧板边 |
| EPD Booster | U6、L3、Q1、D6–D8、C25–C36、R29–R31 | FPC 座右侧，紧邻 J2 |
| 电源/充电 | U2、U3、U4、U5、L1、L2、C9–C24、R6/R7、R13–R28、NTC1 | 板中右 |
| 存储 / 电池支路 | C37/C38、R32–R36、F2/F3 | microSD 上方 / 电池座旁 |

---

## 9. 下一步：布线方案（尚未执行）

### 9.1 电源路径（优先）

```
J1 VBUS ── F1 ── USB_VBUS_PROT ── U2.VBUS
J4 ── F2 ─┐
J5 ── F3 ─┴── BAT_BUS ── U2.BAT / U4.VDD
U2.SW ── L1 ── SYS
SYS ── U3.VIN ── L2 ── 3V3_MAIN
3V3_MAIN ── U6.VIN ── EPD_3V3
```

0.8 mm 以上（或 L3 铺铜），过孔并联；BQ25895 的 SW→L1→SYS 电容环路尽量短。

### 9.2 USB 差分布线

```
J1 (A6/B6 D+) ─ ESD D2 ─ R9 22Ω ─ U1.GPIO20
J1 (A7/B7 D−) ─ ESD D3 ─ R10 22Ω ─ U1.GPIO19
```

- L1 同层优先，参考 L2 完整 GND，W/S = 0.24 / 0.18 mm。
- ESD 靠连接器，22 Ω 靠 MCU；控制 skew，避免 stub。
- 该走线从板右下到模块左侧，横跨约 40 mm，是板上最长的关键信号，
  布线时优先保证参考平面连续。

### 9.3 其余信号

SPI / EPD 控制走 L1 并避开 Booster 的 SW 节点；I2C 走 L4；按键与 TF 走 L4。

### 9.4 Booster 区

L3/Q1/D6–D8/高压电容集中在 FPC 右侧；GDR、RESE 尽量短；
VGH/VGL/VSH/VSL/VCOM 不穿越天线禁布区与 USB 差分对。

---

## 10. 投板前仍需关闭的事项

- [ ] **确认 TF 座不能外凸 1 mm 是否可接受**（见 §6.1）
- [ ] 板厂按实际叠层复算 USB 90 Ω W/S（当前 0.24 / 0.18）
- [ ] 全部连接器/按键/电感/MOSFET 确切 MPN 与封装复核（BOM 中 `PROVISIONAL`）
- [ ] FPC Top Contact 实际料号确认，并核对 Pin 1 方向丝印
- [ ] EPD 高压外围逐节点人工复核（见 `SCHEMATIC_NOTES.md` §4）
- [ ] 丝印整理（位号避让、极性标识、`EPD / PIN1 / FPC INSERT → / TOP CONTACT`）
- [ ] 完成全部铜箔布线并重跑 DRC（目标 unconnected = 0）
- [ ] 生成 Gerber / 钻孔 / 贴片坐标并复核

---

## 11. 再生方式

```powershell
$py = 'C:\Users\ggkk2\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_sch.py'          # 原理图
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_pcb.py'          # PCB 布局
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\usb_impedance.py'    # USB 90Ω 计算
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\verify_connectors.py' # 连接器外凸复核
```

ERC / DRC 命令见 `agent.md` §八。
