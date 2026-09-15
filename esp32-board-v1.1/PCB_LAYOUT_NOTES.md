# ESP32-S3 + GDEM102T91 V1.5 — PCB 布局说明与状态

> 本文记录 PCB 阶段（placement / stackup / rules / DRC / ERC policy）的实际结果。
> 与 `agent.md`、`SCHEMATIC_NOTES.md` 配套阅读。
> 本轮执行 `ESP32S3_GDEM102T91_Current_Layout_Optimization_Plan.md`
> 的 ①~⑬、⑭（未执行布线）。
> 用户附带约束：**天线区与轻触开关区的定位孔保持现状**。

---

## 0. 本轮（V1.5）执行摘要

| MD 条目 | 内容 | 状态 |
|---|---|---|
| §1 | `KEY_RIGHT_MECH_KEEP_OUT` 改为 **X 49–51 / Y 0–84** 全高阻挡墙 | 已完成 |
| §1.4 | `RIGHT_SWITCH_COLUMN` 只保留机械说明（不再建 keepout 区） | 已完成 |
| §2 | **R33 移出右侧 Column**；R33/R34 移到 U1 SPI 输出端 | 已完成（R33 现距 SPI_SCLK 2.84 mm） |
| §4 | U1 周边 C1~C4 / R1+C5 / R3~R5 重排到模块左侧 | 已完成 |
| §5 | C12 回到 U2 BAT 引脚；C10/C15 收紧 | 已完成（BAT 3.64 mm、PMID 2.37 mm、REGN 4.65 mm） |
| §6 | U3 R23/R24 收紧、L2 靠近 | 已完成（R24 上移，间距 1.81 mm） |
| §7 | C29 进入 EPD Booster 岛；R30/R31 位置 | 已完成（C29 距 D6 EPD_SW 4.51 mm） |
| §11/§12 | 全板 RefDes 重新归位（≤3 mm，空间不足则隐藏） | 已完成：最远 3.30 mm，5 个位号隐藏 |
| §13 | U1 顶部丝印越板边 | 已完成（本地封装裁掉越界线段） |
| §14 | U1 / J3 library footprint mismatch | **已解决**：改用项目本地封装，DRC 0 warning |
| §15/§16 | ERC / DRC 检查策略 | 保持：ERC 全部启用；DRC 仅 tuning / via-center 待布线后开 |
| §18 ⑯ | 正式布线 | **未开始** |

---

## 1. 板框与机械

| 项目 | 值 | 状态 |
|---|---|---|
| 外形 | **55.0 × 84.0 mm**（竖版） | 保持 |
| 圆角 / 层数 / 厚度 | R2 / 4 层 / 1.20 mm | 保持 |
| 定位孔 | 4 × Ø2.2 mm NPTH，(3,3) (52,3) (3,81) (52,81) | **保持不变** |
| 顶部安装孔 | **塑料柱**（2026-09-14 确认），`Dwgs.User` 已标注 | 保持 |
| 测试点 | 无 | 保持 |

---

## 2. 叠层

```
L1  F.Cu     0.035 mm   （外层成品铜厚 1 oz）
    PP 7628  0.195 mm   Dk = 4.2
L2  In1.Cu   0.035 mm   ← 完整 GND 平面
    CORE     0.63 mm    Dk = 4.2
L3  In2.Cu   0.035 mm
    PP 7628  0.195 mm   Dk = 4.2
L4  B.Cu     0.035 mm
```

---

## 3. 规则区（Rule Area）

### 3.1 `KEY_RIGHT_MECH_KEEP_OUT` —— 右侧按键专用列（全高阻挡墙）

```
范围    X 49.0 – 51.0 mm,  Y 0.0 – 84.0 mm      ← V1.5 由 Y11–73 扩为全高
禁止    Footprint
允许    Track / Via / Pad / Copper pour
例外    SW3 / SW4 / SW5 与 H1~H4（定位孔，courtyard 伸入墙体）
```

V1.4 时该墙只覆盖 Y 11–73，R33 因此能从 Y>73 一侧绕进右侧列（MD §1.1）。
扩大为全高后，X>51 一侧只剩三颗按键与四个定位孔。

KiCad 的 zone keepout 无法对个别器件开例外，所以墙体实现为**命名规则区 +
自定义规则**（`esp32-board-v1.1.kicad_dru`）。**已验证规则会真实触发**：
去掉例外后 DRC 恰好报出 H2 / H4 两条 `items_not_allowed`。

