# PCB 重建状态（2026-09-22，清空后重做的第一轮）

## 已完成

| 阶段 | 内容 | 证据 |
|---|---|---|
| 板框 | 55 × 84 mm，四角 R2（原生圆弧） | `pcb outline-round 0,0,2165.354,3307.087 --radius 78.7402` |
| 叠层 | 4 层，L15(Inner1) = **内电层(GND plane)** | `pcb stackup set --layers 4 --plane 15` |
| 安装孔 | H1–H4 Ø2.2 NPTH @ (3,3)/(52,3)/(3,81)/(52,81) mm | `pcb mount-holes --dia 86.61 --inset 123.11`（inset 必须比 3.000mm 多 5 mil，因为板框 bbox 含线宽） |
| 禁布区 | 11 个：天线铜禁布(L1/L2/L16) + 天线两侧器件禁布 + J3 卡座 5 处 + 右侧按钮列 | `tools/pcb_rebuild.py --stage mech` |
| 器件 | 106 个全部落板并赋网（焊盘网络与 model.json **0 处不一致**） | `tools/pcb_rebuild.py --stage place` |
| 固定件 | J1–J5、SW1–SW5 用**上一轮接受位姿**并锁定 | `pcb lock --ids …`（verified:true） |
| 布局优化 | auto-place+自写合法化实测更差（crossing 611→815），故**回退到上一轮优化位姿** | `tools/pcb_restore_ref.py`（复位 81 件） |
| **① 电源优先** | 24 个电源网用迷宫布线器布通，主干 31.5 mil(0.8 mm)/分支 ≤19.69 mil(0.5 mm)，间距错 **0**，然后 `track-lock` 全部锁定 | `tools/route_power.py`；`work/route-power-report3.json` |
| **② USB 差分** | 4 条 USB 网已布（DP_CONN 由迷宫布线器、其余由 Freerouting） | 见下“未完成” |
| **③ 其余信号** | Freerouting（`tools/router.cmd`，9 分钟）把未布线从 283 降到 36（其内部计分） | `work/board-fr.dsn` → `work/board.ses` |
| GND | Inner1 内电层 + L1/L2 GND 铺铜（`pour-fit --inset 30`）+ `pour-rebuild` | `pcb pour-list` = 2 |
| 丝印 | 105 个位号对齐（`silk-align`）+ 12 条接口/板名标注（USB-C / EPD-24P / TF-CARD / BAT1 / BAT2 / KEY1-3 / RESET / BOOT / ESP32-S3 4L 55x84 / v2.0） | `pcb silk-add` |
| 保存 | `pcb save` + `doc reload` + 复读 | 本轮结束状态已落盘 |

## 第二轮（GND 缝合 + USB 尝试）结果与**回退建议**

本轮做了两件事：

1. **GND 缝合**（`tools/stitch_gnd.py`）：给 12 个未连 GND 焊盘就近配过孔或伸进铺铜的短桩
   → GND 连接错 **12 → 6**（剩 U5_10/U5_11/U4_6/D7_1 + 2 个孤立对象）。
   代价：短桩只校验了端点净空，沿途没校验 → 引入若干间距错（下一轮改成整段校验）。
2. **USB 重布尝试**：先尝试耦合对（R→U1 段被 D3 焊盘挡住，-2.0 mil），
   后改为单独重布 USB_DP_CONN（成功但**把 DP 路径从 3618 缩到 2760 mil**，
   USB0 skew 反而从 389 变成 **1248 mil**），蛇形补偿在紧走廊里只能加到 +87 mil。

**因此当前 DRC 比 Freerouting 导入后更差**（98 vs 67）。建议下一轮**先回退 USB**：

```
easyeda pcb rip-up --net USB_DP_CONN,USB_DN_CONN,USB_DP,USB_DN --doc PCB1
# 重新导出 DSN → 预处理 → tools/router.cmd → import-autoroute（约 9 分钟）
# 这会回到 67 违规的状态（连接 20 / 间距 44 / 差分 2 / netlist 1）
```

然后再按下面的“USB 正确做法”重做差分对。

## 第三轮（USB 前端重摆 + 耦合重布）——**差分对目标达成**

