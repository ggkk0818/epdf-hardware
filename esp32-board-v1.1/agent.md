# ESP32-S3 + GDEM102T91 PCB V1.1 任务交接说明

> **2026-09-16 更新（按 `ESP32S3_GDEM102T91_V1.6_Post_First_Routing_Next_Steps.md` 收尾）**：
> 完成 MD §20 的 ①②③ —— **DRC 已清零：0 Error / 0 Warning**（此前 2 Error + 3 Warning）：
> - EPD_GDR ↔ EPD_RESE 间距（0.125 → 0.225 mm）：把 EPD_RESE 在 J2 Pin3 的过渡重画
>   （抬高 0.25 mm + 收颈 0.20 mm，层间过孔随移），脚本内自动核对间隙、失败即回滚；
> - EPD_3V3 ↔ C31 GND 间距：该 0.5 mm 段与斜线的交点整体上移 0.3 mm，器件不动；
> - EPD_BUSY / EPD_RESE / SPI_SCLK 的 0.1 mm 悬空线头：端点落到所属短桩端点（共享端点）；
> - EPD_VSH1 ↔ C32 的 connection width：端点推入焊盘 0.3 mm。
>
> 同时按 MD §1 统一统计：**69 个非 GND 网络中已布线 55、未完成 14**（线段 706、信号过孔 71、
> GND 缝合过孔 135；unconnected = 92，即未完成网络 + GND 孤岛）。§3.1 的 14 个未完成网络已按
> MD §6~§15 的优先级重排（TPS_L2 → SYS → USB DP/DN → EPD_VGH → CHG_REGN → U2 控制线/I²C →
> TF → TYPEC_INT_N → 最后 3V3_MAIN），细节与操作步骤见 `ROUTING_NOTES.md` §3、§5。

> **2026-09-16 更新（按 `ESP32S3_GDEM102T91_V1.6_Routing_Power_Width_and_R29_Confirmation.md`
> 执行确认项）**：POWER 默认线宽 **0.80 → 0.50 mm** 正式生效；`CHG_PMID`、`EPD_3V3`、
> `TPS_L1`、`TPS_L2` 脱离 `Default`（不再按 0.20 mm 布线），并按要求拆出
> **`SWITCH_NODE`** 网络类（0.50 mm / 0.15 mm）承载 `CHG_SW`/`EPD_SW`/`TPS_L1`/`TPS_L2`
> ——因为 U3（TPS63070）焊盘间隙只有 0.15 mm，若归入 POWER（0.20 mm 规则）焊盘自身就会违规。
> BAT/SYS/USB_VBUS 主干在收尾阶段自动加宽到 **0.80 mm**（20 段）；`CHG_SW`/`TPS_L1`/`TPS_L2`/
> `EPD_SW` 全程**禁用过孔**。**R29 保持冻结位置 (12.8648, 49.5497)**，未使用旧版 (23.x, 43.x)；
> 器件坐标一律未改动。当前 69 个网络中 **54 个已布通**，15 个未完成；ERC = 0，
> DRC = 2 Error / 3 Warning（细节见 `ROUTING_NOTES.md` §3、§4）。

> **2026-09-15 更新（V1.6 首次布线，Routing 已完成第一轮）**：按本文件 §七 的顺序完成了
> **4 层布线**，新增工具 `tools/board_model.py`、`tools/route.py`、`tools/apply_routing.py`、
> `tools/check_routing.py`、`tools/render_board.py`，详见 **`ROUTING_NOTES.md`**。要点：
> - **69 个网络（不含 GND）中 57 个已布线**，12 个未完成（集中在 BQ25895 左列、TPS63070
>   左列、TUSB320、ESP32 底部、USB-C / FPC 扇出的最后 1–2 段）。
> - 线段 689、信号过孔 75、GND 缝合过孔 145；In1.Cu 仍为完整 GND 平面，
>   L1/L2/L3/L4 四层 GND 铺铜已填充。
> - **ERC = 0**；**DRC = 1 Error / 3 Warning**（1 条 EPD_GDR↔EPD_RESE 间距 + 3 条 J2 扇出区
>   0.1 mm 悬空线头）；`tools/check_routing.py` 独立校验线间间距 **0 问题**；
>   unconnected = 83（= 12 个未完成网络 + GND 铺铜孤岛）。
> - **POWER 网络类线宽 0.80 → 0.50 mm**（`.kicad_pro`）：本版没有任何走廊能通过 0.8 mm，
>   需用户确认是否接受，或改为内层铺铜方案。
> - **`tools/gen_pcb.py` 已与冻结板文件分叉**（无法复现 R29 等位置）：布线一律以仓库中的
>   `.kicad_pcb` 为准，`apply_routing.py` 默认从 `routing/board_prerouting.kicad_pcb` 重来。
> - 下一步 = 人工收尾 12 个网络 + 4 个 DRC 项，再开 `track_not_centered_on_via` /
>   `tuning_profile_track_geometries` 检查，最后出 Gerber。

