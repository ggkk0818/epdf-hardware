# ESP32-S3 + GDEM102T91 PCB V1.1 任务交接说明

> **2026-09-12 更新（V1.2 整改）**：按 `..._V1.1_to_V1.2_PCB_Modification_Guide.md`
> 完成布局类整改——BQ25895 / TPS63070 / USB-ESD-TUSB320 / EPD Booster 四个簇改为
> 就近聚集（到锚点 courtyard 最大间隙 11.1 mm）；J4/J5 换 **Molex 53261-0271**；
> U4 改 `MAX17048G+T10`、U5 改 `TUSB320LIRWBR`；**TF 座与 USB-C 座对调**
> （USB-C 移到板下边中部，紧邻充电器）；Dk 4.2 / 外层 1 oz，USB 90 Ω = 0.24/0.18 mm。
> ERC = 0，DRC = 0 Error（42 条丝印类 warning，258 条飞线待布线）。
> 仍待办：**U3 换成 TI RNM0015A 的符号与封装**（缺官方 land pattern）。
>
> **2026-09-10 更新（第二轮）**：板框改为竖版 **55 × 84 mm**，定位孔距边 **3 mm**，
> KEY1/2/3 改用 **Omron B3U-1000P** 且中心距 **27 mm**，USB-C 外凸 1 mm，
> **取消全部测试点**，叠层按 **Dk = 4.2 / 外层成品铜 1 oz** 重算（USB 90 Ω → W 0.24 / S 0.18）。
> 原理图 ERC = 0，PCB DRC = 0 Error（106 个器件已完成摆放，258 条飞线待布线）。
> 详细状态见 `SCHEMATIC_NOTES.md` 与 `PCB_LAYOUT_NOTES.md`。
> **下一步工作 = 4 层铜箔布线**（电源路径 → USB 差分 → SPI/I2C/GPIO → EPD HV）。

本文件用于跨模型/跨会话继续任务。切换模型后请先完整阅读本文件、
`SCHEMATIC_NOTES.md`、`PCB_LAYOUT_NOTES.md` 和
`C:\Users\ggkk2\Downloads\ESP32S3_GDEM102T91_PCB_V1.1_Design.md`。

## 一、任务目标

根据 `ESP32S3_GDEM102T91_PCB_V1.1_Design.md`，在
`C:\Code\epdf-hardware\esp32-board-v1.1` 下创建华秋/KiCad 工程，并完成：

1. 原理图设计与 ERC 检查。
2. PCB 布局/布线，满足 **55 mm × 84 mm（竖版）**、4 层、1.2 mm 板厚。
3. 单面 SMT 贴装，器件高度 ≤ 4 mm。
4. 板框圆角 R2，四个定位孔直径 2.2 mm，孔心距离最近两边 **3 mm**。
5. 接口位置约束：
   - USB-C 在右下方，开口向下，**向板外凸出 1 mm**。
   - 24P FPC 连接器在左侧中央，开口向左。
   - 电池接口在左下方，开口向左。
   - KEY1/KEY2/KEY3 在右侧，**中心距 27 mm**，**Omron B3U-1000P**
     （<https://item.hqchip.com/2500240009.html>）。
   - BOOT/RESET 位置可灵活布置。
   - TF 座宜向板外凸出 1 mm（实测不可行，见 `PCB_LAYOUT_NOTES.md` §6.1）。
   - **本版不设置测试点。**
6. BOM 中候选/待定器件标注“待采购复核”。
7. 最终交付前对 SSD1677 高压外围、BQ25895、TPS63070、TUSB320LI、MAX17048
   按官方数据手册逐脚复核。

## 二、用户已确认的约束

- 官方显示手册已复制到项目：
  `C:\Code\epdf-hardware\esp32-board-v1.1\datasheets\GDEM102T91.pdf`。
- MAX17048 使用 TDFN/LFCSP 封装，不使用 WLP。
- MD 中未明确的器件按文档推荐/候选先选型，并在 BOM 标“待采购复核”。
- 板框：**55 × 84 mm（竖版）**，4 层，1.2 mm。
- 板框圆角 R2。
- 四个定位孔：孔径 2.2 mm，孔心距最近两边 **3 mm**。
- 按键：**Omron B3U-1000P**，KEY1/2/3 中心距 **27 mm**。
- **无测试点**。
- 叠层计算参数：**7628 Dk = 4.2**、**外层成品铜厚 1 oz**。
- 单面贴装，器件限高 4 mm。
- 接口/按键位置按上述约束。
- 设计顺序：先原理图/ERC，用户确认后再进入 PCB。