1. **R9/R10 并排**：R9 → (610,2400) rot90、R10 → (650,2400) rot90（原来相距 177 mil）。
   复读焊盘：R9.1/R10.1（CONN 侧）落在南侧 **y=2370.3**，R9.2/R10.2（U1 侧）在 **y=2429.7**
   —— 正好形成两条平行车道，且 **D3 自动让开通道**（原来就是它把 R→U1 段挡死的）。
2. **耦合重布**（`tools/pair_router.py`，宽 9.449 / 间距 7.087 mil = 文档 §7.4 的 0.24/0.18 mm，
   加 `--pad-clearance 6` 提高余量）：
   - USB0：J1(A6/A7) → R9.1/R10.1，底层 4987.8 mil，最差余量 **+5.95 / +4.58 mil**；
   - USB1：R9.2/R10.2 → U1.14/U1.13，底层 443.8 mil，最差余量 **+10.80 / +5.20 mil**；
   - **skew：USB0 = 0.56 mil、USB1 = 0.00 mil**（要求 ≤10 mil）→
     `Differential Pair Error` **6 → 0** ✓
3. GND 缝合保持：GND 连接错 6。

**代价 / 待修**：`apply_edits` 落盘时平台拒了一部分段（88/94、116/202），
所以 USB 四条网各留下 4–6 个连接错（共 20 条）。当前 DRC：**92** =
59 Clearance（其中 **43 条是安装孔 Hole/Hole**）+ 32 Connection + 1 Netlist，
但 **Differential Pair 已为 0**。

**第四轮（补连接错）进展与诊断**：

* 落盘失败的根因找到了：耦合计划里有大量**退化/重复小段**（USB0 10 段、USB1 **86 段**）。
  写了 `tools/apply_plan_batch.py`（过滤 <1 mil 与重复段 + 分批 25 段落盘）后
  **USB0 84/84、USB1 116/116 全部落盘成功**（此前 88/94、116/202）。
  → 现在 `Diff Pair` skew：USB0 **0.56 mil**、USB1 **0.00 mil**（重跑 pair_router 后），
  落盘后实测 USB0 52 mil / USB1 0 mil。
* **剩下的连接错是"端点扇出"问题，不是落盘问题**：耦合对走**中心线 ±(w+s)/2 = ±8.27 mil**，
  所以在端点上两条走线只相距 **16.5 mil**，而实际焊盘间距是
  J1 **19.7**、R9/R10 **40**、U1 **50** mil → 走线落在焊盘之间。
  用 `tools/close_net.py`（就近收口，含 L 形绕行）只能救回 3 个（R9.2/R10.2/U1.13），
  其余 7 个（J1.B6/B7、R9.1/R10.1、D2.1/D3.1、U1.14）**无论直连还是 L 形都会压到
  "另一条腿"的焊盘**（J1 的 A6/A7 交叉焊盘、R9/R10 相邻焊盘）→ 必须**真正的扇出**。
* **正确做法（下一轮）**：把整条对拆成三段
  ① 端点扇出：用迷宫布线器（`tools/sys_router.py`）从焊盘走到"车道起点"（离焊盘 ~80–120 mil，
     车道间距已按 16.5 mil 定好）；
  ② 中间耦合段：`tools/pair_router.py` 走两段车道起点之间（skew 天然 0）；
  ③ 端点扇入：同 ① 到另一端焊盘。
  这样端点用迷宫布线器处理交叉焊盘（它会绕行并保证净空），中间用耦合对保证等长与阻抗。

## 第五轮（三段式收口尝试）——落盘问题彻底解决，端点扇出仍未闭合

* **落盘问题彻底解决**：写了 `tools/apply_plan_batch.py`（过滤 <1 mil 与重复段 + 每 25 段一批
  + 批间 save）。耦合计划里 USB0 有 10 段、USB1 有 **86 段**退化/重复段，过滤后
  **USB0 84/84、USB1 116/116 全部落盘**（此前 88/94、116/202）。
  当前板上有完整耦合对：**`pcb report` → USB1 skew 0.000 mil、USB0 52.0 mil**。