> **2026-09-15 更新（V1.6 文档 / BOM / 生产资料收尾）**：按
> `ESP32S3_GDEM102T91_V1.6_Final_Documentation_and_BOM_Fixes.md` 完成文档与生产
> 资料修正，**仍未开始布线**。要点：
> - **SW1–SW5 = Omron B3U-1000P 为顶部按压型（Top-actuated）**：外壳按键柱从
>   PCB **正面垂直向下**压执行器。全文删除“侧按 / 侧面按压 / 按压方向沿 PCB X 轴 /
>   朝板右外侧 / Right-angle side-actuated”等旧描述；90° 摆放只影响焊盘与丝印方向，
>   不改变按压方向。`RIGHT_SWITCH_COLUMN`（X 49–55）与
>   `KEY_RIGHT_MECH_KEEP_OUT`（X 49–51 / Y 0–84）保持不变。
> - **系统输入能力定义为 “5 V / 2 A source compatible，非高温连续 2 A 保证”**：
>   允许使用 5 V/2 A 适配器，但不承诺 40 °C / 50 °C 环境下长时间接近 2 A（PTC 保持
>   电流随温度降额）。充电目标仍为 ICHG ≈ 896 mA。原型测试新增 25 / 40 / 50 °C、
>   并发负载，并记录 F1 温升与 PTC 两端压降。
> - **L3 = cjiang FHD4020S-470MT** 参数统一为 47 µH ±20 % / Rated 660 mA /
>   Isat 1.3 A / DCR 950 mΩ / −40…+125 °C / H ≈ 2.0 mm（删除旧的 Isat 1.10 A、
>   Irms 0.56 A）。本轮**只改参数记录，不动 EPD Booster 摆放**。
> - **生产 BOM 新增 `Populate` 字段（FIT / DNP）**：R21 = DNP、C16 = DNP、
>   R31 = FIT。R21 与 R31 同值但已落到不同 BOM 行，不会再出现“整行删除误删 R31”
>   的风险。
> - **补齐关键无源器件 MPN（华秋国内现货）**：C27–C33 = CL21A475KAQNNNG（G0936665）、
>   C34/C35 = CL10B105KA8NNNC（G0021698）、C36 = 0805B105K250AT（G4185910）、
>   10 µF = CL21A106KAYNNNE（G0022684）、22 µF = TCC0805X5R226K250FT（G14559843）、
>   R16 = 0603WAF5231T5E（G3705144）、R17 = RC0603DR-0730K1L（G4243913）、
>   R23 = 0603WAF4703T5E（G0064373）、R24 = RC0603FR-07150KL（G0072618）。
> - **ERC 说明统一**：V1.6 为 0 violations；`footprint_link_issues` 与
>   `footprint_filter` 启用，`single_global_label` / `four_way_junction` /
>   `simulation_model_issue` 按项目设计策略保持 Ignore。删除“没有关闭任何全局 ERC
>   检查项”的旧说法。
> - 验证：**ERC = 0 violations；DRC = 0 Error / 0 Warning**（unconnected = 255，
>   未布线状态的预期值）。
>
> **2026-09-15 更新（采购冻结，Rev 仍为 V1.6）**：把 BOM 里最后一组
> `PROVISIONAL` 器件全部落到华秋商城（hqchip）**国内现货**料号并冻结。
> 本轮**不改变电路拓扑与器件摆放**，只改 L1/L3 的封装和 MPN/Status 字段，
> 因此 Title Block Rev 保持 **V1.6** 不变。要点：
> - **D1** = PESD5V0S1BA,115（安世，SOD-323 双向 5 V，VBUS）；
> - **D2/D3** = GBLC05C（台舟，**1 pF 低容**，USB D+/D−）；
> - **D4/D5** = LESD3Z5.0CMT1G（乐山无线电，USB CC1/CC2）；
> - **D6~D8** = MBR0530T1G（安森美，SOD-123，EPD 整流）；
> - **F1~F3** = BSMD0805L-200（佰宏，0805 PTC，保持 2 A / 跳闸 4 A / 6 V）；
> - **L1** = Sunlord MWSA0503S-1R0MT（1.0 µH / DCR 14 mΩ / Isat 10 A），
>   封装由 Coilcraft XAL5030 改为 `Inductor_SMD:L_Sunlord_MWSA0503S`；
> - **L3** = cjiang FHD4020S-470MT（47 µH ±20 % / Rated 660 mA / Isat 1.3 A /
>   DCR 950 mΩ / 4×4×2.0 mm），
>   封装由 Taiyo-Yuden NR-40xx 改为 `Inductor_SMD:L_Changjiang_FNR4020S`；
> - **R13** = 0603WAF1800T5E（厚声，180 Ω ±1 %，BQ25895 KILIM）。
> - MPN 字段统一写作 `MPN（华秋 Gxxxxxxxx）`，已同时写进**原理图字段**与生成
>   脚本 `tools/gen_sch.py`；`bom.csv` 重新导出后 **PROVISIONAL = 0，全部
>   RELEASED**（当时 51 行；V1.6 文档轮拆出 R21/R31 后为 **52 行**）。
>   完整冻结清单见 `SCHEMATIC_NOTES.md` §7。
> - 验证：**ERC = 0；DRC = 0 Error / 0 Warning**，unconnected = 255（未布线状态的
>   预期值，与冻结前一致）。
> - 结构提示：L3 高度 1.8 → **2.0 mm**、L1 高度 3.1 → 3.0 mm。
>
> **2026-09-15 更新（V1.6，Routing 前最后一轮）**：按
> `ESP32S3_GDEM102T91_V1.5_to_V1.6_PreRouting_Remaining_Items.md` 完成全部 P0/P1
> 及 P2 的版本统一，**未布线**。要点：
> - **Q1 = Si1304BDL-T1-GE3 + SC-70-3**（原 SOT-23）。不再列出 Si1308EDL 作为
>   互换料（同封装但 Pin1 是 S，与符号映射相反）。Booster 岛随之收紧，
>   R30 距 Gate 4.30 → **3.81 mm**。
> - **L2 = Sunlord MWSA0402S-1R2MT**（1.2 µH / DCR 27 mΩ / Isat≈5.2 A），
>   封装用 KiCad 官方库 `Inductor_SMD:L_Sunlord_MWSA0402S`。电感**中心落在
>   U3 L1/L2 引脚中心线上**，两条 switching trace 各 **4.38 mm（等长）**。
> - **J2 = XKB X05B20U24T**（24P / 0.5 mm / 上接点 / 抽屉锁扣）。
>   FPC 厚度已从屏幕机械图确认 **0.30 ± 0.03 mm**，与连接器规格一致。
>   封装 `esp32-board-v1.1:X05B20U24T` 由 XKB 官方图纸（焊盘 0.30×1.60、
>   安装盘 2.40×3.50）+ 立创官方 CAD 数据（位置交叉核对）生成，
>   脚本 `tools/import_xkb_fpc.py`；Pin1/Pin24 未反序（J2 焊盘仍在 X=2.10 列）。
> - **NTC1 = Vishay NTCS0603E3103FLT**（10 kΩ、B25/85 = 3435 K，匹配 103AT）；
>   J1 = GCT USB4105-15-A-120、J3 = Hirose DM3AT-SF-PEJM5、SW1-5 = Omron
>   B3U-1000P 一并冻结（RELEASED）。
> - **版本统一**：PCB / 原理图 Title Block Rev = **V1.6**（2026-09-15）；
>   发布文件命名规则见 `PCB_LAYOUT_NOTES.md` §13。
> - **ERC 策略说明已修正**：footprint_link_issues / footprint_filter 启用；
>   single_global_label、four_way_junction、simulation_model_issue 为 Ignore。
> - 最终：**ERC = 0；DRC = 0 Error / 0 Warning**，排除项 0，unconnected = 255。
> - **Placement 冻结**：除 J2/Q1 封装已按 MD 完成外，其余距离按 MD §10 接受。
>
> **2026-09-15 更新（V1.5 整改）**：按
> `ESP32S3_GDEM102T91_Current_Layout_Optimization_Plan.md` 完成 ①~⑬，
> **不含布线**。要点：
> - **右侧按键墙改为全高**（X 49–51，Y 0–84）：V1.4 时只挡到 Y73，R33 从下方
>   绕进按键列；现在 X>51 只剩 SW3/4/5 与四个定位孔（已验证规则会真实报错）。
>   `RIGHT_SWITCH_COLUMN` 只保留 `Dwgs.User` 机械说明，不再建 keepout 区。
> - **R33 / R34 移到 U1 SPI 输出端**（2.84 / 2.34 mm），SW1/SW2 下移 3 mm 让位。
> - **U1 周边重排**：C1~C4、R1/C5、R3~R5 全部移到模块左侧两列，C4 距 3V3 引脚
>   2.33 mm、R1 距 RESET 3.63 mm。
> - **C12 回到 U2 BAT 引脚**（3.64 mm）、C15 PMID 2.37 mm、C10 REGN 4.65 mm；
>   **C29 进入 EPD Booster 岛**（距 EPD_SW/EPD_X 焊盘 4.5 / 3.3 mm）；R24 上移
>   至 R23 下方 1.81 mm。
> - **全板丝印重排**：位号只在自身轮廓外 0.25–3.3 mm 内，空间不足则隐藏
>   （本轮隐藏 5 个）；`silk_overlap` 10 → **0**，被器件遮挡 14 → **0**。
> - **U1 / J3 library mismatch 已消除**：改用项目本地封装、把封装内嵌 rule area
>   提升为板级规则区、U1 顶部丝印不再越板边。
> - 最终：**ERC = 0，DRC = 0 Error / 0 Warning**，排除项 0，unconnected = 255。
>
> **2026-09-14 更新（V1.4 收尾）**：
> 1. **顶部两个安装孔确定使用塑料柱**（用户确认）：孔位保持不动，板内
>    `Dwgs.User` 已标注 `NYLON / PLASTIC POST ONLY / NO METAL IN ANTENNA AREA`；
>    整机 RF 实测仍建议做。
> 2. **丝印全面优化**：位号摆放算法重写（遮挡感知评分、环绕基准改用实体轮廓、
>    贪心 + 迭代爬坡 + 个别救援三遍求解），小尺寸无源器件位号字号改 0.8 mm。
>    结果：`silk_over_copper` 0、**位号被器件遮挡 0 个**（原 14 个，含 3 个被
>    J2 座体盖住）、`silk_overlap` **1**（原 10）。
> 3. 当前：**ERC = 0，DRC = 0 Error / 5 Warning**（1 丝印压字 + 2 模块丝印压板边 +
>    2 含规则区封装的固有 mismatch），排除项 0，unconnected = 255（未布线）。
>
> **2026-09-14 更新（V1.4 整改）**：按
> `ESP32S3_GDEM102T91_V1.3_to_V1.4_Placement_and_Checklist.md` 完成
> ①②③④⑤⑥⑦⑧(文档)⑩⑪⑫，**不含布线**。要点：
> - **J2 EPD FPC 换成上接点连接器** `Amphenol F32Q-1A7x1-11024`（24P／0.5mm／
>   Top contact，官方库 land pattern），位置改 (5.0, 42.0)。
> - **`RIGHT_SWITCH_COLUMN`（X 49–55）** 成为正式机械列：命名规则区 +
>   `Dwgs.User` 说明框 + 自定义 DRC 规则（SW3/4/5 为例外）。实测列内只剩三颗按键。
> - **C37 / R32 / R35 移出右侧**并围绕 J3 重排：C38 2.97 mm、C37 4.24 mm、
>   R35 4.45 mm、R32 7.04 mm（到各自 J3 引脚）。
> - **BQ25895 收紧**：C9 VBUS 2.09 mm、C15 PMID 4.18 mm、C10 REGN 6.61 mm、
>   R21/C16 Snubber 成对（2.19 mm）且紧贴 L1；C12 移到电池端、C14 移到 U3 输入组。
> - **USB ESD 四颗改成 90° 同一行镜像排列**（CC1/D−/D+/CC2），离连接器 2.6–3.5 mm。
> - **EPD 高压电容改 3×2 紧凑矩阵**（占 X 8.3–19.8），比原单排短约 9.5 mm；
>   R30 移到 Q1 侧。
> - **ERC 策略恢复**：`footprint_link_issues`、`footprint_filter` 重新启用（error）→
>   抓出并修掉 J4/J5 符号↔封装过滤不匹配（新增本地符号 `CONN_01X02_PICO`）。
> - **DRC 策略恢复**：`missing_courtyard`（error，0 条）、`lib_footprint_mismatch`
>   （warning，2 条固有）；安装孔改用官方库封装；ESP32 天线禁布区补上"禁器件"。
> - 最终：**ERC = 0，DRC = 0 Error / 14 Warning，排除项 0**，unconnected = 255（未布线）。
> - 详细逐项对照见 `PCB_LAYOUT_NOTES.md` §0 与 §10。
>
> **2026-09-14 更新（V1.3 整改）**：按
> `ESP32S3_GDEM102T91_V1.2_to_V1.3_Next_Round_Modifications.md` 完成 P1 + P2
> （**不含布线**）。要点：
> - 建立两个正式 DRC 规则区：`ESP32_ANT_KEEP_OUT`（天线，四层全禁）、
>   `KEY_RIGHT_MECH_KEEP_OUT`（右侧按键机械区，只禁器件）。
> - 放置引擎由 0.2 mm 栅格改为**精确矩形判断**（GAP = 0.50 mm），新增
>   **29 个引脚级对齐放置**：L1 与 U2 SW 引脚 Center-Y 完全一致、C11 BTST 1.95 mm、
>   C18 SYS 1.90 mm、R23 FB 3.63 mm、R23/R24 同 Center-X 分压列、
>   EPD 五颗高压电容同一 Center-Y = 37.25 mm、USB ESD 两列镜像对。
> - 卫星器件到锚点最大间隙 **34.9 mm → 7.6 mm**；最紧 courtyard 间距 0.50 mm。
> - 新增**丝印位号自动摆放**：silk_over_copper **63 → 0**，丝印类告警 **121 → 15**。
> - MD §2 充电策略（ICHG = 896 mA、/CE 启动时序）已写入原理图注释区（无电路改动）。
> - 最终：**ERC = 0，DRC = 0 Error / 15 Warning**（11 文字互搭 + 2 定位孔 + 2 模块丝印压板边），
>   unconnected = 255（未布线）。
> - 定位孔（含天线区、按键区）按用户要求**保持不变**；板框仍 55 × 84 mm。
> - 详细逐项对照见 `PCB_LAYOUT_NOTES.md` §0 与 §10（含未满足项与原因）。
>
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
8. 已生成 `bom.csv`（含 `Status` = RELEASED / PROVISIONAL 与 `MPN` 列）；
   2026-09-15 采购冻结后**全部行均为 `RELEASED`**，MPN 后附华秋编号。
   V1.6 文档轮新增 `Populate` 列（FIT / DNP）后共 **52 行**（R21 与 R31 拆行）。
