# 电源与充电机制

> 硬件来源：原理图 P1（USB-C 输入/保护、充电管理 BQ25895、电量计 MAX17048、Type-C 检测 TUSB320、
> 3V3 升降压 TPS63070、EPD 电源开关 TPS22918、电池接口 J4/J5）。
> 寄存器数值取自本地数据手册原文（TI BQ25895、Maxim MAX17048/49、TI TUSB320LI），括号内为手册章节/页码。

---

## 1. 电源树

| 节点 | 电压 | 来源 | 下游 |
|---|---|---|---|
| `USB_VBUS_RAW` | 5 V | USB-C J1 VBUS（A4/B9、B4/A9） | F1 2 A PPTC、R11 900 kΩ（VBUS_DET 分压） |
| `USB_VBUS_PROT` | 5 V | F1 → D1 TVS 钳位 | BQ25895 VIN（U2.1）、C6/C9 1 µF |
| `BAT1_RAW` / `BAT2_RAW` | 电池 | J4 / J5 | F2 / F3 2 A PPTC |
| `BAT_BUS` | 电池 | F2 / F3 汇流 | BQ25895 BAT、MAX17048 VCELL、C12 10 µF、C17 100 nF |
| `SYS` | 3.0–4.4 V | BQ25895（L1 1 µH 开关节点 `CHG_SW`） | TPS63070 VIN、C13/C14/C18/C19 |
| `3V3_MAIN` | **3.3 V** | TPS63070 升降压（L2 1.2 µH） | ESP32-S3、I2C 上拉、LED1、TPS22918、microSD |
| `EPD_3V3` | 3.3 V（受控） | TPS22918（GPIO6 使能） | 墨水屏 J2 脚 15/16 + 板载升压 |

### 1.1 关键器件

| 位号 | 型号 | LCSC | 作用 |
|---|---|---|---|
| U2 | BQ25895RTWT | C2861263 | 单节锂电充电器 + NVDC 电源路径 + I2C |
| U3 | TPS63070RNMT | C964639 | 升降压 3.3 V（VIN 2.0–16 V），FB = R23 470 kΩ / R24 150 kΩ |
| U4 | MAX17048G+T10 | C2682616 | ModelGauge 电量计（I2C） |
| U5 | TUSB320LIRWBR | C2836598 | USB Type-C CC 检测 / 电流档位（I2C） |
| U6 | TPS22918DBVR | C131941 | 墨水屏 3.3 V 负载开关（可调压摆率） |
| F1/F2/F3 | BSMD0805L-200-12V | C48392678 | 2 A PPTC 自恢复保险 |
| L1 / L2 | 1 µH / 1.2 µH | C49581188 / C167204 | 充电器 / 升降压电感 |

### 1.2 TPS63070 输出电压

`VOUT = 0.8 V × (1 + R23/R24) = 0.8 × (1 + 470 k/150 k) = 3.307 V`

`TPS_EN`(U3.14) 由 R26 10 kΩ 从 `SYS` 上拉 = **默认使能**；`PS/SYNC`(U3.1) 经 R27 100 kΩ 上拉 = 强制 PWM；
`VSEL`(U3.15) 经 R28 100 kΩ 下拉；`PG`(U3.2) 经 R25 10 kΩ 上拉（**PG 未接 MCU**）。
→ 只要 `SYS` 有电，3.3 V 就会建立，MCU 无需软件使能。

---

## 2. BQ25895 硬件配置（本板实际接法）