* **计划本身是连续链**（每网只有 4 个自由端点、无近端对），所以落盘失败纯粹是过滤问题，
  不是几何问题 —— 这条经验对以后所有"计划一次性 apply"都适用。
* **仍未闭合的是端点扇出**：DRC 的连接错覆盖
  `J1_B6/B7`、`R9_1/R10_1`、`D2_1/D3_1`、`U1_14/R9_2/R10_2/U1_13` 等，
  以及若干 **图元 id（`e####`）**。原因是耦合对按 ±8.27 mil 生成（对内 16.5 mil），
  而实际焊盘间距是 J1 19.7 / R9,R10 40 / U1 50 mil，端点必然落在焊盘之间；
  我试过盘内过孔收口、L 形绕行、亚 mil 桥接，都是"补铜"而不能让平台把这些段
  识别成同一棵树。
* **正确做法（下一轮，写进计划器而不是事后补）**：把每条 USB 走线生成成三段
  ① 焊盘 → 车道起点（用 `tools/sys_router.py` 迷宫布线，它能绕开 J1 的交叉焊盘）；
  ② 车道起点 → 车道终点（`tools/pair_router.py` 耦合对，skew 天然 0）；
  ③ 车道终点 → 焊盘（同 ①）。
  两端扇出的长度差用 `tools/serpentine.py` 补（它们很短，需要预先留出净空）。
* 当前 DRC（本轮回退到最干净的确定性状态）：**96–98** =
  64 Clearance + 30~31 Connection + 1~2 Differential Pair + 1 Netlist。
  （Clearance 里 43 条是安装孔 Hole/Hole；Connection 里 6 条 GND + 4 条 I2C/CHG。）

## 第六轮（三段式实测结论）

保留已落盘的耦合中段、只让迷宫布线器补两端扇出，实测**不成立**：

* `sys_router` 对 `USB_DP_CONN` **整网重布了 69 mm**（23 段 + 5 过孔），而不是沿既有同网
  车道补两端 —— 也就是说它的 A* 并不把"已有同网铜"当作已连通，等于又叠了一条并行线；
* `USB_DN_CONN` 仍然 **0 段**（J1 口袋 + 端点问题依旧）；
* `USB_DP` / `USB_DN` 补了 11.8 mm / 1.5 mm 的小段 ✓。

净效果：Connection **30 → 22**（USB 部分明显减少），但 Clearance 64 → 69、
Diff Pair 2，总 DRC **94**。

**结论**：扇出必须在**计划器内部**生成，不能事后补。具体做法（下一轮直接实现）：

1. 在 `pair_router.py` 里增加"端点扇出"：从焊盘出发先走一段 **45° 斜跳**（避开同排相邻焊盘），
   再接回耦合带的两条车道；扇出段按单线处理（不进耦合带的等长约束）；
2. 扇出长度用同一条轴线的平行偏移保证两腿相等，或在扇出末端做一次小蛇形
   （需要预留 ≥2×ampl×teeth 的净空）；
3. J1 侧直接从 A6/A7 两条焊盘出发（间距 19.7 mil ≈ 耦合带 16.5 mil，误差 3.2 mil 可由
   20 mil 的斜跳吸收），B6/B7 用现有的 L2 逃逸线（`work/usb-escape2.json`）并联即可；
4. R9/R10 与 U1 侧的扇出同理（间距 40 / 50 mil → 需要 ~30 mil 的斜跳）。

## 未完成（下一轮从这里继续）

当前 DRC：**98** = 79 Clearance + 12 Connection + 6 Differential Pair + 1 Netlist
（其中 USB_DN_CONN 一条网占 23 条间距错，来自 Freerouting 的绕行；回退 USB 后会消失）。

### USB 正确做法（已验证过的配方，下一轮直接用）

1. **重摆 USB 前端**（用户已授权优化非固定件位置）：
   - R9/R10 改成**并排、轴向沿通道**（轴线间距 ~40 mil，两组焊盘分别朝 J1 与 U1）；
   - D2/D3 移出 R→U1 通道，做成**旁路抽头**（D2 焊盘朝西、D3 转 180° 焊盘朝东），
     信号脚落在配对车道上、GND 脚朝外。
