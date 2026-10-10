# esp32-board-v2.0 原理图 × `PCB_INTERFACE_POSITIONS.md` 需求核对报告

日期：2026-09-22　范围：**原理图（P1 / P2）**，对照需求文档 1–10 节与 v1.1 冻结设计。
核对工具：`tools/req_check.py`、`tools/pcb_netlist_check.py`、`tools/sch_audit.py`、
`tools/sch_untangle.py`（输出留档 `work/audit/req-check.txt`、`req-pcb-netlist.txt`）。

---

## 0. 结论

* **功能与连接：无缺陷。** 原理图网表与需求文档声明的数据源（`esp32-board-v1.1_final_drc_20260920.kicad_pcb`
  焊盘网表）逐脚一致；文档 §7 全部功能块、§5 全部接口引脚分配、§7.2 GPIO 表、
  FPC/microSD 引脚表全部对得上。
* **发现 1 项已处理、3 项已确认**（均不影响连接正确性）：

| # | 项 | 严重度 | 处置（2026-09-22） |
|---|---|---|---|
| 1 | `R21`/`C16`（SW 节点 RC 吸收）在数据模型里是 **DNP**，但 EasyEDA 原理图里 `addIntoBom=true`、没有任何不装配标记 | 中 | **已处理**：两页分别 `sch modify` 写入 `addIntoBom=false` + 自定义属性 `Populate=DNP`（R31 保持 FIT），`sch save` + `doc reload` 后复读确认，连接不变（P1 190/190、P2 137/137） |
| 2 | `L1` 电感与 v1.1 冻结件不同（v1.1 `MWSA0503S-1R0MT` 10 A Isat ↔ v2 `NR5040-1.0µH` 4.9 A 额定/7.35 A Isat） | 中 | **用户决定不换**（保留 v2 选型）；如日后启用 OTG 或 5 A 快充再评估 |
| 3 | `J1` 料号写法与文档不同（文档 `USB4105-15-A-120` ↔ v2 `USB4105-GF-A-120`，焊盘几何一致） | 低 | **已确认保留 v2 料号 `USB4105-GF-A-120`（用户决定）**；文档 §4 / §5.1 已统一为该料号，并注明旧写法属同系列 |
| 4 | §7.5"每路各一颗 0.1 µF"未按字面实现（100 nF 放在公共 `BAT_BUS` 侧，`BAT1_RAW`/`BAT2_RAW` 上无电容） | 低 | **已确认按现状**：文档 §7.5 已改写为"电容在公共 BAT_BUS 侧" |

另附 5 处**文档文字与设计的出入**，已按设计修正文档（不改原理图），见 §3。

---

## 1. 核对方法与依据

| 层 | 方法 | 结果文件 |
|---|---|---|
| 连接（逐脚） | 活体原理图 `sch read/list` → 与 `design/model.json` 逐脚对账 | `tools/sch_audit.py` |
| 连接（源） | `design/model.json` ↔ v1.1 **终版 PCB** 焊盘网表（按封装实例逐焊盘比较，两端无源器件按网络集合比较） | `tools/pcb_netlist_check.py` |
| 需求表 | 文档 §7.2 GPIO 表 / §5.5 microSD 表 / SCHEMATIC_NOTES §4.2 + GDEM102T91 规格书 p.7 FPC 表 / §7.4-7.9 功能脚 | `tools/req_check.py` |
| 器件参数 | v1.1 `bom.csv`（含 MPN/Populate）↔ v2 `design/parts-map.json` + 活体器件属性 | 同上 |
| 数据手册 | TUSB320LI / MAX17048 / TPS63070 / TPS22918 引脚表（`datasheets/pin_extract.txt`）、GDEM102T91 p.7/p.20 | 人工逐条 |
| 图形 | `sch export-image` 局部渲染核对二极管/MOS 极性 | `work/audit/d6.png` 等 |

---

## 2. 通过项（逐条）

### 2.1 网表与数据源一致（最强判据）

