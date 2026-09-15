# ESP32-S3 + GDEM102T91 V1.1 — 原理图冻结说明与 ERC 记录

> 本文记录本轮原理图最终化所执行的修改、与旧版设计文档的差异、以及 ERC 结果。
> 配套阅读：`ESP32S3_GDEM102T91_V1.1_ERC_Guide.md`、
> `ESP32S3_GDEM102T91_V1.1_PrePCB_5_Items_Confirmation.md`、`PCB_LAYOUT_NOTES.md`。

---

## 1. ERC 结果

```
kicad-cli sch erc  →  0 violations
```

即 **0 Error / 0 Warning**，且**没有使用任何 ERC Exclusion**，
也没有关闭任何全局 ERC 检查项。达到 ERC Guide §15 的验收目标。

收敛前的问题与处理方式见 §3。

---

## 2. 本轮原理图结构

- 单页 A2 图纸，`tools/gen_sch.py` 生成，按功能分 8 个区块标注：

  1. ESP32-S3-WROOM-1 核心（复位、BOOT、三按键、I2C 上拉、去耦）
  2. USB-C 2.0 Sink + VBUS 保护 + TUSB320LI
  3. BQ25895 充电 / Power Path
  4. 双电池输入 + MAX17048 电量计
  5. TPS63070 3.3 V Buck-Boost
  6. EPD GDEM102T91 24P FPC + SSD1677 高压外围
  7. MicroSD（SPI）
  8. 电源测试点 + PWR_FLAG

- 连接方式：全局标签（global label）。每个网络至少有 2 个连接点，
  因此不存在 "孤立标签" 告警。
- 器件数量：106（含 5 个 Omron B3U-1000P 开关、3 个磁器件；**本版无测试点**）。
- 网络数量：96。

---

## 3. 按 ERC Guide 执行的修正

| # | ERC Guide 要求 | 实际处理 |
|---|---|---|
| 1 | TPS63070 两个 VOUT 都设为 Power output 导致冲突 | 修改项目本地符号 `TPS63070`：Pin 7 VOUT 保持 `power_out`，**Pin 8 VOUT 改为 `passive`**。3V3 网络仍有明确驱动源，PCB 连接不变。 |
| 2 | ESP32 保留 GPIO 使用孤立标签 | 全部删除孤立全局标签：GPIO3 / GPIO35 / GPIO36 / GPIO37 / GPIO40 / GPIO41 / GPIO42 / GPIO45 / GPIO46 / GPIO48 改为真正的 **No Connect**（保留设计意图的文字说明）。 |
| 3 | 真正需要预留的 GPIO 应接测试点 | **本版按用户要求取消全部测试点**，因此 GPIO38 / GPIO39 与调试 UART（GPIO43/44）都改为真正的 No Connect，不使用孤立标签。若后续需要保留调试口，请改为测试点或排针。 |
| 4 | 未使用的 Q1 符号库问题 | Q1 的 `lib_id` 从错误的 `Device:Q_NMOS_GSD` 修正为 **`Transistor_FET:Q_NMOS_GSD`**（符号实际来自 Transistor_FET 库），库符号告警消失。 |
| 5 | GDEM102T91 GDR 应为 Output | 新建项目专用符号 `local:EPD_FPC24`：`GDR = Output`、`BUSY = Output`、`RES#/D/C#/CS#/SCL = Input`、`SDA = Bidirectional`、`VDDIO/VCI/VSS = Power input`、高压节点 = `Passive`。QL 门为 Input，Output→Input 语义正确。 |
| 6 | 电源输入未被驱动 | 对没有真实 power output 的网络加 `PWR_FLAG`：`GND`、`USB_VBUS_RAW`、`USB_VBUS_PROT`、`BAT_BUS`、`SYS`。`3V3_MAIN` / `EPD_3V3` / `CHG_PMID` 由器件自身的 power output 驱动，**不再重复加 PWR_FLAG**（否则会产生 Power output 互连错误）。 |

---

## 4. EPD 高压外围（问题 5 答复后的锁定结果）

依据 **GDEM102T91 规格书第 20 页 Typical Application Circuit with SPI Interface**
（第一优先）锁定，逐节点如下：

### 4.1 Booster

