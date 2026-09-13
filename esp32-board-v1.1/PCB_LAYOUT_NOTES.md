# ESP32-S3 + GDEM102T91 V1.2 — PCB 布局说明与状态

> 本文记录 PCB 阶段（placement / stackup / design rules / DRC）的实际执行结果。
> 与 `agent.md`、`SCHEMATIC_NOTES.md` 配套阅读。
> 本轮执行了 `ESP32S3_GDEM102T91_V1.1_to_V1.2_PCB_Modification_Guide.md`
> 中的布局类整改（第 ⑤⑥⑦⑨⑩ 项），并完成 TF 座与 USB-C 座对调。

---

## 1. 板框与机械

| 项目 | 值 | 状态 |
|---|---|---|
| 外形 | **55.0 (X) × 84.0 (Y) mm**（竖版，长边竖直） | 按用户指令保持 |
| 圆角 | R2（4 个角，Edge.Cuts 圆弧，圆心角平分线取中点） | 已实现 |
| 层数 | 4 层 | 已实现 |
| 成品厚度 | 1.20 ± 0.10 mm | 已实现 |
| 定位孔 | 4 × Ø2.2 mm NPTH，(3,3) (52,3) (3,81) (52,81) | 已实现 |
| 孔心距最近两边 | **3 mm** | 已实现 |
| 贴装面 | 单面 SMT（SMD 全在 L1），插件仅连接器/按键 | 已实现 |
| 测试点 | **无** | 已实现 |

坐标系：板左上为 (0, 0)，X 向右 55 mm，Y 向下 84 mm（KiCad 屏幕坐标）。

> 定位孔没有绘制 F.CrtYd courtyard：ESP32-S3-WROOM-1 的库封装自带 48 × 21 mm 天线
> 禁布 courtyard，在 55 mm 宽板上必然覆盖两个上角定位孔，保留 courtyard 会产生
> 无法消除的 courtyard 重叠违规。定位孔为 NPTH，无铜无网络，去掉 courtyard 不影响制造。

---

## 2. 叠层（板厂结构图 + 用户给定参数）

```
L1  F.Cu     0.035 mm   （外层成品铜厚 1 oz）
    PP 7628  0.195 mm   Dk = 4.2
L2  In1.Cu   0.035 mm   ← 完整 GND 平面
    CORE     0.63 mm    Dk = 4.2（0.70 mm "含铜" 减去上下各 0.035 mm）
L3  In2.Cu   0.035 mm
    PP 7628  0.195 mm   Dk = 4.2
L4  B.Cu     0.035 mm
```

---

## 3. 层定义与铺铜

| 层 | 用途 |
|---|---|
| L1 F.Cu | 器件 + 关键信号（USB、SPI）+ 局部电源铜 |
| L2 In1.Cu | **完整 GND 平面** |
| L3 In2.Cu | 电源平面 / 低速信号 |
| L4 B.Cu | 低速信号 + 辅助走线 |

已放置的 zone 轮廓（在 KiCad 中执行一次 "填充所有 zone"）：

- `GND_PLANE_L2`（In1.Cu，整板）
- `GND_POUR_L1`（F.Cu，整板）
- `GND_POUR_L4`（B.Cu，整板）
- `ANTENNA_KEEPOUT`（L1~L4 禁止铺铜/走线/过孔/焊盘）：X 17.0–38.0，Y 0.0–6.0

---

## 4. Net Class 与规则

| Net Class | 线宽 | 间距 | Via | 适用网络 |
|---|---|---|---|---|
| Default | 0.20 mm | 0.15 mm | 0.6 / 0.3 | 信号、I2C、SPI、按键 |
| **USB90** | **0.24 mm**（差分间隙 **0.18**） | 0.15 mm | 0.45 / 0.2 | `USB_DP*`, `USB_DN*` |
| POWER | 0.80 mm | 0.20 mm | 0.8 / 0.4 | `USB_VBUS_*`, `BAT*`, `SYS`, `3V3_MAIN`, `CHG_SW`, `EPD_SW` |
| HV_EPD | 0.30 mm | 0.20 mm | 0.6 / 0.3 | `EPD_V*`, `EPD_X`, `EPD_GDR`, `EPD_RESE` |

### 4.1 USB 90 Ω 差分线宽/间距