* v1.1 终版 PCB 有 110 个封装；与 v2 `model.json` 逐焊盘比较：**102 个完全一致**，
  其余 4 个（`J1`/`U1`/`U2`/`U4`）差异只来自 v1.1 里**无名称、无网络**的机械/散热焊盘，
  **网络分配差异 0 处**。
* 活体原理图：P1 **190/190**、P2 **137/137** 引脚网络与 `model.json` 一致；
  悬空 0、错网 0、多余网 0、显式 NC 36 个（P1 13 + P2 23）。

### 2.2 文档 §7.2 ESP32-S3 GPIO 表

22 个已分配脚 **22/22** 与文档一致（IO4/5/6/7/15/16/17/18/8/19/20/9/10/11/12/13/14/21/47/0/2/1）。
模组 U1 的显式 NC：GPIO3/35/36/37/38/39/40/41/42/43/44/45/46/48（14 脚），
与 SCHEMATIC_NOTES §3"未用 GPIO 一律显式 NC、取消全部测试点"一致。

### 2.3 接口引脚分配

| 接口 | 依据 | 结果 |
|---|---|---|
| `J2` 墨水屏 24P FPC | GDEM102T91 规格书 p.7 + SCHEMATIC_NOTES §4.2 | **24/24 一致**（1/4/6/7/19 NC；8 BS1=GND；15/16 VDDIO/VCI=`EPD_3V3`；18 VDD=`EPD_VDD` 仅挂 C35——符合规格书"VDD 由 VCI 内部稳压，仅需电容"） |
| `J3` microSD | 文档 §5.5 | **14/14 一致**（1/8 NC；9 `TF_CD_N` 10 kΩ 上拉；SH 焊盘=GND） |
| `J1` USB-C 16P | 文档 §5.1/§7.4 | CC1/CC2=A5/B5、D±=A6/A7/B6/B7、VBUS=A4/B4/A9/B9、GND=A1/B1/A12/B12、SHIELD=SH；A8/B8(SBU) 显式 NC |
| `J4`/`J5` | 文档 §5.3 | Pin1=BATx_RAW、Pin2=GND、2 个固定脚显式 NC（v1.1 同为无网络） |
| `SW1`–`SW5` | 文档 §5.4/§7.9 | SW1=`RESET_N`、SW2=`BOOT`、SW3/4/5=`KEY1/2/3_N` |

### 2.4 功能需求（§7.3–§7.9）

* **EPD 高压**：`L3` 47 µH(`EPD_3V3`→`EPD_SW`)、`Q1` G/S/D = 1/2/3 = `EPD_GDR`/`EPD_RESE`/`EPD_SW`、
  `D6` 阳极 `EPD_SW`→阴极 `EPD_VGH`、`D7` 阳极 `EPD_X`→阴极 GND、`D8` 阳极 `EPD_VGL`→阴极 `EPD_X`、
  `C29` 飞跨 `EPD_SW`↔`EPD_X`、`R30` 1 MΩ 栅极下拉、`R31` 2.2 Ω 检测 —— **全部与规格书 p.20 一致**
  （用 `sch export-image` 局部渲染核对过二极管朝向）。
* **EPD 供电门控**：`U6` VIN=`3V3_MAIN`、ON=`EPD_PWR_EN`、VOUT=`EPD_3V3`，
  `R29`=100 kΩ 下拉（默认关断）✔；CT/QOD 悬空（最快上升沿/无快速放电，可接受）。
* **USB-C 输入**：`F1` 2 A PTC + `D1` 5 V 双向 TVS；`D2/D3` D± ESD；`D4/D5` CC ESD；
  `R9/R10`=22 Ω 串阻到 GPIO20/GPIO19。
  **TUSB320LI 逐脚复核**：VBUS_DET(4) 经 **R11=900 kΩ** 接 VBUS —— 规格书要求
  "between system VBUS and VBUS_DET **one 900-kΩ resistor**"，**不需要下臂电阻** ✔；
  PORT(3)=GND→UFP(Sink) ✔；ADDR(5)=GND→I²C 地址 0x47 ✔；EN_N(11)=GND 使能 ✔。
