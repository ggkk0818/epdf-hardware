# ESP32-S3 + GDEM102T91 V1.6 — 布线说明与状态

> 2026-09-15：完成 **4 层铜箔布线** 的第一次完整实现（自动布线器 + 独立校验）。
> 与 `agent.md`、`PCB_LAYOUT_NOTES.md`、`SCHEMATIC_NOTES.md` 配套阅读。

---

## 1. 本轮产物

| 文件 | 内容 |
|---|---|
| `routing/routing.json` | 布线结果（线段 / 信号过孔 / GND 缝合过孔 / 未完成网络清单） |
| `routing/model.json` | 从 `.kicad_pcb` 抽取的几何模型（焊盘、网络、规则区、网络类） |
| `esp32-board-v1.1.kicad_pcb` | 已写入布线的板文件（四层 GND 均已铺铜） |
| `esp32-board-v1.1.kicad_dru` | 新增 5 个 `PWR_NECK_*` 窄颈规则区与对应自定义规则 |
| `drc.json` | 最终 DRC 结果 |
| `routing/*.png` | 布线渲染图（人工核对用） |

> `routing.json` 里的 `failed` 字段是**布线器的历史标注**（会粘住不再更新），
> **判断完成度一律以 `drc.json` 的 `unconnected_items` 为准**。例如 `TPS_EN` / `TPS_VSEL`
> 已经布通、已从 DRC 列表消失，但仍留在该字段里。

重跑顺序（KiCad 自带解释器含 pcbnew + numpy）：

1. `python tools/board_model.py` — `.kicad_pcb` → `routing/model.json`
2. `python tools/route.py --mode hard` — 自动布线 → `routing/routing.json`（约 2.5 分钟）
3. `python tools/apply_routing.py` — 写入 PCB、生成窄颈规则区、铺铜、保存
4. `python tools/check_routing.py` — 独立校验线间/线过孔间距（当前 0 问题）
5. `kicad-cli pcb drc --format json --severity-all -o drc.json esp32-board-v1.1.kicad_pcb`

> `apply_routing.py` 默认从 `routing/board_prerouting.kicad_pcb`（原始摆放文件）重新开始，
> 因此可反复运行。**注意：`tools/gen_pcb.py` 目前无法复现仓库中的板文件**（其摆放代码与
> 冻结的 V1.6 文件已分叉：例如 R29 在脚本输出中位于 (23.49, 43.09)，而 V1.6 板文件中
> 位于 (12.86, 49.55)）。因此布线一律以仓库中的 `.kicad_pcb` 为准，只有加 `--gen`
> 才会调用 `gen_pcb.py` 重新生成摆放。

---

## 2. 布线方法

- **栅格** 0.1 mm；F.Cu / In2.Cu / B.Cu 可走线，**In1.Cu 保持完整 GND 平面**。
- **障碍**：焊盘 / 规则区 / 板边用精确圆角矩形距离函数（非栅格近似）计算，间距判断与 DRC 同源。
- **A\***：4 邻域 + 45° 移动（45° 要求两端留有额外间隙），过孔代价折合 1.9 mm 线长。
- **分层策略**：所有 SMD 焊盘都在 F.Cu，故 F.Cu 每步加价（长网络 +12），长走线自动落到
  In2.Cu / B.Cu，把 F.Cu 留给焊盘出线；USB 差分对强制走 L1（阻抗参考 L2）。
- **出线预约**：每个出线受限的焊盘先布 0.35–0.7 mm 短桩并登记为固定铜箔，防止后续网络
  把焊盘封死；主布线只接到短桩末端。
- **功率宽度阶梯 + 回填**：0.5 → 0.4 → 0.3 → 0.25 → 0.2 → 0.15 mm 逐级尝试，成功后对有余量
  的连续段回填至网络类宽度（POWER 0.5 mm）。
- **收尾**：`trim_dangling_stubs` 裁剪/删除未被接上的短桩；`legality sweep` 对仍有间距
  冲突的网络撕掉重布（历史代价惩罚同一走廊）。

---

## 3. 结果

```
网络 69（不含 GND）：已布线 54，未完成 15
线段 1079，信号过孔 117，GND 缝合过孔 140
ERC  0 violations
DRC  0 Error / 0 Warning
     unconnected 35 项（2026-09-17：68 → 62 → 59 → 50 → 35）
tools/check_routing.py：线-线 / 线-过孔间距 0 问题（精确几何校验）
```

### 3.0c 最终收敛阶段（2026-09-17，依 `..._Routing_Final_Convergence_Plan.md`）

**第二轮（依 `..._Routing_Final_Convergence_Next_Steps.md`）**——停止全局 reroute，改做局部收敛：

**第三轮（2026-09-17，MD §7 TPS 区 + §2 U3 地引脚）**——`tools/fix_tps.py` 局部收敛：

| 项目 | 结果 |
|---|---|
| `TPS_L2`（U3.9 ↔ L2.2，F.Cu / **无 Via** / 目标 0.50 mm） | ✅ **已布通**（15 段：4 段 0.50 mm + 焊盘处 0.25 mm 收颈，0 过孔） |
| `TPS_PS_SYNC`（U3.1 ↔ R27.2） | ✅ **已布通**（32 段 / 0.20 mm） |
| `TPS_EN`（U3.14 ↔ R26.2）、`TPS_VSEL`（U3.15 ↔ R28.2） | ❌ 未能闭合：U3 顶部引脚 14/15 的出线走廊被 SYS 铜皮/走线占住，连短桩都放不下；需要局部 rip-up SYS 或交互布线 |

**第四轮（2026-09-17，用户批准的 SYS 局部 rip-up）**——结论：仍然走不通，已回退。

按用户授权实现"只 rip 引脚附近 1–2 mm 的 SYS、随后立刻重走并验证 DRC"（`fix_tps.py` 的
`rip_near_pads()`：把段在边界处切开，只取靠引脚那一段，且**超过 2 mm 就拒绝**）。实测：