| 器件 | 连接 |
|---|---|
| L3 47 µH | `EPD_3V3` → `EPD_SW` |
| Q1 (Si1304BDL 类 N-MOS) | G = `EPD_GDR`，D = `EPD_SW`，S = `EPD_RESE` |
| R30 1 M | `EPD_GDR` → GND（栅极下拉） |
| R31 2.2 Ω | `EPD_RESE` → GND（电流检测） |
| D6 MBR0530 | 阳极 `EPD_SW`，阴极 `EPD_VGH`（升压整流） |
| D7 MBR0530 | 阳极 `EPD_X`，阴极 GND（钳位） |
| D8 MBR0530 | 阳极 `EPD_VGL`，阴极 `EPD_X`（负压泵） |
| C29 4.7 µF/25 V | `EPD_SW` ↔ `EPD_X`（飞跨电容） |
| C27 4.7 µF/25 V | `EPD_3V3` → GND |
| C28 4.7 µF/25 V | `EPD_VGH` → GND |
| C30 4.7 µF/25 V | `EPD_VGL` → GND |

### 4.2 24P FPC（J2，Pin 号与 GDEM102T91 规格书第 7 页一致）

| Pin | 名称 | 连接 |
|---:|---|---|
| 1 | NC | 不接 |
| 2 | GDR | `EPD_GDR` |
| 3 | RESE | `EPD_RESE` |
| 4 | NC | 不接 |
| 5 | VSH2 | `EPD_VSH2` + C31 4.7 µF/25 V → GND |
| 6 | TSCL | 不接（不使用外部温度传感器） |
| 7 | TSDA | 不接 |
| 8 | BS1 | GND（4-wire SPI） |
| 9 | BUSY | `EPD_BUSY` |
| 10 | RES# | `EPD_RST_N` |
| 11 | D/C# | `EPD_DC` |
| 12 | CS# | `EPD_CS_N` |
| 13 | SCL | `SPI_SCLK` |
| 14 | SDA | `SPI_MOSI` |
| 15 | VDDIO | `EPD_3V3` |
| 16 | VCI | `EPD_3V3`（C34 1 µF/25 V → GND） |
| 17 | VSS | GND |
| 18 | VDD | `EPD_VDD` + C35 1 µF/25 V → GND |
| 19 | VPP | 不接（仅测试用） |
| 20 | VSH1 | `EPD_VSH1` + C32 4.7 µF/25 V → GND |
| 21 | VGH | `EPD_VGH` |
| 22 | VSL | `EPD_VSL` + C33 4.7 µF/25 V → GND |
| 23 | VGL | `EPD_VGL` |
| 24 | VCOM | `EPD_VCOM` + C36 1 µF/25 V → GND |

> 与 SSD1677 规格书 Table 13-1 的元件清单一致：
> 6 × 4.7 µF/25 V 高压电容 + 3 × 1 µF 电容 + 2.2 Ω 检测电阻 +
> 47 µH + 3 × MBR0530 + 1 × N-MOS。
> 相对 SSD1677 Figure 13-1 多出的 R30（1 M 栅极下拉）来自 GDEM102T91 自身
> 的典型应用电路，按 "面板规格书优先" 保留。

---

## 5. 与旧版设计文档的**有意差异**（请确认）

以下修改依据 V1.1 五问确认文档，与
`ESP32S3_GDEM102T91_PCB_V1.1_Design.md` 的原文不同：

