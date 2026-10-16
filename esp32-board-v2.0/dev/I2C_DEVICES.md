# I2C 总线与从机器件

> 数据来源：原理图 P1 网表（现场回读）+ 本地数据手册原文（BQ25895 / MAX17048 / TUSB320LI）。

---

## 1. 总线概况

| 项 | 值 |
|---|---|
| 控制器 | ESP32-S3 内部 I2C（任意 GPIO 可映射） |
| **SDA** | **GPIO18**（网络 `I2C_SDA`） |
| **SCL** | **GPIO21**（网络 `I2C_SCL`） |
| 上拉 | **R6 / R7 = 4.7 kΩ 上拉到 `3V3_MAIN`**（两组，分别拉 SDA/SCL） |
| 逻辑电平 | 3.3 V（所有从机与 MCU 同域，**无需电平转换**） |
| 建议速率 | 调试用 100 kHz；稳定后 400 kHz（三颗从机都支持 400 kHz） |
| 从机数量 | 3（地址互不冲突） |

```text
3V3_MAIN ──[R6 4.7k]──┬──────────────┬──────────────┬─────────────
                      │              │              │
              U2 BQ25895        U4 MAX17048     U5 TUSB320LI
              (0x6A)            (0x36)          (0x47)
GPIO18 ───────────────┴──────────────┴──────────────┴──── SDA
GPIO21 ─────────────────────────────────────────────────── SCL
```

### 1.1 ⚠️ Arduino 上必须显式指定引脚

ESP32-S3 Arduino 的 `Wire.begin()` 默认引脚**不是** 18/21，本板必须：

```cpp
Wire.begin(18 /*SDA*/, 21 /*SCL*/);
Wire.setClock(400000);
```

---

## 2. 从机地址总表

| 器件 | 位号 | 7 位地址 | 写地址(8 位) | 读地址(8 位) | 地址来源 |
|---|---|---|---|---|---|
| BQ25895（充电器） | U2 | **0x6A** | 0xD4 | 0xD5 | 数据手册 p32："I2C Target Address: **6AH** (1101010B + R/W)" |
| MAX17048（电量计） | U4 | **0x36** | 0x6C | 0x6D | 数据手册 p16：slave address `0110110` |
| TUSB320LI（Type-C） | U5 | **0x47** | 0x8E | 0x8F | 数据手册 p3：ADDR=L → 7-bit address **0x47** |

> Arduino `Wire` API 使用 **7 位地址**（0x6A / 0x36 / 0x47），不要传 8 位地址。
> TUSB320 的地址由 ADDR 引脚决定：**H→0x67，L→0x47，NC→GPIO 模式（I2C 关闭）**；
> 本板 ADDR 接 GND，所以是 **0x47**。如果以后改板把 ADDR 悬空，I2C 会**整个不可用**。

---

## 3. BQ25895（U2，0x6A）

寄存器 0x00–0x14，**每寄存器 8 位**。复位后设备处于"默认模式"，主机写入后进入"主机模式"
（受看门狗保护，见 `POWER_AND_CHARGING.md` §3.1）。