| 引脚 | 网络 | 外围 | 说明 |
|---|---|---|---|
| VIN (1) | `USB_VBUS_PROT` | C6/C9 1 µF、D1 TVS | USB 5 V 输入 |
| ILIM (10) | `CHG_ILIM` | **R13 180 Ω 到地** | 硬件输入限流 `IINMAX = KILIM/RILIM`，KILIM = 320/355/390 A·Ω → **≈1.78 / 1.97 / 2.17 A** |
| TS (11) | `CHG_TS` | **REGN —R16 5.23 kΩ— TS —(NTC1 10 kΩ ∥ R17 30.1 kΩ)— GND** | JEITA 温度检测（NTC B25/85 = 3435 K） |
| STAT (4) | `CHG_STAT` | **R15 10 kΩ 上拉到 3V3_MAIN，未接 MCU** | `/CHG` 状态灯输出，固件读不到 |
| /CE (9) | `CHG_CE` | **R18 10 kΩ 上拉**，接 **GPIO47** | 低电平允许充电 → **复位后默认禁止充电** |
| OTG (8) | `CHG_OTG` | **R19 100 kΩ 下拉** | OTG 升压默认关闭 |
| DSEL (24) | `CHG_DSEL` | **R20 10 kΩ 上拉** | 开漏输出：D+/D- 检测进行中拉低 |
| /INT (7) | `CHG_INT_N` | R14 10 kΩ 上拉，接 **GPIO16** | 状态/故障变化时拉低 |
| SCL/SDA (5/6) | `I2C_SCL` / `I2C_SDA` | 4.7 kΩ 上拉 | I2C 地址 **0x6A** |
| SW (19/20) | `CHG_SW` | L1 1 µH → `SYS`；C11 47 nF（BTST 自举） | 开关节点 |
| BAT (13/14) | `BAT_BUS` | C12 10 µF + C17 100 nF | 电池端 |
| SYS (15/16) | `SYS` | C13 22 µF、C14 22 µF、C18 10 µF、C19 10 µF | 系统端 |
| REGN (22) | `CHG_REGN` | C10 4.7 µF | 内部 LDO，供 TS 分压 |
| PMID (23) | `CHG_PMID` | C15 10 µF | PMID 电容 |

### 2.1 输入限流的硬件上限

```
IINMAX = KILIM / RILIM，RILIM = R13 = 180 Ω，KILIM = 355 A·Ω(典型)
       ≈ 1.97 A
```

* `EN_ILIM`(REG00 bit6) 复位值为 **1**（使能 ILIM 引脚），所以**实际输入限流 = min(IINLIM 寄存器, ILIM 引脚上限)**。
* ILIM 引脚不支持 < 500 mA 的限流：要设更小的输入电流，必须靠 **IINLIM 寄存器**（把 `EN_ILIM` 清 0 可由寄存器独占控制）。

### 2.2 温度检测（NTC）

| 参数 | 值 |
|---|---|
| NTC1 | 10 kΩ @25 °C，B25/85 = 3435 K（0603） |
| 上臂 R16 | 5.23 kΩ（REGN → TS） |
| 下臂 R17 | 30.1 kΩ（TS → GND，与 NTC 并联） |
| 25 °C 时 TS 电压 | ≈ REGN × 7.52 k/(5.23 k+7.52 k) ≈ **59% of REGN** |

> ⚠️ NTC 贴在**板上靠近电池接口处**，测的是**板温/环境温度**，不是电芯内部温度。
> 若产品需要真实电芯温度保护，需改用带 NTC 的电池包（3 线接口）。
> JEITA 阈值可通过 REG01（BHOT/BCOLD）与 REG0C 的 `NTC_FAULT[2:0]` 读取。

---

## 3. 充电机制（NVDC Power Path）

```text
VBUS  ──► [BQ25895] ──► SYS ──► [TPS63070] ──► 3V3_MAIN
             ▲  │
             │  └──► BAT_BUS ──► 电池 J4/J5
             │
     I2C ◄───┘ + /INT + /CE
```

* **NVDC 结构**：系统优先由 VBUS 供电，电池只在系统功率不足时补充；电池未接/电量低时，
  `SYS` 仍能维持在 `SYS_MIN`（默认 3.5 V）以上，MCU 不会掉电重启。
* **插拔行为**：支持 USB 与电池同时接入；VBUS 路径与电池路径由芯片自动仲裁。
* **默认（复位后）状态**（来自数据手册 §8.4 各寄存器复位值）：

