# ESP32-S3 + GDEM102T91 PCB V1.1 任务交接说明

> **2026-09-18 更新（GND Final Convergence 第一轮：18 → 17）**：
> 按 `..._GND_Final_Convergence_and_Final_DRC_Plan.md` 执行；**USB 正式冻结为 Plan C**
> （不再动 USB_SHIELD / R8 / BAT_BUS / 3V3_MAIN / CC1 / DP-DN fanout）。
>
> - **§3 ① U3 Pad4** ✅：加 3 段 0.20 mm F.Cu `(33.80,45.00)→(33.60,45.00)→(33.60,45.75)
>   →(32.95,45.75)` 接到已有 GND Via，**未新增过孔**，U3.4 record 消失。
> - **§16.1 真孤岛** ✅：删除 (43.1078,64.575)→(43.1078,64.8578) 的 0.2828 mm 历史短桩
>   （无 Pad / 无 Via），J3.SH 相关 record 消失。
> - **GND 18 → 17，DRC 0 Error / 0 Warning，Non-GND = 0**。
> - 剩余 17 = 11 条 Zone/Plane + U5.3 / U5.5 短桩（3 条）+ R13.2（2 条）+ C38.2（1 条）。
>   下一步按 MD §26：U5.3 补短铜 → U5.5 先局部 rip USB_VBUS_DET 让路 → R13.2 先局部 rip
>   I2C_SDA 再接到 U2 Pad25 → C38.2 补缝合过孔 → 最后生成 GND component report 处理
>   11 条 Zone/Plane（A 删孤岛 / B 补 1 颗缝合过孔 / C Refill 或删碎片）。
> - 检查点：`esp32-board-v1.1_gnd_round3_20260918.kicad_pcb`。

> **2026-09-18 更新（USB SI Freeze = Plan C；GND 逐条分类）**：
> 按 `..._USB_SI_Freeze_and_GND_Final_Cleanup_Plan.md` 执行。
>
> - **USB Plan A 实测不可行（有硬证据）**：把 DN 的 3 过孔绕行整段删掉后，从 D3.1 做
>   **F.Cu 洪水填充**，口袋只有 1982 格、bbox 到 **y≈71.6 就封死**（R10.1 侧是整板 172k 格）
>   → F.Cu 根本连不到 R10.1。封死它的是 **USB_SHIELD 扇出**（(17,74.7)→(20.5,71.2) 斜线 +
>   →(22.3,71.2) 横线 + **R8.1 焊盘 x 22.23~23.03**），正压在 MD 建议的 DN 走廊 x≈22.98 上。
>   MD §4 只授权动 `CC1 局部 Via` 与 `BAT_BUS 局部换层点`，而真正的阻塞物不在授权清单内 →
>   按 MD §13 止损：**USB 冻结为 Plan C**（DP 全 F.Cu/0 过孔；DN F.Cu→In2→B.Cu/3 过孔），
>   并已恢复 DN 绕行，保持 **Non-GND = 0**。
> - **GND 逐条分类（18 条 = 11 Zone/Plane + 4 Pad + 3 Track）**：
>   · 已删除 U3.4 的历史短桩残段（8 段），无新违规（record 组合变化、总数仍 18）。
>   · `R13.2` 的 F.Cu 口袋只有 118 格（被 I2C_SDA/SCL/CHG 扇出封死）→ MD §21 的短直线画不过去，
>     需先局部 rip I2C_SDA 一小段。
>   · `U5.3` 短桩末端口袋是整板级 → 补短铜即可；`U5.5` 末端口袋只有 79 格且过孔放不下 →
>     需局部让路。`J3.SH` 自身已有过孔，残留的是一段 0.2828 mm 旧短铜。
>   · 11 条 Zone/Plane 记录按 MD §27 逐块判断（删孤岛 / 补缝合过孔）。
> - 状态：**DRC 0 Error / 0 Warning，unconnected 18（全部 GND），Non-GND = 0**。
>   检查点：`esp32-board-v1.1_gnd_round2_20260918.kicad_pcb`。