| 地址 | 名称 | 关键位 | 复位值 | 建议值 |
|---:|---|---|---|---|
| `0x00` | 输入限流 | bit6 `EN_ILIM`、bit5:0 `IINLIM`（100 mA + N×50 mA） | 0x08（500 mA） | 按适配器能力，如 0x10 = 900 mA（100 + 16×50） |
| `0x01` | 温度/电压补偿 | bit7:6 `BHOT`、bit5 `BCOLD`、bit4:0 `VINDPM_OS` | 0x05 | 保持 |
| `0x02` | ADC 与检测控制 | `CONV_START`、`CONV_RATE`、`ICO_EN`、`AUTO_DPDM_EN` | 0x3D | 保持（`AUTO_DPDM_EN=1`） |
| `0x03` | 模式配置 | bit5 `OTG_CONFIG`（1=升压输出）、bit4 `CHG_CONFIG`（1=允许充电）、bit3:1 `SYS_MIN` | 0x3A | **0x1A**（关 OTG、开充电） |
| `0x04` | 充电电流 | bit6:0 `ICHG`（64 mA/LSB） | 0x20（2048 mA） | **0x0E（896 mA）** |
| `0x05` | 预充/终止电流 | bit7:4 `IPRECHG`、bit3:0 `ITERM`（64 mA + N×64 mA） | 0x13 | **0x11**（128/128 mA） |
| `0x06` | 充电电压 | bit7:2 `VREG`（3.840 V + N×16 mV）、bit1 `BATLOWV`、bit0 `VRECHG` | 0x5E（4.208 V） | 保持 |
| `0x07` | 终止/定时器/看门狗 | bit7 `EN_TERM`、bit5:4 `WATCHDOG`、bit6 `WD_RST` | 0x9D | **0x8D**（关看门狗） |
| `0x08` | 阻抗补偿/结温 | `BAT_COMP`、`VCLAMP`、`TREG` | 0x03 | 保持 |
| `0x09` | 特殊功能 | `FORCE_ICO`、`TMR2X_EN`、`BATFET_DIS` | 0x44 | 保持 |
| `0x0A` | OTG 升压电压 | bit7:4 `BOOSTV`（4.55 V + N×64 mV） | 0x93（5.126 V） | 保持 |
| `0x0B` | **状态（只读）** | `VBUS_STAT`、`CHRG_STAT`、`PG_STAT`、`VSYS_STAT` | - | 轮询 |
| `0x0C` | **故障（只读）** | `WATCHDOG_FAULT`、`BOOST_FAULT`、`CHRG_FAULT`、`NTC_FAULT` | - | 读两次清标志 |
| `0x0D` | 绝对 VINDPM | bit6:0（100 mV/LSB，默认 4.4 V） | 0x12 | 保持 |
| `0x0E` | VBAT ADC（只读） | 20 mV/LSB，偏移 2.304 V | - | 也可用 MAX17048 |
| `0x0F` | VSYS ADC（只读） | 20 mV/LSB，偏移 2.304 V | - | - |
| `0x10` | TS% ADC（只读） | 0.465 %/LSB，偏移 21 % | - | 读温度用 |
| `0x11` | VBUS ADC（只读） | bit7 `VBUS_GD`、bit6:0 100 mV/LSB，偏移 2.6 V | - | - |
| `0x12` | 充电电流 ADC（只读） | 50 mA/LSB | - | - |
| `0x14` | 复位 | 写 `0x80` 触发寄存器复位 | - | - |

> 位定义与默认值均取自数据手册 §8.4.1–§8.4.19（REG00→p32 … REG12→p47）。
> **写寄存器后一定要回读**：看门狗超时会把设备拉回默认模式，静默丢弃你的设置。

---

## 4. MAX17048（U4，0x36）

| 项 | 值 |
|---|---|
| 地址 | 0x36 |
| 数据宽度 | **16 位**（先 MSB 后 LSB；8 位写无效） |
| 测量对象 | `BAT_BUS`（并联电池总正极），单节 |

| 地址 | 名称 | 访问 | 换算 |
|---:|---|---|---|
| `0x02` | VCELL | R | × 78.125 µV = 伏特 |
| `0x04` | SOC | R | ÷ 256 = % |
| `0x06` | MODE | W | bit14 QuickStart / bit13 EnSleep / bit12 HibStat |
| `0x0A` | HIBRT | R/W | 休眠阈值 |
| `0x0C` | CONFIG | R/W | bit5 ALRT（写 0 清报警）、bit6 SLEEP |
| `0x14` | VALRT | R/W | 高/低电压报警阈值 |
| `0x1A` | STATUS | R/W | 报警来源 |
| `0xFE` | CMD | R/W | 写 `0x5400` = POR |

* 报警脚 `ALRT` → `FG_ALRT_N` → **GPIO1**（开漏，10 kΩ 上拉，低有效）。
* 报警触发后必须**写 `CONFIG.ALRT=0`** 清除，否则一直拉低。

---

## 5. TUSB320LI（U5，0x47）

| 项 | 值 |
|---|---|
| 地址 | 0x47（ADDR = GND） |
| 端口模式 | 硬件固定 **UFP**（PORT = GND），本板不做 DFP |
| 中断 | `INT_N` → `TYPEC_INT_N` → **GPIO17** |