## 三、当前工程状态

工程目录：`C:\Code\epdf-hardware\esp32-board-v1.1`

主要文件：

- `esp32-board-v1.1.kicad_pro`
- `esp32-board-v1.1.kicad_sch`
- `esp32-board-v1.1.kicad_pcb`
- `bom.csv`（含 Status / MPN 列）
- `drc.json` / `erc.json`
- `SCHEMATIC_NOTES.md`（原理图冻结说明 + ERC 记录）
- `PCB_LAYOUT_NOTES.md`（叠层 / 规则 / 摆放 / DRC / 布线方案）
- `sym-lib-table`
- `fp-lib-table`
- `lib\esp32-board-v1.1.kicad_sym`
- `tools\gen_sch.py`
- `tools\gen_pcb.py`
- `tools\kicad_fp.py`
- `datasheets\*.pdf`
- `current.net`

### 已完成内容

1. 已创建华秋/KiCad 工程骨架。
2. 已复制官方 GDEM102T91 PDF 到 `datasheets`。
3. 已收集并放置主要数据手册到 `datasheets`。
4. 已用 `tools\gen_sch.py` 生成完整单页原理图（106 器件 / 96 网络 / A2 图纸，按 8 个功能区标注）。
5. 已按数据手册复核并冻结以下关键器件引脚映射：
   - ESP32-S3-WROOM-1 模块脚号与 GPIO 对应关系（GPIO47 改作 `CHG_CE`）。
   - TUSB320LI 的 PORT/ADDR/EN_N/ID/VBUS_DET。
   - MAX17048 的 CTG/CELL/VDD/GND/ALRT/QSTRT/SCL/SDA/EP（CELL 接 BAT_BUS）。
   - TPS63070 的 PS/SYNC、PG、VAUX、FB、FB2、VOUT、L1/L2、VIN、EN、VSEL、EP（470k/150k 对应 VREF 800 mV）。
   - TPS22918 的 VIN/GND/ON/CT/QOD/VOUT。
   - BQ25895 的 VBUS、D+/D-、STAT、I2C、INT、OTG、CE、ILIM、TS、QON、BAT、SYS、SW、BTST、REGN、PMID、DSEL、PGND。
   - MicroSD SPI（改用 `Micro_SD_Card_Det2` 符号：DAT3=CS、CMD=MOSI、DAT0=MISO、DET_B=DET_A=卡检测）。
6. 原理图已用全局标签方式建立连接，**ERC = 0 Error / 0 Warning，且无任何 Exclusion**。
7. EPD SSD1677 高压外围已按 GDEM102T91 第 20 页典型应用电路逐节点锁定（见 `SCHEMATIC_NOTES.md` §4）。
8. 已生成 `bom.csv`（含 `Status` = RELEASED / PROVISIONAL 与 `MPN` 列）。
9. 已生成 `esp32-board-v1.1.kicad_pcb`：**55×84 mm 竖版**、R2 圆角、
   4×Ø2.2 mm 定位孔（距边 3 mm）、4 层叠层（Dk 4.2 / 外层 1 oz）、
   4 个 Net Class（Default / USB90 0.24-0.18 / POWER / HV_EPD）、
   天线禁布规则区，106 个器件全部摆放完毕。
10. PCB DRC：**0 Error**（86 条告警全部为丝印/天线 courtyard 类 warning；
    258 条未连接飞线＝尚未布线，本阶段预期）。

### 当前 ERC 结果

```
kicad-cli sch erc  →  0 violations
```

收敛过程记录在 `SCHEMATIC_NOTES.md` §3。

## 四、已完成的关键网络

以下网络已在当前原理图中建立：