- U3.14 / U3.15 的出线通道在栅格上只有**一列 0.1 mm 宽**的可行格（两侧被 U3.12/13 的 SYS
  焊盘与 U3.15/14 自身焊盘夹住），
- 上方唯一的挡路物是 **1.2 mm 宽的 SYS 主干段**（(33.25,42.2)→(37.1,40.9)，距引脚中心 1.21 mm）；
  即使把这 1–2 mm 挖掉，通道也接不到板上的 SYS 网络其余部分——因为该处"缺口"被
  U3 自身焊盘列封成一个死端。

因此自动手段到此为止，已把 routing.json 回退到验证过的状态（DRC 0/0、unconnected 62），
并把基准板更新。`TPS_EN` / `TPS_VSEL` 建议在交互布线里解决，可选做法：

1. 把那段 SYS 主干整体上移 ≈1 mm（属于主干重走，不是局部 rip）；
2. 或让 TPS_EN / TPS_VSEL 从 U3 底部绕行（需跨越 U3 焊盘列，人工布更稳）；
3. 或把 R26 / R28 移到 U3 顶部一侧（涉及 move placement，需评审）。

**第五轮（2026-09-17，方案 1：SYS 主干上移）**——已实现并测试，结论：**不可行**，已回退。

`tools/move_sys_trunk.py` 的做法：把落在"U3 顶排引脚上方走廊"内的 SYS 铜整体摘掉
（只摘该走廊内的一段），再用**显式走廊折线**重画（保留原两个连接端点，因此连通性由结构保证），
每一版都先用布线器的真实间距引擎打分，只有"不劣于基线"才写盘。

实测（基线 = 摘除后的 SYS 分数 99，越小越好）：

| 走廊高度 | SYS 间距分数 |
|---|---|
| 41.90 mm | 205 |
| 41.70 mm | 205 |
| 41.50 mm | 207 |
| 41.30 mm | 210 |
| 41.05 mm | 212 |
| 40.50 mm | 235 |

即：把主干抬高只会把冲突**搬到上方**——U3 上方 1~2 mm 的区域已经被其它网络的走线占满。
脚本按设计**拒绝写盘**，`routing.json` 与基准板保持验证过的状态（ERC 0 / DRC 0/0、
unconnected 62），未产生任何回归。

> 结论：`TPS_EN` / `TPS_VSEL` 属于"必须人工/交互布线"的少数网络。建议在 KiCad 交互布线里，
> 从 U3 底部绕行（方案 2），或评审把 R26 / R28 移到 U3 顶部一侧（方案 3）。

**第六轮（2026-09-17，依 `..._TPS_EN_VSEL_Routing_Solution.md`）**——按 MD §1/§4/§5
"局部减宽 + 尽快换 B.Cu"的方案，`TPS_EN` / `TPS_VSEL` **双双布通**。

> **根因不在 SYS，而在布线器自己的铜箔几何模型。** 第三～五轮的失败尝试
> （局部 rip-up、主干上移）都是在"通道明明够宽"的前提下失败的。

`route.py` 原先把所有线段障碍建成**轴对齐外接矩形**：轴向铜箔是精确的，但 45° 走线的
外接矩形比真实铜箔宽 √2 倍，还会在斜线两侧刷出一整片方形阴影。实测：

| 项目 | 说明 |
|---|---|
| 挡路者 | `3V3_MAIN` F.Cu 斜线段 (28.1,49.7) → (30.7,47.1)，0.25 mm 宽 |
| 它的外接矩形 | (27.98,46.98)–(30.82,49.83)，把 **R28.2 焊盘的 78/78 个栅格全部盖死** |
| 真实铜箔距离 | 该斜线离 R28.2 焊盘中心 **1.10 mm**，扣掉半宽/焊盘后仍有 **0.50 mm** 余量 |

新增 `seg_shape()`：线段按**真实胶囊形**（长 L、宽 w、两端圆头，带旋转角）建模，
在 `Board.load_routing` / `Session.route_net` / `Session._commit_stub` 三处统一使用。
改完后 R28.2 的 78/78 栅格恢复可走，`TPS_VSEL` / `TPS_EN` 当场布通。

| MD 条目 | 执行情况 |
|---|---|
| §1 / §2 SYS 局部减宽 | U3 上方那段 SYS 主干 1.20 → **0.80 mm**（0.80 mm 已是本工程 BAT/SYS/USB_VBUS 的主干标准，不算放宽规则），**主干位置不动**；间距分数 0 → 0，无回归 |
| §4 `TPS_VSEL` | U3.15 → F.Cu 向左短出 → Via **(32.5,43.5)** → **B.Cu 长距离** → Via (29.0,47.1) → R28.2 ✅ |
| §5 `TPS_EN` | U3.14 → F.Cu 向上极短 → **向左** → Via **(32.4,42.7)** → **B.Cu 长距离** → Via (40.9,41.3) → R26.2 ✅ |
| §8 两根控制线过孔错开 | `(32.5,43.5)` / `(32.4,42.7)`，X、Y 均不同，中心距 0.806 mm ≥ 0.75 mm ✅ |
| §9 不移动 R26 / R28 | 未移动 ✅ |
| §10 `TPS_CTRL_ESCAPE` 规则区 | **未启用**（前两项方案已成功） |
| §11 不动 TPS_L1 / L2 / PS_SYNC / 3V3_MAIN | `fix_tps_ctrl.py` 的 `FROZEN` 集合只读不改 ✅ |
| §14 `SYS` 在 TPS 区连通 | U3.12/U3.13（两块叠放的 SYS 焊盘）→ 新增 0.5 mm 短桩向上 1.4 mm 接到 C18.1 与 `SYS_ISLAND_U3` 铜皮 ✅ |
| §13 ⑧⑨ 铺铜 + DRC | `apply_routing.py` → `kicad-cli pcb drc`：**DRC 0 Error / 0 Warning** ✅ |
| §13 ⑩ TPS_EN / TPS_VSEL 不再出现 | ✅ 两条都已从 `unconnected_items` 消失 |