9. 已生成 `esp32-board-v1.1.kicad_pcb`：**55×84 mm 竖版**、R2 圆角、
   4×Ø2.2 mm 定位孔（距边 3 mm）、4 层叠层（Dk 4.2 / 外层 1 oz）、
   4 个 Net Class（Default / USB90 0.24-0.18 / POWER / HV_EPD）、
   天线禁布规则区 `ESP32_ANT_KEEP_OUT`、按键机械禁布区
   `KEY_RIGHT_MECH_KEEP_OUT`，106 个器件全部摆放完毕（其中 29 个为引脚级对齐放置）。
10. ~~PCB DRC：0 Error / 15 Warning~~ → **已清零**：V1.6 起 **0 Error / 0 Warning**
    （历史 15 条为位号文字互搭、定位孔在天线 courtyard 内、模块丝印压板边，已在
    丝印重做与规则区调整中消除）。255 条未连接飞线＝尚未布线，本阶段预期。
    丝印位号已由 `gen_pcb.py` 的 `build_silk()` 自动避让焊盘（silk_over_copper = 0）。

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

### 布线阶段（2026-09-15 第一轮已完成，详见 `ROUTING_NOTES.md`）

1. 已完成：4 层布线框架（0.1 mm 栅格 A* + 出线预约 + 功率宽度阶梯 + 合法性重布）、
   In1.Cu 完整 GND 平面、四层 GND 铺铜与 145 个缝合过孔、5 个 `PWR_NECK_*` 窄颈规则区。