- `3V3_MAIN`
- `SYS`
- `BAT_BUS`
- `USB_VBUS_RAW`
- `USB_VBUS_PROT`
- `EPD_3V3`
- `I2C_SDA`
- `I2C_SCL`
- `SPI_SCLK`
- `SPI_MOSI`
- `SPI_MISO`
- `RESET_N`
- `BOOT`
- `KEY1_N`
- `KEY2_N`
- `KEY3_N`
- `CHG_INT_N`
- `TYPEC_INT_N`
- `FG_ALRT_N`
- `TF_CD_N`
- `TF_CS_N`
- `USB_DP`
- `USB_DN`

## 五、未完成内容

### 原理图阶段

1. EPD 高压外围已按 GDEM102T91 第 20 页锁定（`SCHEMATIC_NOTES.md` §4），
   投板前仍需人工逐节点复核。
2. 原理图仍为单页（按 8 个功能区标注）。正式发布前建议按 MD 分页
   `00_System_Block` 至 `08_Buttons_Debug_Testpoints`。
3. USB、MicroSD、FPC、电池连接器、按键的最终料号和 3D 模型未确定
   （BOM 中已标 `PROVISIONAL`）。
4. BOM 已生成（`bom.csv`），候选器件已标 `PROVISIONAL / 待采购复核`。
5. 与旧版设计文档的有意差异（例如 BQ25895 /CE 默认禁止充电、
   改用 GPIO47 作为 `CHG_CE`）需用户确认，见 `SCHEMATIC_NOTES.md` §5。

### PCB 阶段（布局完成，布线未开始）

1. 板框（55×84 竖版）、R2 圆角、4 个 2.2 mm 定位孔（距边 3 mm）、4 层叠层、
   4 个 Net Class、
   天线禁布规则区：**已完成**。
2. 106 个器件摆放完成，接口约束（USB-C 外凸 1 mm / FPC / 电池 / KEY 27 mm）：**已完成**。
3. **尚未布线**：电源路径、USB 差分、SPI/I2C/GPIO、EPD HV 目前只有飞线
   （DRC unconnected = 258）。
4. USB 90 Ω 已按 Dk 4.2 / 外层 1 oz 计算为 **W 0.24 / S 0.18 mm** 并写入 Net Class；
   仍建议板厂按实际材料复算确认。
5. 丝印未人工整理（86 条告警，全部为丝印/天线 courtyard 类 warning）。
6. 投板前需完成全部布线、重跑 DRC（目标 unconnected = 0）、生成 Gerber/钻孔/坐标文件。
7. **TF 座未能外凸 1 mm**（前部固定焊盘在本体最前端），需用户确认是否接受，见
   `PCB_LAYOUT_NOTES.md` §6.1。

## 六、待用户确认的问题

原 5 个问题已由 `ESP32S3_GDEM102T91_V1.1_PrePCB_5_Items_Confirmation.md` 答复并落实。

现仍需用户确认/提供：

1. 是否接受 `SCHEMATIC_NOTES.md` §5 列出的与旧版设计文档的差异
   （/CE 默认 HIGH = 禁止充电；`CHG_CE` 使用 GPIO47；TPS63070 PS/SYNC 上拉）。
2. 板厂对 7628 半固化片实际 Dk/Df、外层成品铜厚、阻焊参数的确认，
   以及按实际叠层**复算** USB 90 Ω 差分线宽/间距（当前计算值 0.24 / 0.18 mm）。
3. 连接器/按键/电感/MOSFET 的确切 MPN（BOM 中 `PROVISIONAL` 项）。
4. 最终电池规格（满充电压 / PCM / 线束 / 连接器额定电流）。
5. MicroSD 位置（现放在板下边缘中央）与按键高度/手感是否有结构限制。
6. ~~TF 座不能外凸 1 mm~~ → **已确认接受**（2026-09-12）。
7. ~~板框尺寸~~ → **已确认：保持 55 × 84 mm**（2026-09-12）。
8. **U3 的 RNM0015A land pattern**：KiCad 库中没有该封装，数据手册里只有
   TI 图纸 4222000 的 "LAND PATTERN EXAMPLE"。请提供 TI 官方 land pattern
   （或 SnapEDA / Ultra Librarian 导出的封装），或授权我按该图重建（需人工复核）。

## 六之二、V1.2 整改清单执行状态（依 `ESP32S3_GDEM102T91_V1.1_to_V1.2_PCB_Modification_Guide.md`）