| 寄存器 | 默认值 | 含义 |
|---|---|---|
| REG00 `0x00` | `0x08` | EN_HIZ=0、EN_ILIM=1、**IINLIM = 500 mA** |
| REG03 `0x03` | `0x3A` | OTG_CONFIG=1、CHG_CONFIG=1、SYS_MIN=3.5 V |
| REG04 `0x04` | `0x20` | **ICHG = 2048 mA** |
| REG05 `0x05` | `0x13` | IPRECHG = 128 mA、**ITERM = 256 mA** |
| REG06 `0x06` | `0x5E` | **VREG = 4.208 V**、BATLOWV = 3.0 V、VRECHG = 100 mV |
| REG07 `0x07` | `0x9D` | EN_TERM=1、**看门狗 40 s 开启**、充电安全定时器 12 h |

### 3.1 ⚠️ 两个必须处理的默认行为

1. **看门狗（WATCHDOG）默认 40 s 且开启**。设备上电后处于"默认模式"，只要看门狗超时，
   芯片会**回到默认模式并丢弃主机写入的寄存器值**（表现为充电电流回落到 2 A 默认值或被限流）。
   两种正确做法（二选一）：
   * **关闭看门狗**：把 REG07 的 `WATCHDOG[1:0]` 写 `00`（数据手册 §8.3.x 明确："disable watchdog timer by setting WATCHDOG bits = 00"）；
   * 或者**每 40 s 内写一次 `WD_RST`(REG07 bit6)=1** 喂狗。
2. **`OTG_CONFIG` 复位值为 1**，而 OTG 引脚经 R19 100 kΩ 下拉（默认禁用升压）。
   为避免任何"电池经 VBUS 反灌 USB 口"的风险，建议固件初始化时**显式写 OTG_CONFIG = 0**。

---

## 4. 固件初始化清单（推荐顺序）

```text
① 上电后 GPIO47(CHG_CE) 保持高 → 充电被硬件禁止（安全默认）
② I2C 初始化（400 kHz 以内，建议先用 100 kHz 调试）
③ 读 DEVICE 确认通信：REG0B 的 PG_STAT / VBUS_STAT 能反映 USB 是否插入
④ 关闭看门狗：REG07 ← 0x8D   （EN_TERM=1, WATCHDOG=00, EN_TIMER=1, 12 h）※ 见下方位说明
⑤ 关 OTG：REG03 ← 0x2A      （OTG_CONFIG=0, CHG_CONFIG=1, SYS_MIN=3.5 V）
⑥ 写充电参数：
     REG00 ← IINLIM（按适配器能力；建议 0x10 = 900 mA，或 0x08 = 500 mA 保守值）
     REG04 ← ICHG   （建议 0x0E = 896 mA，与硬件热设计一致）
     REG05 ← ITERM  （建议 0x11 = IPRECHG 128 mA / ITERM 128 mA）
     REG06 ← VREG   （保持默认 0x5E = 4.208 V）
⑦ 逐条回读校验（不匹配则重试一次，仍失败则保持禁充并上报）
⑧ GPIO47 拉低 → 允许充电
⑨ 之后按 /INT(GPIO16) 事件或 1 s 轮询读取状态
```

> 第 ④ 步的 `0x8D` = `1000 1101`：EN_TERM=1、STAT_DIS=0、**WATCHDOG=00（关闭）**、
> EN_TIMER=1、CHG_TIMER=10（12 h）。位定义见数据手册 §8.4.8 REG07（p39）。
> 第 ⑤ 步的 `0x2A` = `0010 1010`：OTG_CONFIG=0、CHG_CONFIG=1、SYS_MIN=101(3.5 V)。
> 若你的固件允许边走边充，第 ④ 步也可以改成"保留看门狗 + 周期性写 `WD_RST`"。

### 4.1 充电电流的取值依据