* **充电**：`U2` 引脚名与 TI 脚位一一对应；`/CE`=R18 10 kΩ **上拉**（默认禁充）✔；
  ILIM=R13 180 Ω；PMID=C15 **10 µF**（规格书要求 ≥8.2 µF）✔；
  TS 网络 R16 5.23 kΩ / R17 30.1 kΩ + NTC1 10 kΩ(B3435) = TI 推荐值 ✔；
  `CHG_STAT`(STAT) 只挂 R15 10 kΩ 上拉、**未接 MCU**（符合 §7.6 与 §9-4）✔。
* **电量计**：`U4` CTG(1)=GND、**CELL(2)=`BAT_BUS`**、VDD(3)=`BAT_BUS`+0.1 µF、QSTRT(6)=GND、
  ALRT#(5)=`FG_ALRT_N`（R22 10 kΩ 上拉）、EP(9)=GND —— 与 MAX17048 规格书引脚表一致 ✔。
* **3V3 主电源**：`U3` SYS→`3V3_MAIN`；FB 分压 **470 kΩ/150 kΩ → 3.307 V** ✔；
  PS/SYNC 经 `R27` **100 kΩ 到 SYS**（规格书要求 1 k–1 M 串阻，不直连 VIN）✔；
  VSEL 100 kΩ 下拉 → FB2 高阻、FB2 悬空 ✔；L2 1.2 µH(MWSA0402S) ✔。
* **存储**：SPI_SCLK/MOSI/MISO 经 `R33/R34/R35`=0 Ω 与 TF 共用；`TF_CS_N` 独立片选、
  `TF_CD_N` 10 kΩ 上拉 ✔。
* **按键**：KEY1/2/3_N 各 10 kΩ 上拉到 `3V3_MAIN`、低有效 ✔。
* **测试点**：全板无测试点（与 §7.2 一致）✔。
* **网络清单**：文档 §7.8 点名的 70 个网络**全部存在**，全工程 70 网、**无单脚网**。

---

## 3. 文档文字与设计的出入（**已按设计更新文档**，2026-09-22）

1. §7.2 "模组 3V3 引脚就近去耦（C1 22 µF + C2/C3/C4/**C5**）"—— C5 实际是 `RESET_N` 的
   1 µF 电容（v1.1 亦然）；模组侧 3V3 去耦为 C1/C2/C3/C4（另有 C18/C37/C38）。
2. §7.2 "GPIO38/39 与 UART(GPIO43/44)为显式 No Connect" —— 实际还 NC 了
   GPIO3/35/36/37/40/41/42/45/46/48（与 SCHEMATIC_NOTES §3 一致），文档只列了 4 个。
3. §7.3 "4 线 SPI（SCLK/MOSI/**MISO**/CS#）" —— GDEM102T91 的 FPC 无 MISO/SDO 脚
   （1/4/6/7/19 为 NC），`SPI_MISO` 只给 TF 卡；原理图按面板规格书接。
4. §5.5 / §7.8 写 `TF_MISO`；原理图中 `SPI_MISO` 经 R35 0 Ω 与 `TF_MISO` 相连（同 v1.1）——
   文档未提这层 0 Ω 桥接。
5. §7.5 "输入保护：每路各一颗 2 A PTC + 0.1 µF" —— 见 §0 第 4 项（电容在公共 `BAT_BUS` 侧）。

---

## 4. 复现命令

```powershell
cd C:\Code\epdf-hardware\esp32-board-v2.0
python tools/sch_verify.py            # 活体 read/check/bridge-check + 逐脚对账
python tools/pcb_netlist_check.py     # model.json ↔ v1.1 终版 PCB 焊盘网表
python tools/req_check.py             # 文档 GPIO/FPC/SD/接口表 + BOM 对比
python tools/sch_untangle.py --page P1 ; python tools/sch_untangle.py --page P2
```

---

## 5. PCB 侧机械复测（2026-09-22 追加，**只读测量，未改动 PCB**）