> **为什么 TPS_EN 必须向左**：向右的那条 F.Cu 走廊正好压在 U3.12/U3.13（SYS 电源焊盘）
> 上方，会把这两块焊盘的出线口整条封死（实测该走廊被 0.2 mm 走线一占，SYS 的
> 0.5 mm 出线就再也上不去）。先让 SYS 自己占住这条走廊（同时满足 MD §14 的连通要求），
> MD §5 要求的"向上→向左→过孔→B.Cu"就自然成为**唯一可行走法**。

本轮的诊断工具（都可重跑）：

| 脚本 | 用途 |
|---|---|
| `tools/diag_tps_ctrl.py [net]` | 从每个锚点洪水填充，指出到底是哪个焊盘被切断 |
| `tools/diag_blocked_cell.py <net> <x> <y> [w]` | 打印某个栅格上所有"距离不足"的真实铜箔 |
| `tools/probe_via.py <net> x0 y0 x1 y1` | ASCII 打印一片区域内"哪里能放过孔" |
| `tools/drc_diff.py <old.json> [new.json]` | 两次 DRC 的差异（修好了什么 / 新冒了什么） |

检查点：`esp32-board-v1.1_routing_tps_ctrl_20260917.kicad_pcb` +
`routing/routing_tps_ctrl_20260917.json`；上一轮基准 `esp32-board-v1.1_routing_pre_tps_ctrl_20260917.kicad_pcb` 保留。

> 剩下的 `SYS_ISLAND_U2` / `SYS_ISLAND_C13` / `3V3_ISLAND_U3` / `3V3_ISLAND_CAPS`
> 岛—岛 / 焊盘—岛断点仍待处理（`tools/anchor_islands.py` 已就绪，未在本轮执行）。

**第七轮（2026-09-17，依 `..._Post_TPS_Final_Convergence_Plan.md`）**——按 MD 的三段式
Checkpoint 推进，**Checkpoint 1 全部达成、Checkpoint 2 只差 `CHG_OTG` 一项**。

新工具 `tools/bridge_net.py` 是这一轮的主力：它**先把网络现有的铜箔按真实几何拆成连通
分量**（线段/过孔/焊盘/铺铜填充块，含"铺铜轮廓 ≠ 铺铜填充"这一坑），再用 MST 只补真正缺的
那几段。源格点取自**真实铜箔内部**，所以新铜必然与旧铜搭上；目标优先取走线**端点**，
避免落在已有走线中间留下悬空残段。

| MD 条目 | 处理 | 结果 |
|---|---|---|
| §3.1 U3 Pad10 GND | `fix_gnd.py` 在焊盘旁放 **0.4/0.2** 过孔 + 0.3 mm 短铜 | ✅ U3 地引脚闭合 |
| §4 SYS 剩余 3 项 | `SYS_ISLAND_U2` 两块填充块分别接 In2 主干、`L1.2`→In2 主干、顶层 F.Cu 组 → In2 | ✅ **SYS 从 unconnected 中完全消失** |
| §5 3V3_MAIN 剩余 2 项 | 两个 island 各放过孔 + In2 短铜互连（不依赖同名 Zone 自动连通） | ✅ 岛—岛闭合 |
| §5.2 两段 3V3_MAIN 孤立铜 | 查明并不是"历史短桩"，而是**ESP32 模组 3V3 群（C1–C4/R1–R5/U1.2）整块与电源区断开了 24 mm**！MD 里没预料到这一点。用一条 **0.65 mm** 主线（In2 → B.Cu → F.Cu）把它接回 TPS 输出区 | ✅ **3V3_MAIN 从 unconnected 中完全消失** |
| §6 BAT_BUS | `bridge_net` 按 F2/F3 → U4/C17 → U2 的拓扑补齐：主干 **0.80 mm**、器件端 0.50/0.35 mm，跨板段走 B.Cu | ✅ 8 个焊盘全部并入（40 段 / 5 过孔） |
| §7 EPD_3V3 | 连成一条 0.50 mm 主干 + 短支路；U6/L3/C25/C26/C27/C34 全部并入 | ✅ 7 项全闭合 |
| §9 CHG_REGN | 只加 1 段 **0.15 mm** 竖线把 U2.22 接回 C10/R16 组 | ✅ |
| §10 CHG_CE | U2.9 ↔ R18.2（18 段 / 3 过孔）+ R18.2 ↔ U1.24 | ✅ |
| §11 CHG_DSEL | U2.24 ↔ R20.2（6 段 / 3 过孔） | ✅ |
| §11 CHG_OTG | U2.8 被 0.4 mm 间距引脚区封成一个 **34 格的窄井**（F.Cu 上只有一列 0.15 mm 可行格，且四周无出口） | ❌ 待局部 rip-up |

**工具链修正（本轮发现并修掉的真 bug）**：

| 问题 | 修正 |
|---|---|
| `fix_gnd.py` 验证的是 0.4 mm 过孔，写盘却一律写成 **0.6 mm** → 直接制造 `clearance` 违规 | 记住并通过实际验证的 (dia, drill) |
| 布线器的过孔掩膜**不看同网络过孔** → 新过孔和旧过孔孔壁相碰（`hole_to_hole`） | `via_mask()` 增加同网络孔间距约束（0.25 mm，取自工程规则） |
| 单批 `bridge_net` 里后一个网络看不到前一个刚加的铜 → CHG_CE/CHG_OTG 叠在一起 | 每桥一段就 `rebuild_copper()` |
| 贴焊盘中心的 `snap_end` 会**拉长末端线段**擦过旁边的焊盘（0.125 mm 违规） | 位移 >0.2 mm 不吸附；吸附后还要过一遍可行性校验 |
| 新 BAT_BUS 主干切开 B.Cu GND 铺铜，填充器在 0.4 mm 缝隙里挤出一条 **0.116 mm** 细颈（`connection_width` 警告） | `apply_routing.py` 把 **B.Cu GND 铺铜的局部净空提高到 0.30 mm**，让铺铜不再去填这种缝隙 |