> **2026-09-18 更新（J1 交错焊盘扇出：Non-GND unconnected = 0 ✅）**：
> 按 `..._J1_USB_Interleaved_Pad_Fanout_Final_Plan.md` 的 Plan A 执行。
>
> - **§3~§11 VBUS 下沉**：删掉 J1 内侧 y≈78.60 的 F.Cu VBUS 横线，在西侧 VBUS 焊盘组旁加
>   0.6/0.3 过孔 (21.60,76.80) 接 In2 汇流；USB_SHIELD 不动 → `USB_VBUS_RAW` 仍全连通。
> - **§12~§14 DP 下侧 / DN 上侧 short**：局部 rip DP 的 J1 扇出（8 段）后重画 ——
>   A6 →(下侧 short y=76.72)→ B6，B7 →(上侧 short y=78.55)→ A7；主出口分别取 A6 / B7。
> - **§15~§17 DN 主干**：MD 期望「沿 DP 平行、全程 F.Cu / 0 Via」实测走不通 ——
>   D3.1 的北/西/东三个方向分别被 D3 自己的 Pad2、USB_CC1 的过孔、DP 的竖直段挡住；
>   DP 西侧想再放一条又被 **BAT_BUS 0.8 mm F.Cu 主干（y≈70）与 3V3_MAIN 的三个 F.Cu
>   支路（y 66.75~69.36）**夹死。故先按可布通完成：DN 主干 F.Cu→In2→B.Cu，3 颗过孔。
> - **结果：`USB_DN_CONN` 闭合 → Non-GND unconnected = 0**（MD 的 Checkpoint G ✅）；
>   **DRC 0 Error / 0 Warning**。
> - **Checkpoint H（GND 第一轮）**：`fix_gnd.py` 再放 5 颗 GND 过孔 + 缝合 2 块铺铜：
>   **GND 22 → 18 项**。剩余 18 项 = 铺铜/平面之间 13 条 + 真实地焊盘 4 条 + 历史短桩 3 条；
>   实测 U5.3/U5.5、R13.2 处连 0.4/0.2 过孔都放不下（相邻 0.4 mm 间距焊盘 / 内层走线卡净空）。
> - 检查点：`esp32-board-v1.1_nongnd_zero_20260918.kicad_pcb`、
>   `esp32-board-v1.1_gnd_round1_20260918.kicad_pcb`。
> - 待确认：① USB DN 主干是否要做「0 Via」的局部重排（需动 3V3_MAIN 三个 F.Cu 支路 /
>   BAT_BUS F.Cu 段 / CC1 过孔）；② GND 剩余 18 项是否按 MD §24 继续逐类清理。

> **2026-09-18 更新（U5/USB/GND 收敛：Checkpoint E 达成，non-GND 只剩 USB_DN）**：
> 按 `..._U5_USB_GND_Final_Convergence_Plan.md` 执行。
>
> - **§3~§6 3V3_MAIN 局部减宽**：新工具 `tools/neck_trunk.py`，保持 In2.Cu 主干中心线不动，
>   在 **y 68.0~71.2** 把 U5 下方那段由 1.20 → **0.50 mm**（两端 0.35 mm 的 0.85 mm 过渡，
>   不加过孔）。Refill+DRC 后 **3V3_MAIN 仍完全连通**。
> - **§7~§9 `I2C_SDA` ✅**：减宽后 U5.7 的过孔位恢复 —— F.Cu 东出 → 0.4/0.2 过孔
>   (31.300,69.700) → B.Cu（正是 MD 给的参考区域），其余用 `bridge_net --layer-pen 5,8,0`。
> - **§10~§11 `TYPEC_INT_N` ✅**：先把 USB_VBUS_DET 的 U5 东侧竖线**手工东推**到 x=31.81
>   （`rip_local` + `add_track`，不用自动重布），再 U5.6 → F.Cu 东出 → 过孔
>   (31.300,70.500)（与 SDA 过孔 Y 错开 0.8 mm）→ B.Cu。
> - **unconnected 29 → 25，non-GND 9 → 3**（只剩 `USB_DN_CONN`），**DRC 0 Error / 0 Warning**。
> - **Checkpoint F（USB DP/DN）停下来等确认**：勘察发现 J1 的焊盘顺序是
>   `B7(DN) A6(DP) A7(DN) B6(DP)`，DN 的搭接必须穿过 DP 的竖直出线 ——
>   **A6—B6 与 B7—A7 两条搭接在同一层上无法同时成立**（数学上必有一次交叉）；
>   连接器内侧也被 USB_VBUS_RAW(y=78.60) 与 USB_SHIELD(y=79.40) 横穿。
>   因此 MD §17 的「Via = 0」与该封装冲突，**至少需要 1 颗过孔**完成一条搭接（短桩过孔，
>   不影响差分对本身）。等用户确认方案后再做。
> - 检查点：`esp32-board-v1.1_u5_closed_20260918.kicad_pcb`。

