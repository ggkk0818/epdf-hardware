# 引脚定义（PINOUT）

> 来源：EasyEDA 工程 `esp32s3-board-v2.0` 原理图 P1/P2 网表现场回读（2026-10-10）。
> 模组引脚号 = ESP32-S3-WROOM-1 的物理引脚序号（1–41），GPIO 名取自原理图符号引脚名。

---

## 1. 主控 ESP32-S3-WROOM-1（U1）完整引脚表

| 模组脚 | GPIO | 网络名 | 方向 | 功能 | 外部偏置 |
|---:|---|---|---|---|---|
| 1 | - | `GND` | 电源 | 地 | - |
| 2 | - | `3V3_MAIN` | 电源 | 3.3 V 供电（C1 22 µF / C2 10 µF / C3 1 µF / C4 100 nF 就近去耦） | - |
| 3 | EN | `RESET_N` | 输入 | 芯片复位（低有效） | R1 10 kΩ 上拉到 3V3；C5 1 µF 到地；SW1 按下拉低 |
| 4 | **GPIO4** | `KEY1_N` | 输入 | 用户按键 1（SW3） | R3 10 kΩ 上拉；按下=低 |
| 5 | **GPIO5** | `KEY2_N` | 输入 | 用户按键 2（SW4） | R4 10 kΩ 上拉；按下=低 |
| 6 | **GPIO6** | `EPD_PWR_EN` | 输出 | 墨水屏 3.3 V 负载开关使能（TPS22918 U6） | R29 100 kΩ 下拉 → **上电默认关断** |
| 7 | **GPIO7** | `EPD_BUSY` | 输入 | 墨水屏忙标志（面板输出） | 无（面板驱动） |
| 8 | **GPIO15** | `KEY3_N` | 输入 | 用户按键 3（SW5） | R5 10 kΩ 上拉；按下=低 |
| 9 | **GPIO16** | `CHG_INT_N` | 输入 | BQ25895 中断 `/INT`（低有效，开漏） | R14 10 kΩ 上拉 |
| 10 | **GPIO17** | `TYPEC_INT_N` | 输入 | TUSB320LI 中断 `INT_N`（低有效，开漏） | R12 10 kΩ 上拉 |
| 11 | **GPIO18** | `I2C_SDA` | 双向 | I2C 数据（三颗从机共用） | R6 4.7 kΩ 上拉到 3V3 |
| 12 | **GPIO8** | `EPD_RST_N` | 输出 | 墨水屏复位（低有效） | 无 |
| 13 | **GPIO19** | `USB_DN` | USB | USB D−（原生 USB） | R10 22 Ω 串阻到 USB-C |
| 14 | **GPIO20** | `USB_DP` | USB | USB D+（原生 USB） | R9 22 Ω 串阻到 USB-C |
| 15 | GPIO3 | *(NC)* | - | 未连接（strap 引脚，悬空） | - |
| 16 | GPIO46 | *(NC)* | - | 未连接（strap 引脚，悬空） | - |
| 17 | **GPIO9** | `EPD_DC` | 输出 | 墨水屏 D/C#（1=数据，0=命令） | 无 |
| 18 | **GPIO10** | `EPD_CS_N` | 输出 | 墨水屏片选（低有效） | 无 |
| 19 | **GPIO11** | `SPI_MOSI` | 输出 | SPI MOSI（墨水屏 + microSD 共用） | 经 R34 0 Ω 到 `TF_MOSI` |
| 20 | **GPIO12** | `SPI_SCLK` | 输出 | SPI SCLK（墨水屏 + microSD 共用） | 经 R33 0 Ω 到 `TF_SCLK` |
| 21 | **GPIO13** | `SPI_MISO` | 输入 | SPI MISO（**只接 microSD**，墨水屏无 MISO） | 经 R35 0 Ω 到 `TF_MISO` |
| 22 | **GPIO14** | `TF_CS_N` | 输出 | microSD 片选（低有效） | R32 10 kΩ 上拉 |
| 23 | **GPIO21** | `I2C_SCL` | 双向 | I2C 时钟 | R7 4.7 kΩ 上拉到 3V3 |
| 24 | **GPIO47** | `CHG_CE` | 输出 | BQ25895 `/CE`（低=允许充电） | R18 10 kΩ 上拉 → **上电默认禁充** |
| 25 | GPIO48 | *(NC)* | - | 未连接 | - |
| 26 | GPIO45 | *(NC)* | - | 未连接（strap 引脚，悬空） | - |
| 27 | **GPIO0** | `BOOT` | 输入 | BOOT / 下载模式（低电平进入下载） | R2 10 kΩ 上拉；SW2 按下拉低 |
| 28 | GPIO35 | *(NC)* | - | 未连接 | - |
| 29 | GPIO36 | *(NC)* | - | 未连接 | - |
| 30 | GPIO37 | *(NC)* | - | 未连接 | - |
| 31 | **GPIO38** | `LED_DIN` | 输出 | WS2812 数据（LED1） | 经 R37 33 Ω |
| 32 | GPIO39 | *(NC)* | - | 未连接 | - |
| 33 | GPIO40 | *(NC)* | - | 未连接 | - |
| 34 | GPIO41 | *(NC)* | - | 未连接 | - |
| 35 | GPIO42 | *(NC)* | - | 未连接 | - |
| 36 | RXD0 / GPIO44 | *(NC)* | - | 未连接 | - |
| 37 | TXD0 / GPIO43 | *(NC)* | - | 未连接 | - |
| 38 | **GPIO2** | `TF_CD_N` | 输入 | microSD 卡检测（内部无卡=高） | R36 10 kΩ 上拉；插卡=低 |
| 39 | **GPIO1** | `FG_ALRT_N` | 输入 | MAX17048 报警 `ALRT`（低有效，开漏） | R22 10 kΩ 上拉 |
| 40 | - | `GND` | 电源 | 地 | - |
| 41 | - | `GND` | 电源 | 地（模组底部散热焊盘也接地） | - |