| # | 整改项 | 状态 | 说明 |
|---:|---|---|---|
| ① | PCB 外形改 77 × 45 | **已决定：保持 55 × 84** | 用户 2026-09-12 确认板框保持 55 × 84；原因：45 mm 高度装不下 27 mm 间距的 3 个按键 |
| ② | U3 符号 / 封装改 RNM0015A | **部分完成** | 料号已改 `TPS63070RNMT`；符号仍含 Pin16、封装仍是通用 VQFN-16，**待换成 TI RNM0015A 15 脚 land pattern** |
| ③ | J4/J5 改 Molex 53261-0271 | **已完成** | 封装 `Connector_Molex:Molex_PicoBlade_53261-0271_1x02-1MP_P1.25mm_Horizontal`，BOM 标 RELEASED |
| ④ | U4 / U5 料号冻结 | **已完成** | `MAX17048G+T10` / `TUSB320LIRWBR`，BOM 标 RELEASED |
| ⑤⑥⑦⑨ | BQ25895 / TPS63070 / USB-ESD-TUSB / EPD Booster 局部收紧 | **已完成** | 改成"围绕锚点螺旋扩散"放置；实测器件到锚点 courtyard 最大间隙 11.1 mm，多数 < 8 mm |
| ⑧⑩ | 全板功能分区、布线顺序与规则 | **已完成** | 见 `PCB_LAYOUT_NOTES.md` §6 与 §9 |
| ⑪ | 布线 | **未开始** | — |

附加要求（用户）：**TF 座与 USB-C 座位置对调** —— **已完成**：
USB-C 移到板下边中部 (24.0, 81.33)，TF 座移到右下 (42.0, 75.20)，VBUS 现在紧邻充电器。

## 七、继续任务时的建议顺序

1. 阅读本文件、`SCHEMATIC_NOTES.md`、`PCB_LAYOUT_NOTES.md` 和 MD 设计文档。
2. 如需重新生成：
   - 原理图：`tools\gen_sch.py`
   - PCB 布局：`tools\gen_pcb.py`
3. 运行 ERC / DRC 并检查 `erc.json` / `drc.json`。
4. **下一步工作 = 4 层铜箔布线**，顺序：
   - 电源路径（BAT / SYS / 3V3 / VBUS），0.8 mm 以上或 L3 铺铜
   - USB 差分对（ESD 靠连接器、22 Ω 靠 MCU、参考 L2 连续 GND）
   - SPI / I2C / GPIO / 按键 / TF
   - EPD Booster 区短环路（GDR / RESE / SW）
5. 完成后重跑 DRC（目标 unconnected = 0）并人工整理丝印。
6. 关闭投板前 Open Items（见 `PCB_LAYOUT_NOTES.md` §9），生成 Gerber/钻孔/贴片坐标。

## 八、常用命令

生成原理图：

```powershell
$py = 'C:\Users\ggkk2\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_sch.py'
```

运行 ERC：

```powershell
$env:KICAD_CONFIG_HOME='C:\Code\epdf-hardware\esp32-board-v1.1\.kicad_config'
$env:KICAD10_SYMBOL_DIR='C:\Program Files\KiCad\10.0\share\kicad\symbols'
$env:KICAD10_FOOTPRINT_DIR='C:\Program Files\KiCad\10.0\share\kicad\footprints'
$env:KIPRJMOD='C:\Code\epdf-hardware\esp32-board-v1.1'
& 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe' sch erc --format json -o "C:\Code\epdf-hardware\esp32-board-v1.1\erc.json" "C:\Code\epdf-hardware\esp32-board-v1.1\esp32-board-v1.1.kicad_sch"
```

导出网表：

```powershell
& 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe' sch export netlist --format kicadxml -o "C:\Code\epdf-hardware\esp32-board-v1.1\current.net" "C:\Code\epdf-hardware\esp32-board-v1.1\esp32-board-v1.1.kicad_sch"
```

## 九、交接注意点

- `tools\gen_sch.py` 中当前 `USE_WIRES = False`，使用全局标签方式生成原理图。
- 组件采用自动网格摆放，视觉上为草稿；正式交付前需人工整理原理图。
- `lib\esp32-board-v1.1.kicad_sym` 为本地符号库，包含 TPS63070、MAX17048、
  TUSB320LI、TPS22918。
- EPD 高压外围未最终确认，不要直接按当前草稿发板。