| 项 | 值 | 说明 |
|---|---|---|
| 设计目标 ICHG | **≈896 mA**（REG04 = 14 → 14 × 64 mA） | 由连接器/线束热预算决定，1.25 mm 电池线与 PPTC 2 A |
| 寄存器默认 ICHG | 2048 mA（REG04 = 0x20） | **偏大，务必按实际电池规格下调** |
| 输入限流 | 硬件 ≤ ~1.97 A（ILIM 引脚），软件可用 IINLIM 进一步压低 | USB 2.0 标准口请设 500 mA（`0x08`）；900 mA → `0x10` |
| 终止电流 ITERM | 建议 128 mA（REG05 低 4 位 = 0001） | 默认 256 mA 对 896 mA 充电电流偏大 |

> ICHG 的 LSB = 64 mA（REG04 bits[6:0]），0 mA 起算；
> IINLIM 的 LSB = 50 mA 且**带 100 mA 偏移**（`IINLIM = 100 mA + N × 50 mA`）；
> ITERM/IPRECHG 的 LSB = 64 mA 且带 64 mA 偏移。以上均取自数据手册 §8.4.1/8.4.5/8.4.6。

---

## 5. 充电状态与故障读取

### 5.1 状态寄存器 REG0B（`0x0B`，只读）

| 位 | 字段 | 取值 |
|---|---|---|
| 7:5 | `VBUS_STAT[2:0]` | 000 无输入 / 001 USB SDP / 010 USB CDP / 011 USB DCP / 101 未知适配器(500 mA) / 111 可调压适配器 |
| 4:3 | `CHRG_STAT[1:0]` | **00 未充电 / 01 预充 / 10 快充 / 11 充电完成** |
| 2 | `PG_STAT` | 0 电源不良 / 1 电源正常 |
| 1 | `SDP_STAT` | 0 / 1 检测到 USB100 / USB500 输入 |
| 0 | `VSYS_STAT` | 1 = 处于 VSYSMIN 调节（电池电压偏低） |

### 5.2 故障寄存器 REG0C（`0x0C`，只读，**连续读两次**才清标志）

| 位 | 字段 | 含义 |
|---|---|---|
| 7 | `WATCHDOG_FAULT` | 看门狗超时（回到默认模式） |
| 6 | `BOOST_FAULT` | OTG 升压异常（VBUS 过载/过压/电池过低） |
| 5:4 | `CHRG_FAULT[1:0]` | 00 正常 / 01 输入故障 / **10 过温关断** / 11 安全定时器到期 |
| 3 | `BAT_FAULT` | 电池过压 |
| 2:0 | `NTC_FAULT[2:0]` | TS 温度状态（冷/热/正常） |

> 读 REG0C 会清除故障锁存并允许产生新的 /INT，因此**每次读都要完整处理**。
> 数据手册另外说明：主机读取 REG0C 前，芯片不会因新故障再发 /INT。

### 5.3 中断

`/INT`(U2.7) → `CHG_INT_N` → **GPIO16**（开漏 + 10 kΩ 上拉，低有效）。
建议在 Arduino 中挂 `attachInterrupt(digitalPinToInterrupt(16), isr, FALLING)`，
ISR 里只置标志，主循环再执行 I2C 读取（I2C 不能在 ISR 里跑）。

---

## 6. 电量计 MAX17048（U4）

| 项 | 值 |
|---|---|
| I2C 地址 | **0x36**（7 位；数据手册 Figure/Slave Address `0110110`，p16） |
| 测量点 | `CELL`/`VDD` 接 **`BAT_BUS`**（并联电池总正极），单点测整组电池 |
| 报警输出 | `ALRT` → `FG_ALRT_N` → **GPIO1**（开漏 + R22 10 kΩ 上拉，低有效） |
| 寄存器宽度 | **全部按 16 位读写**（8 位写无效，p10 明确说明） |

### 6.1 寄存器表（数据手册 Table 2，p10–11）

