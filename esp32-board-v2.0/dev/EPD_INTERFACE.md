# 墨水屏接口与驱动要点

> 面板：Good Display **GDEM102T91**（10.2 英寸 AM EPD，**960 × 640**，驱动 IC **SSD1677**）。
> 接口引脚取自面板数据手册 p7，板级连接取自原理图 P2 网表（2026-10-10 现场回读）。

---

## 1. 电气接口一览

| 信号 | MCU 引脚 | 网络 | 方向 | 说明 |
|---|---|---|---|---|
| SPI SCLK | GPIO12 | `SPI_SCLK` | MCU → 面板 | 与 microSD 共用 |
| SPI MOSI/SDA | GPIO11 | `SPI_MOSI` | MCU → 面板 | **单向写入**（面板无 MISO） |
| D/C# | GPIO9 | `EPD_DC` | MCU → 面板 | 1 = 数据，0 = 命令 |
| CS# | GPIO10 | `EPD_CS_N` | MCU → 面板 | 低有效 |
| RES# | GPIO8 | `EPD_RST_N` | MCU → 面板 | 低有效 |
| BUSY | GPIO7 | `EPD_BUSY` | 面板 → MCU | **高 = 忙**（SSD1677 的 BUSY 高有效） |
| 电源开关 | GPIO6 | `EPD_PWR_EN` | MCU → TPS22918 | 高 = 面板上电；100 kΩ 下拉 → **默认断电** |

面板侧 VDDIO/VCI 由 `EPD_3V3` 供电；VDD（内核）由面板内部从 VCI 稳压，但**必须外接电容 C35 1 µF**；
VPP（脚 19）保持开路。

## 2. 上电 / 断电顺序（建议）

```text
上电：
  ① GPIO12(SCLK)/GPIO11(MOSI)/GPIO9(DC)/GPIO10(CS)/GPIO8(RST) 先设为 OUTPUT 并置为安全电平
     （CS=1 高、RST=1 高、DC=0、SCLK=0）
  ② GPIO6 = 1 → EPD_3V3 建立（TPS22918 有软启动）
  ③ 等待 > 10 ms 让面板电源稳定
  ④ RST: 高 → 低(≥10 µs) → 高，然后等待 BUSY 变高（面板开始初始化）
  ⑤ 等 BUSY 回到低 → 可以发命令

断电（省电）：
  ① 发深度睡眠命令并等 BUSY 低
  ② GPIO6 = 0 关闭 EPD_3V3（面板高压随之泄放）
  ③ CS/DC/SCLK 拉低
```

> SSD1677 的复位脉宽、BUSY 极性、上电时序细节请以 **SSD1677 数据手册第 6/15 章** 为准；
> 本板只保证硬件连接，软件必须按驱动 IC 的时序实现。

## 3. 板载高压升压电路（面板需要，MCU 不直接控制）

面板引脚 **GDR**（栅驱动控制）与 **RESE**（电流检测）不只是电源脚，它们与板上的
**Q1（Si1304BDL）+ L3 47 µH + D6/D7/D8（MBR0530）+ C29 4.7 µF** 组成升压变换器，
产生面板工作所需的高压，再回送到 FPC 的 VGH / VGL / VSH1 / VSH2 / VSL：

```text
  EPD_GDR ──┐(Q1 栅驱动)
  EPD_RESE ─┤(电流取样, R31 2.2Ω 到地)
            └──► Q1 ──► EPD_SW ─[L3 47µH]─ EPD_3V3
                          │
              D6/D7/D8 整流 + C29/C30/C32/C31/C33 滤波
                          │
        ┌─────────┬───────┼────────┬────────┐
     EPD_VGH   EPD_VGL  EPD_VSH1  EPD_VSH2  EPD_VSL   (回送 FPC 20–23)
```

* **软件侧无需配置这些电压**：升压由面板内部逻辑通过 GDR/RESE 自行闭环控制；
  MCU 只要保证 `EPD_3V3` 正常、SPI/控制时序正确即可。
* 这些节点是高压（可达 ±20 V 量级）：**不要用万用表/示波器探头接地夹随意接触**，
  测试前确认探头耐压与接地方式。
* VCOM 由面板 + C36 1 µF 稳定，同样不需要软件干预。