2. `tools/pair_router.py` 重布两对（轴线 + 平行偏移，**skew 恒为 0**）：
   - USB0：J1(A6/A7) → R9.1/R10.1；USB1：R9.2/R10.2 → U1.14/U1.13；
   - width/gap = 0.24/0.18 mm（9.449/7.087 mil，文档 §7.4）；
   - 已探明可走：USB0 底层 3812 mil、USB1 205 mil。
3. 需要更长时用 `tools/serpentine.py --search --need <mil>`，但要先确认目标段
   **有 ≥2×ampl×teeth 的净空**（本板只有 USB0 的 740 mil 段能放，且只放得下 +87 mil）。

1. **20 条 Connection Error**：GND ×12（铺铜没连到这些焊盘，需要 **缝合过孔/热焊盘**：
   `pcb via-stitch --net GND` 或 `pcb power-planes`）、I2C_SCL ×2、USB_DP_CONN ×2、
   CHG_STAT ×2、CHG_DSEL ×2（这几条用迷宫布线器单独补）。
2. **44 条 Clearance Error**：
   - **40 条是 Hole/Hole**，全部与四个安装孔铣槽相关（很可能是平台对槽多边形的重复判定，
     需先确认是否真违规；若是，按 `pcb check` 的槽区净空处理）。
   - 2 条 GND 走线 0.48/0.51 mm（差一点点，应被铺铜吸收/删残桩）。
   - 其余是我锁定的电源网与孔的净空（USB_VBUS_RAW 差 0.09 mm 等）——修法：把这些
     走线分段微调（`pcb track-delete` + `pcb track`），**不要解锁**。
3. **2 条 Differential Pair Error + USB 等长**：Freerouting 把 USB 当普通两网布线，
   对内间距超 10 mil、skew USB0 389 mil / USB1 111 mil。
   下一轮用 `tools/pair_router.py`（轴线+平行偏移，skew 恒为 0）重布：
   - USB0：J1(A6/A7) → R9.1/R10.1，起止中线 `944.85,264` → `581.5,2495.5`；
   - USB1：R9.2/R10.2 → U1.14/U1.13，`611.15,2495.5` → `738.2,2343.3`；
   - 已探明可走：USB0 底层 3812 mil、USB1 205 mil；但 **R9/R10（相距 177 mil）与
     D2/D3（压在对内通道上）需要重摆**成“两条平行车道”，否则末端无法耦合。
   - width/gap 用文档 §7.4 的 0.24/0.18 mm（9.449/7.087 mil）。
4. **1 条 Netlist Error**：原理图/PCB 绑定提示（`pcb drc` 的 hint：
   `easyeda board rebind --schematic <uuid> --pcb <uuid>`），不是布线缺陷。
5. 天线禁布区在 L15 内电层上的挖空尚未做（需要“先删 L15 区域 → 转 signal → 铺凹形 GND
   → rebuild → 再加 region”的配方，见 HANDOFF 第十一轮），投板前必须补。

## 工具与产物

* 重建：`tools/pcb_rebuild.py`（mech/place）、`tools/pcb_restore_ref.py`、`tools/make_obstacles.py`
* 布线：`tools/route_power.py`、`tools/route_usb.py`、`tools/sys_router.py`（已修：通孔焊盘/槽区/禁布区进障碍模型）、`tools/pair_router.py`、`tools/apply_edits.py`
* 校验：`tools/drc_summary.py`（保存→重载→DRC→分类）、`tools/drc_rules_dump.py`
* 快照：`work/pcb-rebuild-status.png`
* 参照位姿：`work/ref-last-layout.json`（清空前抓取的上轮 106 器件位姿）

## 两个关键教训（本轮踩到）

1. `geom.dump()` **必须给路径**才会写 `work/geom.json`；否则布线器读到的是上一轮的旧快照，
   于是“看不到新铜”并直接穿过它（表现为大量 dist=0 的跨网间距错）。
2. daemon 的读缓存是**陈旧**的：每写一批铜后必须 `pcb save` + `doc reload` 再 dump，
   否则模型和真板不一致。

---

# 第七轮（2026-09-23 续做）：去重过孔 + GND/信号收口，DRC 94 → 33