### 3.2 `RIGHT_SWITCH_COLUMN` —— 仅机械说明

按 MD §1.4，不再建立"footprints allowed"的 keepout 区以免含义混乱，
只在 `Dwgs.User` 画虚线框并标注
`RIGHT_SWITCH_COLUMN / X 49-55 mm / SW + LOCATING HOLES ONLY`。

### 3.3 `ESP32_ANT_KEEP_OUT` —— 天线禁布区

```
范围    X 16.0 – 39.0 mm,  Y 0.0 – 6.0 mm
层      F.Cu / In1.Cu / In2.Cu / B.Cu
禁止    Track / Via / Pad / Copper pour / Footprint
```

### 3.4 `J3_SOCKET_KEEP_OUT_1..5` —— microSD 卡槽禁布区（新）

厂商封装在卡座下方内嵌了 5 个 rule area（禁走线/过孔/焊盘/铺铜）。
KiCad 的"与库不一致"检查**无法比较封装内嵌的 zone**，保留它们会让
`lib_footprint_mismatch` 永久告警（MD §14）。因此把这 5 个区域**原样提升为
板级规则区**，几何不变、保护不变，但板内封装与项目库完全一致。

---

## 4. 层定义与铺铜

| 层 | 用途 |
|---|---|
| L1 F.Cu | 器件 + 关键信号（USB、SPI）+ 局部电源铜 |
| L2 In1.Cu | **完整 GND 平面** |
| L3 In2.Cu | 电源平面 / 低速信号 |
| L4 B.Cu | 低速信号 + 辅助走线 |

---

## 5. Net Class 与规则

| Net Class | 线宽 | 间距 | Via | 适用网络 |
|---|---|---|---|---|
| Default | 0.20 mm | 0.15 mm | 0.6 / 0.3 | 信号、I2C、SPI、按键 |
| **USB90** | **0.24 mm**（差分间隙 **0.18**） | 0.15 mm | 0.45 / 0.2 | `USB_DP*`, `USB_DN*` |
| POWER | 0.80 mm | 0.20 mm | 0.8 / 0.4 | `USB_VBUS_*`, `BAT*`, `SYS`, `3V3_MAIN`, `CHG_SW`, `EPD_SW` |
| HV_EPD | 0.30 mm | 0.20 mm | 0.6 / 0.3 | `EPD_V*`, `EPD_X`, `EPD_GDR`, `EPD_RESE` |

USB 90 Ω：L1 微带参考 L2，介质 0.195 mm、Dk 4.2、外层 1 oz →
**W 0.24 / S 0.18 mm（≈89.7 Ω）**。

---

## 6. 器件放置

### 6.1 放置引擎

精确矩形碰撞判定 + 解析板框；`GAP = 0.50 mm`（courtyard 间距）。
**引脚级对齐 `PIN_ALIGN` 共 50 个器件**（含两遍补放：C16→R21、R30→Q1 等
锚点本身由轨道放置的条目）。

结果：106 个器件全部放置、courtyard 碰撞 0、最紧间距 0.50 mm。

### 6.2 机械约束器件

| 器件 | 位置 (x, y) | 旋转 | 说明 |
|---|---|---|---|
| U1 ESP32-S3-WROOM-1 | (27.5, 12.75) | 0° | 模块上缘与板框齐平 |
| J1 USB-C | (24.0, 81.33) | 0° | F.Fab 外凸 **+1.00 mm** |
| J3 microSD | (40.0, 75.20) | 0° | 卡片从 +Y 出板 |
| J2 EPD FPC | (5.0, 42.0) | 90° | Amphenol F32Q，开口朝 −X |
| J4 / J5 电池座 | (6.0, 62.0) / (6.0, 72.0) | 270° | 插口朝 −X |
| **SW1 / SW2** | **(22.0, 32.0) / (30.0, 32.0)** | 0° | **本轮下移 3 mm**，为 SPI 串阻让出一行 |
| SW3 / SW4 / SW5 | (52.85, 15 / 42 / 69) | 90° | 中心距 27 mm |

### 6.3 U1 周边（MD §4）

所有 U1 支撑器件移到模块**左侧**两列；需要贴着引脚的电容按 180° 放置，
让供电焊盘朝向模块。