### 1.1 已用 / 未用统计

* **已引出功能脚（22 个）**：GPIO0、1、2、4、5、6、7、8、9、10、11、12、13、14、15、16、17、18、19、20、21、38、47（含 EN）。
* **未连接（14 个）**：GPIO3、GPIO35、GPIO36、GPIO37、GPIO39、GPIO40、GPIO41、GPIO42、GPIO43(TXD0)、GPIO44(RXD0)、GPIO45、GPIO46、GPIO48。
* ⚠️ **本板没有预留扩展排针**，上述未用 GPIO 均为悬空 No-Connect。若固件需要更多 IO，
  必须改板（飞线到模组焊盘或改版），不能靠软件开启。
* Strapping 引脚现状：**GPIO0** 有 10 kΩ 上拉 + BOOT 按键（正常启动为高）；
  **GPIO3 / GPIO45 / GPIO46** 悬空（默认电平，ESP32-S3 正常启动）；
  GPIO19/20 用作 USB，USB 上电时不要复用为普通 IO。

### 1.2 Arduino 常用映射（见 `platformio/include/board_pins.h`）

```cpp
#define PIN_KEY1        4   // SW3, 低有效
#define PIN_KEY2        5   // SW4, 低有效
#define PIN_KEY3       15   // SW5, 低有效
#define PIN_EPD_PWR_EN  6   // 高=墨水屏上电
#define PIN_EPD_BUSY    7   // 高=忙
#define PIN_EPD_RST     8   // 低有效
#define PIN_EPD_DC      9
#define PIN_EPD_CS     10   // 低有效
#define PIN_SD_CS      14   // 低有效
#define PIN_SD_CD       2   // 低=已插卡
#define PIN_I2C_SDA    18
#define PIN_I2C_SCL    21
#define PIN_CHG_INT    16   // BQ25895 /INT, 低有效
#define PIN_TYPEC_INT  17   // TUSB320 INT_N, 低有效
#define PIN_FG_ALRT     1   // MAX17048 ALRT, 低有效
#define PIN_CHG_CE     47   // 低=允许充电
#define PIN_LED_DIN    38   // WS2812
#define PIN_BOOT        0
#define PIN_SPI_SCK    12
#define PIN_SPI_MOSI   11
#define PIN_SPI_MISO   13
```

---

## 2. 墨水屏 24P / 0.5 mm FPC（J2，`X05B20U24T`）

面板侧引脚名取自 Good Display **GDEM102T91** 数据手册第 5 节（p7）的 Input/Output Pin Assignment，
与 PCB 侧网络逐脚对应：