> **2026-09-17 更新（Final 16 Non-GND：Checkpoint A 完成、C/D 各完成一半）**：
> 按 `..._Final_16_NonGND_Convergence_Plan.md` 推进。
>
> - **Checkpoint A ✅**：`CHG_OTG` 闭合（做法完全按 MD §3.1：先用 `move_endpoint.py` +
>   `rip_local.py` 只拆掉 U2.7 附近一小段 `CHG_INT_N`，`bridge_net` 重布它，再收 `CHG_OTG`）。
>   **BQ25895 区正式封闭**，CHG_OTG / CHG_INT_N / CHG_CE 三者均 Connected。
> - **Checkpoint C**：`I2C_SCL` ✅（`bridge_net --layer-pen 5,8,0`）；`I2C_SDA` ❌。
> - **Checkpoint D**：`TF_CS_N` ✅；`TYPEC_INT_N` ❌。
> - **Checkpoint B（USB）⏸**：`USB_DP_CONN` 已布通（F.Cu 0.24 mm 差分对形态），
>   但 `USB_DN_CONN` **一点铜都没有**（4 个焊盘全孤立，J1 扇出区已被占满，A7↔B7 只差
>   0.7 mm 也放不下）。按 MD §9 应与 DP 一起做差分对，不要用 bridge_net 硬补。
>
> ❌ 的两项（`I2C_SDA` / `TYPEC_INT_N`）卡在同一个地方：**TUSB320（U5）的引脚口袋**。
> 过孔只能落在 U5 焊盘之间，而口袋里：In2.Cu 被 **1.2 mm 宽的 3V3_MAIN 主干**压住
> （x 30.0~31.2）、东侧是 USB_VBUS_DET / TF_CD_N 的 F.Cu、四周是 0.4 mm 间距引脚。
> 实测 x ≤ 29.58 或 x ≥ 31.62 才有过孔位置，两种位置都被占住。
> → 需要**局部重排 U5 扇出**，其中一步是「把 In2 的 3V3_MAIN 主干在 U5 下方局部收窄
> 到 0.5 mm 或平移 ~1.5 mm」。这超出 MD §1「不要再动 3V3_MAIN」的授权范围
> （3V3_MAIN 本身没有 DRC 回归，是它在挡 I2C），**需先与用户确认**。
>
> 现状：**unconnected 35 → 29**（non-GND 16 → 9），**DRC 0 Error / 0 Warning**。
> 检查点：`esp32-board-v1.1_bq_i2c_tf_checkpoint_20260917.kicad_pcb`。

