# PlatformIO + Arduino 开发指南

> 目标板：ESP32-S3-WROOM-1-**N16R8**（16 MB Flash + 8 MB OPI PSRAM）。
> 模板工程：[`platformio/`](platformio/)，含 `platformio.ini`、`include/board_pins.h`、`src/main.cpp`。

---

## 1. 环境准备

**方式 A（推荐）**：VS Code + 扩展 **PlatformIO IDE**。

**方式 B（命令行）**：

```bash
pip install -U platformio      # 或 python -m pip install -U platformio
pio --version
```

首次编译会联网下载 `espressif32` 平台与工具链（约几百 MB），需要能访问网络。

## 2. 工程结构

```text
platformio/
├── platformio.ini          # 板卡/存储/烧录配置（已按 N16R8 调好）
├── include/
│   └── board_pins.h        # 本板全部引脚宏、I2C 地址、BQ25895 寄存器地址
└── src/
    └── main.cpp            # 板级自检 Demo（I2C/充电器/电量计/Type-C/按键/LED）
```

复制成自己的工程：

```bash
cp -r dev/platformio ~/my-epd-firmware && cd ~/my-epd-firmware
pio run                 # 编译
pio run -t upload       # 烧录
pio device monitor      # 串口（USB CDC, 115200）
```

## 3. platformio.ini 关键点

| 配置 | 值 | 为什么必须这样 |
|---|---|---|
| `board` | `esp32-s3-devkitc-1` | 通用 S3 底板定义，配合下面的覆盖项适配本板 |
| `board_build.flash_size` / `board_upload.flash_size` | `16MB` | 模组是 N**16**R8，默认 8 MB 会用不满 |
| `board_build.arduino.memory_type` | **`qio_opi`** | **R8 = 八线 PSRAM**；写错（如 `qio_qspi`）会导致 PSRAM 不可用或启动异常 |
| `board_build.partitions` | `default_16MB.csv` | 16 MB Flash 的分区表 |
| `-DARDUINO_USB_MODE=1`<br>`-DARDUINO_USB_CDC_ON_BOOT=1` | - | 本板 USB D+/D- 直接接模组 **GPIO19/20**（原生 USB），串口监视走 USB CDC |
| `-DBOARD_HAS_PSRAM` | - | 启用 PSRAM 支持（墨水屏整屏缓存需要） |
| `monitor_speed` | 115200 | 与示例代码一致 |

> 若你的 PlatformIO 版本报 `memory_type` 无效，说明平台包太旧：
> `pio pkg update -g -p espressif32`，或改用 `board = esp32-s3-devkitc-1-n16r8v`（新版本已内置该板型）。

## 4. 烧录与进入下载模式

本板**没有 USB-TTL 芯片**，靠模组原生 USB（GPIO19/20）下载。

* 正常情况：插上 USB-C，`pio run -t upload` 即可。
* 若出现 `Failed to connect to ESP32-S3: No serial data received`：
  1. 按住 **BOOT(SW2)**；
  2. 按一下 **RESET(SW1)** 再松开；
  3. 松开 BOOT —— 此时进入下载模式，重新上传。
* 上传成功后按 RESET 运行。

## 5. 串口监视

```bash
pio device monitor -b 115200
# 退出：Ctrl + ]
```

示例程序上电后会打印：芯片信息 → I2C 扫描结果 → 充电器状态 → 电池电压/SOC →
Type-C 电流档位 → 按键状态，然后每秒轮换 LED 颜色并实时打印按键事件。

## 6. 依赖库

| 用途 | 库 | 说明 |
|---|---|---|
| WS2812 LED1 | `adafruit/Adafruit NeoPixel` | 在 `platformio.ini` 的 `lib_deps` 打开即可；未安装时示例会自动跳过 LED |
| 墨水屏 | **Good Display GDEM102T91 官方驱动** | 建议把官方源码放到 `lib/` 下用 `file://lib/xxx` 引用（见 EPD_INTERFACE.md） |
| microSD | 内置 `SD` / `SdFat` | 走 SPI（SCLK=12, MOSI=11, MISO=13, CS=14） |
| 其他 | `Wire`（内置） | I2C |

## 7. 在固件里使用 PSRAM

```cpp
#include <esp_heap_caps.h>

// 墨水屏整屏缓存（960×640 / 8 = 76800 字节）建议放 PSRAM
uint8_t *frame = (uint8_t *)heap_caps_malloc(960 * 640 / 8, MALLOC_CAP_SPIRAM);
if (!frame) { Serial.println("PSRAM 分配失败"); }

Serial.printf("PSRAM 总量 %u KB，空闲 %u KB\n",
              ESP.getPsramSize() / 1024, ESP.getFreePsram() / 1024);
```

> 若 `ESP.getPsramSize()` 返回 0：检查 `platformio.ini` 的 `memory_type = qio_opi` 与
> `-DBOARD_HAS_PSRAM`，并确认买到的确实是 **R8** 版本模组。

## 8. 多任务与实时性建议

| 场景 | 建议 |
|---|---|
| 墨水屏刷新（秒级阻塞） | 放到独立 FreeRTOS 任务，避免阻塞按键/串口 |
| I2C 访问 | 用互斥（`SemaphoreHandle_t`）保护，中断里只置标志 |
| 按键 | 用 `attachInterrupt(..., FALLING)` + 20 ms 消抖，或 10 ms 轮询 |
| WS2812 | 用 RMT 驱动（Adafruit NeoPixel 已内置）；不要在临界区关中断过久 |
| 省电 | 空闲时 `digitalWrite(PIN_EPD_PWR_EN, LOW)` 断屏电；深度睡眠需评估 `SYS`/3V3 常开（本板 3V3 无软件开关） |

## 9. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 编译报 `PSRAM` 相关错误 | `memory_type` 不是 `qio_opi`，或平台包过旧 |
| 上传失败 `No serial data received` | 按 §4 手动进下载模式 |
| 串口无输出 | 确认 `ARDUINO_USB_CDC_ON_BOOT=1`；换成 USB 数据线（有些线只供电） |
| `Serial` 一直为 false | 本板 USB CDC 需要主机打开串口后才就绪，示例已加 3 s 超时等待 |
| I2C 一个都扫不到 | `Wire.begin()` 必须显式传 18/21（见 I2C_DEVICES.md §1.1） |
| 屏幕一直全白/全黑 | `EPD_PWR_EN` 未拉高、或 LUT/初始化序列不是 GDEM102T91 官方版本 |
| 屏幕刷新后残影 | 波形 LUT 与温度档位不匹配（面板温度传感器未接，见 EPD_INTERFACE.md §5） |

## 10. 验证状态说明

> ⚠️ 截至 2026-10-10，**本项目所在机器未安装 PlatformIO**，模板工程**未在真机编译/烧录验证**。
> 文件按 ESP32-S3 Arduino 常用写法编写，引脚与器件定义均来自现场原理图回读（可信）；
> 首次使用请先 `pio run` 编译一次，若平台包版本差异导致报错，按 §3 的提示调整 `platformio.ini`。