其它一次性手术：`SPI_SCLK` 的过孔原本落在 J2 电源脚（J2.15/16）出口正前方，把 EPD_3V3
唯一的逃生口封死；把它连同短桩一起 rip 后重布（`rip_local.py` + `bridge_net.py`），
并用 `move_endpoint.py` 把留下的悬空残段剪掉。

检查点：`esp32-board-v1.1_power_backbone_checkpoint_20260917.kicad_pcb`（Checkpoint 1）、
`esp32-board-v1.1_bat_epd_checkpoint_20260917.kicad_pcb`（Checkpoint 2 除 CHG_OTG 外）。

> 本轮 non-GND unconnected **40 → 16**，总计 **59 → 35**，全程 DRC 保持 **0 Error / 0 Warning**。

**第八轮（2026-09-17，依 `..._Final_16_NonGND_Convergence_Plan.md`）**——按 MD 的
Checkpoint A/B/C/D 推进：**A 完成、C 完成一半、D 完成一半**；**non-GND 16 → 9**。

| MD 条目 | 处理 | 结果 |
|---|---|---|
| §2~§6 Checkpoint A：`CHG_OTG` | ① 先 `pre_chg_otg` 存盘；② 用 `move_endpoint` + `rip_local` 把 U2.7 的短桩与 y≈63.1 走线**只拆掉本地一小段**，`bridge_net` 重布 CHG_INT_N；③ 再 `bridge_net` 收 `CHG_OTG`（U2.8 → F.Cu 短出 → via → In2/B.Cu → R19.1） | ✅ **BQ25895 区封闭**（CHG_OTG / CHG_INT_N / CHG_CE 均 Connected） |
| §11~§12 Checkpoint C：`I2C_SCL` | `bridge_net I2C_SCL --layer-pen 5,8,0`（把 In2 的每步代价抬高，优先 B.Cu / F.Cu） | ✅ 已闭合（50 段 / 10 过孔） |
| §11~§12 Checkpoint C：`I2C_SDA` | 两端都被封死，见下 | ❌ 待局部重排 U5 区 |
| §13~§14 Checkpoint D：`TF_CS_N` | `bridge_net TF_CS_N` | ✅ 已闭合（17 段 / 6 过孔） |
| §13~§15 Checkpoint D：`TYPEC_INT_N` | U5.6 一侧被封死，见下 | ❌ 待局部重排 U5 区 |
| §7~§10 Checkpoint B：USB DP/DN | 见下（DP 已布通，DN 完全没有铜） | ⏸ 需要差分对布线 |

**`I2C_SDA` / `TYPEC_INT_N` 的准确阻塞点**（这两个都在 TUSB320 U5 那一小片）：

```text
U5 引脚：3/4/5/6 在 y=70.33（GND / VBUS_DET / GND / TYPEC_INT_N）
         7/8 在 x=30.23（I2C_SDA / I2C_SCL，0.4 mm 间距）

它们的过孔必须落在 U5 的引脚口袋里，而口袋里：
  · In2.Cu 正好被 1.2 mm 宽的 3V3_MAIN 主干压住（x 30.0~31.2，y 66~76）→ 任何过孔
    都会与主干冲突（0.42 mm 的过孔净空）；
  · 东侧 F.Cu 是 USB_VBUS_DET（x=31.8 竖线 + 斜线）与 TF_CD_N（x=32.2 竖线）；
  · 西/南侧是 U5 自己的 0.4 mm 间距引脚（U5.2/U5.4/U5.6/U5.9）。
实测：x ≤ 29.58 或 x ≥ 31.62 才有过孔位置，但这两种位置分别被 U5 焊盘/上述走线占住。
```

> 因此这两项需要**局部重排 U5 扇出**，而其中一步会是「把 In2 的 3V3_MAIN 主干在 U5
> 下方局部收窄（1.2 → 0.5 mm）或平移约 1.5 mm」。这属于 MD §1「不要再动车 3V3_MAIN」
> 的例外情形（3V3_MAIN 自身没有回归，是它在挡 I2C），**等确认后再动**。
> 本轮已实测过的失败尝试：rip USB_VBUS_DET 本地两段后重布（重布结果反而更靠中间，把
> 通道堵得更死）；先 SCL 后 SDA（SCL 抢走 SDA 的出口）、先 SDA 后 SCL（SDA 两端仍封死）。

**USB（Checkpoint B）现状**：

```text
USB_DP_CONN  = 已布通（F.Cu / 0.24 mm，从 J1.A6/B6 ↔ D2.1 ↔ 往北）
USB_DN_CONN  = 一点铜都没有：D3.1 / J1.A7 / J1.B7 / R10.1 四个焊盘全孤立，
               连 0.7 mm 的 A7↔B7 也放不下（J1 扇出区已被 CC1/CC2/VBUS/DP 占满）
```

按 MD §9，DN 应该**照着已布好的 DP 一起做差分对**，不要用 bridge_net 硬补。

检查点：`esp32-board-v1.1_pre_chg_otg_20260917.kicad_pcb`、
`esp32-board-v1.1_u2_u5_progress_20260917.kicad_pcb`、
`esp32-board-v1.1_bq_i2c_tf_checkpoint_20260917.kicad_pcb`（本轮最终状态）。

**第九轮（2026-09-18，依 `..._U5_USB_GND_Final_Convergence_Plan.md`）**——Checkpoint E 达成，
**non-GND 9 → 3**（只剩 `USB_DN_CONN`）。