| FPC 脚 | 面板侧名称（GDEM102T91） | PCB 网络 | 方向（对 MCU/板） | 说明 |
|---:|---|---|---|---|
| 1 | NC（Keep Open） | *(NC)* | - | 空脚 |
| 2 | **GDR** | `EPD_GDR` | 面板输出 → 板 | N-MOSFET 栅驱动控制，驱动板载升压（Q1，R30 1 MΩ 到地） |
| 3 | **RESE** | `EPD_RESE` | 面板输入 ← 板 | 控制环电流检测输入（板侧 R31 2.2 Ω 取样到地） |
| 4 | NC（Keep Open） | *(NC)* | - | 空脚 |
| 5 | **VSH** | `EPD_VSH2` | 电源 | 正源极驱动电压（C31 4.7 µF） |
| 6 | **TSCL** | *(NC)* | - | 面板内部数字温度传感器 I2C 时钟，**本板未接** |
| 7 | **TSDA** | *(NC)* | - | 面板内部数字温度传感器 I2C 数据，**本板未接** |
| 8 | **BS1** | `GND` | 配置 | 接口选择脚，本板**接地固定** |
| 9 | **BUSY** | `EPD_BUSY` | 面板输出 → **GPIO7** | 忙标志 |
| 10 | **RES#** | `EPD_RST_N` | **GPIO8** → 面板 | 复位，低有效 |
| 11 | **D/C#** | `EPD_DC` | **GPIO9** → 面板 | 1=数据，0=命令 |
| 12 | **CS#** | `EPD_CS_N` | **GPIO10** → 面板 | 片选，低有效 |
| 13 | **SCL** | `SPI_SCLK` | **GPIO12** → 面板 | SPI 时钟 |
| 14 | **SDA** | `SPI_MOSI` | **GPIO11** → 面板 | SPI 数据（单向写入） |
| 15 | **VDDIO** | `EPD_3V3` | 电源 | 接口逻辑电源（TPS22918 输出，C25/C26/C34/C27 去耦） |
| 16 | **VCI** | `EPD_3V3` | 电源 | 芯片电源输入 |
| 17 | **VSS** | `GND` | 电源 | 地 |
| 18 | **VDD** | `EPD_VDD` | 电源 | 核心逻辑电源（C35 1 µF） |
| 19 | **VPP** | *(NC)* | - | 测试用，**保持开路**（与手册 "Keep Open" 一致） |
| 20 | **VSH1** | `EPD_VSH1` | 电源 | 正源极驱动电压（C32 4.7 µF） |
| 21 | **VGH** | `EPD_VGH` | 电源 | 栅极正高压（C28 4.7 µF） |
| 22 | **VSL** | `EPD_VSL` | 电源 | 负源极驱动电压（C33 4.7 µF） |
| 23 | **VGL** | `EPD_VGL` | 电源 | 栅极负高压（C30 4.7 µF） |
| 24 | **VCOM** | `EPD_VCOM` | 电源 | 公共电压（C36 1 µF） |
| 25 / 26 | - | *(NC)* | 机械 | FPC 固定焊盘（非电气） |

⚠️ **该面板 FPC 没有 MISO/SDO 脚**（SPI 是单向写），固件里 `SPI_MISO`(GPIO13) 只用于 microSD。
⚠️ 面板内部温度传感器（脚 6/7，TSCL/TSDA）**未接到 MCU**，无法读屏温 —— 波形/LUT 需按固定温度
或使用板载 NTC（`NTC1`，测的是板温）来补偿。

---

## 3. microSD 卡座（J3，`DM3AT-SF-PEJM5`，SPI 模式）

| 脚 | 网络 | 说明 |
|---:|---|---|
| 1 | *(NC)* | 空脚 |
| 2 | `TF_CS_N` | 片选 ← **GPIO14**（R32 10 kΩ 上拉） |
| 3 | `TF_MOSI` | 数据入 ← `SPI_MOSI`（GPIO11，经 R34 0 Ω） |
| 4 | `3V3_MAIN` | 3.3 V 供电 |
| 5 | `TF_SCLK` | 时钟 ← `SPI_SCLK`（GPIO12，经 R33 0 Ω） |
| 6 | `GND` | 地 |
| 7 | `TF_MISO` | 数据出 → `SPI_MISO`（GPIO13，经 R35 0 Ω） |
| 8 | *(NC)* | 空脚 |
| 9 | `TF_CD_N` | 卡检测 → **GPIO2**（R36 10 kΩ 上拉，插卡=低） |
| 10–14 | `GND` | 外壳/屏蔽地 |

> 屏幕与卡共用 SCLK/MOSI，**MISO 只有卡在用**；两侧通过 0 Ω 电阻（R33/R34/R35）连接，
> 便于调试时断开隔离。软件上必须严格互斥访问，切换前把另一路的 CS 拉高 ≥ 1 µs。

---

## 4. 按键

| 位号 | 功能 | 网络 | MCU 引脚 | 上拉 | 有效电平 | 备注 |
|---|---|---|---|---|---|---|
| SW1 | 复位 | `RESET_N` | EN（模组脚 3） | R1 10 kΩ | 低 | 硬复位，非 GPIO |
| SW2 | BOOT / 下载 | `BOOT` | **GPIO0** | R2 10 kΩ | 低 | 按住上电或复位进入下载模式 |
| SW3 | 用户键 1（右侧） | `KEY1_N` | **GPIO4** | R3 10 kΩ | 低 | 壳体顶部按压 |
| SW4 | 用户键 2（右侧） | `KEY2_N` | **GPIO5** | R4 10 kΩ | 低 | 壳体顶部按压 |
| SW5 | 用户键 3（右侧） | `KEY3_N` | **GPIO15** | R5 10 kΩ | 低 | 壳体顶部按压 |