L1 微带线参考 L2 GND，介质 0.195 mm、Dk 4.2、外层成品铜 1 oz
（`tools/usb_impedance.py`，Hammerstad 单端模型 + 边耦合差分修正）：

```
目标 Zdiff = 90 Ω
解：W = 0.243 mm, S = 0.180 mm  →  取 W = 0.24 mm, S = 0.18 mm（约 89.7 Ω）

固定间距对应线宽：
  S = 0.15 mm → W = 0.221 mm
  S = 0.18 mm → W = 0.243 mm
  S = 0.20 mm → W = 0.255 mm
  S = 0.25 mm → W = 0.283 mm
```

已写入 `USB90` Net Class。投板前仍建议板厂按实际材料复算确认（允许 ±10 %）。

设计规则：

```
min track width        0.15 mm     min copper-to-edge     0.30 mm
min clearance          0.15 mm     min hole clearance     0.15 mm
min via                0.40 / 0.20 mm
min through hole       0.20 mm     solder mask min width  0.05 mm
```

---

## 5. 器件放置

### 5.1 机械约束器件

| 要求 | 器件 | 位置 (x, y) | 旋转 | 结果 |
|---|---|---|---|---|
| ESP32 天线朝板边 | U1 | (27.5, 12.75) | 0° | 模块上边缘与板框对齐，天线区外伸；板内 L1~L4 禁布 |
| **USB-C 与 TF 对调后**：USB-C 在板下边中部、外凸 1 mm | J1 | (24.0, 81.33) | 0° | F.Fab 前缘 +1.00 mm 出板，铜箔距板边 0.69 mm |
| TF 座移到右下 | J3 | (42.0, 75.20) | 0° | 卡片从 +Y 出板；座体前缘距板边 0.675 mm（见 §7） |
| 24P FPC 左侧中央、开口向左 | J2 | (4.0, 42.0) | 90° | 开口朝 −X，Y 32.95–51.05 |
| 电池接口左侧、开口向左 | J4 / J5 | (6.0, 62.0) / (6.0, 72.0) | **270°** | Molex PicoBlade 卧式。该封装插口在局部 +Y 侧，**必须 270° 才朝板外**；90° 会插口朝板内 |
| KEY1/2/3 右侧、中心距 27 mm | SW3/SW4/SW5 | (52.85, 15 / 42 / 69) | 90° | 间距 27.00 / 27.00 mm |
| BOOT / RESET（自由） | SW2 / SW1 | (30.0, 29.0) / (22.0, 29.0) | 0° | 模块正下方 |

### 5.2 电源 / 高速簇（本次整改重点）

放置器改成 **围绕锚点螺旋扩散**：锚点先固定，其外围器件从锚点向外逐圈找最近空位，
因此"必须紧贴"的器件自然落在最近的位置。器件按重要性排序，重要的先放。

| 锚点 | 位置 | 就近聚集的器件（按放置优先级） |
|---|---|---|
| J1 USB-C | (24.0, 81.33) | D2/D3（D± ESD）→ D4/D5（CC ESD）→ D1（VBUS TVS）→ F1（保险）→ C6 → C7 → R8 |
| U5 TUSB320LI | (31.5, 73.0) | R11 → R12 → C8 |
| U2 BQ25895 | (34.0, 60.0) | C11（BTST）→ C10（REGN）→ C15（PMID）→ C9（VBUS）→ L1（SW 电感）→ C12（BAT）→ C13/C14（SYS）→ R13（ILIM）→ R16/R17/NTC1（TS）→ 其余 |
| U3 TPS63070 | (34.0, 45.0) | L2 → C18/C19（VIN）→ C20（VOUT）→ C24（VAUX）→ R23/R24（FB 分压）→ 其余 |
| U4 MAX17048 | (13.5, 62.0) | C17 → R22（靠近电池座，远离 BQ SW/L1） |
| J2 EPD FPC | (4.0, 42.0) | U6 → L3 → C28/C30/C31/C32/C33/C35/C36 → C29 |
| **L3（升压电感）** | J2 簇内 | Q1 → D6 → D7 → D8 → R30 → R31（开关环路自成一小簇） |
| **U6（EPD 负载开关）** | J2 簇内 | C25 → C26 → C27 → C34 → R29（3V3 去耦，不占用 FPC 旁空间） |
| U1 ESP32 | (27.5, 12.75) | C1–C5、R1、R2（模块左侧）→ R3/R4/R5（靠按键）→ R9/R10（USB 22 Ω，靠 MCU） |
| J3 microSD | (42.0, 75.2) | C37 → C38 → R32–R36 |
| J4 / J5 | 电池座 | F2 / F3 |