| MD 条目 | 处理 | 结果 |
|---|---|---|
| §3~§6 U5 下方 3V3_MAIN 局部减宽 | 新增 `tools/neck_trunk.py`：保持中心线不动，把 In2.Cu 主干在 **y 68.0~71.2** 由 1.20 → **0.50 mm**，两端各留 0.35 mm 的 0.85 mm 过渡段，不加过孔 | ✅ Refill + DRC 后 **3V3_MAIN 仍完全连通**（0 条 unconnected） |
| §7~§9 `I2C_SDA` | 减宽后 U5.7 的过孔位恢复：**F.Cu 向东短出 → 0.4/0.2 过孔 (31.300,69.700) → B.Cu**（正是 MD §7.1 的参考区域）→ `bridge_net --layer-pen 5,8,0` 收掉整条 SDA | ✅ **4 → 0** |
| §10 `TYPEC_INT_N` | 先按 §11 把 USB_VBUS_DET 的 U5 东侧竖线**手工东推**到 x=31.81（手工画线，不用自动重布）；随后 U5.6 → F.Cu 东出 → 0.4/0.2 过孔 **(31.300,70.500)**（与 SDA 过孔 Y 错开 0.8 mm）→ B.Cu | ✅ **2 → 0** |
| §13~§20 Checkpoint F：USB DP/DN | 做了详细勘察，**发现结构性问题**（见下） | ⏸ 需确认方案 |

**USB（Checkpoint F）勘察结论**——`USB_DN_CONN` 的 4 个焊盘（J1.B7 / J1.A7 / D3.1 / R10.1）
一个铜都没有，而 J1 扇出区已被 CC1 / DP / VBUS_RAW / SHIELD 占满。逐点实测后确认：

```text
J1 焊盘 x 顺序： B7(23.25,DN)  A6(23.75,DP)  A7(24.25,DN)  B6(24.75,DP)   ← 都在 y=77.65

要接的两条搭接： DP: A6—B6   /   DN: B7—A7
但 A7 夹在 A6 与 B6 之间 → DN 的搭接横线必须穿过 A6 的竖直出线；
反过来把 DP 搭接放到更远处，DN 的横线又会撞 DP 的搭接横线。
即：A6—B6 与 B7—A7 在**同一层上无法同时成立**（数学上必有一次交叉）。

想从连接器“内侧”（y 78.8~82.3）绕也不行：
  USB_VBUS_RAW 在 y=78.60 横穿、USB_SHIELD 在 y=79.40 横穿，
  两条竖出线都会被它们挡住。
```

> 所以 MD §17「Via = 0」与这个连接器的焊盘排列存在冲突：**至少需要 1 颗过孔**来完成其中
> 一条搭接（短桩上的过孔不影响差分对本身的连续性）。请确认：
> ① 允许在 DN（或 DP）的搭接短桩上放 1 颗 0.4/0.2 过孔（推荐）；或
> ② 保持 Via = 0，改为在连接器外侧另行飞线（会很长、且仍与 CC/VBUS/SHIELD 扇出冲突）；
> ③ 其他指定做法。
> DP 本身已经布通（F.Cu / 0.24 mm / 0 过孔），DN 的主干长线可以照 DP 平行复核后再定。

检查点：`esp32-board-v1.1_pre_u5_fanout_20260918.kicad_pcb`（改动前）、
`esp32-board-v1.1_u5_closed_20260918.kicad_pcb`（Checkpoint E 完成）。

**第十轮（2026-09-18，依 `..._J1_USB_Interleaved_Pad_Fanout_Final_Plan.md`）**——
**`USB_DN_CONN` 闭合，Non-GND unconnected = 0** ✅（MD 的 Checkpoint G）。

| MD 条目 | 处理 | 结果 |
|---|---|---|
| §3~§11 Plan A：VBUS 下沉 | 删掉 J1 内侧 y≈78.60 的 F.Cu VBUS 横线（10 段），在西侧 VBUS 焊盘组旁加 **0.6/0.3 过孔 (21.60,76.80)** 接 In2 汇流；USB_SHIELD 保持不动 | ✅ `USB_VBUS_RAW` 仍完全 Connected，DRC 0 |
| §12~§14 DP 下侧 short | 局部 rip J1 A6/B6 的 DP 扇出（8 段），重画：A6 → 下侧 short **y=76.72** → B6；A6 作主出口向北接回原主干 | ✅ DP 仍 Connected |
| §14 DN 上侧 short | 重画：B7 → 上侧 short **y=78.55** → A7；B7 作主出口向北 → D3.1 | ✅ J1 侧全部并入 DN |
| §15~§17 DN 主干 | ⚠️ 见下 | DN 已闭合（带过孔） |

**DN 主干的实测结论（与 MD 的期望有出入）**：MD 期望 DN 沿 DP 平行、全程 F.Cu / 0 过孔。
实测该走廊在 ESD 管北侧就被占满，逐段量过：

```text
D3.1 的四个方向：
  北：D3 自己的 Pad2（GND，x 22.575~23.025）挡住
  西：USB_CC1 的过孔 (22.20,75.60) 挡住（净空差 0.14 mm）
  东：USB_DP 的竖直段 (x 23.40) 挡住
  南：DN 自己的扇出

DP 西侧想跑第二条线（DN）：
  y 69.6~70.4 被 BAT_BUS 的 0.8 mm F.Cu 主干挡死（铜到 x=22.90）
  y 66.75~69.36 被 3V3_MAIN 的三个 F.Cu 支路挡死（x 23.75~25.43）
  → DP 与该两道墙之间已无 0.27 mm 余量
```

因此本轮先按"可布通"完成：DN 主干用现有布线器走 **F.Cu→In2→B.Cu，3 颗 0.45/0.2 过孔**
（`bridge_net USB_DN_CONN`），**非地网络已全部连通**。

> 若要回到 MD 期望的「DN 全程 F.Cu / 0 Via」，需要再做一次局部重排（按优先级）：
> ① 把 3V3_MAIN 在 (24.10,67.00)-(24.10,69.10) 一带的三个 F.Cu 支路局部改走 In2；
> ② 把 BAT_BUS 的 F.Cu 段 (22.50,70.00)→(15.50,70.00) 的东端收短或改层；
> ③ 或者把 USB_CC1 的过孔 (22.20,75.60) 西移，允许 DN 从 D3.1 西侧出线。
> 这三项都会碰到已完成的电源/CC 布线，需确认后再动。