> **2026-09-17 更新（Post-TPS 收敛：Checkpoint 1 全部达成，Checkpoint 2 只差 CHG_OTG）**：
> 按 `..._Post_TPS_Final_Convergence_Plan.md` 推进。新增主力工具 `tools/bridge_net.py`
> （按真实几何把网络的铜箔拆成连通分量 → MST → 只补真正缺的那几段）。
>
> - **Checkpoint 1 达成**：U3 Pad10 GND、`SYS`、`3V3_MAIN` 全部从 unconnected 中消失。
>   ⚠️ **重要发现**：3V3_MAIN 原先并不是"只差两段短桩"，而是 **ESP32 模组的 3V3 群
>   （C1–C4 / R1–R5 / U1.2）整块与电源区断开了约 24 mm**（历史上几轮"3V3_MAIN 已闭合"
>   的结论有误）。已用一条 0.65 mm 主线（In2 → B.Cu → F.Cu）接回。
> - **Checkpoint 2**：`BAT_BUS`（0.80 mm 主干 + 器件端 0.50/0.35）✅、`EPD_3V3`（0.50 mm
>   主干 + 短支路，含打开 J2.15/16 的电源出口）✅、`CHG_REGN` ✅、`CHG_CE` ✅、
>   `CHG_DSEL` ✅；**`CHG_OTG` 未闭合**——U2.8 在 0.4 mm 间距引脚区里被围成一个 34 格的
>   窄井，需局部 rip-up 邻近走线。
> - **unconnected 59 → 35**（non-GND 40 → 16），全程 **DRC 0 Error / 0 Warning**。
> - 修掉的工具链真 bug：`fix_gnd.py` 过孔尺寸写错（0.4 验证却写 0.6）、布线器过孔掩膜
>   不看同网络过孔（`hole_to_hole`）、单批 `bridge_net` 跨网络看不到新铜、`snap_end`
>   拉长末端擦焊盘、B.Cu GND 铺铜被 BAT_BUS 主干切出 0.116 mm 细颈。
> - 检查点：`esp32-board-v1.1_power_backbone_checkpoint_20260917.kicad_pcb`（CP1）、
>   `esp32-board-v1.1_bat_epd_checkpoint_20260917.kicad_pcb`（CP2 除 CHG_OTG）。
> - 下一步（MD §13~§18）：`CHG_OTG`（局部 rip）→ USB DP/DN → I2C → TF_CS_N →
>   TYPEC_INT_N → Non-GND unconnected = 0 → GND 统一清理。

> **2026-09-17 更新（TPS_EN / TPS_VSEL 已闭合 ✅，依 `..._TPS_EN_VSEL_Routing_Solution.md`）**：
> 按 MD §1/§4/§5 的"**局部减宽 + 尽快换 B.Cu**"方案，两条控制线**双双布通**，前几轮
> 的"必须交互布线"结论已作废。**根因不在 SYS，而在布线器自己的几何模型**：
> `route.py` 原先把线段障碍建成**轴对齐外接矩形**，45° 走线因此比真实铜箔"胖" √2 倍。
> 实测一支 `3V3_MAIN` 斜线段 (28.1,49.7)→(30.7,47.1) 的外接矩形把 **R28.2 焊盘的
> 78/78 个栅格全部盖死**，而真实铜箔离它还有 0.50 mm 余量 —— 这就是历次 rip-up /
> 主干上移都失败的真正原因。新增 `seg_shape()` 把线段按**真实胶囊形**建模后，R28.2
> 恢复可走，`TPS_VSEL` / `TPS_EN` 当场布通。
>
> - `SYS` 主干：U3 上方局部 1.20 → **0.80 mm**（0.80 已是本工程主干标准），**位置不动**。
> - `TPS_VSEL`：U3.15 → 左出 → Via (32.5,43.5) → **B.Cu 长距离** → R28.2 ✅
> - `TPS_EN`：U3.14 → 上短出 → **左转** → Via (32.4,42.7) → **B.Cu 长距离** → R26.2 ✅
> - U3.12/U3.13（SYS 电源焊盘）→ 0.5 mm 出线向上 1.4 mm 接到 C18.1 与 `SYS_ISLAND_U3` ✅
> - 未动 `TPS_L1/L2/PS_SYNC/FB`、未移动 R26/R28、未启用 `TPS_CTRL_ESCAPE` 规则区。
> - **DRC 0 Error / 0 Warning**，unconnected **62 → 59**；基准板更新为
>   `esp32-board-v1.1_routing_tps_ctrl_20260917.kicad_pcb`。
> - 下一轮（MD §15）：BQ 区（`CHG_REGN` → `CHG_CE` → `CHG_OTG`/`CHG_DSEL`）→
>   USB DP/DN → I2C → TF_CS_N → TYPEC_INT_N；同时用 `tools/anchor_islands.py`
>   收掉 `SYS_ISLAND_U2/C13`、`3V3_ISLAND_U3/CAPS` 的岛—岛断点。