方法：`tools/mech_crosscheck.py`、`tools/gerber_j1_outline.py`。
坐标基准已用 **板框 Gerber 自证**：`Gerber_BoardOutlineLayer.GKO` 的实测范围正好是
X 0.000–55.000 / Y 0.000–84.000 mm（原点在板左下，Y 向上），所以文档坐标
（原点在板左上、Y 向下）映射为 `(X, 84 − Y)`；H1–H4 安装孔实测 (3.000, 3.000) 亦印证该映射。

| 受约束项 | v2 实测 | 文档 | 偏差 |
|---|---|---|---|
| J1 信号焊盘列 X | 20.800 – 27.201 | 20.800 – 27.200 | ✓ 0.001 |
| J1 信号焊盘行 Y | **77.294** | 77.650 | **−0.356 mm（整列向板内偏）** |
| J1 屏蔽孔 / 定位孔尺寸 | 1.00×1.80 / 1.00×2.10、Ø0.65 | 同 | ✓（相对间距 8.64 / 4.18 / 5.780 全对） |
| J1 定位孔 Y | **78.369** | 78.725 | **−0.356 mm**（与焊盘行同向同量） |
| J2 焊盘列 X | 2.101 | 2.100 | ✓ |
| J2 Pin1 / Pin24 Y | 47.777 / 36.276 | 47.750 / 36.250 | +0.027 / +0.026 ✓ |
| J3 焊盘行 Y | **67.650** | 67.475 | **+0.175 mm（向板边偏）** |
| J3.9 X | 34.201 | 34.125 | +0.076 |
| J4 / J5 Pin1 X | **7.450** | 8.400 | **−0.950 mm（向左侧偏）** |
| J4 / J5 Pin1 Y | 61.374 / 71.374 | 61.375 / 71.375 | ✓ |
| SW3 / SW4 / SW5 焊盘 | Y 13.299/16.700、40.299/43.700、67.299/70.701；X 52.850 | 同 | ✓ |

结论与待办：

* SW3–SW5、J2 与 J4/J5 的 Y 完全符合；J1 的**封装内部几何**（焊盘尺寸/间距、屏蔽孔、
  定位孔及相互间距）与文档逐项一致。
* **J1 整体相对板下边缘内移 0.356 mm**（焊盘行、定位孔、屏蔽孔同向同量），
  意味着 USB-C 本体外凸约 **0.65 mm** 而非文档的 1.005 mm —— 外壳开孔基准会差 0.36 mm。
  v1.1 参考板的该数值经 F.Cu Gerber flash 校核，因此按文档对齐更稳妥。
* 另有 J3 +0.175 mm、J4/J5 X −0.95 mm 两处小偏差（均为机械净空量级，不影响插接功能）。
* **处置（2026-09-22，用户决定）：接受 v2.0 实装现状，不改 PCB。**
  文档已新增 **§5.6 v2.0 实装坐标（实测）** 记录这些实测值（含偏差列，可按需反向平移），
  §4 表与 §5.1–5.5 标注为 v1.1 参考基线并指向 §5.6；§9 追加第 8/9 条（J4/J5、J3），
  第 1 条 USB-C 外凸改为实装值 **0.874 mm**。外壳/结构件以 §5.6 为准。

---

## 6. 2026-10-10 现场只读复核（EasyEDA typed 回读，**未改动设计**）

方法：`easyeda health` → `board current` → `sch pages/read/check` → `pcb list/nets/report/drc/check/dump`。
现场快照 `work/scan-20261010/board-dump.json`（逐条 CLI 回读输出已在 2026-10-10 清理时删除，
可用 `tools/scan-20261010.ps1` / `scan2-20261010.ps1` / `scan3-20261010.ps1` / `scan4-20261010.ps1` 重跑生成）。
完整数据见 `HANDOFF.md` §16。

### 6.1 复测通过项

