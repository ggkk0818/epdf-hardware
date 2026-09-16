# ESP32-S3 + GDEM102T91 V1.6 — PCB 布局说明与状态

> **2026-09-15 更新（首次布线）**：§11 的布线顺序已由 `tools/route.py` 执行一轮，
> 结果、未完成项、窄颈规则区与待确认差异见新增的 **`ROUTING_NOTES.md`**。
> 摘要：57/69 网络完成、线间间距校验 0 问题、ERC 0、DRC 1 Error / 3 Warning、
> POWER 网络类线宽由 0.80 调整为 0.50 mm（本版无走廊可通过 0.8 mm）。

> Routing 前最后一轮（`ESP32S3_GDEM102T91_V1.5_to_V1.6_PreRouting_Remaining_Items.md`）。
> 2026-09-15 追加 `ESP32S3_GDEM102T91_V1.6_Final_Documentation_and_BOM_Fixes.md`
> 的文档 / BOM / 生产资料收尾，**仍未开始布线**。
> 与 `agent.md`、`SCHEMATIC_NOTES.md` 配套阅读。
> 板框 55 × 84 mm / 4 层 / 1.2 mm；**Placement 已冻结，布线未开始**。

---

## 0. 本轮（V1.6）执行摘要

| MD 条目 | 内容 | 状态 |
|---|---|---|
| P0 §1 | Q1 → **Si1304BDL-T1-GE3 + SC-70-3** | 已完成（MPN/封装/脚位映射） |
| P0 §1.3 | Q1 换小封装后重新收紧 Booster 岛 | 已完成（R30 4.30 → **3.81 mm**） |
| P0 §2 | L2 → **Sunlord MWSA0402S-1R2MT** | 已完成（厂商 land pattern） |
| P0 §2.3 | U3 ↔ L2 两条 switching trace 对称 | 已完成（两段均为 **4.38 mm**） |
| P0 §3 | J2 → **XKB X05B20U24T** | 已完成（含 FPC 厚度确认 + 官方 CAD 数据） |
| P1 §5 | BQ25895 /CE 上电异常状态验证 | 列入原型测试计划（见 §13） |
| P1 §6 | NTC1 精确料号冻结 | 已完成（Vishay NTCS0603E3103FLT） |
| P2 §7 | BOM PROVISIONAL 继续冻结 | **已完成**（2026-09-15：全部 `RELEASED`；V1.6 文档轮拆出 R21/R31 后为 **52 行**） |
| P2 §8 | 版本号 / Rev / 输出文件名统一 | 已完成（Rev = **V1.6**，命名规则见 §14） |
| §9 | ERC 说明同步 | 已完成（§9） |
| §10 | Placement 不再为 1~2 mm 重排 | 遵守 |
| §11 ⑭ | 正式布线 | **未开始** |
| V1.6 清单 §1 | SW1–SW5 机械说明改为**顶部按压** | 已完成（删除全部“侧按 / 朝右”表述） |
| V1.6 清单 §3 | 系统输入写为 5 V/2 A source compatible | 已完成（§12 测试项同步） |
| V1.6 清单 §4/§5 | L3 参数统一 + 摆放不动 | 已完成（§5.5、§13） |
| V1.6 清单 §6 | 关键 MLCC / 精密电阻 MPN | 已完成（`SCHEMATIC_NOTES.md` §7.3） |
| V1.6 清单 §7 | BOM 增加 `Populate`（R21/C16 DNP、R31 FIT） | 已完成（§13） |

RF 净空决策：ESP32 天线保持 `ESP32_ANT_KEEP_OUT`（X 16–39 / Y 0–6，四层禁铜/走线/
过孔/器件）+ 顶部定位孔**塑料柱**，状态记为 **RF LIMITED-CLEARANCE ACCEPTED**，
本轮不再调整 Placement。

---

## 1. 板框与机械（保持）

55.0 × 84.0 mm 竖版、R2 圆角、4 层 1.2 mm、4 × Ø2.2 NPTH（距边 3 mm）、
无测试点、顶部安装孔用塑料柱（`Dwgs.User` 已标注）。

---

## 2. 叠层（保持）

```
L1 F.Cu 0.035 / PP7628 0.195 (Dk4.2) / L2 In1.Cu 0.035 (完整 GND)
/ CORE 0.63 (Dk4.2) / L3 In2.Cu 0.035 / PP7628 0.195 (Dk4.2) / L4 B.Cu 0.035
```

USB 90 Ω：L1 微带参考 L2，**W 0.24 / S 0.18 mm（≈89.7 Ω）**。

---