2. 未完成：12 个网络（`3V3_MAIN`、`SYS`、`USB_VBUS_RAW/PROT`、`I2C_SCL/SDA`、
   `CHG_CE/INT_N/OTG`、`TPS_L2`、`SPI_SCLK`、`TF_SCLK`、`TYPEC_INT_N`、`EPD_VGH`、
   `USB_DN_CONN`）的最后 1–2 段，需人工交互布线收尾。
3. 未完成：4 个 DRC 项（1 间距 + 3 悬空线头，均在 J2 FPC 扇出区）。
4. 待确认：POWER 网络类线宽 0.80 → 0.50 mm（见 `ROUTING_NOTES.md` §4.1）。

### 原理图阶段

1. EPD 高压外围已按 GDEM102T91 第 20 页锁定（`SCHEMATIC_NOTES.md` §4），
   投板前仍需人工逐节点复核。
2. 原理图仍为单页（按 8 个功能区标注）。正式发布前建议按 MD 分页
   `00_System_Block` 至 `08_Buttons_Debug_Testpoints`。
3. ~~USB、MicroSD、FPC、电池连接器、按键的最终料号未确定~~
   → **已全部冻结**（2026-09-15 采购冻结轮 `bom.csv` 全部 `RELEASED`；V1.6 文档轮
   补齐关键 MLCC / 精密电阻 MPN 后为 52 行，清单见 `SCHEMATIC_NOTES.md` §7、§7.3）；
   3D 模型除本项目自制封装外均取自 KiCad 官方库。