**Checkpoint H：GND 第一轮清理**（MD §24）——`fix_gnd.py` 又放了 5 颗 GND 过孔、缝合 2 块
铺铜块：**GND 22 → 18 项**。剩余 18 项的分布：

```text
A 类（含 Pad）：U5.3↔U5.5、R13.2↔U2.25、R13.2↔短铜、J3.SH↔短铜
                —— 实测这几处的 0.4/0.2 过孔都放不下（相邻焊盘/内层走线卡净空）
B 类（Track↔Track）：3 条历史 GND 短桩
C 类（Zone/Plane）：13 条 = F.Cu 铺铜块之间 / 与 In1 平面 / 与 In2、B.Cu 铺铜的孤立铜
```

检查点：`esp32-board-v1.1_nongnd_zero_20260918.kicad_pcb`（Non-GND = 0 时刻）、
`esp32-board-v1.1_gnd_round1_20260918.kicad_pcb`（GND 第一轮之后）。

| U3 地引脚（Pad4 / Pad10，"短粗 F.Cu 地铜 + GND Via"） | 部分完成：`SYS_ISLAND_U3` 铜皮下沿由 44.05 收到 **42.55**（原先把 U3 顶排引脚的出线整段盖住），铺铜随后可以流进 U3 区域；真实 GND 焊盘 23 → **6** |
| `3V3_MAIN` | ✅ **完全闭合**（不再出现在 unconnected） |
| `SYS` | 仅剩 2 项（`SYS_ISLAND_U2`/`C13` 需岛内过孔或人工接线） |

顺带修掉：TF_SCLK 重复过孔 2 组、EPD_VCOM/TPS_VSEL 悬空残段；**DRC 保持 0 Error / 0 Warning**。

| MD 条目 | 执行情况 |
|---|---|
| §11 停止全局自动 reroute，保存基准板 | ✅ 保存 `esp32-board-v1.1_routing_final_convergence_20260917.kicad_pcb`（+ 同名 routing json）；此后只做局部修改 |
| §2 剩余真实 GND Pad | ✅ **23 → 2 个**：`fix_gnd.py` 逐焊盘放 GND 过孔（0.6/0.5/0.4 mm）或用 0.15~0.3 mm 短 GND 铜接到最近的 GND 铜/铺铜；**只剩 U3 Pad4 / Pad10**（TPS63070 的 GND 引脚，出线走廊被开关节点走线占住，需局部 rip-up 或交互布线） |
| §14 GND Zone 碎片 | ✅ GND 铺铜启用"自动删除孤立铜岛"（`ISLAND_REMOVAL_MODE_ALWAYS`），并新增 1 颗缝合过孔把仍带 Pad/Via 的碎片接回地平面；纯碎片由填充器直接删除，不再以 unconnected 形式残留 |
| §3 SYS 闭合 | 部分完成：`SYS_ISLAND_U3` 已锚定，SYS unconnected 8 → 6（`SYS_ISLAND_U2`/`C13` 需在岛内放过孔或人工接线） |
| §4 3V3_MAIN 闭合 | 部分完成：`3V3_ISLAND_CAPS` 已锚定，剩余 4 项（`3V3_ISLAND_U3` 位于 U3 焊盘阵列内，锚点被自身焊盘挡住） |
| §12 小循环验证 | ✅ 每轮 `apply_routing → DRC`，中途出现的 3 个新增违规已回退；**DRC 持续 0 Error / 0 Warning** |

阶段定位：**Routing final convergence** —— 主布线结构成型，剩下的是把电源/地/局部控制网络
真正收敛到 0 unconnected。本轮完成：

| 项目 | 处理 | 结果 |
|---|---|---|
| 电源铜皮"岛—主干"锚点（MD §5） | 布线器新增 `anchor_islands()`：逐个铜皮检查是否有同网络 Track/Via 落在铜皮内，没有就画一段最短合法锚点接过去 | `SYS_ISLAND_U3`、`3V3_ISLAND_CAPS` 已锚定 |
| GND 真实焊盘未接地（MD §4） | 新增 `tools/fix_gnd.py`：对 DRC 报出的未连接 GND 焊盘，优先在其焊盘内/旁放 GND 过孔（0.6→0.5→0.4 mm 递减），放不下就用 0.3/0.2/0.15 mm 短 GND 铜连到最近的 GND 铜 | 已放置 9~11 颗；GND unconnected 48 → 36 |
| GND 铺铜可达性 | `apply_routing.py` 把 GND 铺铜的局部净空从 0.30 收到 **0.20 mm**（KiCad 仍按网络对取较大值，POWER 仍保持 0.2） | 更多密集区焊盘被铺铜覆盖 |
| DRC 复核 | 每轮 `apply → DRC` 迭代，出现过 3 个新增违规（过孔间距/连接宽度）立即回退 | **DRC 维持 0 Error / 0 Warning** |

当前 DRC 未连接项按网络（2026-09-18 第十轮后，共 **18** 项，按 DRC record 计）：**全部是 GND**
（铺铜块 / 平面之间 13 条 + 真实地焊盘 4 条 + 历史短桩 3 条…去重后 18 条）。
**Non-GND unconnected = 0** ✅
**已闭合**：`3V3_MAIN`、`SYS`、`BAT_BUS`、`EPD_3V3`、`CHG_REGN`、`CHG_CE`、`CHG_DSEL`、
`CHG_OTG`、`CHG_INT_N`、`I2C_SCL`、`I2C_SDA`、`TF_CS_N`、`TYPEC_INT_N`、`USB_DP_CONN`、
`USB_DN_CONN`、TPS 全家、U3 的 GND 与 SYS 焊盘、全部电源铜皮锚点。
**所有非地网络均已连通。**
**已闭合**：`3V3_MAIN`、`SYS`、`BAT_BUS`、`EPD_3V3`、`CHG_REGN`、`CHG_CE`、`CHG_DSEL`、
TPS 全家（L1/L2/PS_SYNC/FB/EN/VSEL）、U3 的 GND 与 SYS 焊盘、`3V3_ISLAND_*`、`SYS_ISLAND_*`。