> **2026-09-17 更新（方案 1：SYS 主干上移 1 mm，已测试后回退）**：按用户选择实现
> `tools/move_sys_trunk.py`（摘掉 U3 顶排引脚上方走廊内的 SYS 铜 → 用显式走廊折线重画、
> 保留原端点以保证连通 → 逐版用真实间距引擎打分，不劣于基线才写盘）。**结论：不可行**。
> 6 个走廊高度（41.90 ~ 40.50 mm）的 SYS 间距分数为 205~235，而摘除后的基线是 99——
> 抬高主干只是把冲突搬到上方，因为 U3 上方 1~2 mm 已被其它网络走线占满。脚本按设计拒绝写盘，
> **基准板保持验证状态（ERC 0 / DRC 0 Error 0 Warning / unconnected 62），无回归**。
> `TPS_EN` / `TPS_VSEL` 因此归入"必须交互布线"清单（建议：从 U3 底部绕行，或评审把
> R26/R28 移到 U3 顶部一侧）。

> **2026-09-17 更新（SYS 局部 rip-up 尝试，用户已授权）**：按授权实现"只 rip 引脚附近
> 1–2 mm 的 SYS → 立刻重走 → 验证 DRC"（`fix_tps.py::rip_near_pads()`，段按边界切开、
> 超过 2 mm 直接拒绝）。**实测仍无法闭合 `TPS_EN` / `TPS_VSEL`**：U3.14/15 的出线通道在
> 栅格上只有一列 0.1 mm 可行格，唯一挡路物是 1.2 mm 宽的 SYS 主干（距引脚中心 1.21 mm），
> 挖掉后通道仍被 U3 自身焊盘列封成死端。已**回退**到验证过的状态（DRC 0/0、unconnected 62），
> 未产生回归。这两个网络留待交互布线，可选方案见 `ROUTING_NOTES.md` §3.0c 第四轮
> （SYS 主干上移 ~1 mm / 从 U3 底部绕行 / 移动 R26/R28）。

> **2026-09-17 更新（最终收敛第三轮：TPS 区，MD §7 + §2）**：新增 `tools/fix_tps.py`
> 做**局部**收敛（不做全局重跑）：
> - **`TPS_L2` 已布通** ✅（F.Cu、**0 过孔**、4 段加宽到 0.50 mm，焊盘处 0.25 mm 收颈）；
>   **`TPS_PS_SYNC` 已布通** ✅（32 段 / 0.20 mm）。
> - `TPS_EN` / `TPS_VSEL` 仍未闭合 ❌：U3 顶部引脚 14/15 的出线走廊被 SYS 铜皮与走线占满，
>   连 0.35 mm 短桩都放不下 → 需要局部 rip-up SYS 或交互布线。
> - **关键修正**：`SYS_ISLAND_U3` 铜皮下沿 44.05 → **42.55**（原值把 U3 顶排引脚的出线整段盖住）。
>   修正后铺铜可流入 U3 区域，真实 GND 焊盘 **23 → 6**（剩 U3.10 / C18.2 / C24.2 / D5.2 / U5.3 / U5.5）。
> - **`3V3_MAIN` 已完全闭合** ✅（不再出现在 unconnected_items）；`SYS` 仅剩 2 项。
> - 顺带清理：TF_SCLK 重复过孔 2 组、EPD_VCOM / TPS_VSEL 悬空残段。
> - **ERC 0 / DRC 0 Error 0 Warning**，unconnected 62；基准板
>   `esp32-board-v1.1_routing_final_convergence_20260917.kicad_pcb` 已更新。
> - 下一轮（MD §8~§10）：BQ 区（CHG_REGN → CHG_CE → CHG_OTG/DSEL）→ USB DP/DN →
>   I2C/TF_CS/TYPEC_INT；TPS_EN/VSEL 与 U3 剩余地引脚建议在交互布线中一并收掉。