## 4. SPI 使用要点

| 项 | 建议 |
|---|---|
| 模式 | **SPI Mode 0**（CPOL=0, CPHA=0，SSD1677 在 SCLK 上升沿采样 SDI） |
| 位序 | MSB first |
| 速率 | 先用 **1–4 MHz** 验证；稳定后按 SSD1677 数据手册 AC Timing 章节确认上限再提高 |
| CS# 建立/保持 | 手册要求 CS# 在 SCLK 首个上升沿前 ≥ 20 ns 建立、末个下降沿后 ≥ 20 ns 保持 |
| DC 切换 | 切换 D/C# 时必须 **CS# 为高**（或至少在字节边界切换），否则命令/数据会错位 |
| 总线互斥 | 与 microSD 共用 SCLK/MOSI，**同一时刻只能有一个 CS 有效**；切换前把另一个 CS 拉高 |

## 5. 驱动软件建议

1. **优先渠道**：向 Good Display 索取 **GDEM102T91 官方示例**（含 SSD1677 的初始化序列与
   波形 LUT），这是唯一保证显示效果与寿命的正确起点（错的 LUT 会导致残影甚至损坏面板）。
2. 若使用开源库（如 GxEPD2 / epdiy 等），先确认库中**已有 GDEM102T91 或等价 960×640 SSD1677
   面板类**；没有则必须自行移植 LUT 与初始化表，不要拿别的尺寸面板的参数直接套用。
3. 温度补偿：面板内部温度传感器（TSCL/TSDA，FPC 脚 6/7）本板**未连接**，
   如果需要按温度切换波形，只能用固定档位或读板载 NTC（`NTC1`）。
4. 局部刷新（partial update）需要 SSD1677 的窗口/模式寄存器支持，
   在使用前确认官方 LUT 是否包含局部刷新波形。

> **已核实（2026-10-11）**：GxEPD2 **1.6.9** 已内置本板两块面板的驱动类 ——
> `GxEPD2_420_GDEY042T81`（400×300，SSD1683）与 `GxEPD2_1020_GDEM102T91`（960×640，SSD1677），
> 两者都声明了 `hasPartialUpdate / hasFastPartialUpdate = true`，所以上面第 2 条“没有则必须自行移植”
> 对本板不适用。示例程序的屏幕调试输出就是基于 GxEPD2 实现的，见
> `platformio/src/epd_debug.cpp`（开关 `ENABLE_EPD_DEBUG`，面板选择 `-DEPD_PANEL_GDEM102T91=1`）。

## 6. 典型刷新流程（伪代码）

```cpp
void epdRefreshFull(const uint8_t* blackBuf, const uint8_t* redBuf) {
  epdPowerOn();                 // GPIO6=1 + 复位 + 等 BUSY
  epdCmd(0x12);                 // SW Reset，等 BUSY 低
  epdWriteLut();                // 载入官方波形 LUT（面板相关，不可省略）
  epdCmd(0x11); epdData(0x03);  // 数据入口模式
  epdSetWindow(0, 0, 959, 639); // 分辨率 960x640
  epdWriteImage(0x24, blackBuf, 960 * 640 / 8);
  epdWriteImage(0x26, redBuf,   960 * 640 / 8);
  epdCmd(0x22); epdData(0xC7);  // 显示更新序列
  epdCmd(0x20);                 // 触发
  epdWaitBusy();                // BUSY 高 → 低 表示完成
}
```

> 上面的命令码（0x11/0x12/0x20/0x22/0x24/0x26）是 SSD1677 系列通用序列的写法示意，
> **实际参数（尤其 LUT 与 0x22 的序列值）必须使用 GDEM102T91 官方版本**。

## 7. 分辨率与缓存

| 项 | 值 |
|---|---|
| 分辨率 | 960 × 640（横屏，2 色；通常再叠加一层红色/彩色通道） |
| 单色帧缓存 | 960 × 640 / 8 = **76 800 字节**（75 KB） |
| 双缓存（黑白 + 红） | 约 **150 KB** |
| 说明 | 模组有 8 MB PSRAM，放多帧缓存绰绰有余；建议把大缓存放到 PSRAM（见 PLATFORMIO.md） |