> 用户要求“按 `_REBUILD/_STATUS.md` 继续”。该路径不存在，实际状态文件就是本文件
> （`work/PCB_REBUILD_STATUS.md`）。本轮从这里“未完成（下一轮从这里继续）”继续。

## 起点与终点

| 项 | 起点（本轮开始） | 终点（本轮结束） |
|---|---|---|
| DRC 总数 | **94** = 62 Clearance + 30 Connection + 1 DiffPair + 1 Netlist | **33** = 16 Clearance + 14 Connection + 2 DiffPair + 1 Netlist |
| 走线 / 过孔 | 1413 / 203 | **1475 / 170** |
| 零铜网络 | 0 | **0**（CHG_STAT/CHG_DSEL 有铜但未连通，见下） |
| 丝印/板框/叠层/器件 | — | 未改动（55×84 R2、4 层、106 器件、L15=内电层） |

本轮所有改动都来自参数化数据 + typed CLI，每步 `save` → `doc reload` → 复读；
铜箔改动前均有快照（`work/copper-before-cleanup.json`、`work/geom-final.json`）。

## 逐项

### ① 去掉 43 个重复过孔（−43 Clearance，纯白捡）

`pcb via-list` 里有 **43 对完全重合的过孔**（同坐标/同网络/同孔径），DRC 因此报 43 条
`Hole to Hole`。这是 `via-stitch` 类动作重复落盘留下的**记账残留**，不是几何问题。
新工具 `tools/dedupe_vias.py`（按 0.001 mil 归并，删多余副本）：
**203 → 160 过孔，DRC 94 → 51**。

### ② 清掉切网的 GND 残桩（−8 Clearance，+4 Connection，净 −4）

上一轮 `stitch_gnd.py` 留下的 6 条 GND 短桩**横穿异网**（如 C10_2→过孔那条横穿两条
CHG_REGN；U5 上下排之间那条横穿 U5_4 的 USB_VBUS_DET），另有 2 条完全悬空。全部删除
（`pcb track-delete --ids`，用真 `primitiveId`），代价是被它们"假装"连着的 8 个 GND 点
暴露出来（见 ⑤）。

### ③ 内层天线禁布（部分完成，未获 DFM 认可）

天线铜禁布原本只有 L1/L2/L16 三层。本轮补了 **L15（内电层）同尺寸 region**
（`pcb region create --rect 629.82,3070.77,1535.53,3307.19 --layer 15
--rule no-fills --rule no-wires --rule no-pours --name antenna-L15 --locked`，
id `47d16c8773088179`）。`pcb check` 仍报 `antennaKeepout=1`（它期望的是 HANDOFF 第十一轮
那套"转 signal → 铺凹形 GND → rebuild → 再转 PLANE"配方），**投板前必须按那条配方复核**。

### ④ 新工具：`tools/patch_gnd.py`（迷宫收口）+ `tools/revert_plan.py`（按几何回滚）

`patch_gnd.py`：
1. 把某个网络的全部 track/via/pad 按"铜是否相接"聚成簇（`shapes_touch`：track-track 同层相交、
   pad 用**矩形**距离而不是外接圆——外接圆会把 QFN 细长焊盘错连一圈）；
2. 取最大簇为该网络的"主干"；
3. 用与 DRC 同源的规则矩阵（Track↔Track 4.016、Track↔Pad/Via 5.984、Via 孔↔孔 11.8、
   板边 11.8 mil）做 A* 把孤立焊盘接到主干；
4. 输出 track/via 计划交 `apply_plan_batch.py` 落盘（仍会过滤退化段）。

`--net/--pads/--radius` 可复用到任何网络；**每次只规划一个网络、落盘后再规划下一个**，
否则两个计划会互相穿插（本轮 I2C_SCL × CHG_STAT 就这么撞过一次，11 条新间距错，已回滚重来）。

### ⑤ 连上的：I2C_SCL、USB 前端扇出、5 个 GND 孤立簇