| 器件 | 目标引脚 | 距离 mm | 位置 |
|---|---|---:|---|
| C4 (0.1 µF) | U1 3V3 | **2.33** | 左列最靠近引脚 |
| C3 (1 µF) | U1 3V3 | **2.81** | 左列 |
| C2 (10 µF) | U1 3V3 | 5.82 | 第二列（bulk） |
| C1 (22 µF) | U1 3V3 | 6.13 | 第二列（bulk） |
| R1 (RESET 上拉) | U1 RESET_N | **3.63** | 左列 |
| C5 (RESET 电容) | U1 RESET_N | 与 R1 相邻构成 RC | 左列 |
| R3 / R4 / R5 (KEY 上拉) | U1 KEY1/2/3_N | 6.03 / 6.46 / 5.99 | 第二列统一成列 |
| R9 / R10 (USB 22 Ω) | U1 GPIO20/19 | 3.81 / 3.81 | 保持成对镜像 |
| **R34 / R33 (SPI 串阻)** | U1 SPI_MOSI / SPI_SCLK | **2.34 / 2.84** | 模块下方新行 |

### 6.4 BQ25895（MD §5）

| 器件 | 目标引脚 | 距离 mm | 变化 |
|---|---|---:|---|
| L1 | U2 SW | 3.60 | Center-Y 与 SW 引脚完全一致 |
| C11 (BTST) | U2 BTST | 1.95 | 最小 bootstrap 环路 |
| **C12 (BAT 10 µF)** | U2 BAT13/14 | **3.64** | 由电池端移回充电器 BAT 引脚（§5.1） |
| C13 (SYS 22 µF) | U2 SYS | 5.86 | 留在 U2/L1 输出行（§5.5） |
| C15 (PMID) | U2 PMID | **2.37** | 移到电容堆左侧空位（§5.3） |
| C10 (REGN) | U2 REGN | **4.65** | 上移到 C11 上方空位（§5.2） |
| C9 (VBUS) | U2 VBUS | 2.14 | 保持 |
| R21 / C16 Snubber | CHG_SW / L1 | R21 紧贴 L1 本体，C16 距 R21 2.2 mm | 保持成对（§5.4） |

### 6.5 microSD 行（MD §3）

| 器件 | 目标引脚 | 距离 mm |
|---|---|---:|
| R35 (MISO 串阻) | J3 TF_MISO | **2.96** |
| C38 (0.1 µF) | J3 VDD | **3.60** |
| C37 (10 µF) | J3 VDD | 6.38 |
| R36 (CD 上拉) | J3 TF_CD_N | 6.85 |
| R32 (CS 上拉) | J3 TF_CS_N | 14.47（见 §10） |

### 6.6 EPD / TPS63070（MD §6、§7）

| 器件 | 结果 |
|---|---|
| **C29** | 由高压电容行移入 Booster 岛：距 D6 的 EPD_SW 焊盘 **4.51 mm**、距 D8 的 EPD_X 焊盘 **3.34 mm** |
| R30 | 靠 Q1 Gate（4.30 mm），不在 J2→Q1 走廊 |
| R31 | 靠 Q1 RESE 侧 |
| L2 | 焊盘落在 U3 L1/L2 引脚中心线 |
| R23 → FB | 3.63 mm |
| **R24 → R23** | **1.81 mm**（本轮上移，分压中点更短） |
| C14 / C18 / C19 | U3 输入电容组 |

---

## 7. J2 EPD 连接器

保持 V1.4 决定：**Amphenol F32Q-1A7x1-11024**（24P / 0.5 mm / Top contact），
封装为 KiCad 官方库 land pattern。投板前仍需按 Amphenol 数据手册核对
FPC 厚度 / Locking Direction / Mated Height / 3D 间隙。

---

## 8. 丝印策略（MD §11、§12）

规则（`build_silk()`）：

1. **字号**：小尺寸无源件（0603/0805 R/C/D）0.8 mm / 0.12 mm 笔画；
   IC / 连接器 / 按键 / 电感 1.0 mm / 0.15 mm。
2. **距离**：位号只在自身实体轮廓（F.Fab）外 **0.25 ~ 3.3 mm** 的环带内搜索，
   不再出现 6–10 mm 的漂移（§11.4）。
3. **遮挡**：落在任何器件实体轮廓内的比例 > 25 % 时**隐藏该位号**（§11.5），
   位号仍保留在 F.Fab / 装配图。
4. **评分**：压焊盘（硬禁止）> 被遮挡面积 > 文字相压 > 距离。

结果：**101 个位号可见，5 个隐藏**（C9、C10、C25、C30、R25 —— 均位于
BQ25895 / EPD 高密度岛内）；可见位号最远 **3.30 mm**。
`silk_over_copper` 0、`silk_overlap` **0**（对比整改前：14 个被遮挡、10 处压字）。