## 3. 规则区（保持 V1.5）

| 规则区 | 范围 | 约束 |
|---|---|---|
| `KEY_RIGHT_MECH_KEEP_OUT` | X 49–51, Y 0–84 | 禁 Footprint；走线/过孔/铜/焊盘允许；例外 SW3-5 与 H1-H4 |
| `ESP32_ANT_KEEP_OUT` | X 16–39, Y 0–6 | 四层禁走线/过孔/焊盘/铜/**器件** |
| `J3_SOCKET_KEEP_OUT_1..5` | 卡座下方 5 处 | 禁走线/过孔/焊盘/铜（由厂商封装内嵌区提升为板级） |

另有 `Dwgs.User` 机械说明：`RIGHT_SWITCH_COLUMN` 框与
`MOUNTING HOLES: NYLON / PLASTIC POST ONLY`。

---

## 4. Net Class

| 网络类 | 线宽 / 间距 | 网络 |
|---|---|---|
| Default | 0.20 / 0.15 | 信号、INT、KEY、SPI、I2C、TF |
| USB90 | 0.24 / 0.15（目标间距 0.18） | `USB_DP*`、`USB_DN*` |
| POWER | **0.50 / 0.20** | `USB_VBUS_*`、`BAT*`、`SYS`、`3V3_MAIN`、`CHG_PMID`、`EPD_3V3` |
| SWITCH_NODE | **0.50 / 0.15** | `CHG_SW`、`EPD_SW`、`TPS_L1`、`TPS_L2` |
| HV_EPD | 0.30 / 0.20 | `EPD_V*`、`EPD_X`、`EPD_GDR`、`EPD_RESE` |

> 2026-09-16（`..._Routing_Power_Width_and_R29_Confirmation.md`）：POWER 默认线宽
> 0.80 → **0.50 mm**；新增 `CHG_PMID`/`EPD_3V3`/`TPS_L1`/`TPS_L2`（脱离 Default 的
> 0.20 mm）；按要求拆出 `SWITCH_NODE`（0.50 mm 但保留 0.15 mm 间距，因为 U3 焊盘间隙
> 只有 0.15 mm）。高电流主干在布线收尾时自动加宽到 **0.80 mm**（BAT/SYS/USB_VBUS，
> 当前 20 段），R29 保持冻结位置 (12.8648, 49.5497)。
> min track 0.15 / clearance 0.15 / via 0.40-0.20 / 铜到板边 0.30（不变）。

---

## 5. 本轮器件更换

### 5.1 Q1 → Si1304BDL-T1-GE3（SC-70-3）

| 项 | 原 | 现 |
|---|---|---|
| MPN | "Si1304BDL / Si1308EDL or compatible" | **Si1304BDL-T1-GE3**（RELEASED） |
| 封装 | SOT-23 | **SC-70-3**（`Package_TO_SOT_SMD:SOT-323_SC-70`） |
| 脚位 | G/S/D = 1/2/3 | 同（符号 `Q_NMOS_GSD` 正好对应 Si1304BDL） |

> **不再把 Si1308EDL 列为互换料**：同样 SC-70-3，但它的 Pin1 = S、Pin2 = G，
> 与本板符号映射相反（MD §1.1）。

### 5.2 L2 → Sunlord MWSA0402S-1R2MT

1.2 µH / DCR 27 mΩ max / Isat ≈ 5.2 A / 4.2 × 4.4 mm。封装用 KiCad 官方库
`Inductor_SMD:L_Sunlord_MWSA0402S`（由顺络推荐 land pattern 生成，比自建本地
封装更可靠，也避免库存副本与库不一致）。

### 5.3 J2 → XKB X05B20U24T

| 项 | 原 | 现 |
|---|---|---|
| 料号 | Amphenol F32Q-1A7x1-11024 | **XKB X05B20U24T**（RELEASED） |
| 封装 | KiCad 官方库 Amphenol | **项目本地 `esp32-board-v1.1:X05B20U24T`** |
| 规格 | 24P / 0.5 mm / 上接点 | 同（X05B20U24T = 0.5 mm 间距、上接点、抽屉锁扣、H=2.0 mm） |

**FPC 厚度确认（MD §3.2）**：从 GDEM102T91 机械图（第 6 页侧视图）读到
排线**插入端厚度 0.30 ± 0.03 mm**（排线本体 0.12 ± 0.03 mm，连接侧加补强板），
与 X05B20U24T 的 0.30 mm 规格一致 ✅ → 按 MD 可以正式冻结该连接器。

**封装来源**（按 MD §3.3 的优先顺序）：

1. **XKB 官方图纸** `datasheets/X05B20U24T.pdf`：
   - 推荐 PCB layout 焊盘 **0.30 × 1.60 mm**、间距 0.50 mm、**安装焊盘 2.40 × 3.50 mm**
2. **立创官方 CAD 数据** `datasheets/X05B20U24T_easyeda.json`（C437036）交叉核对
   位置：信号焊盘行跨距 11.50 mm（23 × 0.5 ✅）、两个安装焊盘位于行中心
   ±7.40 mm、行后方 2.35 mm。

生成脚本 `tools/import_xkb_fpc.py`（可重跑）。

**脚位方向核对（MD §3.4）**：

| 检查项 | 结果 |
|---|---|
| Pin1 方向 | 引脚 1 在 **左侧**（与厂商 pin-1 圆点、以及换封装前的 Amphenol 一致） |
| Pin1 = GDEM102T91 Pin1 (NC) | ✅ 网表按编号连接，未改变 |
| Pin24 = GDEM102T91 Pin24 (VCOM) | ✅ |
| 1 ↔ 24 反序 | **无**（J2 焊盘仍在板内 X = 2.10 同一列） |
| Top Contact 面 / 插入方向 | 上接点；排线自 −X（板左缘）插入 |
| 开口朝向 | 仍朝 PCB 左侧 ✅ |

> 更换后 J2 位置由 (5.0, 42.0) 调整为 **(3.275, 42.0)**，使信号焊盘落在
> 板内 X = 2.10 mm（与换封装前完全相同），courtyard 距板左缘 1.05 mm。

### 5.4 NTC1 → Vishay NTCS0603E3103FLT

10 kΩ @25 °C、**B25/85 = 3435 K**（与 BQ25895 TS 网络设计的 Semitec 103AT 同 B 值）、
0603、RELEASED。

> **测量含义（MD §6.3）**：J4/J5 是 2Pin 电池接口，板上 NTC 测的是
> **PCB / 电池附近环境温度**，不是电芯内部温度。若产品需要真正的电芯温度保护，
> 需要 3Pin 电池接口或电池包内置 NTC。

### 5.5 采购冻结轮（2026-09-15）的封装变更

| 位号 | 原封装 | 现封装 | 变更原因 |
|---|---|---|---|
| L1 | `Inductor_SMD:L_Coilcraft_XAL5030-XXX` | **`Inductor_SMD:L_Sunlord_MWSA0503S`** | 原设计料 Coilcraft XAL5030-102MEC 在华秋**无现货**（仅订货/代购，￥19.44 起 @400+）；改用顺络 MWSA0503S-1R0MT（1.0 µH / DCR 14 mΩ / Isat 10 A / 5.4×5.2×3.0 mm），外形与原 5.48×5.28×3.1 mm 基本一致 |
| L3 | `Inductor_SMD:L_Taiyo-Yuden_NR-40xx` | **`Inductor_SMD:L_Changjiang_FNR4020S`** | 原 47 µH/4×4 现货款余量偏紧（500 mA 额定 / Isat 570 mA）；改用 cjiang FHD4020S-470MT（**47 µH ±20 % / Rated 660 mA / Isat 1.3 A / DCR 950 mΩ** / 4.0×4.0×2.0 mm），其推荐焊盘 1.10×3.7 mm @ ±1.50 mm 与 KiCad 官方 FNR4020S 封装一致 |

两处替换均保留原 uuid、原坐标与焊盘网络（L1：CHG_SW / SYS；L3：EPD_3V3 /
EPD_SW），仅封装图形与焊盘尺寸更新；替换后 **DRC = 0 Error / 0 Warning**、
**ERC = 0**。L1 中心仍落在 U2 SW 引脚中心线上（§6 的对称约束不变）。

> 结构提示：**L3 高度 1.8 → 2.0 mm**（+0.2 mm），L1 高度 3.1 → 3.0 mm。

---

## 6. 器件放置

### 6.1 放置引擎（保持 V1.5）

精确矩形碰撞 + `GAP = 0.50 mm`；**49 个引脚级对齐**；106 器件、courtyard 碰撞 0。

### 6.2 本轮相关距离

| 项目 | 距离 mm | 说明 |
|---|---:|---|
| **L2 ↔ U3 L1 引脚** | **4.38** | 电感中心落在 L1/L2 引脚中心线（Y = 45.00） |
| **L2 ↔ U3 L2 引脚** | **4.38** | 与上一行**完全相等** → 两条 switching trace 等长 |
| **R30 ↔ Q1 Gate** | **3.81** | SC-70-3 缩小后收紧（原 4.30） |
| R31 ↔ Q1 Source/RESE | 5.24 | 下方被 D6/D8 占满，见 §10 |
| C29 ↔ D6 EPD_SW | 5.32 | Booster 岛内（D8 的 EPD_X 3.3 mm） |
| J2 焊盘 → 板左缘 | 2.10 | 与换封装前一致 |

其余保持 V1.5 已确认的距离（R32→J3 CS 14.47、C10→REGN 4.65、C13→SYS 5.86、
R23→FB 3.63、R24→R23 1.81、R33/R34→U1 2.84/2.34、R35→J3 MISO 2.96 mm），
按 MD §10 不再为 1~2 mm 重排。

---

## 7. 丝印（保持 V1.5 策略）

小无源件 0.8 mm / IC·连接器 1.0 mm；位号只在自身轮廓外 0.25–3.3 mm 内，
空间不足者移到 F.Fab（装配图可见）。当前 104 个可见位号、2 个移到 F.Fab
（C9、C15，位于 BQ25895 / J2 高压区）；`silk_over_copper` 与 `silk_overlap` 均为 0。

---

## 8. ERC / DRC 结果

```
ERC           : 0 violations
                已启用：footprint_link_issues (error)、footprint_filter (error)
                仍 Ignore：single_global_label、four_way_junction、
                          simulation_model_issue（与本设计无关，MD §9）
DRC Errors    : 0
DRC Warnings  : 0
Unconnected   : 255   = 尚未布线的飞线（本阶段预期）
DRC Exclusions: 0
```

**Placement 阶段 DRC 已全零**（含 courtyard、库一致性、丝印、规则区检查）。
`track_not_centered_on_via`、`tuning_profile_track_geometries` 按 MD §16
保持 Ignore，布线完成后开启。

---

## 9. 与 MD 清单的差异 / 未完成项

| 项 | MD 期望 | 实际 | 原因 |
|---|---|---|---|
| §1.3 | R30 贴 Q1 Gate | 3.81 mm | 岛上 D6/D7/D8/R28 已占满，这是当前最近空位 |
| §1.3 | R31 靠 Q1 Source/RESE | 5.24 mm | Q1 下方整排被 D6（EPD_SW→VGH）与 D8 占据，再近需拆开关环路 |
| §2.2 | 新建本地封装 `esp32-board-v1.1:MWSA0402S` | 改用 KiCad 官方库 `Inductor_SMD:L_Sunlord_MWSA0402S` | 该库封装即由顺络推荐 land pattern 生成，避免多一份需维护的本地副本，且库一致性检查为 0 |
| §7 | BOM PROVISIONAL 全部冻结 | **已完成（2026-09-15）** | D1 / D2-D5 / D6-D8 / F1-F3 / L1 / L3 / R13 已全部落到华秋商城国内现货料号，L1、L3 顺带换成 KiCad 官方库封装；`bom.csv` 全 `RELEASED`（V1.6 文档轮拆出 R21/R31 后 52 行），清单见 `SCHEMATIC_NOTES.md` §7 / §7.3 |
| §8 | 输出文件名统一 | 已统一 Rev/Title Block；工程文件仍名 `esp32-board-v1.1.*` | 见 §14 的发布命名规则；重命名工程会破坏工具链与既有引用 |
| §3.4 | J2 逐项复核 | 已核对 Pin1/Pin24/Top Contact/插入方向/固定焊盘位置 | **建议投产前再用实物或厂商 3D 模型核对一次**（本封装由官方图纸+CAD 数据生成，未经实物比对） |

---

## 10. 已接受、不再调整的项（MD §4/§10）

```
RF LIMITED-CLEARANCE ACCEPTED
天线净空：ESP32_ANT_KEEP_OUT（X 16-39 / Y 0-6，四层全禁）+ 顶部塑料柱
```

以下距离按 MD §10 接受，不再追求极限压缩：
R32→J3 CS 14.47 / C10→REGN 4.65 / C13→SYS 5.86 / C29→EPD_SW·X 4.51·3.34 /
R23→FB 3.63 / R24→R23 1.81 / R33·R34→U1 2.84·2.34 / R35→J3 MISO 2.96 mm。

---

## 11. 正式布线顺序

1. BQ25895 switching loop（SW→L1→SYS）
2. TPS63070 switching loop（U3 L1/L2 ↔ L2，两侧等长 4.38 mm）
3. EPD Booster switching loop（L3/Q1/D6-D8/C29/R30/R31）
4. BAT / SYS / 3V3 / VBUS 电源分配（优先铺铜）
5. USB 差分对（W/S = 0.24/0.18，L2 连续参考，ESD 靠连接器、22 Ω 靠 MCU）
6. SPI（R33/R34 在 MCU 端、R35 在卡端）
7. I2C / INT / GPIO / KEY
8. 电源平面 / GND / 缝合过孔
9. Refill → 最终 DRC（开启 via-center 与 tuning 检查）→ Gerber / 钻孔 / CPL

---

## 12. 原型测试计划（非布线阻塞项，MD §5/§13）

```
[ ] /CE 异常启动时序（BAT-only 冷启动 / 仅 VBUS / 同时接入 / 极低电量插 USB /
    充电中 MCU 复位 / Brownout / 反复插拔 USB）——同时观察 CE、3V3_MAIN、
    VBUS、BAT 电压与充电电流，确认 MCU 配置完成前无高充电电流窗口
[ ] 25 °C 下最大 USB 输入电流
[ ] 40 °C 环境下持续运行
[ ] 50 °C 环境下持续运行
[ ] Wi-Fi TX + EPD refresh + microSD 并发
[ ] 充电 + 系统最大负载并发
[ ] 单电池最大系统电流 / J4-J5 与线束温升 / BAT_BUS 压降
[ ] ESP32 Wi-Fi / BLE RSSI、吞吐、距离、装壳前后对比（有限净空验证）
[ ] EPD Booster 高压波形 / TPS63070 3V3 ripple / USB 枚举 / microSD 高速读写
[ ] 外壳按键柱垂直按压 SW3 / SW4 / SW5 的装配公差
```

> **系统输入能力（V1.6 清单 §3）**：`5 V / 2 A source compatible，非高温连续 2 A
> 保证`。允许使用 5 V/2 A 适配器，但不承诺 40 / 50 °C 环境下长时间接近 2 A ——
> 原因是 F1~F3（BSMD0805L-200）的 PTC Hold Current 随温度降额。高温工况需同时记录
> **F1 温升、USB-C 温升、BQ25895 温升、VBUS 压降、PTC 两端压降**，并确认无热跳闸。

---

## 13. 版本与发布命名（MD §8）

| 项 | 值 |
|---|---|
| PCB Revision | **V1.6**（PCB 与原理图 Title Block 均已更新，日期 2026-09-15） |
| 采购冻结 | **2026-09-15**：BOM 全部 52 行 `RELEASED`（R21 与 R31 已按 `Populate` 拆行）；L1 → Sunlord MWSA0503S-1R0MT、L3 → cjiang FHD4020S-470MT（两者均改用 KiCad 官方库封装）。本轮不改拓扑与摆放，**Rev 保持 V1.6** |
| BOM | `bom.csv` 随工程生成，列为 `Reference,Value,Footprint,Status,MPN,Populate`；`Populate` = FIT / DNP（**R21 = DNP、C16 = DNP、R31 = FIT**）；MPN 格式为 `MPN（华秋 Gxxxxxxxx）`，导出命令见 `SCHEMATIC_NOTES.md` §7 |
| 开关机械动作 | **SW1~SW5 = Omron B3U-1000P 为顶部按压型（Top-actuated）**：外壳按键柱从 PCB 正面垂直压下。90° 摆放只影响焊盘/丝印方向；`RIGHT_SWITCH_COLUMN`（X 49–55）与 `KEY_RIGHT_MECH_KEEP_OUT`（X 49–51 / Y 0–84）保持不变 |
| 发布文件命名建议 | `ESP32S3_EPD_V1.6_PCB.gbr`、`..._PTH.drl`、`..._NPTH.drl`、`..._BOM.csv`、`..._CPL.csv` |

工程文件名仍为 `esp32-board-v1.1.*`（工具链与历史引用依赖它）；**版本以 Title Block
的 Rev 字段为准**，Gerber/BOM 导出时按上表命名，避免"板是 V1.6、生产资料写 V1.1"。

---

## 14. 再生方式

```powershell
$py = 'C:\Users\ggkk2\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_sch.py'          # 原理图
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\gen_pcb.py'          # PCB 布局 + 丝印
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\import_xkb_fpc.py'   # J2 封装（厂商数据）
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\usb_impedance.py'    # USB 90Ω 计算
& $py 'C:\Code\epdf-hardware\esp32-board-v1.1\tools\verify_connectors.py'# 连接器外凸复核
```

厂商资料：`datasheets/X05B20U24T.pdf`（XKB 图纸）、
`datasheets/X05B20U24T_easyeda.json`（立创官方 CAD）；
本地封装库：`lib/esp32-board-v1.1.pretty/`。