> 检查点板：`esp32-board-v1.1_routing_checkpoint_20260917.kicad_pcb` +
> `routing/routing_checkpoint_20260917.json`（MD §13.1 要求的收尾基准板）。

### 3.0b 局部电源铜皮（MD §8 / §15，2026-09-16）

布线器新增"局部电源铜皮 + 宽主干"能力，用来收掉 `SYS` 与 `3V3_MAIN`：

| 对象 | 层 | 范围 (mm) | 作用 |
|---|---|---|---|
| `SYS_ISLAND_U2` | F.Cu | 35.30–42.85 / 58.95–60.55 | U2 SYS Pin15/16 + L1 输出 |
| `SYS_ISLAND_C13` | F.Cu | 31.35–32.55 / 63.95–65.10 | C13 电池端大电容 |
| `SYS_ISLAND_U3` | F.Cu | 31.45–35.05 / 40.35–44.05 | U3 VIN + C18/C19 |
| `3V3_ISLAND_U3` | F.Cu | 33.90–35.20 / 45.60–47.20 | U3 VOUT Pin7/8 |
| `3V3_ISLAND_CAPS` | F.Cu | 32.10–33.60 / 47.90–51.85 | 3V3 输出电容 C22 / R6 |

实现要点：

- 铜皮以 KiCad zone 形式生成（优先级 20，覆盖 GND 铺铜），**实体连接（非热焊盘）**，
  并开启"移除孤立铜岛"，避免密集区里的碎片被 DRC 判为 isolated copper。
- 布线器把铜皮当作**该网络自身的铜**：铜皮内的焊盘由铜皮连通，迷宫只需把主干/
  支线接到铜皮即可，因此 `3V3_MAIN`（34 个焊盘）与 `SYS`（11 个焊盘）的布通率大幅提升。
- 其它网络在铜皮范围内保持 0.1 mm 净空，保证铜皮不被切碎。
- 主干**不再依赖 0.5 mm 单线**：`SYS` 与 `3V3_MAIN` 走 In2.Cu 宽铜，收尾阶段自动加宽到
  **1.2 mm**（36 段），BAT/SYS/USB_VBUS 主干维持 0.8 mm（15 段）。

结果：**`SYS` 与 `3V3_MAIN` 已布通**（3V3_MAIN：158 段 / 12 过孔，含 1.2 mm 主干；
SYS：14 段 / 2 过孔，含 1.2 mm 主干），unconnected 由 92 → **68**，DRC 仍为 **0/0**。

### 3.0 DRC 清零记录（MD §2 / §20 ①②③）

| 项 | 处理方式 | 结果 |
|---|---|---|
| EPD_GDR ↔ EPD_RESE 间距 0.125 mm | 把 EPD_RESE 在 J2 Pin3 处的过渡重画：抬高 0.25 mm、收颈到 0.20 mm，层间过孔随之内移；EPD_GDR 保持原路径。脚本内自动核对两网最小间隙（0.225 mm）后才接受，否则回滚 | ✅ |
| EPD_3V3 ↔ C31 GND 间距 0.127 mm | 把该 0.5 mm 段与斜线的交点整体上移 0.3 mm（10.7,44.7 → 10.7,44.4），器件不动 | ✅ |
| EPD_BUSY / EPD_RESE / SPI_SCLK 0.1 mm 悬空线头 | 把残留端点落到所属短桩的端点上（共享端点即连通）；SPI_SCLK 本身已连通，仅清理残段 | ✅ |
| EPD_VSH1 ↔ C32 Pad1 connection width 0.135 mm | 端点从焊盘边缘推到焊盘内 0.3 mm | ✅ |

> 清零后：`DRC Error = 0 / Warning = 0`，`unconnected = 92`（保留未完成网络，符合 MD §2 的阶段性目标）。

线宽分布（0.8 mm = 主干加宽段；0.5/0.4 mm = POWER 与 SWITCH_NODE；
0.3 mm = HV_EPD；0.24 mm = USB 差分；0.2 mm = 默认；0.15–0.25 mm = 焊盘收颈）：

```
0.80 mm : 20 段（BAT1_RAW / BAT2_RAW / BAT_BUS / USB_VBUS_RAW / USB_VBUS_PROT）
0.50 mm : 73   0.40 mm : 9    0.30 mm : 42   0.25 mm : 48
0.20 mm : 401  0.24 mm : 32   0.15 mm : 25
```

### 3.1 未完成的 14 个网络（按 MD §6~§15 的人工收尾顺序排列）

| 网络 | 位置 |
|---|---|
| ~~② `SYS`~~ | **已完成**（SYS_ISLAND_U2/C13/U3 + 1.2 mm In2.Cu 主干） |
| ① `TPS_L2` | U3 Pin9 ↔ L2 Pin2（switching path，要求 F.Cu / 0 Via / 0.5 mm） |
| ③ `USB_DN_CONN` | 与 `USB_DP_CONN` 一起人工重整（0.24/0.18、F.Cu、无 Via） |
| ④ `EPD_VGH` | D6 → C28 → J2 Pin21（HV_EPD 0.3/0.2） |
| ⑤ `CHG_REGN` | U2 REGN → C10 → R16（本地电源节点，短、无 Via） |
| ⑥ `CHG_CE` / `CHG_INT_N` / `CHG_OTG` / `CHG_DSEL` | U2 控制线（低速，允许换层） |
| ⑦ `I2C_SCL` / `I2C_SDA` | U2 左列 + U4/U5（0.2 mm，允许换层） |
| ⑧ `TF_SCLK` / `TF_CS_N` | U1 → R33 → J3（SPI_SCLK 本身已连通） |
| ⑨ `TYPEC_INT_N` | U5.6，用剩余通道 |
| ~~⑩ `3V3_MAIN`~~ | **已完成**（U3 输出铜皮 + In2.Cu 1.2 mm 主干 + 各区域 F.Cu 支线） |
| `BAT_BUS` / `EPD_3V3` | 本轮因功率网络"出线预约"改动被挤出（见 §6） |