4. BOM 已生成（`bom.csv`），**所有器件均为 `RELEASED`**，MPN 后附华秋编号
   （格式 `MPN（华秋 Gxxxxxxxx）`）。
5. 与旧版设计文档的有意差异（例如 BQ25895 /CE 默认禁止充电、
   改用 GPIO47 作为 `CHG_CE`）需用户确认，见 `SCHEMATIC_NOTES.md` §5。

### PCB 阶段（布局完成，布线未开始）

1. 板框（55×84 竖版）、R2 圆角、4 个 2.2 mm 定位孔（距边 3 mm）、4 层叠层、
   4 个 Net Class、
   天线禁布规则区：**已完成**。
2. 106 个器件摆放完成，接口约束（USB-C 外凸 1 mm / FPC / 电池 / KEY 27 mm）：**已完成**。
3. **尚未布线**：电源路径、USB 差分、SPI/I2C/GPIO、EPD HV 目前只有飞线
   （DRC unconnected = 255）。
4. USB 90 Ω 已按 Dk 4.2 / 外层 1 oz 计算为 **W 0.24 / S 0.18 mm** 并写入 Net Class；
   仍建议板厂按实际材料复算确认。
5. 丝印位号已自动避让焊盘（silk_over_copper = 0）；U2/U3 电源岛内仍有 11 处
   **位号文字互搭**（纯外观）。如需进一步减少，可把该处字号从 1.0 缩到 0.8 mm。
6. 投板前需完成全部布线、重跑 DRC（目标 unconnected = 0）、生成 Gerber/钻孔/坐标文件。
7. **TF 座未能外凸 1 mm**（前部固定焊盘在本体最前端），需用户确认是否接受，见
   `PCB_LAYOUT_NOTES.md` §6.1。
8. **U3 脚位三方核对**（符号 ↔ TI 数据手册 ↔ RNM0015A 封装，尤其 1 脚方向）仍需人工确认一次。
9. 天线区两个上角定位孔保持原位，用金属螺钉还是塑料柱需结构评审确认（MD §7.3）。

## 六、待用户确认的问题

原 5 个问题已由 `ESP32S3_GDEM102T91_V1.1_PrePCB_5_Items_Confirmation.md` 答复并落实。

现仍需用户确认/提供：

1. 是否接受 `SCHEMATIC_NOTES.md` §5 列出的与旧版设计文档的差异
   （/CE 默认 HIGH = 禁止充电；`CHG_CE` 使用 GPIO47；TPS63070 PS/SYNC 上拉）。
2. 板厂对 7628 半固化片实际 Dk/Df、外层成品铜厚、阻焊参数的确认，
   以及按实际叠层**复算** USB 90 Ω 差分线宽/间距（当前计算值 0.24 / 0.18 mm）。
3. ~~连接器/按键/电感/MOSFET 的确切 MPN（BOM 中 `PROVISIONAL` 项）~~
   → **已冻结**（2026-09-15；D1/D2-D5/D6-D8/F1-F3/L1/L3/R13 落到华秋国内现货
   料号，L1/L3 同步换封装，清单见 `SCHEMATIC_NOTES.md` §7）。
4. 最终电池规格（满充电压 / PCM / 线束 / 连接器额定电流）。
5. MicroSD 位置（现放在板下边缘中央）与按键高度/手感是否有结构限制。
6. ~~TF 座不能外凸 1 mm~~ → **已确认接受**（2026-09-12）。
7. ~~板框尺寸~~ → **已确认：保持 55 × 84 mm**（2026-09-12）。
8. ~~U3 的 RNM0015A land pattern~~ → **已提供并导入**（2026-09-14，
   `Downloads/ul_TPS630701RNMR`）。投板前仍需按 §六之二 做三方脚位核对。