MD §12 点名的 U1 / U5 / R35 / J3 / L1 / R21 位号现在分别距本体
0.70 / 0.34 / 0.40 / 0.25 / 3.06 / 1.77 mm。

---

## 9. ERC / DRC 结果

```
ERC           : 0 violations（footprint_link_issues / footprint_filter 均为 error）
DRC Errors    : 0
DRC Warnings  : 0
Unconnected   : 255     = 尚未布线的飞线（本阶段预期）
DRC Exclusions: 0
```

**U1 / J3 的 library footprint mismatch 已彻底消除**（MD §14）：

1. 官方 land pattern 复制为项目本地封装
   `esp32-board-v1.1:ESP32-S3-WROOM-1_EPDF` 与
   `esp32-board-v1.1:microSD_DM3AT-SF-PEJM5_EPDF`；
2. U1 本地封装把 48 × 21 mm 天线禁布 courtyard 裁成**模块实体轮廓**，
   并删掉越出板边的顶部丝印线段（§13）；
3. 两个封装内嵌的 rule area 提升为板级规则区（§3.4）；
4. 生成器不再丢弃封装的 `version / generator` 字段，Value 字段与库一致。

`track_not_centered_on_via` 与 `tuning_profile_track_geometries` 仍按 MD §16
保持 Ignore，布线完成后开启。

---

## 10. 与 MD 清单的差异 / 未满足项

| 项 | MD 期望 | 实际 | 原因 |
|---|---|---|---|
| §3 | R32 靠 J3 CS | 距 CS 焊盘 14.47 mm，但**紧贴 J3 本体左侧**（0.51 mm） | U2↔J3 那条 3.75 mm 带要放 C13、R35、C12、C38、C37 五件（C12 按 §5.1 必须回 BAT 引脚），已无 0603 位置；R32 是上拉，两版 MD 均注明不敏感 |
| §5.1 | C12 距 BAT 2–4 mm | 3.64 mm ✔ | — |
| §5.3 | C15 继续压缩 | 2.37 mm ✔ | — |
| §5.2 | C10 继续压缩 | 4.65 mm | BTST/REGN/PMID 引脚中心距 0.5 mm、0805 本体 3.4 mm，三颗无法都在 3 mm 内 |
| §4.2 | R1/C5 紧靠 RESET | R1 3.63 mm | 3V3 与 RESET 引脚仅相距 1.3 mm，两套网络共用同一条左侧带 |
| §11.5 | 空间不足时隐藏位号 | 已隐藏 5 个 | 若需要全部可见，只能把字号再缩小或接受 4–6 mm 漂移 |
| §14 | mismatch 解决 | 已解决 | 见 §9 |
| §7.1 | C29 进 Booster 岛 | 距 EPD_SW/EPD_X 焊盘 4.5 / 3.3 mm | 岛内已无更近空位（L3/Q1/D6-D8/R31 占满） |
| §19 | 布线前检查表 | 除上述项外全部满足 | 布线未开始 |

---

## 11. 正式布线顺序（尚未执行）

1. 三组开关电源环路：BQ25895 SW→L1→SYS、TPS63070 L1/L2、EPD Booster
2. 大电流电源网络（BAT / SYS / 3V3 / VBUS）优先铺铜
3. USB 差分：ESD 靠连接器、22 Ω 靠 MCU、L2 连续参考、W/S = 0.24/0.18
4. SPI（R33/R34 已在 MCU 端、R35 在卡端）
5. I2C / INT / GPIO / 按键
6. L2 完整 GND；U2 的 EP 用散热过孔阵列
7. L3 电源分配
8. 铺铜 → Refill → DRC（并打开 via-center / tuning 检查）→ Gerber / 钻孔 / 贴片坐标

---

## 12. 再生方式

```powershell
$py = 'C:\Users\ggkk2\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_sch.py'           # 原理图
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_pcb.py'           # PCB 布局 + 丝印
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\usb_impedance.py'     # USB 90Ω 计算
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\verify_connectors.py' # 连接器外凸复核
```

自定义 DRC 规则：`esp32-board-v1.1.kicad_dru`；
项目本地封装：`lib/esp32-board-v1.1.pretty/`（RNM0015A、ESP32-S3-WROOM-1_EPDF、
microSD_DM3AT-SF-PEJM5_EPDF）。