| 校验项 | 判据 | 结果 |
|---|---|---|
| 工程与文档身份 | `board current` | Board1 = `Schematic1` `cc227a1a0e59e2a5` + `PCB1` `bf67266b4f7b8c7f`，`linked: true` |
| 原理图 ↔ PCB 器件数一致 | P1 63 + P2 46 = **109** = PCB 器件数 | ✓ |
| 网表可用、跨页无异常 | `sch read` P1/P2（`netlistAvailable: true`） | ✓ 无几何-网表不匹配 / 多网线 / 交叉 / 悬空线 / 零长线 |
| 网络数 | `pcb nets` = **72** | ✓ 与文档 §7.8 点名的 70 个网络 + 2 路 USB 差分可对应；**无未布线网络** |
| **焊盘网表 ↔ 原理图逐脚一致** | `pcb list --include-pads` × `sch read` | ✓ **371 / 371 逐脚一致、0 差异、0 孤儿**（PCB 的 `padNumber → net` 与原理图 P1+P2 的 `pin → net` 全集比对；例：J1 A5=USB_CC1 / B5=USB_CC2 / A6=B6=USB_D_P / A7=B7=USB_D_N / A8=B8=NC；J2 Pin24=EPD_VCOM / Pin13=SPI_SCLK；J3 Pin9=TF_CD_N / Pin2=TF_CS_N；U1 Pin2=3V3_MAIN / Pin27=BOOT） |
| 接口/按键位置 | `pcb list --include-pads --include-bbox` | ⚠️ **与 §5.6（2026-09-22）不符**：J1 −7.62 mm、J3 −3.30 mm、J4/J5 −1.23~−1.63 mm、SW3–SW5 中心间距 27 → 17 mm。见 6.3 |
| 天线禁布区**宽度** | `pcb region list` | 23.000 mm 宽 × 6.000 mm 深 ✓（位置另有偏差，见 6.3） |
| 四角孔**孔数** | `pcb dump` | 4 个 ✓（尺寸/位置另有偏差，见 6.3） |
| 叠层 | `pcb layers` / `stackup show` | 4 铜层：Top(SIGNAL) / Inner1(**PLANE**) / Inner2(**PLANE**) / Bottom(SIGNAL) ✓ 与 §2 的 L2 = 完整 GND、L3 = 内层一致 |
| 板框尺寸 | `pcb outline-get` | 55.000 × 84.000 mm ✓（圆角半径本轮不可 typed 读取，见 6.3） |

### 6.2 电气状态

* **原生 DRC：1 条违规**（唯一阻断项）：
  `Clearance Error / Plane Zone to Via / Inner2 / 3V3_MAIN @(284,-2875)`，
  `distance is 0mil, should be >= 10mil` —— Inner2（3V3_MAIN 内电层）与一个 GND 过孔 0 mil。
  属 `via-crosses-plane`（内电层反焊盘），不是原理图/网表缺陷。
* **DFM 审计（`pcb check`）**：431 issue，但**其阈值来自失真的 live 规则回读**
  （signal/power/gnd 全部读成 393.7 mil ⇒ clearance 按 235.6 mil 判，产生成片假阳）。
  **判定以 `pcb drc` 为准**；`pcb check` 只采信与阈值无关的项：
  `dangling-end` 3 条（`CHG_SW` @605,-1985；`SYS` @535,-1875；`TPS_L1` @1455,-1975）、
  `power-not-poured`（`EPD_VDD`）、`via-crosses-plane` 2 条（= 上述 DRC）。
* **差分对**（`pcb report`）：`USB_DATA` = `USB_D_P`/`USB_D_N` 111.67/111.75 mm，skew **2.96 mil**；
  `USB_DATA2` = `USB_DP`/`USB_DN` 3.56/3.78 mm，skew **8.65 mil**。均在规则容差 10 mil 内。
* **NC 引脚**与文档一致：P1 13 个、P2 23 个（清单见 `HANDOFF.md` §16.6），
  与 §7.2 的未用 GPIO 清单、J2/J3 空脚、电池座 3/4 脚完全对应。

### 6.3 与需求文档的**新偏差**（2026-10-10 新发现，需用户裁决；本轮只读、未改板也未改文档数值）