| 网络 | 收口结果 | 证据 |
|---|---|---|
| I2C_SCL | U4_7（4 mil 短接）+ U2_5（269 mil，1 过孔）→ **2 条连接错消失** | `work/patch-i2c.json` |
| USB_DP_CONN | J1.B6 / R9.1 / D2.1 三条**扇出**（61/76/79 mil，各 1 过孔）→ 该网连接错清零 | `work/patch-usbdp-conn.json` |
| USB_DN_CONN | R10.1 / D3.1 扇出（243/189 mil）→ 只剩 J1_B7 一条 | `work/patch-usbdn-conn2.json` |
| USB_DP | R9.2（308 mil）+ U1.14（50 mil）→ 该网连接错清零 | `work/patch-usbdp.json` |
| USB_DN | R10.2（612 mil）→ 只剩 U1_13 | `work/patch-usbdn.json` |
| GND | C10.2 / C28.2 / C30.2 / D1.2 接到主干（C30.2 绕 606 mil）| `work/gnd-patch2.json` |

## ⚠️ 本轮最重要的发现：U5 的 GND 焊盘是**引擎判据问题**，不是布线问题

`U5_3 / U5_5 / U5_10 / U5_11` 四条 GND 网络一直被 DRC 判 `Connection Error`，
但几何上**全都能追到 J3.14（GND）**：

```
U5.10 ─(1707.9,1029.5)-(1707.9,1293.7)─┐
U5.3  ─(1676.4,970.5)-(1676.4,949.5)─(1669.8,949.5)-(1669.8,721.9)─(1717.3,674.5)─(1717.3,643.7)─J3.14
                                        └ 与上面那条在 (1707.9,1293.7) 汇合 ─(1729.3,1293.7)─…
```

本轮做的排除实验（都不成立）：

| 假设 | 实验 | 结果 |
|---|---|---|
| 走线比焊盘宽（10 mil 走线压 7.9 mil 焊盘）导致判不连 | 删掉 10 mil 走线，换 5 mil 走线从焊盘中心出去 | 仍报断开 |
| 没打过孔到内层 | 在主干节点 (1707.9,1293.7) 加 GND 过孔 | 仍报断开，且 +4 条间距错 |
| 焊盘被异网铜压住 | `pcb drc` 全量按对象过滤 | U5 焊盘只有 Connection Error，无任何间距错 |
| 铜是老的、net 绑定失效 | 删掉重画（5 mil 新线段） | 仍报断开 |

同类现象在 v1.1/v2.0 第六轮也出现过，当时的结论就是"有铜但连通性判据不认，怀疑引擎
连通性缓存"。**结论：这 4 个点不要再用布线去补**，应走 §六的 rebind/重新导入路线。
同类但**真实**的孤立点还是少数：C6_2（`patch_gnd` 报 no path，走廊实测不通）。

## 六、下一轮从这里继续（按优先级）