| 地址 | 名称 | 访问 | 说明 |
|---:|---|---|---|
| `0x00–0x07` | DEVICE_ID | R | 读 `0x06→0x00` 得到 ASCII `"TUSB320"`（寄存器 0x06='T', 0x05='U', 0x04='S', 0x03='B', 0x02='3', 0x01='2', 0x00='0'） |
| `0x08` | 电流模式 | R/W | bit7:6 `CURRENT_MODE_ADVERTISE`（RW：00 默认 / 01 1.5 A / 10 3 A）<br>bit5:4 `CURRENT_MODE_DETECT`（RU，读到的电源能力：00 默认 / 01 中 / 10 充电配件 500 mA / 11 高）<br>bit3:1 `ACCESSORY_CONNECTED`、bit0 `ACTIVE_CABLE_DETECTION` |
| `0x09` | 连接状态/中断 | R/W | bit4 `INTERRUPT_STATUS`（**写 1 清除**）、`ATTACHED_STATE`、`CABLE_DIR`、`DRP_DUTY_CYCLE` |
| `0x0A` | 模式选择 | R/W | bit5:4 `MODE_SELECT`、bit0 `DISABLE_TERM` |
| `0x45` / `0xA0` | 厂商/测试 | - | 见数据手册 §7.5.5/7.5.6 |

### 5.1 典型用法

```text
检测到 /INT(GPIO17) 拉低
  → 读 0x09，判断 ATTACHED_STATE（是否插入）与 INTERRUPT_STATUS
  → 写 0x09 的 bit4 = 1 清除中断
  → 读 0x08 的 CURRENT_MODE_DETECT，得到充电器能力
  → 用该能力回写 BQ25895 REG00 的 IINLIM（并受 ILIM 硬件 ≈1.97 A 上限约束）
```

---

## 6. 通用寄存器读写帮助函数（Arduino）

```cpp
#include <Wire.h>

#define ADDR_BQ25895   0x6A
#define ADDR_MAX17048  0x36
#define ADDR_TUSB320   0x47

// ---- 8 位寄存器（BQ25895 / TUSB320）----
bool wr8(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

uint8_t rd8(uint8_t addr, uint8_t reg, bool *ok = nullptr) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) { if (ok) *ok = false; return 0; }
  if (Wire.requestFrom((int)addr, 1) != 1) { if (ok) *ok = false; return 0; }
  if (ok) *ok = true;
  return Wire.read();
}

// ---- 16 位寄存器（MAX17048，MSB 在前）----
uint16_t rd16(uint8_t addr, uint8_t reg, bool *ok = nullptr) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) { if (ok) *ok = false; return 0; }
  if (Wire.requestFrom((int)addr, 2) != 2) { if (ok) *ok = false; return 0; }
  uint16_t v = ((uint16_t)Wire.read()) << 8;
  v |= (uint16_t)Wire.read();
  if (ok) *ok = true;
  return v;
}
```

### 6.1 组合读写与"回读校验"的注意事项

* BQ25895 的 **REG0C 不支持多读**（必须单字节读，且读两次才清标志）。
* MAX17048 **必须 16 位访问**，用 `rd8` 读 `0x04` 只会拿到一半数据。
* I2C 时钟拉到 400 kHz 前先用 100 kHz 验证接线；ESP32-S3 的 I2C 超时较短，
  出现 `endTransmission()!=0`（错误码 5 = 超时）时先降低速率。

---

## 7. 排查清单

| 现象 | 检查 |
|---|---|
| 扫描不到任何器件 | SDA/SCL 是否接反（SDA=18、SCL=21）；上拉 R6/R7 是否在位；3V3_MAIN 是否建立 |
| 只扫到 0x6A / 0x36，没有 0x47 | TUSB320 的 ADDR(U5.5) 必须接 GND；若悬空则器件进入 GPIO 模式，I2C 关闭 |
| 偶发 NACK | 总线速率过高、线太长；降低到 100 kHz；确认 `Wire.begin(18,21)` |
| 写 BQ25895 后一会儿失效 | 看门狗 40 s 超时（读 REG0C 的 `WATCHDOG_FAULT`，或把 REG07 看门狗位写 00） |
| MAX17048 读数固定为 0 | `BAT_BUS` 上是否有电池；是否用了 16 位读 |
| 读数跳变 | 与 ALRT/INT 中断重入有关：I2C 访问加互斥（Arduino 单核可用简单标志） |