> **2026-09-17 更新（最终收敛第二轮，按 `..._Final_Convergence_Next_Steps.md`）**：
> 按 MD §11 停止全局自动 reroute，转为**局部收敛**，并保存基准板
> `esp32-board-v1.1_routing_final_convergence_20260917.kicad_pcb`。要点：
> - **真实 GND 焊盘 23 → 2**：`tools/fix_gnd.py` 逐焊盘放 GND 过孔（0.6/0.5/0.4 mm 递减）
>   或用 0.15–0.3 mm 短 GND 铜接到最近的 GND 铜 / 铺铜；剩下 **U3 Pad4 / Pad10**
>   （TPS63070 地引脚，出线走廊被开关节点走线占住，需要在 TPS 区局部 rip-up 或交互布线）。
> - **GND 铺铜**：启用"自动删除孤立铜岛"，纯碎片由填充器删除（不再算 unconnected），
>   仍带 Pad/Via 的碎片补 1 颗缝合过孔接回地平面。
> - **SYS**：`SYS_ISLAND_U3` 已锚定，unconnected 8 → 6（`SYS_ISLAND_U2`/`SYS_ISLAND_C13`
>   需在岛内放过孔或人工接线）；**3V3_MAIN**：`3V3_ISLAND_CAPS` 已锚定，剩 4 项
>   （`3V3_ISLAND_U3` 在 U3 焊盘阵列内部，锚点被自身焊盘挡住）。
> - **ERC 0 / DRC 0 Error 0 Warning** 保持；unconnected 维持在 62
>   （含 BAT_BUS 14、EPD_3V3 14、I2C 16、SYS 6、USB_DN_CONN 6、3V3_MAIN 4、TPS/BQ/TF/TYPE-C 若干）。
> - 下一轮按 MD §18：TPS 区（含 U3 两个 GND 引脚的局部收尾）→ BQ 区 → USB → I2C/TF/TYPE-C →
>   Refill → 非 GND unconnected = 0 → 清理 GND 碎片 → 开启最后两项 Routing DRC → Final DRC。

> **2026-09-17 更新（最终收敛阶段 / Routing final convergence）**：按
> `ESP32S3_GDEM102T91_V1.6_Routing_Final_Convergence_Plan.md` 推进，重点从"减少 DRC 错误"
> 转为"把电源 / GND / 局部控制网络真正收敛到 0 unconnected"：
> - **状态定位更正**：`SYS` / `3V3_MAIN` = **电源拓扑已完成，但仍有局部连通断点**
>   （铜皮与主干之间此前只靠"同名 Zone"隐式连通，实际未接上）。
> - 新增 `Session.anchor_islands()`：逐个电源铜皮检查是否有同网络 Track/Via 落在铜皮内，
>   没有就自动画一段最短合法锚点 → `SYS_ISLAND_U3`、`3V3_ISLAND_CAPS` 已锚定。
> - 新增 `tools/fix_gnd.py`：对 DRC 报出的未连接 **GND 真实焊盘**，优先放 GND 过孔
>   （0.6→0.5→0.4 mm），放不下则用 0.15~0.3 mm 短 GND 铜连到最近 GND 铜；
>   只删除"无 Pad / 无 Via"的孤立铺铜，不做 Exclude。
> - GND 铺铜局部净空 0.30 → **0.20 mm**（POWER 仍按网络对保持 0.2 mm）。
> - **DRC 维持 0 Error / 0 Warning**；unconnected **68 → 62**
>   （GND 48→36，SYS 8→6，3V3_MAIN 归入 4 项）；已布线 54/69。
> - 检查点：`esp32-board-v1.1_routing_checkpoint_20260917.kicad_pcb` +
>   `routing/routing_checkpoint_20260917.json`（MD §13.1 的收尾基准板）。
> - 剩余顺序按 MD §14：GND 剩余焊盘 → SYS/3V3_MAIN 锚点 → **BAT_BUS / EPD_3V3 受控重跑**
>   （把它们加入 `STUB_ALL_NETS`，仅此一次）→ TPS → BQ → USB → I2C/TF/TYPE-C。
>   MD 明确建议此后**停止全局重跑**，改用 KiCad 交互布线收尾。