**（a）受约束接口 / 按键摆位**（焊盘级实测，本文档坐标为「原点板左上、Y 向下」mm）

| 项 | §4/§5.6 基线（2026-09-22） | 现场实测（2026-10-10） | 偏差 |
|---|---|---|---|
| J1 信号焊盘行 X / Y | 20.800–27.201 / 77.294 | **13.183–19.583 / 77.490** | X **−7.617**、Y +0.196 |
| J1 屏蔽孔 X / 本体外凸 | 19.680–28.321 / 0.874 | **12.062–20.704 / 1.069** | X −7.617、外凸 +0.195 |
| J2 焊盘列 X / Pin1–Pin24 方向 | 2.101 / Pin1 在 Y 47.777 | **6.383 / Pin1 在 Y 36.223（针序反向）** | X **+4.282**、针序互换 |
| J3 焊盘行 Y / Pin1–Pin9 X | 67.650 / 34.201–42.850 | **67.635 / 30.904–39.553** | Y −0.015、X **−3.297** |
| J4 / J5 引脚列 X | 7.450 | **5.822** | **−1.628** |
| SW3 / SW4 / SW5 焊盘 | Y 13.299-16.700 / 40.299-43.700 / 67.299-70.701，X 52.850，旋转 90° | **(49.299, 25.001) / (49.301, 41.999) / (49.299, 58.999)，旋转 0°（横排）** | 中心间距 **27.000 → 17.000**、朝向 90° → 0° |

旁证：`work/geom.json` / `geom-final.json` / `ref-last-layout.json`（2026-09-22/23）与 §5.6 一致
（J1 x=944.882 mil、SW3 x=2080.709 mil），而 `work/dump-now.json`（2026-09-28）起就是现场这组值
⇒ **2026-09-24 ~ 09-28 之间板上做过新一轮布局**，§5.6 已被取代。

**（b）板框 / 禁布区 / 孔**

| 项 | 本文件（v1.1 基线） | v2.0 实测（2026-10-10） | 偏差 |
|---|---|---|---|
| 四角安装孔 孔径 | Ø2.200 mm（§3） | **Ø4.400 mm**（半径 2.200 mm 的 Multi-Layer 圆填充） | **+2.200 mm** |
| 四角安装孔 位置 | 距两边各 3.000 mm（§3：(3,3)/(52,3)/(3,81)/(52,81)） | 距两边各 **4.000 mm**（(4,4)/(51,4)/(4,80)/(51,80)） | **+1.000 mm** |
| 天线禁布区 X | 16.000 – 39.000 mm（§6） | **20.500 – 43.500 mm** | **+4.500 mm（宽度不变）** |
| 板框圆角 | R2.000（§2、2026-09-21 Gerber 自证） | **无法 typed 读取**（`outline-get` 返回 `unexpected-start:R`，points/segments 空，只能拿到 AABB） | 待确认 |

补充事实：`work/fab/Drill_NPTH_Through.DRL`（2026-09-21 导出）只有 J1 的两个 Ø0.650 mm 定位孔，
**四角孔没有钻孔记录** ⇒ 它是**铣孔（BoardCutout / Multi-Layer 填充）**而非 NPTH 钻孔。
天线禁布区整体右移 4.500 mm 的原因已查明：v2.0 的 U1 摆在 X 22.500–41.500 mm，
禁布区是跟着模块天线端居中的；v1.1 的 U1 位置不同，所以文档的 16–39 是 v1.1 基线值。

### 6.4 结论

* **功能与连接无缺陷**（沿用第 0 节的结论，本轮现场网表复核仍然成立）。
* **机械侧新增 2 项待裁决偏差**（四角孔 Ø/位置、天线禁布区 X），
  处置方式与 2026-09-22 的 J1/J3/J4/J5 相同：**要么改板，要么把实测值写进本文档**。
  本轮按用户要求只读，两侧都没动。
* 板侧还差 1 条 DRC（Inner2 内电层 ↔ GND 过孔 0 mil）才到“DRC 全过”。