| 地址 | 名称 | 访问 | 默认 | 说明 / LSB |
|---:|---|---|---|---|
| `0x02` | VCELL | R | - | 电池电压，**78.125 µV/LSB** |
| `0x04` | SOC | R | - | 荷电状态，**1/256 % / LSB**（高字节 = 1%） |
| `0x06` | MODE | W | 0x0000 | bit14 Quick-Start、bit13 EnSleep、bit12 HibStat(只读) |
| `0x08` | VERSION | R | 0x001_ | 芯片版本 |
| `0x0A` | HIBRT | R/W | 0x8030 | 休眠进出阈值 |
| `0x0C` | CONFIG | R/W | 0x971C | bit5 ALRT（写 0 清报警）、bit6 SLEEP、ATHD 等 |
| `0x14` | VALRT | R/W | 0x00FF | 过压/欠压报警阈值 |
| `0x16` | CRATE | R | - | 充放电速率，0.208 %/hr |
| `0x18` | VRESET/ID | R/W | 0x96__ | 复位阈值 + 出厂 ID |
| `0x1A` | STATUS | R/W | 0x01__ | 报警状态（RI/VR/HD/SC/VH/VL） |
| `0x40–0x7F` | TABLE | W | - | 电池模型参数 |
| `0xFE` | CMD | R/W | 0xFFFF | 写 `0x5400` 触发 POR |

### 6.2 常用读法

```cpp
// SOC: 0x04 → uint16，除以 256 得百分比
// VCELL: 0x02 → uint16 × 78.125e-6 得伏特
```

* 上电后第一次 SOC 更新约需 1 s（POR 后），之后按工况变速率更新。
* 报警默认开启：低 SOC、SOC 变化 1%、复位、过压、欠压；触发后 `ALRT` 拉低并置位
  `STATUS`，**必须写 `CONFIG.ALRT = 0` 才能清除**（否则一直拉低）。
* 休眠模式下 IC 不检测自放电，唤醒方法见数据手册 Sleep Mode 一节。

---

## 7. Type-C 控制器 TUSB320LI（U5）在充电链中的角色

| 项 | 值 |
|---|---|
| I2C 地址 | **0x47**（ADDR 脚接 GND 时，数据手册 p3：`L - I2C is enabled and I2C 7-bit address is 0x47`） |
| ADDR 脚（U5.5） | 本板接 **GND** → I2C 使能 + 地址 0x47 |
| PORT 脚（U5.3） | 接 **GND** → **UFP（受电端）模式** |
| EN_N（U5.11） | 接 **GND** → 器件使能 |
| VBUS_DET（U5.4） | ← `USB_VBUS_DET` ← R11 **900 kΩ** ← `USB_VBUS_RAW` |
| INT_N（U5.6） | → `TYPEC_INT_N` → **GPIO17**（10 kΩ 上拉） |
| 器件 ID | 读 `0x06…0x00` 得到 ASCII **"TUSB320"** |

### 7.1 关键寄存器（数据手册 §7.5，p16–19）

| 地址 | 字段 | 说明 |
|---:|---|---|
| `0x08` bit7:6 | `CURRENT_MODE_ADVERTISE` | 对外声明电流能力：`00` 默认(500/900 mA)、`01` 中(1.5 A)、`10` 高(3 A) |
| `0x08` bit5:4 | `CURRENT_MODE_DETECT` | **检测到的电源能力**：`00` 默认、`01` 中、`10` 充电配件 500 mA、`11` 高 |
| `0x08` bit3:1 | `ACCESSORY_CONNECTED` | 附件类型（音频/调试） |
| `0x08` bit0 | `ACTIVE_CABLE_DETECTION` | 检测到有源线缆 |
| `0x09` bit4 | `INTERRUPT_STATUS` | 中断标志，**写 1 清除**（RCU） |
| `0x09` 其他位 | `ATTACHED_STATE`、`CABLE_DIR`、`DRP_DUTY_CYCLE` | 连接状态/线缆方向 |
| `0x0A` bit5:4 | `MODE_SELECT` | 端口模式切换（UFP/DFP/DRP） |
| `0x0A` bit0 | `DISABLE_TERM` | 关断内部端接 |

### 7.2 固件怎么用它