> **2026-09-16 更新（局部电源铜皮 + 宽主干，收掉 SYS / 3V3_MAIN）**：布线器新增
> "局部电源铜皮 + In2.Cu 宽主干"能力（MD §8 / §15）：
> - **5 个电源铜皮**（F.Cu，优先级 20，实体连接、自动移除孤立铜岛）：
>   `SYS_ISLAND_U2`（U2 SYS 引脚 + L1 输出）、`SYS_ISLAND_C13`、`SYS_ISLAND_U3`
>   （U3 VIN + C18/C19）、`3V3_ISLAND_U3`（U3 VOUT 引脚）、`3V3_ISLAND_CAPS`。
> - 铜皮内的焊盘由铜皮连通，迷宫只需把主干接到铜皮 → **`SYS` 与 `3V3_MAIN` 已布通**；
>   主干走 In2.Cu 并自动加宽到 **1.2 mm**（36 段），BAT/SYS/USB_VBUS 保持 0.8 mm（15 段）。
> - **DRC 重新回到 0 Error / 0 Warning**；unconnected 由 92 → **68**；
>   已布线 **54 / 69**，未完成 15（`TPS_L2`、`TPS_EN/VSEL/PS_SYNC`、`USB_DN_CONN`、
>   `CHG_CE/INT_N/OTG/DSEL/REGN`、`I2C_SCL/SDA`、`TF_CS_N`、`TYPEC_INT_N`、
>   `BAT_BUS`、`EPD_3V3`）。
> - 取舍：为给 `3V3_MAIN`/`SYS` 的全部焊盘预约出线（它们最后布），`BAT_BUS` 与
>   `EPD_3V3` 本轮被挤出；把这两个网络加入 `tools/route.py` 的 `STUB_ALL_NETS`
>   后重跑即可恢复（详见 `ROUTING_NOTES.md` §6）。
> - 重跑命令：`python tools/route.py --passes 1 --mode hard --quiet`（约 15–20 min）
>   → `python tools/apply_routing.py` → `kicad-cli pcb drc`。
>   `python tools/route.py --post` 只重跑收尾步骤（约 1 s），用于微调最后几个 DRC 项。

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
2. 进行中（2026-09-18 第十轮后）：**DRC 0 Error / 0 Warning**，unconnected **18**（起点 255），
   **Non-GND unconnected = 0** ✅（所有信号网络都已连通，含 `USB_DP_CONN` / `USB_DN_CONN`）。
   已闭合清单见上文与 `ROUTING_NOTES.md` §3.0c 第十轮。
3. 未完成：**GND 剩余 17 项**（11 Zone/Plane + U5.3/U5.5 短桩 3 条 + R13.2 2 条 + C38.2 1 条）。
   已逐条定位卡点：`U5.3` 补短铜即可；`U5.5` 需先局部 rip `USB_VBUS_DET`；`R13.2` 需先局部
   rip `I2C_SDA`（约 1~3 mm）再接到 U2 Pad25；`C38.2` 补 1 颗缝合过孔；11 条 Zone/Plane
   先生成 GND component report 再按 A/B/C 分类处理。（`fix_gnd.py` 已按 MD §13 停用。）
   完成 `Unconnected = 0` 后再逐个开启 `track_not_centered_on_via` 与
   `tuning_profile_track_geometries` 跑 Final DRC。
4. 待确认：USB DN 主干目前是 F.Cu→In2→B.Cu / 3 过孔；若要回到 MD 期望的「全程 F.Cu /
   0 Via」，需局部改 3V3_MAIN 的三个 F.Cu 支路 + BAT_BUS 的 F.Cu 段 + CC1 过孔位置。
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
