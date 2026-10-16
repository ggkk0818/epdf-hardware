// =====================================================================
//  ESP32-S3 墨水屏主板 v2.0 - 板级引脚与器件定义
//  来源：EasyEDA 工程 esp32s3-board-v2.0 原理图 P1/P2 网表现场回读
//  生成日期：2026-10-10   原理图版本：V1.0（更新 2026-10-07）
//  详见 ../PINOUT.md / ../I2C_DEVICES.md / ../POWER_AND_CHARGING.md
// =====================================================================
#pragma once

#include <Arduino.h>

// ------------------------- 主控与电源 --------------------------------
#define BOARD_NAME          "ESP32-S3-EPD-102-V2.0"
#define MCU_MODULE          "ESP32-S3-WROOM-1-N16R8"

// ------------------------- 用户按键（低有效）-------------------------
#define PIN_KEY1            4    // SW3  右侧按键 1   (KEY1_N)
#define PIN_KEY2            5    // SW4  右侧按键 2   (KEY2_N)
#define PIN_KEY3            15   // SW5  右侧按键 3   (KEY3_N)
#define PIN_BOOT            0    // SW2  BOOT / 下载

// ------------------------- 墨水屏（SSD1677 / 24P FPC）----------------
#define PIN_EPD_PWR_EN      6    // 高=给面板上电（TPS22918），默认下拉=断电
#define PIN_EPD_BUSY        7    // 高=忙（面板输出）
#define PIN_EPD_RST         8    // 复位，低有效
#define PIN_EPD_DC          9    // 1=数据 0=命令
#define PIN_EPD_CS          10   // 片选，低有效

// ------------------------- SPI（墨水屏 + microSD 共用）---------------
#define PIN_SPI_SCK         12
#define PIN_SPI_MOSI        11
#define PIN_SPI_MISO        13   // 只有 microSD 在用（面板无 MISO）
#define PIN_SD_CS           14   // microSD 片选，低有效
#define PIN_SD_CD           2    // microSD 卡检测：插卡=低

// ------------------------- I2C ---------------------------------------
#define PIN_I2C_SDA         18
#define PIN_I2C_SCL         21
#define I2C_FREQ_HZ         400000UL   // 调试阶段建议 100000

// ------------------------- 中断 / 控制 -------------------------------
#define PIN_CHG_INT         16   // BQ25895 /INT      低有效（开漏）
#define PIN_TYPEC_INT       17   // TUSB320 INT_N     低有效（开漏）
#define PIN_FG_ALRT         1    // MAX17048 ALRT     低有效（开漏）
#define PIN_CHG_CE          47   // BQ25895 /CE：低=允许充电（上电默认高=禁止）
#define PIN_LED_DIN         38   // WS2812 数据（经 R37 33Ω）

// ------------------------- I2C 从机地址（7 位）-----------------------
#define ADDR_BQ25895        0x6A   // 充电器
#define ADDR_MAX17048       0x36   // 电量计
#define ADDR_TUSB320        0x47   // Type-C 控制器（ADDR 脚接 GND）

// ------------------------- BQ25895 寄存器 ----------------------------
#define BQ_REG_INPUT_LIMIT  0x00   // EN_HIZ / EN_ILIM / IINLIM[5:0]
#define BQ_REG_THERM_VINDPM 0x01
#define BQ_REG_ADC_CTRL     0x02
#define BQ_REG_MODE_CFG     0x03   // OTG_CONFIG / CHG_CONFIG / SYS_MIN
#define BQ_REG_ICHG         0x04   // 充电电流，64 mA/LSB
#define BQ_REG_ITERM_IPRE   0x05   // 终止/预充电流，64 mA/LSB + 64 mA
#define BQ_REG_VREG         0x06   // 充电电压，16 mV/LSB + 3.840 V
#define BQ_REG_TERM_TIMER   0x07   // EN_TERM / WATCHDOG / CHG_TIMER
#define BQ_REG_STATUS       0x0B   // 只读状态
#define BQ_REG_FAULT        0x0C   // 只读故障（需连读两次）

#define BQ_STATUS_CHRG_MASK 0x18   // CHRG_STAT[1:0] = bit4:3
#define BQ_STATUS_CHRG_SHIFT 3
#define BQ_STATUS_PG        0x04   // PG_STAT = bit2

// ------------------------- MAX17048 寄存器 ---------------------------
#define MAX_REG_VCELL       0x02   // ×78.125 µV
#define MAX_REG_SOC         0x04   // ÷256 = %
#define MAX_REG_MODE        0x06
#define MAX_REG_CONFIG      0x0C   // bit5 ALRT（写 0 清报警）
#define MAX_REG_CRATE       0x16   // 有符号，0.208 %/h LSB（正=充电 负=放电）
#define MAX_REG_STATUS      0x1A
#define MAX_REG_CMD         0xFE   // 写 0x5400 = POR

// ------------------------- TUSB320 寄存器 ----------------------------
#define TYPEC_REG_DEVICE_ID 0x00   // 0x06..0x00 = "TUSB320"（反向读取）
#define TYPEC_REG_CURRENT   0x08   // CURRENT_MODE_ADVERTISE / _DETECT
#define TYPEC_REG_ATTACH    0x09   // ATTACHED_STATE / INTERRUPT_STATUS(bit4,写1清)
#define TYPEC_REG_MODE      0x0A   // MODE_SELECT / DISABLE_TERM