* **读取"充电器能给多大电流"**：读 `0x08` 的 `CURRENT_MODE_DETECT`，
  再据此**回写 BQ25895 的 `IINLIM`**（例如检测到 1.5 A 就把 IINLIM 设到 1400 mA，
  但硬上限仍被 ILIM 引脚 ≈1.97 A 限制）。
* `/INT`(GPIO17) 变化 → 读 `0x09` 判断是"插拔"还是"电流档位变化"，并写 1 清 `INTERRUPT_STATUS`。
* 本板 **PORT=GND 固定为 UFP**，不需要也不应该在运行中切到 DFP（硬件未接外部电源路径）。

---

## 8. 输入保护与安全设计

| 环节 | 器件 | 作用 |
|---|---|---|
| VBUS 过流 | F1 = BSMD0805L-200-12V（2 A PPTC） | 自恢复限流 |
| VBUS 过压 | D1 = PESD5V0S1BA（5 V TVS） | 钳位浪涌 |
| 电池支路 | F2 / F3 = 2 A PPTC | 双电池各自保护后再汇流 |
| D+/D− ESD | D2 / D3 = GBLC05C | 静电/浪涌 |
| CC1/CC2 ESD | D4 / D5 = LESD3Z5.0CMT1G | 静电/浪涌 |
| 输入限流（硬） | R13 180 Ω 于 ILIM | 硬件最大输入电流 ≈1.97 A |
| 温度保护 | NTC1 + R16/R17 | JEITA 温度区间充放电 |
| 充电默认禁止 | R18 10 kΩ 于 `/CE` | 上电/复位后必须由固件显式使能 |

> **硬件限流 ≠ 寄存器限流**：二者取较小值。请勿在固件里把 `IINLIM` 设得比适配器能力更高，
> 否则 VBUS 会被拉低（`CHRG_FAULT = 输入故障`）甚至触发 PPTC。

---

## 9. 常见问题排查

| 现象 | 可能原因 | 检查点 |
|---|---|---|
| 插上 USB 不充电 | `/CE` 仍为高（默认禁止）；或适配器被判定为 SDP | REG0B 的 `PG_STAT`/`VBUS_STAT`；GPIO47 电平 |
| 充电一会儿就停 | 看门狗 40 s 超时回默认模式；或过温/定时器到期 | REG0C `WATCHDOG_FAULT`/`CHRG_FAULT`；是否关了看门狗 |
| 充电电流远小于设定 | IINLIM/ILIM 双重限制；`EN_ILIM=1` 时 ILIM 上限生效 | REG00 值、R13 是否为 180 Ω |
| I2C 上扫不到 0x6A/0x36/0x47 | 上拉被拔、总线被拉低、器件未上电 | 3V3_MAIN 是否建立；SCL/SDA 静态电平应≈3.3 V |
| 电量计读数不动/为 0 | `BAT_BUS` 未接电池、或读的是 8 位而不是 16 位 | 电池是否在 J4/J5 且 F2/F3 未熔断 |
| USB 口被反向供电 | OTG 升压被意外打开（`OTG_CONFIG` 复位为 1） | 初始化时显式写 OTG_CONFIG = 0 |
| 板子反复重启 | `SYS` 掉到 SYS_MIN 以下（电池过放/U3 过载） | REG0B `VSYS_STAT`；3V3_MAIN 波形 |

---

## 10. 与旧文档的差异

| 项 | 旧文档 §7.5/7.6 | 本手册（现场实测 + 数据手册） |
|---|---|---|
| 充电电流默认值 | 写"默认 ICHG ≈ 896 mA" | 896 mA 是**设计目标值**，芯片**寄存器默认是 2048 mA**，必须由固件写入 |
| ILIM 硬件上限 | 未给出 | R13 = 180 Ω → **≈1.97 A**（KILIM 355 A·Ω 典型） |
| DSEL | 未说明 | 是**开漏输出**（检测进行中拉低），R20 10 kΩ 为其上拉，不是配置跳线 |
| 看门狗 | 未提及 | **默认 40 s 开启**，不处理会导致"充电一会儿就停" |