均位于密集引脚区（BQ25895 左列、TPS63070 左列、TUSB320、ESP32 底部、USB-C / FPC 扇出）的
最后 1–2 段，部分位置四条 0.2 mm 走线必须共用不到 1 mm 的走廊。建议用 KiCad 交互布线收尾
（自动布线器已尽量把这些通道留出）。

### 3.2 DRC 项（已清零，保留记录）

| 类型 | 位置 | 说明 |
|---|---|---|
| — | — | 见 §3.0：4 类共 8 项已全部修复，当前 DRC = 0/0 |

---

## 4. 2026-09-16 确认结论的执行情况

依据 `ESP32S3_GDEM102T91_V1.6_Routing_Power_Width_and_R29_Confirmation.md`：

| MD 条目 | 执行情况 |
|---|---|
| §1 POWER 默认线宽 0.80 → **0.50 mm** | ✅ 已写入 `.kicad_pro` |
| §1.3 BAT/SYS/USB_VBUS 主干 0.5 起步后加宽 | ✅ 收尾阶段自动加宽：20 段 → **0.80 mm**（BAT1_RAW/BAT2_RAW/BAT_BUS/USB_VBUS_RAW/USB_VBUS_PROT），仅在几何允许处加宽 |
| §1.3 CHG_SW / TPS_L1 / TPS_L2 / EPD_SW 短、小面积、**不打 Via** | ✅ 这四个网络在布线器中禁用过孔（`NO_VIA`），并优先在早期轮次布线（最短路径优先） |
| §1.4/§1.5 新增 `CHG_PMID`、`EPD_3V3`、`TPS_L1`、`TPS_L2` | ✅ 已脱离 `Default`（不再按 0.20 mm 布线） |
| §1.6 拆分为 POWER_MAIN / SWITCH_NODE | ✅ 采用：新增 `SWITCH_NODE` 网络类（`track_width 0.50 mm`、`clearance 0.15 mm`）承载 `CHG_SW`/`EPD_SW`/`TPS_L1`/`TPS_L2`；`POWER`（0.50 mm / 0.20 mm）承载 `USB_VBUS_*`/`BAT*`/`SYS`/`3V3_MAIN`/`CHG_PMID`/`EPD_3V3` |
| §1.7 不为 0.8 mm 重排 Placement | ✅ 未修改任何器件坐标 |
| §2 R29 冻结位置 (12.8648, 49.5497) | ✅ 板内实测 `R29 = (12.8648, 49.5497)`；未使用旧版 (23.x, 43.x) |
| §2.4 U6 位置 | ✅ 板内实测 `U6 = (15.55, 43.70)`，与 MD 一致 |

> `SWITCH_NODE` 拆分的必要性：TPS63070（U3）引脚 0.5 mm 间距、焊盘 0.35 mm，相邻焊盘
> 间隙只有 0.15 mm；若把 `TPS_L1/TPS_L2` 归入 `POWER`（0.20 mm 间距要求），**焊盘本身**
> 就会违反 DRC。因此它们必须保留 0.15 mm 间距规则，同时拿到 0.50 mm 线宽。

仍然存在的差异：

1. **窄颈规则区** `PWR_NECK_1..8`（矩形由真实窄段包围盒 + 0.35 mm 生成），区域内允许
   POWER / SWITCH_NODE / HV_EPD 网络低于网络类线宽（最小 0.15 mm）。这是 IC 焊盘处的
   常规收颈，规则不会覆盖到窄段以外。
2. **USB 差分对**：`USB_DP/DN`、`USB_DP/DN_CONN` 全程 L1 微带（0.24 mm），耦合间距因
   0.1 mm 栅格量化为 0.26–0.40 mm，与 0.18 mm 目标略有差异。
3. **GND** 不布独立走线，靠四层铺铜 + 135 个缝合过孔连通（含每个 GND 焊盘附近的过孔）。

---

## 6. 本轮（电源铜皮）的取舍

为了给 `3V3_MAIN` / `SYS` 的全部焊盘预约出线通道（它们排在最后布，出线一旦被封就
再也接不上），布线器对这两个网络的**每个焊盘**都预订了短桩。代价是 `BAT_BUS` 与
`EPD_3V3` 这两条功率网络在本轮被挤出（它们的焊盘未做同样预约）。

修复方式已明确：把 `BAT_BUS`、`EPD_3V3` 加入 `tools/route.py` 的 `STUB_ALL_NETS`
（一行改动）后重跑布线即可。重跑一次约 15–20 分钟（`3V3_MAIN` 34 个焊盘的迷宫搜索
耗时最长）。

---

## 5. 下一步（依 `..._Post_First_Routing_Next_Steps.md`）

已完成 MD 的 ① ② ③（DRC 清零）与 §1（统计统一、网络类调整）。剩余顺序：

1. 按 MD §6 顺序人工收尾 §3.1 的网络：
   `TPS_L2` → `SYS` → `USB DP/DN` 重整 → `EPD_VGH` → `CHG_REGN`
   → `CHG_CE/INT_N/OTG/DSEL` → `I2C_SCL/SDA` → `TF_SCLK/TF_CS_N`
   → `TYPEC_INT_N` → 最后 `3V3_MAIN`（电源分配思路，见 MD §15）。
2. `Refill All Zones` → 确认 69/69 connected、`Unconnected = 0`。
3. 打开 `track_not_centered_on_via`、`tuning_profile_track_geometries` 后重跑 DRC。
4. GND unconnected 若仍存在：先判断是否为孤立铜岛（无 GND Pad/Via），孤岛删除，
   不要直接 Exclude。
5. Return Path Review（MD §19）：USB 下方 In1 连续、Switching 节点短小无跨层、
   SPI/I²C 换层处附近有合理 GND 缝合。
6. 板厂按实际叠层复算 USB 90 Ω（当前 0.24 mm 线宽，目标间距 0.18 mm）。
7. 生成 Gerber / 钻孔 / 贴片坐标（命名见 `PCB_LAYOUT_NOTES.md` §13）。