9. **U3 脚位三方核对**：Ultra Librarian 封装已导入，但 `Symbol ↔ TI 数据手册 ↔
   Footprint` 的一一对应（特别是 1 脚方向、顶视/底视）必须人工确认一次。

## 六之二、V1.2 整改清单执行状态（依 `ESP32S3_GDEM102T91_V1.1_to_V1.2_PCB_Modification_Guide.md`）

| # | 整改项 | 状态 | 说明 |
|---:|---|---|---|
| ① | PCB 外形改 77 × 45 | **已决定：保持 55 × 84** | 用户 2026-09-12 确认板框保持 55 × 84；原因：45 mm 高度装不下 27 mm 间距的 3 个按键 |
| ② | U3 符号 / 封装 / 3D 模型改 RNM0015A | **已完成** | 采用用户提供的 Ultra Librarian 导出：符号 `local:TPS63070RNM`（15 脚、无 EP），封装 `esp32-board-v1.1:RNM0015A`，3D 模型 `lib/3dmodels/RNM0015A.stp`。见 `SCHEMATIC_NOTES.md` §4.6 |
| ③ | J4/J5 改 Molex 53261-0271 | **已完成** | 封装 `Connector_Molex:Molex_PicoBlade_53261-0271_1x02-1MP_P1.25mm_Horizontal`，BOM 标 RELEASED |
| ④ | U4 / U5 料号冻结 | **已完成** | `MAX17048G+T10` / `TUSB320LIRWBR`，BOM 标 RELEASED |
| ⑤⑥⑦⑨ | BQ25895 / TPS63070 / USB-ESD-TUSB / EPD Booster 局部收紧 | **已完成** | 改成"围绕锚点螺旋扩散"放置；实测器件到锚点 courtyard 最大间隙 11.1 mm，多数 < 8 mm |
| ⑧⑩ | 全板功能分区、布线顺序与规则 | **已完成** | 见 `PCB_LAYOUT_NOTES.md` §6 与 §9 |
| ⑪ | 布线 | **未开始** | — |

附加要求（用户）：**TF 座与 USB-C 座位置对调** —— **已完成**：
USB-C 移到板下边中部 (24.0, 81.33)，TF 座移到右下 (42.0, 75.20)，VBUS 现在紧邻充电器。

## 六之三、V1.3 整改清单执行状态（依 `ESP32S3_GDEM102T91_V1.2_to_V1.3_Next_Round_Modifications.md`）

| # | 整改项 | 状态 | 说明 |
|---:|---|---|---|
| ① | ESP32 天线正式 Keepout | **已完成** | 规则区 `ESP32_ANT_KEEP_OUT`，X 16–39 / Y 0–6，L1–L4 禁铜、禁走线、禁过孔、禁焊盘、禁器件 |
| ② | KEY1/2/3 机械禁布区 | **已完成** | 规则区 `KEY_RIGHT_MECH_KEEP_OUT`，X 49–51 / Y 11–73，只禁器件；走线/过孔/铜皮/定位孔按 MD §8.5 允许。另加放置障碍带 `KEY_PLACEMENT_BAN`（X 49–55）保证右侧整条带内只剩三颗按键 |
| ③ | BQ25895 功率岛压缩 | **已完成** | SW→L1 为最高优先，**L1 输入焊盘与 U2 SW19/20 的 Center-Y 完全相同（58.04）**；C11 BTST 1.95 mm；C10/C15 同列、ΔY 2.6 mm；C12/C13/C14 同行等间距 |
| ④ | TPS63070 功率岛 | **已完成** | L2 焊盘 Center-Y = U3 L1/L2 引脚中心线；C18 SYS 1.90 mm；C20 VOUT 5.22 mm；R23/R24 同 Center-X 垂直分压列，FB 3.63 mm |
| ⑤ | USB D±/ESD/串阻成对 | **已完成** | D2/D3 同 X = 25.15，D4/D5 同 X = 21.42，全部 0°；R9/R10 同 X = 14.18 镜像、等长 |
| ⑥ | EPD 高压电容对齐 + Booster 岛 | **已完成** | C36/C30/C33/C28/C32 五颗统一 Center-Y = 37.25、间距 4.0 mm；L3/Q1/D6–D8/R30/R31 单独成簇 |
| ⑦ | 3 mm 对齐规则 | **已完成** | 29 个器件改为引脚级对齐；相邻器件 ΔX/ΔY ≤ 3 mm 处统一 Center 线 |
| ⑧ | 单电池限流策略（ICHG 896 mA + /CE 时序） | **已完成（文档）** | 写入原理图 03 区注释；硬件无改动（/CE 已有 10 kΩ 上拉，默认禁充）。§2.4 实机峰值测试待做 |
| ⑨ | Placement Review | **已完成** | 见 `PCB_LAYOUT_NOTES.md` §6、§9、§10 |
| ⑩ | 正式布线 | **未开始** | 按用户要求：先确认布局，再布线 |

用户附带约束：**天线区与轻触开关区的定位孔保持现状** —— 已遵守，孔径与坐标均未改动。

## 六之四、V1.4 整改清单执行状态（依 `ESP32S3_GDEM102T91_V1.3_to_V1.4_Placement_and_Checklist.md`）