实测"器件 courtyard 到锚点 courtyard"的最大间隙 **11.1 mm**（C33→J2），
绝大多数 < 8 mm；没有出现只能丢到板边的器件。

> 说明：EPD 高压簇共 21 个器件，FPC 座贴左板边、焊盘在座体左侧，
> 因此高压电容只能在 FPC 右侧约 11 mm 范围内排布，这是几何必然。
> 真正对电气性能敏感的是 `EPD_SW` 开关环路（L3/Q1/D6–D8），已单独成簇。

---

## 6. 功能分区

| 区域 | 内容 |
|---|---|
| 顶部 | ESP32-S3 模块 + 天线禁布区 |
| 上部左右 | 模块去耦（左）、USB 前端与 22 Ω 串阻（右） |
| 中部左 | 24P FPC + EPD Booster 簇（U6/L3/Q1/D6–D8 + 高压电容） |
| 中部右 | TPS63070（U3）+ L2 + FB 分压 |
| 中下部 | BQ25895（U2）+ L1 + 充电外围 |
| 左下 | 电池座 J4/J5 + MAX17048（U4）+ F2/F3 |
| 下边中部 | USB-C（J1）+ ESD/TVS/保险 |
| 右下 | microSD（J3） |
| 右侧板边 | KEY1/2/3（中心距 27 mm） |

---

## 7. TF 座外凸说明（用户已接受）

`Hirose DM3AT-SF-PEJM5` 的两个前部固定焊盘位于本体最前端（局部 y 6.4–8.3，
本体前缘 y = 8.125），座体一旦外凸焊盘即出板。实测选择：

```
座体前缘距板边    0.675 mm（在板内）
最前铜箔距板边    0.470 mm
插卡后卡片外伸    约 5 mm（满足插拔可达性）
```

如需座体本身外凸 1 mm，需改选前部焊盘后移的型号。
**2026-09-12 用户确认：接受当前做法。**

---

## 8. DRC 结果（kicad-cli 10.0.5）

```
Errors        : 0
Warnings      : 42      silk_overlap 28 / silk_over_copper 7 /
                        silk_edge_clearance 3 / npth_inside_courtyard 2
Unconnected   : 258     = 尚未布线的飞线（本阶段预期）
Parity        : 0       原理图 ↔ PCB 器件/网络完全一致
```

丝印类告警来自自动摆放、尚未人工整理丝印；`npth_inside_courtyard` 是 2 个上角定位孔
落在 ESP32 天线 courtyard 内（均为 warning，无功能影响）。
同一网络焊盘短路、间距违规、板边间距、阻焊桥、外框成形均为 **0**。

---

## 9. 正式布线顺序（尚未执行）

按整改清单 §11 的次序：

1. **三组开关电源环路**：BQ25895 SW→L1→SYS、TPS63070 L1/L2、EPD Booster
   （短、宽、同层优先、小环路；SW 铜面积最小化）
2. **大电流电源网络**：`USB_VBUS*`、`BAT1_RAW`、`BAT2_RAW`、`BAT_BUS`、`SYS`、`3V3_MAIN`
   优先铺铜而非细线；BAT 支路按单电池完整电流设计
3. **USB 差分**：L1 走线、L2 完整参考、W/S = 0.24/0.18；ESD 靠连接器、22 Ω 靠 MCU
4. **SPI**：`SPI_SCLK`/`SPI_MOSI`/`SPI_MISO`/`EPD_CS_N`/`TF_CS_N`，避开三处开关节点
5. **I2C / INT / GPIO / 按键**
6. **L2 完整 GND**，关键器件 GND 短过孔直连；U2 的 EP 用散热过孔阵列
7. **L3 电源分配**（BAT_BUS / SYS / 3V3_MAIN），避免切碎
8. 铺铜 → Refill Zones → DRC → 丝印整理 → Gerber/钻孔/贴片坐标

---

## 10. 再生方式

```powershell
$py = 'C:\Users\ggkk2\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_sch.py'           # 原理图
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_pcb.py'           # PCB 布局
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\usb_impedance.py'     # USB 90Ω 计算
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\verify_connectors.py' # 连接器外凸复核
```

ERC / DRC 命令见 `agent.md` §八。