> 三颗用户键均为**接地式 + 上拉**，不需要外部电源；软件用 `INPUT_PULLUP` 亦可（外部已有 10 kΩ）。
> 现场实测按键中心间距为 **17 mm**（25 / 42 / 59 mm，自板顶边），与需求文档早期的 27 mm 不同，
> 见 `PCB_INTERFACE_POSITIONS.md` §11.2 —— **对固件无影响**。

---

## 5. 指示灯 WS2812C-4020-V6（LED1）

| 引脚 | 网络 | 说明 |
|---|---|---|
| 1 (DIN) | `WS2812_DIN` | 数据入 ← R37 **33 Ω** ← `LED_DIN`（**GPIO38**） |
| 2 (VDD) | `3V3_MAIN` | **3.3 V 供电**（按 3.3 V 选型的 V6 版本） |
| 3 (DOUT) | *(NC)* | 未使用（单颗，不级联） |
| 4 (VSS) | `GND` | 地 |

> 单颗 LED，数据格式与 WS2812B 兼容（GRB，800 kHz）。驱动库可用 Adafruit NeoPixel /
> FastLED，注意 3.3 V 供电时颜色亮度略低，且模组输出高电平 3.3 V 已在器件允许范围内。
> 上电后 GPIO38 悬空可能让 LED 出现随机闪烁，建议 `setup()` 里先 `pinMode(PIN_LED_DIN, OUTPUT); digitalWrite(PIN_LED_DIN, LOW);`。

---

## 6. USB-C（J1，`USB4105-GF-A-120`，USB 2.0 Sink）

| 引脚 | 网络 | 说明 |
|---|---|---|
| A4/B9、B4/A9 | `USB_VBUS_RAW` | VBUS → F1（2 A PPTC）→ `USB_VBUS_PROT` → BQ25895；R11 900 kΩ 分压给 TUSB320 VBUS_DET |
| A6/B6 | `USB_D_P` | D+ → R9 22 Ω → `USB_DP`（**GPIO20**）；D2 ESD |
| A7/B7 | `USB_D_N` | D− → R10 22 Ω → `USB_DN`（**GPIO19**）；D3 ESD |
| A5 / B5 | `USB_CC1` / `USB_CC2` | 到 TUSB320LI（U5），各自有 ESD D4/D5 |
| A8 / B8 | *(NC)* | SBU1/SBU2 未使用 |
| A1-B12、B1-A12 | `GND` | 地 |
| 1–4（屏蔽壳） | `USB_SHIELD` | 经 R8 0 Ω 接 GND，C7 1 nF 并联 |

---

## 7. 电源网络一览（软件只需知道"哪些网是电"）

| 网络 | 电压 | 来源 | 说明 |
|---|---|---|---|
| `USB_VBUS_RAW` | 5 V（USB） | J1 VBUS | 经 F1 后为 `USB_VBUS_PROT` |
| `USB_VBUS_PROT` | 5 V | F1 + D1 TVS | BQ25895 VBUS 输入 |
| `BAT1_RAW` / `BAT2_RAW` | 电池电压 | J4 / J5 | 各自经 F2 / F3 汇入 `BAT_BUS` |
| `BAT_BUS` | 电池电压 | F2/F3 | BQ25895 BAT 脚 + MAX17048 VCELL 采样点（**电量计测的就是这个节点**） |
| `CHG_PMID` / `CHG_SW` | 开关节点 | BQ25895 | 电感 L1 1 µH 接 SYS |
| `SYS` | 3.0–4.4 V | BQ25895 | 系统母线（NVDC power path 输出） |
| `3V3_MAIN` | **3.3 V** | TPS63070 升降压 | 全板主电源（MCU / I2C 上拉 / 传感器 / LED） |
| `EPD_3V3` | 3.3 V（门控） | TPS22918 ← 3V3_MAIN | 由 GPIO6 控制，供墨水屏 |
| `EPD_VGH/VGL/VSH1/VSH2/VSL/VCOM/EPD_VDD` | 面板高压 | 板载升压 + 面板 | **软件不可控**，由面板开关波形产生 |

---

## 8. 复位与时钟

| 项 | 说明 |
|---|---|
| 复位 | EN 脚：R1 10 kΩ 上拉 + C5 1 µF 延时；SW1 手动复位 |
| 晶振 | 模组内置 40 MHz 晶振，**无需外部晶振** |
| 天线 | 模组 PCB 天线位于板上边缘；板上有全层禁布区（不可走线/铺铜），**不要在该区域放置金属件** |