| # | 整改项 | 状态 | 说明 |
|---:|---|---|---|
| ① | 建立完整 `RIGHT_SWITCH_COLUMN`（X 49–55） | **已完成** | 命名规则区 + 自定义规则（SW3/4/5 例外）+ `Dwgs.User` 说明框；实测列内只有三颗按键。已验证规则会真实报错 |
| ② | C37 / R32 / R35 移出右侧 Column | **已完成** | 三者现全部位于 X < 49 |
| ③ | C37 / R32 / R35 围绕 J3 重排 | **已完成** | C38→VDD 2.97 mm、C37→VDD 4.24 mm、R35→MISO 4.45 mm、R32→CS 7.04 mm |
| ④ | J2 换成 Top / Top&Bottom Contact | **已完成** | `Amphenol F32Q-1A7x1-11024`（上接点）；位置 (5.0, 42.0)。FPC 厚度/Mated Height 待数据手册确认 |
| ⑤ | BQ25895 收紧（C15/C10/C9/SYS/R21-C16） | **已完成** | C9 2.09、C15 4.18、C10 6.61、C13 4.39 mm；R21/C16 成对 2.19 mm 紧贴 L1 |
| ⑥ | TPS63070 收紧（L2 / R23-R24） | **已完成** | L2 焊盘在 L1/L2 引脚中心线；R23/R24 同 Center-X 分压列，FB 3.63 mm |
| ⑦ | USB D2/D3/D4/D5 成对靠近 J1 | **已完成** | 四颗 90° 同一行镜像（CC1/D−/D+/CC2），2.64–3.50 mm |
| ⑧ | EPD 高压电容改矩阵、R30 靠 Q1 | **已完成** | 3×2 矩阵占 X 8.3–19.8（原单排到 29.3）；R30 移到 Q1 侧 4.30 mm |
| ⑨ | ESP32 顶部安装孔 RF/机械判断 | **已决** | **塑料柱**，孔位保持不动；`Dwgs.User` 已标注；整机 RF 实测仍建议做 |
| ⑩ | ERC 恢复 footprint 检查 | **已完成** | `footprint_link_issues`、`footprint_filter` = error，0 violation；顺带修掉 J4/J5 过滤不匹配 |
| ⑪ | DRC 恢复 courtyard / library 检查 | **已完成** | `missing_courtyard` = error（0 条）；`lib_footprint_mismatch` = warning（2 条，含规则区封装的固有差异） |
| ⑫ | Placement Review | **已完成** | 见 `PCB_LAYOUT_NOTES.md` §6 / §9 / §10 |
| ⑬ | 正式布线 | **未开始** | 按用户要求先确认布局 |

## 六之五、V1.5 整改清单执行状态（依 `ESP32S3_GDEM102T91_Current_Layout_Optimization_Plan.md`）

| # | 整改项 | 状态 | 说明 |
|---:|---|---|---|
| ① | KEY_RIGHT_MECH_KEEP_OUT 改 X49–51 / Y0–84 | **已完成** | 全高阻挡墙；已验证规则会真实触发（去掉例外后报 H2/H4） |
| ② | RIGHT_SWITCH_COLUMN 只留机械说明 | **已完成** | 删除该 keepout 区，仅保留 Dwgs.User 虚线框与文字 |
| ③ | R33 移出右侧 Column | **已完成** | X>51 一侧只剩 SW3/4/5 |
| ④ | SW1/SW2 下移 2.5~3 mm | **已完成** | y 29 → 32 |
| ⑤ | R33/R34 放到 U1 SPI 输出端 | **已完成** | 距 SPI_MOSI/SCLK 2.34 / 2.84 mm |
| ⑥ | R35 保留 J3 MISO 侧 | **已完成** | 2.96 mm |
| ⑦ | U1 周边 C1~C4 / R1+C5 / R3~R5 重排 | **已完成** | 左侧两列；C4 2.33 mm、R1 3.63 mm |
| ⑧ | C12 搬到 U2 BAT pins | **已完成** | 3.64 mm |
| ⑨ | C10 / C15 / R21-C16 收紧 | **已完成** | C15 2.37、C10 4.65、R21/C16 成对紧贴 L1 |
| ⑩ | U3 R23/R24 FB divider 收紧 | **已完成** | R24 上移，间距 1.81 mm |
| ⑪ | C29 搬进 EPD Booster Island | **已完成** | 距 D6 EPD_SW 4.51 mm、D8 EPD_X 3.34 mm |
| ⑫ | U1 / J3 library mismatch | **已解决** | 项目本地封装 + rule area 提升 + 顶部丝印裁剪 + 保留 version 字段 |
| ⑬ | Placement Review | **已完成** | 见 `PCB_LAYOUT_NOTES.md` §6 / §9 / §10 |
| ⑭ | 统一重做全板丝印 | **已完成** | ≤3.3 mm，空间不足隐藏 5 个；silk_overlap 0 |
| ⑮ | Run DRC | **已完成** | 0 Error / 0 Warning |
| ⑯ | 开始正式 Routing | **未开始** | 按用户要求先确认布局 |

## 六之六、V1.6 整改清单执行状态（依 `ESP32S3_GDEM102T91_V1.5_to_V1.6_PreRouting_Remaining_Items.md`）