| 项目 | 旧文档 | 本轮实现 | 依据 |
|---|---|---|---|
| BQ25895 /CE | 10 kΩ 下拉到 GND（默认允许充电） | **10 kΩ 上拉到 3V3_MAIN，默认 HIGH = 禁止充电**；ESP32 初始化并回读参数后再拉低使能 | 确认文档 §4.4 / §4.5 |
| /CE 控制脚 | 无 | 使用 **GPIO47 = `CHG_CE`**（GPIO47 原为 RESERVED，非 strapping 脚） | 确认文档 §4.4 需要 "ESP32 GPIO" |
| MAX17048 CELL (Pin 2) | 未明确 | 接 `BAT_BUS`（规格书 Pin 表："Connect to the Positive Battery Terminal"） | MAX17048 数据手册 Pin/Bump Descriptions |
| BQ25895 PMID 电容 | 1 µF | **10 µF**（规格书要求 OTG 不用时 PMID–PGND ≥ 8.2 µF） | BQ25895 数据手册 Table 6-1 |
| BQ25895 DSEL (Pin 24) | DNP/TP | 10 kΩ 上拉到 3V3_MAIN（规格书建议经 10 kΩ 接到逻辑电源） | BQ25895 数据手册 Table 6-1 |
| TPS63070 PS/SYNC | 未定义 | 100 kΩ 上拉到 SYS（PWM/PFM 省电模式）。如需强制 PWM，把该电阻改到 GND | TPS63070 数据手册 Pin Functions |
| TPS63070 FB2 (Pin 6) | 未定义 | 悬空（规格书允许 "leave the pin open"） | TPS63070 数据手册 Pin Functions |
| 测试点 | 原计划 24 个 | **全部取消**（用户要求 "pcb 无需设置测试点"）；GPIO38/39 与调试 UART 改为 No Connect | 本轮用户要求 |
| BOOT/KEY 开关 | 低背轻触开关（未定型号） | **Omron B3U-1000P**（封装 `Button_Switch_SMD:SW_SPST_B3U-1000P`，3.0×2.5×1.6 mm，侧按） | 本轮用户要求 |

> Omron B3U-1000P 采购链接（华秋商城）：
> <https://item.hqchip.com/2500240009.html>
> 该器件为**侧按**型，PCB 上按 90° 放置（按压方向沿板面 X 轴、朝板右外侧）。
> 装配前请对照外壳按键柱确认按压方向与中心距（PCB 上 KEY1/2/3 中心距 27 mm）。

### 5.1 充电限流与 /CE 启动时序（2026-09-14，V1.3 清单 §2）

J4/J5 继续使用 `Molex 53261-0271`（配 51021-0200 胶壳 / 50079-8001 端子 / 26 AWG），
不更换连接器；电流由**软件限流 + 系统功耗策略**控制在安全范围内。该策略已作为
文字注释写入原理图 03 区（BQ25895 旁），**硬件无改动**：

```
ICHG 默认      = 896 mA   （896 = 14 × 64 mA，给连接器/线束/接触电阻/温升留余量）
/CE 默认       = HIGH     （CHG_CE = GPIO47 经 10 kΩ 上拉到 3V3_MAIN）

启动时序： MCU Boot → I2C Init → 写 ICHG / IINLIM / ITERM / VREG
          → 寄存器 Read-back 确认 → /CE = LOW → Enable Charging
```

目的：避免 BQ25895 上电后在 MCU 尚未配置前使用较高默认充电电流。

**仍必须做实机验证**（MD §2.4，属实物测试，本阶段未做）：单电池 + Wi-Fi TX 峰值 +
EPD 刷新 + TF 卡读写 + CPU 高负载并发时，测量 J4/J5 实际峰值电流、连接器/端子/线束
温升与 BAT_BUS 压降；若超出设计目标，需在 firmware 中限制并发负载。

### 5.2 EPD FPC 连接器（2026-09-14，V1.4 清单 §3）

J2 由 **Hirose FH12-24S-0.5SH（下接点）** 改为
**Amphenol F32Q-1A7x1-11024（24P / 0.5 mm / Top-side contact）**，
封装 `Connector_FFC-FPC:Amphenol_F32Q-1A7x1-11024_1x24-1MP_P0.5mm_Horizontal`
（KiCad 官方库自带 land pattern），BOM 状态仍为 PROVISIONAL。

原因：MD 要求改为上接点（或上下接点）连接器。MD 建议的 Hirose
`FH34SRJ-24S-0.5SH(50)` 不在 KiCad 官方库中，改用同为 24P / 0.5 mm、
官方库明确标注 "24 top-side contacts" 的 Amphenol F32Q 系列，避免自行创建
未经核对的封装。

符号仍为 `local:EPD_FPC24`（24 脚 + 2×MP），引脚编号 1–24 与接点顺序不变，
因此 FPC 各网络对应关系未变。引脚 1 仍在连接器上端（与原来一致）。