1. **先修 Board 绑定（很可能是上面所有幽灵错的根因）**
   `easyeda board current` 显示 `Board1` 绑的是 **`Schematic1` (cc227a1a0e59e2a5)`**，
   而本工程当前原理图是 **P1 (7b1ca0ce011868e2) / P2 (f568f62f67600e3d)** ——
   绑的是一个**不存在的幽灵页**，这正是 `Netlist Error` 的来源，也极可能就是
   U5/U1 那类"有铜却报未连"的来源：
   ```
   easyeda board rebind --name Board1 --schematic <P1 uuid> --pcb 0f5d4fe671bd05f9
   ```
   *风险*：rebind 会**删除并重建 Board**；若它顺带触发网表重导入，PCB 器件/网络可能被改写。
   本轮**没有执行**（用户未授权这个破坏性动作）。执行前务必先 `pcb dump`/`copper_backup save`
   存整板快照，并在 rebind 后立刻 `pcb list` + `pcb drc` 复核。
2. **USB 前端仍要按第三～六轮的配方重做**（旧的 A 排逃逸线 `e4799/e4800` 还压着
   `USB_DP_CONN` 的过孔和 `USB_CC1` 过孔，共 4 条 Track↔Via 间距错；
   `e4939/e4819` 两条 L2 斜线还穿过 **J1_3 屏蔽焊盘/孔**，4 条错）。
   本轮只做了"端点扇出"（把断口接上），**对内间距/等长没有重做**：
   - `pcb report` 现在 USB0 skew **310 mil**、USB1 skew **270 mil**（都在 10 mil 容差外，
     DRC 报 2 条 Differential Pair Error）；
   - 也就是说本轮是**用等长换连通**（连接错 −6，skew +520 mil）。若不接受，可
     `revert_plan.py work/patch-usbdp.json work/patch-usbdn.json` 回到 20 Connection / 1 DiffPair。
   - 正确做法仍是：rip-up `USB_DP_CONN/USB_DN_CONN/USB_DP/USB_DN` → 重摆 R9/R10、D2/D3 →
     `pair_router.py` 走耦合中段 + `patch_gnd.py` 走两端扇出 + `serpentine.py` 补等长；
     另外 J1 的 4 个 USB 焊盘在 x 915.3/935.0/954.7/974.4（19.7 mil 间距），
     A 排/B 排是交叉的，扇出必须**斜跳**而不是直出。
3. **CHG_STAT / CHG_DSEL 是 0 铜网络**（U2_4→R15_1、U2_24→R20_2，跨度约 1900 mil）。
   `patch_gnd` 实测**布不通**（CHG_STAT 在 I2C_SCL 落盘后 no path）。
   正解是**把 R15/R20 这两颗 3V3 上拉搬到 U2 脚边**（用户已授权非固定件可动），
   再各连 30–80 mil 的短线；顺带要重接它们原来的 3V3_MAIN 支路。
4. **剩余 16 条 Clearance** 里真正要改的是：
   - 2 条 `(USB_VBUS_RAW) e2668/e2669` 对 `Slot Region e28e57`（**差 0.88 mil**，微调即可）；
   - 4 条 `e4799/e4800` 对 USB 过孔（属 USB 前端重做）；
   - 4 条 `e4819/e4939` 对 J1_3 屏蔽焊盘（属 USB 前端重做）；
   - 1 条 `I2C_SDA e2531` 对 `USB_DN_CONN e426`（3.3 mil）；
   - 2 条 `Hole to Hole`：`USB_DP_CONN e425/e441`、`USB_DP e447/e448` ——
     本轮的扇出过孔与旧过孔孔距 <11.8 mil，**把新过孔挪开 12 mil 即可**
     （`patch_gnd.py` 已补上孔↔孔规则，重跑扇出不会再产生）。
5. C6_2（GND）在现在的铜密度下走廊不通；可按 §1 修好绑定后再试，
   或把它当作"内层 GND 平面必须真正接上"的验证点。
6. 内层天线禁布按 HANDOFF 第十一轮配方复核（§③）。

## 七、本轮新增/更新的工具

| 文件 | 用途 |
|---|---|
| `tools/dedupe_vias.py` | 删除完全重合的重复过孔（重复落盘残留） |
| `tools/patch_gnd.py` | 通用"孤立焊盘→主干"迷宫收口器（簇分析 + A* + 孔↔孔规则），`--net/--pads/--radius/--analyze` |
| `tools/revert_plan.py` | 按几何（层/网/端点/宽度）回滚一个 plan 落下的铜 |

## 八、本轮踩的坑（很重要）

1. `pcb pour-fit --net GND --layer L` 默认 `--replace`，会**先删同网已有铺铜**——
   连做 L1/L2 时后一个会把前一个删掉，必须 `--replace=false`（或反序）。
2. `pcb track` / `pcb via` 偶发**静默丢弃**（返回 ok 但板上没有）：写完必须
   `pcb track-list` 复核。本轮一次"5 mil 实验线"就是这么凭空消失的，导致一次错误的实验结论。
3. 两个 plan **必须串行**：先规划 A → 落盘 A → 重新 dump → 再规划 B。
   并行规划出的 A/B 会互相穿插（本轮 I2C_SCL×CHG_STAT 撞了 11 条）。
4. `geom.dump(path)` 之后**不要立刻**用它规划下一步——daemon 读缓存可能还没跟上；
   `save` + `doc reload` 再 dump。
5. `pcb drc` 的 `position`/`clearance` 单位不是 mm：位置是 **mil/10**，`clearance` 是
   **mil/10**（例：`clearance 0.40157` = 4.016 mil）。