| # | 整改项 | 状态 | 说明 |
|---:|---|---|---|
| P0① | Q1 = Si1304BDL-T1-GE3 + SC-70-3 | **已完成** | 封装 `Package_TO_SOT_SMD:SOT-323_SC-70`；符号 `Q_NMOS_GSD` 脚位对应正确；不再列 Si1308EDL |
| P0② | Booster 岛重新收紧 | **已完成** | R30 → Gate 3.81 mm；C29 仍在岛内 |
| P0③ | L2 = MWSA0402S-1R2MT | **已完成** | RELEASED；封装取 KiCad 官方库 |
| P0④ | L2 与 U3 switching path 等长对称 | **已完成** | 两段各 4.38 mm（中心对齐 L1/L2 引脚中心线） |
| P0⑤ | J2 = X05B20U24T | **已完成** | FPC 厚度 0.30 mm 已确认；封装由厂商图纸 + 立创 CAD 生成 |
| P0⑥ | J2 Pin1/Pin24/Top Contact/插入方向复核 | **已完成** | 无 1↔24 反序；开口仍朝左；建议投产前实物再核对一次 |
| P1⑦ | BQ25895 /CE 上电异常验证 | **列入原型测试** | 见 `PCB_LAYOUT_NOTES.md` §12（示波器场景清单） |
| P1⑧ | NTC1 精确料号 | **已完成** | Vishay NTCS0603E3103FLT（0603 / 10 kΩ / B3435） |
| P2⑨ | BOM PROVISIONAL 冻结 | **已完成** | 2026-09-15：D1/D2-D5/D6-D8/F1-F3/L1/L3/R13 全部落到华秋国内现货料号，L1（MWSA0503S）与 L3（FHD4020S-470MT）同步换封装；`bom.csv` 全 `RELEASED`（V1.6 文档轮拆行后 52 行），清单见 `SCHEMATIC_NOTES.md` §7 / §7.3 |
| P2⑩ | 版本 / Rev / 输出文件名统一 | **已完成** | Rev = V1.6；发布命名规则见 `PCB_LAYOUT_NOTES.md` §13 |
| ⑪⑫ | Run ERC / DRC | **已完成** | ERC 0 / DRC 0 Error 0 Warning |
| ⑬ | Placement Freeze | **已完成** | 除 J2/Q1 封装外不再重排 |
| ⑭ | 开始 Routing | **未开始** | 等用户确认 |

## 六之七、V1.6 文档 / BOM 收尾状态（依 `ESP32S3_GDEM102T91_V1.6_Final_Documentation_and_BOM_Fixes.md`）

| # | 清单条目 | 状态 | 说明 |
|---:|---|---|---|
| ① | SW3/4/5 机械说明改为顶部按压 | **已完成** | B3U-1000P = Top-actuated；外壳按键柱从 PCB 正面垂直压下。已清掉“侧按 / 朝右 / 沿 X 轴”描述（`agent.md`、`SCHEMATIC_NOTES.md`、原理图注释） |
| ② | SW1–SW5 继续使用 B3U-1000P | **已完成** | 封装 `Button_Switch_SMD:SW_SPST_B3U-1000P` 不变；90° 摆放保留 |
| ③ | 系统输入改写为 5 V/2 A source compatible | **已完成** | 原理图 03 区与三份说明文档统一为“非高温连续 2 A 保证” |
| ④ | 测试计划增加 PTC 高温验证 | **已完成** | 25 / 40 / 50 °C + 并发负载 + F1 温升 + VBUS / PTC 压降，见 `SCHEMATIC_NOTES.md` §5.1、`PCB_LAYOUT_NOTES.md` §12 |
| ⑤⑥⑦ | L3 参数在 SCHEMATIC_NOTES / PCB_LAYOUT_NOTES / agent.md 统一 | **已完成** | 47 µH ±20 % / Rated 660 mA / Isat 1.3 A / DCR 950 mΩ / −40…+125 °C / H 2.0 mm；旧 Isat 1.10 A、Irms 0.56 A 已删除 |
| ⑧ | F1–F3 继续 BSMD0805L-200 | **已完成** | 0805 PTC，保持 2 A / 跳闸 ≈4 A / 6 V，华秋 G5053245 |
| ⑨ | L3 摆放不重排 | **已完成** | 仅核对 footprint `Inductor_SMD:L_Changjiang_FNR4020S` 与采购件 land pattern 一致；Booster 岛未移动 |
| ⑩ | BOM 增加 `Populate` 字段 | **已完成** | `bom.csv` 列 = `Reference,Value,Footprint,Status,MPN,Populate` |
| ⑪ | R21/C16 = DNP、R31 = FIT | **已完成** | 原理图 `(dnp yes)` + `Populate=DNP`；R21 与 R31 已分行为 `R21 DNP` / `R31 FIT` |
| ⑫ | 补关键 MLCC / 精密电阻 MPN | **已完成** | C27–C33 / C34,C35 / C36 / 10 µF / 22 µF / R16 / R17 / R23 / R24 全部落到华秋国内现货料号 |
| ⑬ | 清理 ERC 文档旧描述 | **已完成** | 三份文档统一为“0 violations + 两个检查启用 + 三个按策略 Ignore” |
| ⑭ | 重跑 ERC / DRC | **已完成** | ERC 0 violations；DRC 0 Error / 0 Warning；unconnected 255（未布线） |
| ⑮ | 开始正式 Routing | **未开始** | 等用户确认布局与文档 |

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