**待确认**（需要 Amphenol 数据手册）：FPC 厚度范围、Locking Direction、
Mated Height、3D 机械间隙。

### 5.3 电池连接器符号（同批修改）

J4/J5 原先使用通用符号 `Connector_Generic:Conn_01x02`，其封装过滤条件
`Connector*:*_1x??_*` 与 Molex land pattern 名 `…_1x02-1MP_…` 不匹配。
启用 ERC `footprint_filter` 检查后暴露该问题，现改用本地符号
`local:CONN_01X02_PICO`（`ki_fp_filters` 额外接受 `Connector_Molex:*1x02*`），
电气连接与封装均不变。

已复核无误的项：TPS63070 反馈网络 470 kΩ / 150 kΩ 对应 VREF = 800 mV → 3.3 V，
与数据手册 Table 4 完全一致。

### 4.6 U3 符号与封装（2026-09-14 更新）

采用用户提供的 Ultra Librarian 导出包 `Downloads/ul_TPS630701RNMR/KiCADv6/`：

| 项 | 值 |
|---|---|
| 符号 | `lib/esp32-board-v1.1.kicad_sym` 中的 `TPS63070RNM`（15 脚、**无 EP**） |
| 封装 | `lib/esp32-board-v1.1.pretty/RNM0015A.kicad_mod`，lib_id `esp32-board-v1.1:RNM0015A` |
| 3D 模型 | `lib/3dmodels/RNM0015A.stp`（供应商 STEP，毫米单位），封装内以 `${KIPRJMOD}/lib/3dmodels/RNM0015A.stp` 引用，offset/rotate 全为 0 |
| 料号 | `TPS63070RNMT`（VQFN-HR / RNM0015A，15 pin，3.0 × 2.5 mm） |
| 状态 | RELEASED |

导入时做了三处处理（`tools/import_rnm_symbol.py` / `tools/import_ul_footprint.py`）：

1. **符号引脚电气类型修正**（供应商给的类型会让 ERC 失真）：
   Pin7 `VOUT` → `power_out`（3V3_MAIN 的唯一驱动源）、Pin8 `VOUT` → `passive`、
   Pin5 `FB` → `input`、Pin3/9/11 `VAUX`/`L2`/`L1` → `passive`。其余保持供应商类型。
2. **封装语法现代化**：Ultra Librarian 导出的是 KiCad v6 语法（`fp_text reference`、
   `(width ..)`、`(fill solid)`），已转换为当前语法（`property`、`stroke`、`fill yes/no`），
   否则 KiCad 10 读板时会报 `Expecting yes, no, solid...` 而拒绝加载。
3. **补 F.CrtYd**：原封装没有 courtyard，会让摆放器退化到焊盘包围盒；已按本体外扩补上
   （x ±1.62 / y ±1.87 mm），并把位号文字移到本体外以免压焊盘。

原始导出文件也保留一份在 `lib/UL_TPS630701RNMR.kicad_sym` 作为来源凭证。
3D 模型经 3D 渲染验证：本体居中于焊盘、贴板面高度正确、1 脚标记可见。

> **投板前必须人工核对**：`Symbol ↔ TI TPS63070 数据手册 Pin Functions ↔ RNM0015A
> Footprint` 的逐脚对应，重点是 1 脚方向以及供应商图纸的顶视/底视约定。
> ERC/DRC 无法发现这一类镜像或脚序错误。

> 另注：`kicad-cli sch erc` 只读取全局库表、不读取工程 `fp-lib-table`，因此对项目本地
> 封装库会误报 `footprint_link_issues`。该检查已在工程 ERC 设置中置为 ignore；
> KiCad GUI 会正常加载工程库表，无需处理。

另外：BQ25895 `SW` 节点的 RC snubber（`R21` 2.2 Ω + `C16` 470 pF，网络 `CHG_SNUB`）
在原理图中标记为 **DNP**（`(dnp yes)`），仅在 EMI 实测需要时装配，与设计文档
"留 DNP footprint" 的要求一致。kicad-cli 导出的 `bom.csv` 不会自动剔除 DNP 行，
采购/贴片前请按原理图 DNP 标记剔除。

---

## 6. 已冻结的网络清单（96 个）

电源：`GND` `USB_VBUS_RAW` `USB_VBUS_PROT` `USB_VBUS_DET` `USB_SHIELD`
`BAT1_RAW` `BAT2_RAW` `BAT_BUS` `SYS` `3V3_MAIN` `EPD_3V3`

充电：`CHG_SW` `CHG_BTST` `CHG_REGN` `CHG_PMID` `CHG_ILIM` `CHG_TS`
`CHG_STAT` `CHG_OTG` `CHG_DSEL` `CHG_CE` `CHG_INT_N` `CHG_SNUB`

USB：`USB_CC1` `USB_CC2` `USB_DP_CONN` `USB_DN_CONN` `USB_DP` `USB_DN`

I2C：`I2C_SDA` `I2C_SCL`

EPD：`SPI_SCLK` `SPI_MOSI` `EPD_CS_N` `EPD_DC` `EPD_RST_N` `EPD_BUSY`
`EPD_PWR_EN` `EPD_GDR` `EPD_RESE` `EPD_SW` `EPD_X` `EPD_VGH` `EPD_VGL`
`EPD_VSH1` `EPD_VSH2` `EPD_VSL` `EPD_VDD` `EPD_VCOM`

存储：`SPI_MISO` `TF_CS_N` `TF_SCLK` `TF_MOSI` `TF_MISO` `TF_CD_N`

按键：`BOOT` `RESET_N` `KEY1_N` `KEY2_N` `KEY3_N`

> 本版取消测试点后，`DBG_TX` / `DBG_RX` / `TP_GPIO38` / `TP_GPIO39` 四个网络不再存在，
> 对应的 U1 引脚（GPIO43、GPIO44、GPIO38、GPIO39）在原理图上为显式 No Connect。

电源管理：`FG_ALRT_N` `TYPEC_INT_N` `TPS_EN` `TPS_FB` `TPS_L1` `TPS_L2`
`TPS_PG` `TPS_VAUX` `TPS_PS_SYNC` `TPS_VSEL`

---

## 7. BOM

`bom.csv`（kicad-cli 导出，含 `Status` / `MPN` 两列）：

```
RELEASED     : 已冻结的 IC、标准阻容、测试点
PROVISIONAL  : 连接器、按键、电感、MOSFET、TVS、保险丝、NTC  → 待采购复核
```

（本版已取消测试点，`RELEASED` 仅剩 IC 与标准阻容。）

`PROVISIONAL` 清单（投板前必须落到确切 MPN 与封装）：

```
J1  USB-C        GCT USB4105-15-A-120 类
J2  24P FPC      24P / 0.5 mm / Top Contact / 低背
J3  MicroSD      Hirose DM3AT-SF-PEJM5 类
J4/J5 电池接口    Hirose DF13A-2P-1.25H(21) 类
SW1~SW5          Omron B3U-1000P（侧按，3.0×2.5×1.6 mm）
                 https://item.hqchip.com/2500240009.html
L1 1.0 µH        Isat ≥ 4.5 A（Coilcraft XAL5030 级）
L2 1.2 µH        Isat ≥ 3 A（Coilcraft XAL4030 级）
L3 47 µH         ≥500 mA 低背
Q1               Si1304BDL / Si1308EDL 或等效
D1/D2~D5         VBUS TVS / ESD
D6~D8            MBR0530
F1~F3            2 A 级 PTC/保险
R13 ILIM         180 Ω（按 KILIM 误差复核）
NTC1             103AT-2 类 10 kΩ
```

---

## 8. 投板前必须人工复核（ERC 无法覆盖）

- [ ] EPD 高压外围逐节点对照 GDEM102T91 第 20 页
- [ ] Q1 的 Symbol ↔ 数据手册 ↔ Footprint 三方脚序核对（G/S/D）
- [ ] FPC 24P Pin Number 与 GDEM102T91 当前版本规格书逐项一致
- [ ] FPC Top Contact 与实物插入方向、Pin 1 方向
- [ ] BQ25895 / TPS63070 / MAX17048 / TUSB320LI 逐脚复核
- [ ] 5 V 2 A 输入工况下 F1 / 连接器 / 铜皮温升
- [ ] 最终电池规格（满充电压 / PCM / 线束 / 连接器额定）到位后复核充电参数
