# esp32s3-board-v2.0 交接说明 (2026-09-21)

## 任务
按 `PCB_INTERFACE_POSITIONS.md`（需求文档实际路径；prompt 里的 `PCB\_INTERFACE\_POSITIONS.md` 不存在）
在 EasyEDA Pro 工程 esp32s3-board-v2.0 完成 ESP32-S3 系统板：选型 -> 原理图 -> 布局 -> 布线 ->
铺铜 -> 丝印 -> DRC -> 保存。

## 当前阻塞（需用户先处理）
EasyEDA 连接器窗口已掉线，daemon 报告 `windows: []`：

    easyeda health --project esp32s3-board-v2.0   -> "windows": []
    easyeda sch connect ... --doc P1              -> "--doc guard: no connected window for project"

easyeda.exe (PID 31240, 2026-09-20 23:58 启动) 仍在运行，但 webview 与 daemon 的 WebSocket 已断开，
60 秒内未重连。旁证：`~/.easyeda-agent/audit/2026-09-20.jsonl` 已涨到 1.6 GB。

### 恢复步骤（必须在 GUI 完成）
1. 完全退出 EasyEDA，重新打开，打开工程 esp32s3-board-v2.0。
2. 确认 easyeda-agent 连接器已启用、允许外部交互。
3. 门禁：`easyeda update --check --exit-code`（要 READY/exit 0）与
   `easyeda health --project esp32s3-board-v2.0`（windows 非空）。
4. 重连后先 `easyeda sch save --doc P1` / `--doc P2`，因为画面上的改动可能未落盘。
5. 可顺手清理 1.6 GB 的 audit 日志（不参与工程数据）。

## 已完成
### 选型 design/parts-map.json（全部来自 live `easyeda lib search`，43 个器件身份）
关键件与 v1.1 BOM 的 MPN 精确一致：

| 位号 | MPN | LCSC | 封装 |
|---|---|---|---|
| U1 | ESP32-S3-WROOM-1-N16R8 | C2913202 | WIRELM-SMD_ESP32-S3-WROOM-1 |
| U2 | BQ25895RTWT | C2861263 | WQFN-24 4x4 EP2.7 |
| U3 | TPS63070RNMT | C964639 | VQFN-HR-15 |
| U4 | MAX17048G+T10 | C2682616 | TDFN-8 2x2 |
| U5 | TUSB320LIRWBR | C2836598 | X2QFN-12 |
| U6 | TPS22918DBVR | C131941 | SOT-23-6 |
| J1 | USB4105-GF-A-120 (GCT USB4105 系列 16P 卧式) | C5184243 | USB-C-SMD_MC-311D |
| J2 | X05B20U24T | C437036 | FPC-SMD_X05B20U24T |
| J3 | DM3AT-SF-PEJM5 | C114218 | SD-SMD_DM3AT-SF-PEJM5 |
| J4/J5 | 532610271 | C189700 | CONN-SMD_532610271 |
| SW1-SW5 | B3U-1000P | C231329 | KEY-SMD_B3U-1000PM |
| L1/L2/L3 | NR5040-1.0uH / MWSA0402S-1R2MT / FHD4020S-470MT | C49581188/C408333/C843300 | - |
| NTC1 | NTCS0603E3103FLT | C142556 | R0603 |
| Q1 | SI1304BDL | C7419947 | SOT-323 |

### 连通性模型 design/model.json
106 器件（110 减 4 个 PCB-only 安装孔）/ 70 网络 / 325 条不重复 pin-net 关系，
由 v1.1 终版 `esp32-board-v1.1_final_drc_20260920.kicad_pcb` 焊盘网表提取，
与需求文档 7.2 GPIO 表逐条核对一致。

### 原理图（P1/P2 已改为 A3 图框）
- P1 = 电源/USB/充电/EPD 升压 64 件 8 模块；P2 = MCU/EPD 接口/TF/按键 42 件 5 模块。
- 布局经 `sch autolayout --engine template`，`sch layout-lint` 0 重叠/0 过近/0 出框。
- 功能分区已 `sch zones set` 认领；`sch zone-draw` 待补。
- P1 连接：`sch check` 无短路（0 multiNetWires / 0 net mismatch / 0 danglingWires），
  175/190 stub 已下；15 个未接引脚：C11:2 C12:1 C16:1 C17:1 C17:2 F2:2 L1:1 NTC1:1
  R22:2 R19:1 U2:20 U2:19 U2:11 U2:8 U4:5。
- P2 连接：未开始（137 条）。

## 现场踩过的坑（下次绕开）
1. `net_label` 在该连接器构建上必然失败（"Netlabel create did not settle within 7000ms"）。
   `power` / `ground` / `net_port_bi` 正常。信号网用 net_port_bi 或 power。
2. `sch autoconnect` dry-run 与实跑不一致：dry-run 常报全部可接，实跑按实时状态重规划会大面积失败。
   做法：dry-run 取 selected.direction/offset，再用 tools/exec_connect_plan.py 原样回放；
   长引出 `--offset-min 45 --offset-max 320` 明显提高成功率。
3. 失败的 connect 会留下零长导线，之后整页所有写都被几何守卫拒绝。每批写完先删
   `x0==x1 && y0==y1` 的导线（tools/finish_conn.py 已内置）。
4. 短引出会让 net port 符号互压 -> 两个网被合并（实测 CHG_SW/CHG_TS/CHG_OTG/FG_ALRT_N
   被并进 BAT_BUS/GND）。判据要用 `sch check` 的 floatingPins / multiNetWires / net mismatch。
5. `sch connectivity` 在本构建返回空网表，`sch list --include-pins` 的 net 也可能全空；
   唯一可靠的现网判据是 `sch check --json`。
6. `sch clear --preserve-parts` 必须同时保留图框；换图框分两步（clear -> 删旧图框 -> 放新图框）。
   `sch autolayout --apply` 要求页面零连通性。

## 下一步（连接器恢复后）
1. 用 tools/finish_conn.py 收口 P1 剩余 15 个引脚（用 sch check 判真值，失败回滚）。
2. 给 13 个显式 NC 引脚打 NC：J1:A8,B8 / J4:3,4 / J5:3,4 / U2:2,3,12 / U3:6 / U5:9 / U6:4,5。
3. P2 137 条连接：dry-run 取计划 -> exec_connect_plan.py 回放 -> verify/finish 收口。
4. 图签填写 + `sch group create` 后 `sch zone-draw --mode partition`。
5. 门禁：layout-lint --strict / check / bridge-check / drc -> save -> doc reload -> 重读。
6. PCB：import-changes -> outline-round 55x84 R2 -> 原点 -> H1-H4 Ø2.2 NPTH
   (mount-holes --dia 86.6 --inset 118.1) -> region：天线禁布 X16-39/Y0-6 全层、
   J3 卡座禁布 x5、右侧 X49-51 禁器件 -> 固定件按需求文档第 4 节坐标摆放并锁定 ->
   其余器件避开禁布区 -> 4 层 stackup(In1=GND) -> drc-rules-set / net-class / diff-pair USB ->
   布线(route-critical -> route-short -> 手工补) -> GND 铺铜 -> 丝印 -> DRC -> 保存 -> 重开复核。

## 工程产物
| 文件 | 内容 |
|---|---|
| design/model.json | 106 器件 + 70 网络 + 焊盘网表（权威连通性源） |
| design/parts-map.json | 43 个器件身份（libraryUuid/uuid/lcsc/mpn/封装） |
| design/pin-map.json | 源引脚号 -> EasyEDA 器件引脚号映射（J1/J3/J4/J5/U2 有合并脚） |
| design/sch-place-A/B.json | 器件放置 playbook（easyeda sch apply） |
| design/sch-layout-A/B.json | 模块布局 spec + zone 认领 |
| design/sch-connect-A/B.json | 目标连接 spec |
| design/sch-nc-final.json | 显式 NC 引脚表 |
| design/plan-A*.json | 已校验的 A 页连接计划（含 direction/offset） |
| tools/*.py | 提取/建模/选型/布局/连接/校验全套脚本 |

## PCB 状态（2026-09-21 续做）

原理图连接在单页 A3 上做不满 190 条：该连接器构建在多标记页面上会持续退化
（netlabel 创建失败 / 几何守卫拒绝 / 连接器无响应 / 残留重标），换页、清页重做、
加长引出、加节流都只能推进一部分。因此 PCB 改走 `pcb add-component`
（直接落封装 + 逐焊盘赋网），不再依赖原理图网表可解析。

### 已完成并回读

| 项 | 结果 |
|---|---|
| 板框 | 55.000 × 84.000 mm，四角 R2.000，4 段原生圆弧，locked（`pcb outline-get`） |
| 叠层 | 4 层，Inner1 = 内电层（GND） |
| 安装孔 | H1–H4 Ø2.2 mm，实测中心 (118.11,3188.98)/(2047.24,3188.98)/(118.11,118.11)/(2047.24,118.11) mil = 需求 (3,3)/(52,3)/(3,81)/(52,81) mm |
| 禁布区 | 天线铜禁布（全宽带）+ 天线区左右器件禁布 + J3 卡座 5 处 + 右侧 X49–51 器件禁布，共 8 个 region |
| 器件 | 106 个全部落板，焊盘网络来自 model.json；70 个网络 |
| 机械对齐 | J1/J2/J3/J4/J5/SW3/SW4/SW5 按需求焊盘坐标二次校正（J1 信号焊盘行对齐到 77.650 mm，J4/J5 Pin1 对齐 X=8.400 mm） |
| 布线 | `pcb route-short --corner 45` 画 327 条线 |
| 电源 | `pcb power-planes`：Inner1 GND 内电层 + 72 个缝合过孔；顶层/底层 GND 铺铜 |
| 丝印 | `pcb silk-align` + 9 条接口/板名丝印 |
| 保存 | `pcb save` + `doc reload` 已执行 |

### 未完成 / 已知问题

最终 DRC（save + reload 后）：**190 条违规** =
137 Connection Error（布线未完成 + 13 个 GND 焊盘没有缝合过孔落点）
+ 52 Clearance Error（route-short 的 L 型线压焊盘/槽区）+ 1 Netlist Error。
该连接器没有可用的自动布线器（`pcb_Document.autoRouting` 未定义，本机无 Freerouting/JRE），
route-short 只是短跳启发式，不做换层过孔与推挤，所以稠密板无法收敛。

原理图：P1/P2 器件布局与分区齐全，连接仍为 partial；见上文。

## 重做布局 / 布线（2026-09-21 第二轮，按用户要求）

用户要求：U1、J2（24P FPC）、J4/J5（双电池）、SW3/SW4/SW5（右侧按键）、J1（USB-C）、
H1–H4、J3（TF 卡座）位置保持不动，**其余器件全部按原理图重新布局并重新布线**，
不再沿用 v1.1 的位置。

做法：
1. `pcb rip-up` + `pcb pour-delete`：清掉旧布线与外层铺铜（保留板框/孔/禁布区/内电层）。
2. `tools/pcb_relayout.py`：锁定 9 个固定件，把 6 颗主芯片按功能分区放到新锚点
   （U2 充电器在电池口与 USB-C 之间、U3 在板中供 3V3、U4 紧邻电池、U5 靠 USB-C、
   U6/Q1 靠 FPC 端）。
3. `pcb auto-place --anchor U6,Q1 --multi-gap 0`：按原理图把 91 个小件贴到各自芯片的
   电源/信号脚旁（去耦贴电源脚、上拉贴信号脚）——这一步取代了 v1.1 的摆位。
4. `pcb place-constrained` 做初轮合法化。

踩到的坑（重要）：**`pcb place-constrained` 不遵守 `pcb lock`**，它把 J2 吸到板顶、把 J3
吸到板右并转了 90°，U1 也被挪了 190mil。已用 `tools/pcb_ids.py` 回读并按已知正确位姿复原，
且不再调用 place-constrained。另外 `tools/pcb_align.py` 的焊盘坐标回读曾在 stale 状态下
给出错误值并误移连接器，现改为以 bbox 复核。

5. `tools/pcb_legalize.py`：自写的合法化器——**只搬未锁定件**，螺旋搜索空位，避开板边与
   机械禁布区。搬了 29 件，0 失败。
6. 重新布线：`route-short --corner 45 --max-len 1400` 画 291 条线 → `power-planes`
   （Inner1 GND 内电层 + 缝合孔）→ 顶层/底层 GND 铺铜 → `pour-rebuild` → save → reload。

结果：

| 项 | 数值 |
|---|---|
| 固定件位姿 | J1(944.882,156.400,r0) / J2(128.914,1654.608,r270) / J3(1571.858,353.348,r0) / J4(273.609,866.148,r90) / J5(273.609,472.447,r90) / U1(1082.677,2805.118,r0) / SW3–5(2080.727, 2716.6/1653.6/590.6, r-90)，已按 bbox 复核 |
| 布局 | layout-lint：**0 跨网短路 / 0 出框 / 0 过近**，1 条 J1↔J1 自重叠（USB-C 封装本体与焊盘的自身包络，非真实重叠）；禁布区违规 0 |
| 布线 | 291 条短跳线 + GND 内电层 + 缝合过孔 + 上下层 GND 铺铜 |
| DRC（save+reload 后） | **205** = 171 Connection / 33 Clearance / 1 Netlist |
| 未布线网络 | 70 网中仍有约 28 网零铜 |

未收敛原因同前：该构建没有可用自动布线器（`pcb_Document.autoRouting` 未定义，本机无
Freerouting/JRE），`route-short` 只做同层短跳、不换层、不推挤。要布通需要外部布线器：

```
easyeda pcb autoroute --router '<your-router-cmd> {in} {out}'   # DSN 出、SES 回
```

## 第三轮：PCB 清空后从零重建（2026-09-21）

用户把 PCB 清空，并要求：**MCU 天线不得伸出板边**、**SW1/SW2 相邻且附近有 BOOT/RESET 丝印**，
从布局一路做到 DRC 与保存。

清空后的实际状态：无板框、无器件、2 层、无区域 —— 全部重建。

一键重建脚本 `tools/pcb_build.py`（读 `design/pcb-plan.json` + `design/model.json`）：
板框 55×84 R2 → 4 层（Inner1 内电层）→ H1–H4 Ø2.2mm（距中线上 3.000mm）→ 9 个禁布区
（天线铜禁布 + 天线区左右器件禁布 + J3 卡座 5 处 + 右列器件禁布）→ 106 器件带焊盘网。

固定件按需求文档放置，其余按原理图功能分区：U2 充电器在电池口与 USB-C 之间、U3 buck-boost
居中供 3V3、U4 紧贴电池、U5 靠 USB-C、U6/Q1 靠 FPC 端；`pcb auto-place` 把 89 个小件贴到
各自芯片脚边；`tools/pcb_legalize.py` 只搬未锁定件做合法化（40 + 6 件）。

本轮处理的两个要求：
1. **天线不再伸出板**：U1 锚点从 y=2805 下移到 y=2618，封装 bbox 变为
   y 2238.39–3268.58，板顶 3307.09 —— 天线整体在板内，上沿留 38.5 mil（≈0.98mm）。
   天线禁布带 16–39 / 0–6mm 保留铜禁布；器件禁布只放在模块两侧（16–17.9 / 37.1–39），
   不再与 U1 轮廓相交。
2. **SW1/SW2 相邻 + BOOT/RESET 丝印**：SW1(920,2145)、SW2(1135,2145) 并排放在模块正下方，
   间距 45 mil；丝印 `RESET` 贴 SW1 左侧、`BOOT` 贴 SW2 右侧（字号 26mil）。
   注意：丝印层没有删除接口，标签用 `pcb silk-set --ids <id> --ref SWx --align left/right` 定位。

结果：布局 `0 短路 / 0 重叠 / 0 出框 / 0 过近 / 0 禁布区违规`；
布线 290 条短跳线 + Inner1 GND 内电层 + 缝合过孔 + 上下层 GND 铺铜；
`pcb save` → `doc reload`（PCB 文档 uuid 变为 e3d1b4716a09db63）。
**DRC 144 条未清零**（123 Connection / 20 Clearance / 1 Netlist），70 网中 23 网零铜。

## 第四轮：安装 Freerouting 并跑完整自动布线（2026-09-21）

### 安装（全部在本仓库 tools 下，无需管理员）

| 组件 | 路径 | 说明 |
|---|---|---|
| Freerouting 2.4.1 | `tools/freerouting/freerouting-2.4.1.jar` | 官方 release |
| Temurin JRE 25 | `tools/jre25/jdk-25.0.4.1+1-jre/` | **2.4.1 编译目标是 Java 25**（class 69）；Java 21 会报 UnsupportedClassVersionError |
| 路由包装脚本 | `tools/router.cmd` | `router.cmd <in.dsn> <out.ses>`，headless（`-Djava.awt.headless=true`），`-mp 20 -mt 4` |
| DSN 预处理 | `tools/dsn_prep.py` | 把 Inner1 标成电源层；可选注入安装孔禁布区 |

用法（easyeda-agent 的 autoroute 约定 `{in}` / `{out}`）：

```
easyeda pcb autoroute --router "C:\Code\epdf-hardware\tools\router.cmd {in} {out}"
```

### 关键经验（踩坑记录）

1. **EasyEDA 导出的 DSN 把已有走线标成 `(type protect)`** —— 布线器不能改动它们。
   所以必须**先在干净板上布线**（先 `pcb rip-up` + 删铺铜再导出 DSN），
   否则布线器只能在既有铜的缝隙里塞线，结果很差（实测：干净板 265 未布 → 剩 2；
   带保护线的板 → 剩 148）。
2. DSN 里 `(layer Inner1 (type signal))`，与需求"L2 = 完整 GND"冲突；
   `dsn_prep.py` 把它改成 `(type power)`，布线器就不会在内层走线，改为用缝合孔接到平面。
3. 布线器不知道安装孔是**铣孔**（DSN 里只是小焊盘），会贴着孔走线；
   `dsn_prep.py` 可注入 16 条禁布（4 孔 ×4 层）。
4. 单次布线 3~10 分钟；`-mp` 越大越慢，20 次已足够。

### 结果

板子：**1395 条走线 + 214 个过孔 + Inner1 GND 内电层 + 上下层 GND 铺铜**，
`pcb save` → `doc reload` 已执行。

DRC：**144 → 17**（12 Clearance / 4 Connection / 1 Netlist）。相比手工/启发式布线是质变。

剩余 17 条的具体内容与下一步：

- **4 条 Connection**：`I2C_SDA` / `I2C_SCL` 没布通。布线器 fanout 阶段日志是
  `279 SMD pins fanouted, 3 not routed` —— 即 U5（TUSB320）的 I2C 两个脚在 USB-C 附近
  太拥挤、引不出来。要解决得先给 U5 周围腾地方（挪 U5 或重排它旁边的去耦/ESD）。
  我试过手工在 Inner2/Bottom 拉干线，反而制造 198 条新违规 —— 这条路不划算。
- **12 条 Clearance**：都是"差一点点"（4.8–6.3 mil，要求 6 mil）的走线贴焊盘/过孔，
  外加 1 条 GND 走线进入了天线禁布区、几条贴着安装孔铣槽。属于自动化后的收尾打磨，
  需要逐条 rip-up 重走。
- **1 条 Netlist Error**：PCB 网表是直接按 `design/model.json` 赋的，原理图侧仍是
  partial，所以两边对不上；不是布线缺陷。

## 第五轮：用 Freerouting 迭代到达成（2026-09-21）

### 迭代过程（每轮 ≈6 分钟：清板 → 导 DSN → 布线 → 导入 → 铺铜 → DRC）

| 轮 | U5 位置 | 布线器结果 | 导入后 DRC |
|---|---|---|---|
| board2 | 原位 rot0（贴 J3） | 2 未布 / 8 违规 | 17（12 clr / 4 conn） |
| board5 | 原位 rot90 | 2 未布 / 8 违规 | 14（9 clr / 4 conn） |
| board6 | (1466,769) | 3 未布 / 8 违规 | 18（11 clr / 6 conn） |
| **board7** | **(1580,760)** | **1 未布 / 8 违规** | **20（17 clr / 2 conn）** |

### 关键发现：U5（TUSB320）原位物理上无解

U5 原本放在 J1（USB-C）与 J3（microSD）之间：到 J3 的封装边界只有 **7 mil**。
X2QFN-12 有一整列 4 个脚正对 J3，焊盘间距只有 15.7 mil —— 这一列**无法出线**
（右侧被 J3 挡死、左侧是自己的本体、上下被相邻焊盘挡死）。
这就是 Freerouting 始终剩 2 条 I2C 的原因（fanout 日志：`3 SMD pins not routed`）。

旋转 90° 只把 4 个受困脚从 I2C 换成了别的；必须**挪出** J1/J3 夹缝。
用 `tools/check_spot.py` 按"四边净空"打分选出 **(1580,760)**：左 311 / 右 537 /
下 53 / 上 430 mil，四边都能出线，于是布线器只剩 1 条未布。

> ⚠️ **这是相对需求文档的一处布局改动**：TUSB320 从 USB-C 旁移到了板中央右侧，
> CC1/CC2/VBUS_DET 到 J1 的走线变长（约 600 mil）。功能不受影响（CC 是低速检测线），
> 但如果你希望它紧贴 USB-C，需要改 J3 的相对位置或换更小的 CC 控制器封装。

### 最终板况

- 布局：固定件全部就位（J1/J2/J3/J4/J5/SW3-5/U1 已逐个按 bbox 复核）；
  U1 天线在板内（bbox maxY 3268.6 < 板顶 3307.1）；SW1/SW2 相邻 + BOOT/RESET 丝印。
- 布线：**70 个网络全部有铜**（`pcb report` 的 zero-copper 网络数 = 0），
  265 条连接完成 264 条；Inner1 GND 内电层 + 缝合孔 + 上下层 GND 铺铜。
- DRC：**20 条** = 17 Clearance + 2 Connection + 1 Netlist。

剩余 20 条明细与下一步：

- **2 Connection**：`SPI_MOSI` 的 J2:14（FPC 侧）那一腿没连上。J2 在最左边、
  最近的点在 x≈960，跨度 900 mil，布线器放弃了。补法是手工拉一条（Bottom 层）或
  把 J2 的 fanout 顺序调整后重跑。
- **17 Clearance**：全是"差一点点"——1.9～8.1 mil（要求 6 mil）的 GND 铜贴着
  U2_9/U2_10/F1_2/J1_B4-A9/U5_6 等焊盘；另有一组 `USB_VBUS_RAW` 走线离**安装孔铣槽**
  6.1～8.1 mil（要求 11.8 mil）。这类收尾需要逐条 rip-up 重走；
  注意 `pcb track-delete --ids` 用 DRC 报的 `eXXXX` 名字**删不掉**（返回 ok:false），
  要用 `pcb track-list` 拿真实 `primitiveId`。
- **1 Netlist Error**：PCB 网表按 `design/model.json` 直接赋，原理图侧仍 partial，两边对不上；
  不是布线缺陷。

## 第六轮：收尾（清间距 + 补最后一条连接）2026-09-21

### 做到的事

1. **补上最后一条连接（SPI_MOSI，J2:14）**。根因是相邻引脚 SPI_SCLK 的 fanout 过孔
   (126.4,1664) 正好压在 J2:14 的出线道上（它的顶边离焊盘行只有 0.2mil）。
   处理：把该过孔下移到 (126.4,1650) 并重接它两侧的走线（Top 短跳 + Bottom 45°），
   再从 J2:14 经 `Top → via → Bottom x=230 垂直 → y=2700 水平 → x=1030 垂直 → via → Top`
   接回既有铜。**结果：Connection Error 0**（265 条连接全部布通）。
2. **清理 GND 间距**：用 `tools/fix_gnd_clearance.py` 按 DRC 的 `objs` 真 id 删除
   贴焊盘的 GND 残桩/过孔（GND 有 Inner1 内电层兜底）。DRC 27 → 16。

### 当前最终状态

| 项 | 数值 |
|---|---|
| 走线 / 过孔 | 1391 / 214 |
| 网络 | 70 个，**零铜网络 0 个** |
| DRC | **16** = 13 Clearance + 2 Connection + 1 Netlist |

剩余 16 条：

- **2 Connection**：U5_3 / U5_5（都是 GND）。有趣的是 DRC 报它们断开，但
  `pcb track-list --net GND` 里能看到一条 GND 走线正好终止在 (1556.4,730.5) ——
  即 U5:3 焊盘中心。数据上像是"有铜但连通性判据不认"，怀疑与连接器/引擎的
  连通性缓存有关，建议重开后复查（`pcb save` + `doc reload` 已做过，现象不变）。
- **13 Clearance**：5 条 `USB_VBUS_RAW` 走线离**安装孔铣槽** 6.1~8.1mil（要求 11.8）；
  4 条 `Track to Via`（SPI_MOSI/SCLK 在 FPC fanout 区贴到 EPD_* 的过孔）；
  3 条 `Hole to Track`；1 条 Track to Track。

### 我试过但更差的做法（记下来免得重试）

- 给 U5:3/U5:5 加"dog-bone"过孔缝合：单独加一条就让 DRC 从 16 涨到 24
  （多出 10 条 Track to Via + 5 条 Hole to Track），两条一起加涨到 40。已回滚。
- 手工在 Inner2/Bottom 拉长干线绕过拥堵区：一次制造 198 条违规，已回滚。
- 结论：**剩余收尾应该在 GUI 里对着 DRC 逐条推，或者再跑一轮 Freerouting**；
  用脚本盲改的收益已经是负的了。

## 第七轮：U5 挪到开阔角落 + 布线器一次收敛（2026-09-21）

按用户要求，把 U5 挪到"四边都更宽"的位置：用 `tools/check_spot.py` 全板扫描，
选中 **(1700, 1000) mil = (43.18, 58.61) mm**，四边净空 L428 / R417 / B293 / T249 mil
（全板最优），rot 0。然后清板 → 导出 DSN → `dsn_prep.py` → Freerouting。

**布线器一次收敛：`0 unrouted`（265 条连接全部布通）。**

之后的收尾：

| 步骤 | DRC |
|---|---|
| 导入 board9.ses + power-planes + 铺铜 | 20（19 clr / **0 conn** / 1 netlist） |
| `tools/fix_gnd_clearance.py` 删贴焊盘的 GND 残桩（8 线 + 2 孔） | **8**（7 clr / 0 conn / 1 netlist） |
| 修 J1 屏蔽层走线：y=245.5 下移到 y=252（避开 J1 两个 Ø0.65 NPTH 定位柱孔） | **6**（5 clr / 0 conn / 1 netlist） |

期间试过把 USB_VBUS_RAW 链左移、把 I2C_SDA 过孔下移，两次都制造了更多违规，已回滚。

### 最终状态

| 项 | 数值 |
|---|---|
| 走线 / 过孔 | 1411 / 213 |
| 网络 | 70 个，零铜网络 0 |
| **DRC** | **6** = 4 Clearance + 1 Clearance(Track-Via) + 1 Netlist |

剩余 6 条：

- **4 × Slot Region to Track**：`USB_VBUS_RAW` 走线离 **J1 自己的两个 Ø0.65mm NPTH 定位柱孔**
  6.1~7.3 mil（规则要 11.8）。这段铜在连接器本体正下方，x 1014~1034 一带被 J1 信号焊盘
  占满，往左会压 CC2 焊盘、往右会压定位孔——需要把 J1 的 fanout 整体重排才能彻底解决。
- **1 × Track to Via**：`TYPEC_INT_N` 走线离 `I2C_SDA` 过孔 5.2 mil（要 6）。
  U5 的 INT 焊盘离该过孔只有 22 mil，试过挪过孔反而多出 4 条违规，已回滚。
- **1 × Netlist Error**：PCB 网表按 `design/model.json` 直接赋，原理图侧仍是 partial，
  两边对不上；不是布线缺陷。

### 布局偏离汇总（相对需求文档）

1. **TUSB320（U5）从 USB-C 旁移到 (43.18, 58.61) mm** —— 原位被 J1/J3 夹住（到 J3 只有 7mil），
   一整列引脚无法出线；这是布线能收敛的前提。CC1/CC2/VBUS_DET 走线因此变长约 600mil（低速线）。
2. **J1 上移 14 mil（0.36mm）** —— 让它自己的屏蔽脚不再压在板边；本体外凸量由 1.23mm 变为 0.87mm
   （需求写 1.005mm）。

## 第八轮：用户手改后的分析与铺铜修复（2026-09-21）

### 用户手改的内容（按对象 id 比对确认）

1. 替换了 4 段 `USB_VBUS_RAW` 走线（旧 id dc5d6a4e / f53ed09c / db7d1c42 / 29d58503 已不存在）
   —— 原来那 4 条离 J1 的两个 Ø0.65mm NPTH 定位柱孔只有 6.1~7.3 mil，换掉后 4 条 Slot 违规清零。
2. 把 `I2C_SDA` 过孔从 (1745.8, 968.1) 右移到 **(1749.2, 968.1)**，并重接它的 Top/Inner2 走线
   —— 距 TYPEC_INT_N 走线 22.2 → 25.6 mil，`Track to Via` 违规清零。

结果：**DRC 从 6 降到 1**（只剩 PCb↔原理图网表不一致那条，属预期）。

### 发现的两处铺铜回归（已修复）

1. **Inner1 无铜且层类型是 SIGNAL** —— 违反需求"L2 In1.Cu 完整 GND"。
2. **顶层 GND 铺铜缺失** —— 只剩 Bottom GND + Inner2 EPD_VDD。

根因：`pcb pour-fit` 的 `--replace` **默认 true 且是"按网络"清除（不分层）**。
我之前的 `pour-fit --layer 1` → `pour-fit --layer 2` 序列里，第二次把第一次建的 layer-1 铺铜清掉了，
第一次又把 `power-planes` 建在 Inner1 的 GND 铺铜清掉了。

### 修复过程（每一步都回读）

1. `pour-fit --net GND --layer 1` → 顶层 GND ✓（同时清掉了 layer 2 的，印证 --replace 行为）
2. `pour-fit --net GND --layer 2 --replace=false` → 底层 GND ✓
3. `power-planes` → Inner1 GND 铺铜 ✓，但带来 8 条间距违规（2 个缝合孔 + 4 段 GND 短线压焊盘/禁布区）
4. `fix_gnd_clearance.py` 删掉那 6 个越距对象 → DRC 回到 1
5. **层类型翻转**：`stackup set --plane 15` 在有铺铜时被平台**拒绝**
   （回执 `modified:[{layer:15,ok:false}]`）；**先删掉该层铺铜再翻** → `ok:true, type:PLANE` 成功。
   最后 `pour-fit --layer 15` 补回平面铺铜。

### 最终确认（数据为准）

| 项 | 状态 |
|---|---|
| 叠层 | L1 Top SIGNAL+GND铺铜 / **L2(Inner1) PLANE, use_net GND** / L3(Inner2) SIGNAL+EPD_VDD / L4 Bottom SIGNAL+GND铺铜 |
| 内电层证据 | `pcb export-dsn` 输出 `(layer Inner1 (type power) (use_net GND))` |
| DRC | **1**（仅 Netlist Error：PCB 网表按 model.json 直接赋，原理图侧仍 partial） |
| 布局 | 106 器件，0 短路/重叠/出框/过近 |
| 走线 / 过孔 | 1413 / 213；70 网络全部有铜 |
| 固定件 | J1/J2/J3/J4/J5/SW3-5/U1 位姿与需求一致 |

遗留项（非 DRC 错误）：layer 16 上有 **2 个 EPD_VDD 铺铜对象**（同网同层重叠，电气无害，可清理）；
DFM 另有 9 条 via-in-pad（GND 过孔压在 SW1/2、J4/5 焊盘）、无基准点等情况。

## 第九轮：电源主干加宽（2026-09-21）

### 问题

需求写"大电流主干 BAT / SYS / USB_VBUS 主干 **0.80 mm**；Net Class POWER 默认 0.50 mm"，
但实测全板 1332 条走线**全是 10 mil（0.254 mm）**——Freerouting 导入时按 DSN 默认宽度统一画的。
按 IPC-2221（1oz 外层、10°C 温升）10 mil ≈ **0.91 A**，而 USB/电池/SYS 是按 2 A 设计的。
参考设计 v1.1 是用**顶层局部电源铺铜**（SYS ×3、3V3_MAIN ×2）解决这个问题的。

### 做法（逐段加宽 + DRC 反馈回退）

写了两条工具：

- `tools/widen_nets.py`：导出目标网的全部走线段 → 删除 → 按新线宽重建。
- `tools/revert_wide.py`：跑 DRC，把**出现在违规对象里**的加宽段退回原线宽，循环直到干净。

三轮：20 mil → 31.5 mil（针对已加宽的）→ 14 mil（针对剩下的细线）。
每轮都是"全量尝试 → DRC → 只回退不合格的"。

另外 `tools/clear_gnd_blockers.py` 试过"删掉与主干并行的冗余 GND 走线给主干让位"
（GND 有内电层+铺铜兜底），删了 9 条，但那 7 段仍放不下，已回退（GND 删除保留，无副作用）。

### 最终线宽分布

| 网络 | 10 mil | 14 mil | 20 mil (0.5mm) | 31.5 mil (0.8mm) | 长度加权均值 | 等效载流 |
|---|---|---|---|---|---|---|
| SYS | 27.8mm | 5.4mm | 29.4mm | 1.0mm | 15.3 mil | ~1.2 A |
| BAT_BUS | 1.0mm | 4.0mm | 7.6mm | **12.3mm** | 24.3 mil | ~1.7 A |
| USB_VBUS_PROT | 2.7mm | – | 10.4mm | – | 17.9 mil | ~1.35 A |

（改造前三条网全部 10 mil ≈ 0.91 A。）

### 试过但不成立的两条路

1. **一次全加宽到 20 mil** → 55 条间距违规（板子密度太高，布线器只留了 6 mil 余量）。
2. **让 Freerouting 按网宽重布 SYS**：在 DSN 里注入 `(rule (width W) (net SYS))` 并撤掉 SYS 重布。
   0.8mm 跑 30 分钟未收敛、0.5mm 跑 10 分钟未收敛（正常 3 分钟）——单网在已布通的密集板上
   重布不收敛，已终止。

### 踩坑与回滚

`pcb rip-up --net SYS` **会连同该网络的过孔一起删除**，而我的备份只存了走线（`track-list`），
恢复后出现 4 条断线。补法：找出"两层端点重合"的位置（跨层接点）补回 2 个过孔
(957.3,683.6) 和 (1005.1,1023.9)，DRC 恢复为 1。
**教训：备份网络时必须同时存 `via-list`。**

### 最终状态

| 项 | 值 |
|---|---|
| DRC | **1**（仅网表不一致） |
| 走线 / 过孔 | 1403 / 213 |
| 布局 | 106 器件，0 短路/重叠/出框/过近 |
| 固定件 | 未动 |

**未达标项**：SYS 仍有 27.8mm 卡在 0.25mm（约 0.91A），是全板电源路径的瓶颈；
这些段被邻近铜（信号线，不能删）挤住，需要重新规划那段布局或改走内层才能加宽。

## 第十轮：电源主干"彻底"加宽（2026-09-21 晚）

### 目标
把 SYS（以及早前一并要求的 BAT_BUS / USB_VBUS_PROT）的**整条**主干加宽到
0.5~0.8 mm。第九轮用"逐段加宽 + DRC 回退"只能到 1.2 A 等效，剩下的段被
C13 焊盘（10.9 mil）和 R34（14.7 mil）硬阻塞，且不再能靠挪件解决。

### 关键突破：自研净空感知的迷宫布线器
不再依赖 Freerouting（整板重布两次退化到 29~32 条未布）。新工具
`tools/sys_router.py` 只在**现有板**上重布一条网：

1. **精确障碍模型**。用 `pcb drc-rules` 的 Spacing/Safe Spacing/copperThickness1oz
   真值建每层距离场：Track↔Track 4.016 mil、Track↔焊盘/过孔 5.984 mil、
   Track↔板框 11.80 mil。（Track↔铺铜 10 mil 不建模——铺铜会自动让位。）
2. **校准** `tools/validate_model.py`：拿板上 1403 条既有走线回算最小净空，
   直方图峰值正好落在 6.00 mil，与 DRC 从未报 clearance 互相印证。
3. **A\***：4 mil 栅格 × 3 个信号层（Top/Bottom/Inner2），8 邻域 + 换层过孔，
   代价 = 长度 + 贴墙惩罚 + 换层惩罚；多源多目标支持"已布好的树接下一颗焊盘"。
4. **逐级放松**：先按 31.5 mil 找路，找不到才 28/25/22/20/18…，并依次放松
   栅格安全裕度 3.0→2.0→1.2 mil。找到后再做 string-pulling 平滑 + 逐段按
   精确净空"再抬宽"（`tools/polish_widths.py`）。
5. **离线验收**：`tools/verify_plan.py`（精确几何，非栅格）算每段/每过孔的真实
   余量，必须全为正；`tools/check_net.py` 几何建图确认该网所有焊盘连通。
   只有两步都过才 `tools/apply_plan.py` 写回编辑器。

### 两个必须记住的坑
1. **焊盘 `rotation` 不能再施加一次**。`pcb dump` 给的 `width/height` 已经是
   世界坐标轴对齐尺寸；再按 `rotation` 旋转会让 0.5 mm 间距的 QFN 相邻焊盘重叠，
   模型与 DRC 立刻对不上。判据就是第 2 步的直方图。
2. **内电层（PLANE）的铺铜不会随 `pour-rebuild` 刷新**，新加过孔后 DRC 会报
   `Plane Zone to Via` / `Hole to Plane Zone`。修复配方（已复现两次）：

       stackup set --signal 15            # 翻成信号层（原平面铺铜会被丢掉）
       pcb pour --layer 15 --net GND --points <板框内缩 15mil>
       pour-rebuild                       # 此时 pour-list 可见、DRC 干净
       pour-delete --ids <上一步的 id>
       stackup set --plane 15             # 该层无铺铜时才允许翻回（回执 modified ok:true）
       pcb pour --layer 15 --net GND --points ...
       pour-rebuild → save → doc reload → pcb drc

   注意 `modified:[{layer:15,ok:false}]` 表示翻层被拒（`ok:true` 只代表 HTTP 层成功）。
   另外 `doc reload` 之后 PLANE 层的铺铜对 `pcb.pour.list` 不可见（平台 #110），
   此时以 `pcb drc` 的连接错误数作为唯一裁判。

### 结果（`work/geom.json` 实测，2026-09-21 20:05）

| 网络 | 总长 | 0.8 mm | 0.71 | 0.635 | 0.559 | 0.508 | <0.5 mm |
|---|---|---|---|---|---|---|---|
| **SYS** | 51.4 mm | **41.0** | 2.6 | 3.2 | 4.2 | 0.3 | **0** |
| **BAT_BUS** | 21.9 mm | **17.7** | 1.9 | 0.5 | 0.6 | 1.1 | 0.1（U4 焊盘 4 mil 引出） |
| **USB_VBUS_PROT** | 9.0 mm | **6.7** | – | 2.2 | – | – | 0.1（U2 焊盘 4 mil 引出） |

- SYS：改造前 27.8 mm 卡在 0.254 mm，改造后**最小 0.508 mm、80% 为 0.80 mm**，
  IPC-2221（1oz、10 ℃）等效约 **2.0 A**（最窄段 1.46 A）。
- 三条网合计线长从 63.7+25.0+13.1 = 101.8 mm 降到 82.3 mm（更直）。
- 旧 SYS 的 2 个过孔被原样复用（其余信号线是**绕着它们**布的，袋口只有过孔大小，
  栅格搜索永远找不到，所以布线器把原过孔当固定锚点）。

### 未动的东西（已逐项比对）
- 非目标网络的铜箔与备份**逐条一致**：1330 条走线、209 个过孔，0 增 0 减。
- 固定件坐标、板框、安装孔、禁布区、丝印、器件数（106）全部未动。
- 顶层/底层 GND 铺铜 + Inner1 内电层 + 216 个过孔缝合保留。

### 最终验收

| 项 | 值 |
|---|---|
| `pcb drc` | **1 条**（仅 Netlist Error——原理图连接不完整导致，非几何问题） |
| `pcb check` (DFM) | ERROR=0，273 WARN（丝印压焊盘 / GND 过孔在焊盘 / GND 线宽 / 缺 Mark 点等既有项） |
| 走线 / 过孔 | 1382 / 216 |
| 内电层 | Inner1 = PLANE（完整 GND，已按上面配方刷新） |
| 连通自检 | SYS/BAT_BUS/USB_VBUS_PROT/EPD_VDD/3V3_MAIN/BAT1_RAW/BAT2_RAW 均 1 个连通域 |
| `pcb save` + `doc reload` | 已执行，回读一致 |

### 回滚点
- `work/copper-before-sys-widen.json`：本轮开始前（1403 走线 + 213 过孔）。
- `work/copper-after-sys-widen.json`：SYS 完成后、动 BAT_BUS 之前。
- `design/copper-backup-pre-reroute.json`：第九轮之前的更早回滚点。

### 仍未达标 / 已知遗留（非本轮引入）
1. `Netlist Error`：原理图为 partial，PCB 侧网表与原理图不一致；PCB 自身的
   焊盘-网络绑定来自 `design/model.json`，与需求 7.2 已对齐。
2. GND 有 266 条走线细于 19.7 mil——但 GND 由 Inner1 内电层 + 上下铺铜承担，
   走线只是缝合/局部连接，不影响载流。
3. `via-in-pad` 10 处（GND 过孔压在 SW1-5 / J4/J5 / J3 / U1 焊盘上）、
   `fiducial-missing`、`antennaKeepout`（天线区禁止铺铜未覆盖 Bottom/Inner）、
   J4↔J5 插头护套间距 10.00 mm < 10.45 mm——均为既有 DFM 建议项。
4. Inner2 上原有的 2 个 EPD_VDD 叠层铺铜在第九轮的 `rip-up` 中一并丢失
   （第九轮交接已把它列为"可清理"项）。EPD_VDD 由走线连通（自检通过），
   若需要恢复铺铜可 `pcb pour-fit --net EPD_VDD --layer 16`，但要先确认
   不会与 Inner2 的 236 条信号冲突。

---

## 第十一轮：P0-2 天线禁布区补四层 + P0-3 USB 差分（2026-09-21 夜）

### P0-2 天线禁布区（需求 §6：X16–39、上沿 0–6 mm，四层禁走线/过孔/焊盘/铜皮）

**发现的问题**

1. 禁布区对象只建在 **L1**；L2 的 GND 铺铜、L15 的内电层、L16 的 2 条走线全都压在禁区内。
2. L16 越界的两条走线：`3V3_MAIN (950.8,3110.6)→(1564.1,3110.6)`、
   `KEY2_N (958.2,3074.6)→(786.1,2902.5)` 等 4 段。

**做法**

1. 用 `work/antenna-fix.json`（7 段新走线 + 删 4 段）把 3V3_MAIN 与 KEY2_N 移到
   y≤3055 的走廊，先过 `verify_edits.py` 精确净空（最小余量 3.38 mil）再写回。
2. L2 / L16 各补一个 `no-wires+no-pours+no-fills` 禁区；L15 补
   `no-inner-electrical+no-wires+no-pours+no-fills`。

**关键教训：内电层（PLANE）是"整层负片"，无法挖空**

平台把 layer15 的类型 PLANE 渲染成**整层铺满**，任何"在 PLANE 层上铺一个凹形铜"的
操作都不会改变结果。三处坑：

* `pcb.pour.list` / `eda.pcb_PrimitivePour.getAll()` 都**看不到** PLANE 层的铜；
  真正的对象是文档源码里的 `LAYER_FILL[15]`，`fillStyle:"PLANE"`，
  路径是整块板（`[10.1,78.74,"L",...2155.25,3296.99...]`）。
* 该层有 `no-inner-electrical` 禁布区时 `stackup set --plane 15` **必被拒**
  （`modified:[{layer:15,ok:false}]`）；反过来，只要该层已有任何铺铜/禁布区，
  `stackup set --signal 15` 也会被拒。必须先删掉该层的 region 才能翻层。
* 由此得到**正确顺序**（已复现）：

      ① 删 layer15 的 region → stackup set --signal 15      （ok:true 才算成功）
      ② pcb pour --layer 15 --net GND --points <凹形多边形>   （把天线区挖掉）
      ③ pour-rebuild → save → doc reload
      ④ pcb region create --layer 15 --rule no-inner-electrical \
             --rule no-wires --rule no-pours --rule no-fills

  注意第 ④ 步之后**不要再翻层**（会被拒）。凹形多边形：

      [[15,15],[2150.35,15],[2150.35,3292.09],[1535.53,3292.09],
       [1535.53,3070.77],[629.82,3070.77],[629.82,3292.09],[15,3292.09]]

**验证（Gerber 为准，不再靠 CAD 自述）**

`tools/gerber_fetch.py` 把连接器的 Gerber ZIP（base64）落盘解包，
`tools/gerber_rect_check.py` 逐层判定"矩形内有无铜"（含 G36/G37 填充区域的多边形点测）。
坐标约定：Excellon/Gerber 为 mm、隐含 5 位小数、原点在板左下
（实测 maxX=54.517 mm / maxY=83.517 mm ≈ 板 55×84）。

| 层 | 天线禁区内铜箔 |
|---|---|
| Gerber_TopLayer.GTL | **0** |
| Gerber_BottomLayer.GBL | **0** |
| Gerber_InnerLayer1.G1 | **0**（改造前：整层 PlaneZone + 1 条 draw） |
| Gerber_InnerLayer2.G2 | **0** |

对照：Inner1 在板中部（25–30 mm × 40–45 mm）仍有 18 处铜 → GND 铺铜未被破坏。
`pcb check` 的 `antennaKeepout` 也从 1 → **0**，`viaCrossesPlane` 1 → **0**。

### P0-3 USB 差分对与等长

**改造前**（对比参考设计 v1.1，用 `tools/kicad_net_len.py` 测得）

| | v1.1 参考 | v2.0 改造前 | v2.0 改造后 |
|---|---|---|---|
| USB_DP_CONN / USB_DN_CONN | 60.79 / 64.19 mm（偏 **3.40**） | 61.67 / 67.00（偏 **5.33**） | 67.05 / 67.00（偏 **0.053**） |
| USB_DP / USB_DN | 2.72 / 2.72（偏 0.00） | 8.97 / 8.21（偏 **0.76**） | 8.97 / 8.97（偏 **0.001**） |

**做法**

1. `pcb diff-pair create --name USB0/USB1`（USB0=DP_CONN/DN_CONN，USB1=DP/DN）。
2. 写 90 Ω 差分规则：`tools/set_diff_rules.py` 生成补丁、
   `pcb drc-rules-set --from` 写入 ——
   **线宽 0.2286 mm (9 mil)、对内间距 0.127 mm (5 mil)、长度容差 0.254 mm (10 mil)**。
   依据参考设计叠层（F.Cu − 0.195 mm prepreg、εr 4.2 − In1.Cu、1 oz）：
   单端微带 ≈65 Ω，`Zdiff = 2·Z0·(1−0.48·e^(−0.96·s/h))` ≈ **91 Ω**。
   *注：EasyEDA 叠层里只有默认模板（Dielectric1 = 59.449 mil FR4），介质参数不可写；
   JLC 下单时需按上述 h/εr 复核阻抗条。*
3. 等长用 `tools/serpentine.py`（45° 手风琴，逐段过精确净空再写回）：
   * USB_DP_CONN +106 mil ×2（竖直段顶部与中段，余量 3.83 mil）
   * USB_DN +29.8 mil（L16 斜段，余量 7.21 mil）
   只有这两处能放下 45° 蛇形：DP_CONN 的竖直段其余部分被
   `GND via (673.4,1586.1)`、`EPD_VGL via (689.0,1507.3)` 卡住；
   斜线段（428 mil）放不下 +212 mil 的 512 mil 脚印。
   （45° 折角脚印 ≈ 2.415 × 需要增加的长度，这是本板能放下 212 mil 的唯一原因就是
   竖直段有 1600 mil 长。）

**验收**：`pcb report` 的 `differentialPairs` 给出 USB0 skew = **2.10 mil**、
USB1 = **0.05 mil**（单位是 mil，不是 mm！），均在 10 mil 容差内；
两条网各自 1 个连通域；DRC 仍为 1（仅 Netlist Error）。

### 尚未做到 / 后续可选

* 差分对**没有真正耦合**：D2/D3（ESD）与 R9/R10（串阻）在 y 方向相距 **177 mil**，
  J1 侧 DP/DN 焊盘也只能在 0.5 mm 间距上走。要得到全程等距 5 mil 的耦合对，
  必须把 D2/D3、R9/R10 重新摆放成并排（属于 P0-3 之外的前端重布局），
  届时可用"中线 + 双向偏移"的耦合布线器（本仓库尚未实现）。
* `pcb check` 余下 274 条 WARN 仍是 P1 清单（via-in-pad 10、silk-over-pad 45、
  widthMismatch 43、coupling 137、缺 Mark 点等）。

---

## 第十二轮：USB 前端重布局 + 真耦合布线器（2026-09-22）

### 交付物：`tools/pair_router.py`（真·配对耦合布线器）

算法：把整对的**轴线**当一条线走 A*（带宽 = 2×线宽 + 对内间距 = 23 mil，
所以轴线需要 `线宽 + 间距/2 + 余量` 的净空），再把轴线按 ±(线宽+间距/2)
**平行偏移**出正/负两条走线；拐角用 bevel 连接，保证偏移后的两条线**永远落在
轴线所保证的走廊内**，因此 A* 的净空结论对成品走线同样成立。

副产品：**偏移出的两条线长度天然相等**（同一条轴线的两条平行线），
实测 skew = 0.00 mil —— 这是"真耦合"相对"两条独立走线 + 事后蛇形补偿"的核心优势。

配套诊断开关：

* `--probe`：逐层报告能否走通；
* `--reach`：从起点洪水填充，报告可达格子数与"离目标最近点"，直接指出卡点；
* `--ignore-net X`：what-if——假设某条网让开，看是否成立；
* `--geom <file>` + `tools/reserve_band.py`：把预留通道注入障碍模型，
  用来让**别的网绕开**这条通道。

### 关键结论：当前板上**放不下**真正解耦的 USB 差分对（有证据）

对 USB0（J1 → R9/R10）做完整探测：

| 实验 | 结果 |
|---|---|
| 轴线 (920,430) → (581.5,2495.5)，仅让 USB 两条网让位 | L1 无路；L2 洪水 323,656 格，最近只到 **8.9 mil** 外；L16 起点格不自由 |
| 忽略 `EPD_PWR_EN` 后，终点改 (590,2250)/(620,2200) | **可达 0.0 mil** → 只需让开 EPD_PWR_EN 这一条 |
| 终点仍在 (585,2470) | 仍被 `FG_ALRT_N` 的端点 (563.4,2466.5) 卡住（余量 16.9 < 需 18.2） |
| 忽略 `EPD_PWR_EN + RESET_N + FG_ALRT_N` | L2 走通 2187 mil，两条线 skew **0.00 mil** |
| 中间走廊 (620,700)→(620,2200)，不让任何网 | 只在 safety 1.2 出路径，且精确校验 **-1.58 mil**（不成立） |
| USB1（R → U1 短配对） | 三种层全部无路；起点格在 r=13 时已不自由 |

**卡点的几何本质**（全部在 Bottom/L2，单位 mil）：

```
 FG_ALRT_N  563.4  y1953..2466.5     ← 左墙
 EPD_PWR_EN 597.0  y2277.9..2634.7   ← 中墙（正好占掉 USB 想走的车道）
 RESET_N    691.2  y2133.2..2356.9
            ↙ 斜线到 641.5
 RESET_N    641.5  y2406.6..2646.6   ← 右墙
            ↘ 647.9  y2652.9..2758.8
 R9.1(581.5,2406.9) R10.1(581.5,2584.1)  D2/D3 信号脚 649.3
```

* FG_ALRT_N 与 EPD_PWR_EN 之间只剩 **23.6 mil**（568.4–592），
  两条 10 mil 走线需要 24.02 mil —— 差 0.4 mil，**物理上放不下两个成员**。
* EPD_PWR_EN 想让开就必须往右；往右会撞 RESET_N 的 641.5 墙；
  RESET_N 想让开则要跨过 EPD_PWR_EN —— **两条网互为对方的障碍，必须同时重布**。
* RESET_N 的 L2 是一堵从 (676.6,2118.6) 连续到 (647.9,2758.8) 的墙；
 想绕到左边又被 FG_ALRT_N（y1953–2466）挡住。
* 第三个约束来自**器件焊盘**：D2/D3（GBLC05C，卧式）的 GND 焊盘在 x=561.3、
  宽 38.8（→ 541.9–580.7），正好压住配对左通道；而 R9.1 的焊盘
  （565.6–597.4 × 2389.9–2423.9）又压住右通道。也就是说**光让开两条走线还不够，
  D2/D3 与 R9/R10 也必须重摆**（例如 D2/D3 转 90° 让焊盘沿 y 排布、
  R9/R10 保持同 x 但重新分配 y），否则无论怎么走线都会撞焊盘。

### 协同重布尝试（用户批准后执行）——逐条失败记录

按"同时重布 EPD_PWR_EN + RESET_N / 重摆 D2-D3-R9-R10 / 再走耦合对"推进，
每一步都被下一条既有铜箔挡住，实测数据如下（均用 `verify_edits.py` 精确判定）：

1. **EPD_PWR_EN 597 → 620**：`-22.49 mil` —— 撞 `EPD_RST_N` 的过孔 (620.1,2345.2)。
   该过孔左侧只剩 ≤599、右侧要到 ≥641.2，而 RESET_N 的 641.5 墙就在旁边，
   **没有 21 mil 宽的车道**。
2. **EPD_PWR_EN 597 → 665**（绕到 RESET_N 墙外）：`-13.80 mil` —— 撞 RESET_N 的
   斜线 (691.2,2356.9)→(641.5,2406.6)（该斜线在 y=2383.1 处正好穿过 x=665）；
   下过孔另外撞 `SPI_MOSI`（L16 斜线在 x=665 处 y=2644.5）。
3. **"把前端整体下移到墙区以下（y≈2100）"**：配对轴线洪水只到 (588,2148)，
   离目标 **4.0 mil**。卡点是 `EPD_PWR_EN` 的 **L1** 段
   (588.2,2153.7)-(595.9,2153.7)-(595.9,2241.8)：y=2150 处 FG_ALRT_N(568.4) 与它(583.2)
   之间只剩 **14.8 mil**，远小于配对所需的 23 mil。

**根因**：EPD_PWR_EN 在 L1 与 L2 上各占一段，两段分别在 y≈2150 与 y≈2280–2635 卡住
通道，而它自己又被 `EPD_RST_N` 的过孔、`RESET_N` 的 L2 Z 形墙、`SPI_MOSI` 的 L16 斜线
三面围住。要让开它，就必须同时动 RESET_N（L2 整段）、FG_ALRT_N（L2 两段）、
EPD_RST_N（过孔+斜线）、SPI_MOSI（L16 斜线）中的至少两条 —— 等于把
x 520–700 / y 1900–2800 这一整块做一次**跨两层的前端重新设计**。

**本轮结论**：板子未做任何改动（1408 走线 / 216 过孔 / DRC 1，与第十一轮一致）。
候选方案留在 `work/relayout-1-epd-pwr-en.json`（未应用）供后续使用。

### 完整前端重设计（用户批准后执行）——做通了 80%，卡在 0.23 mil

**成功做通的部分（每一步都过了精确净空）**

1. `EPD_PWR_EN` 的 L1 段由 "绕到 x588 再绕回" 拉直成 (615.1,2153.7)→(614.5,2260.4)，
   释放 x583–601；L2 段由 597 移到 625。
2. `EPD_RST_N` 的过孔由 (620.1,2345.2) 移到 (650,2345.2)（L16 与 L1 两段跟着改）。
3. 上述改动后，**配对真的走通了**：`pair_router.py` 给出
   2407 mil 的耦合对，两条线 **skew = 0.00 mil**，精确净空 +0.42 / +0.82 mil
   （模板：`work/usb0-plan.json`、`work/g2500.json`）。这是本项目第一次得到
   真正"等距耦合"的 USB 走线。

**失败点（三处，都是硬约束）**

1. **对内间距不够**：通道只容得下 20 mil 的带宽（2×线宽 + 间距）。
   20 mil 对应两种组合：`8 mil 线 + 4 mil 间距`（92 Ω）或 `7.5+5`（98 Ω）。
   但 DRC 的 Track↔Track 规则是 **4.016 mil**、我写入的差分规则是 **5 mil**，
   所以 `8+4` 会违规，而 `7.5+5`（band 20）与 `8+5`（band 21）都**走不通**。
   通道的束缚是 `FG_ALRT_N` 的 563.4 竖直段与 `R1/R25/R29` 左焊盘（599.2）之间
   **只有 30.8 mil**，而合规的最小需求是 23+8.03 = **31.03 mil** —— 差 **0.23 mil**。
2. **转层收尾**：配对在 Bottom 层，而 R9.1/R10.1 是 Top 层 SMD 焊盘，
   必须打过孔转层。该区域被 `EPD_BUSY` 与 `FG_ALRT_N` 两条 L16 斜线（斜率 1）
   夹住，可用过孔点极少；扫描出的最佳点是 (578,2603)（净空 +9.02 mil），
   而 USB_DN 的尾巴要走到那里会贴着 USB_DP 的尾巴（差 2.9 mil）——需要专门绕行。
3. **D2/D3 必须重摆**：它们的 GND 焊盘（x 541.9–580.7）横跨新通道；要保留 ESD
   就得把两只二极管移到通道两侧并各自打过孔 + L1 短支路（tap）。

**顺带修掉一个校验漏洞**：`verify_edits.py` 把"被编辑的两个网"都从障碍里剔除，
所以**对内间距从来没被校验过**。这是上面第 1 条能"看起来通过"的原因，已记录。

**最终处置**：`tools/copper_backup.py restore work/copper-before-usb-relayout.json`
回滚全部改动 → 复核 **DRC 1（仅 Netlist）／1408 走线 216 过孔／USB0 skew 2.1 mil、
USB1 skew 0.05 mil**，与本轮起点完全一致。

**下一次继续所需的完整配方（已全部验证过，剩 4 步）**

1. `R1/R25/R29` 三个 0603 右移 ~5 mil（左焊盘 599.2→604.2），把通道从 30.8 抬到 35.8 mil；
2. `D2/D3` 移到通道两侧（建议 `D2` rot 180 @(446,1936)、`D3` rot 0 @(636,1936)），
   各加 1 个过孔 + L1 短支路把信号脚接到配对；
3. 用 `pair_router.py --width 8 --gap 5 --pad-clearance 1.2`（band 21）重跑，
   此时应能过；
4. 配对末端按 `work/relayout-3-usb0-terminate.json` 的思路打过孔上 Top 层进 R9.1/R10.1，
   过孔点用 (578,2603)（DN）与 (592,2455)（DP），并单独处理 DN 尾巴的绕行。

### 第二次尝试（用户批准 4 步收尾）——又发现第 5 步

1. **第 1 步（R1/R25/R29 右移 5 mil）做成了**：`tools/shift_pads.py` 自动把落在
   这 6 个焊盘上的 7 条引线端点一起平移，精确净空最小 **40.87 mil** ✓。
   通道由 30.8 → **35.8 mil**（`R1/R25/R29` 左焊盘 599.2 → 604.2）。
2. **第 2 步必须重做**：上一轮的回滚把"打开通道"的改动（EPD_PWR_EN、EPD_RST_N）
   一起撤了，且 `copper_backup restore` 会重建图元 → id 全变。补写
   `tools/reopen_corridor.py`（按**端点匹配**找 id，不再依赖旧 id）。
3. **新冲突**：重做后的通道编辑与**保留下来的 USB_DP（MCU 侧）现有走线**打架：
   * `EPD_PWR_EN` 新车道 x=625 → 与 `USB_DP` 的过孔 (639,2370.3) 差 **-8.98 mil**
   * `EPD_RST_N` 新过孔 (650,2345.2) → 与 `USB_DP` 的 L2 斜线
     (668.2,2341)→(639,2370.3) 差 **-13.06 mil**
   原因是这两条线之间只有 14–18 mil，塞不下第二条 10 mil 网。
4. **因此需要第 5 步**：把 `USB_DP` / `USB_DN` 的 R→U1 段也一起重布
   （它们的两个关键障碍正是 `USB_DP` 的过孔 (639,2370.3) 与 L2 竖线 x=668.2）。
   这两条网很短，重布后再用 `tools/serpentine.py` 把长度差补回来即可。

**本轮最终处置**：`copper_backup restore` 回滚铜箔 + `pcb move --dx -5` 把
R1/R25/R29 移回 + `pour-rebuild` 重算铺铜。复核结果与 P0-3 结束时**完全一致**：
DRC **1**（仅 Netlist）、1408 走线 / 216 过孔、DFM ERROR=0 / 274 WARN、
`antennaKeepout=0`、`viaCrossesPlane=0`、USB0 skew 2.1 mil、USB1 skew 0.05 mil。
（注意：器件位移不会被 `copper_backup` 回滚，必须手动 `pcb move` 复位；
复位后要 `pour-rebuild`，否则会报 4 条 `Copper Region(Filled) to SMD Pad`。）

---

## 第十三轮：修原理图连接（2026-09-22）

### 做法

1. `tools/sch_plan_connect.py`：以 `design/model.json` + `design/pin-map.json`
   为准生成"引脚→网络"权威表（327 条），再与 `sch read` 的活体状态对比，
   输出需要补的 `sch autoconnect` / `sch no-connect` 操作清单。
   计划里同时校验"权威表要求但既没连也没在计划里"的引脚数 = 0。
2. `tools/sch_apply_connect.py` 逐条回放。**关键补充**：`sch autoconnect` 对这些
   构建上的密集区会判为"tainted"并返回 `ok:false`（例：
   `score 1000000153 / netport folded vertical`），此时回退到低级
   `sch connect --direction … --offset …`，4 个方向 × 4 个偏移逐个试。
   加上这个兜底后成功率从 93/116 提升到 22/25。

### 进度（连接器掉线前的实测）

| 页 | 悬空引脚 | 网络数 |
|---|---|---|
| P1 | 116 → **25 → 约 3**（`J1:A7`、`R22:2`、`U2:6` 三条未成） | 23 → **45** |
| P2 | 160 → **32** | 0 → **43** |

另外按权威表打了 **36 个显式 NC**（J1.A8/B8、J2.1/4/6/7/19/25/26、J3.1/8、
J4.3/4、J5.3/4、U1 若干）。注意 `C21:1` 曾被误打 NC，已用
`sch no-connect --clear` 撤销。

**保存状态**：P1 已 `sch save` 两次 ✓；**P2 的最后一次 save 失败**（连接器掉线），
P2 的 160→32 可能未落盘。

### 阻塞

`easyeda health --project esp32s3-board-v2.0` → `"windows": []`，
`sch read/save` 全部报 `NO_CONNECTOR / no EasyEDA connector is available`，
重试 3 次（间隔 20 s）未自动恢复 —— 与本文件开头记录的连接器掉线是同一现象。
需要在 GUI 里重新打开 EasyEDA、载入工程 `esp32s3-board-v2.0`、
确认 easyeda-agent 连接器已连接；恢复后先 `sch save --doc P2` 把改动落盘，
再继续跑 `work/sch-connect-plan5.json`（剩余 P2 的补连 + P1 三条顽固引脚）。

### 因此

* 本轮**没有改动板子**：DRC 仍为 1（仅 Netlist Error），1408 走线 / 216 过孔，
  与第十一轮验收一致。
* 已备好的**未应用**方案：`work/epd-pwr-en-detour.json`
  （把 EPD_PWR_EN 的 L2 段从 x=597 移到 x=668、下 via 移到 (668.2,2718.3)），
  精确校验仍有 2 处冲突（跨 RESET_N 的斜线、RESET_N 末端 via 太近），
  可与 RESET_N 的重布一起作为"协同重布"的输入。
* 下一步（需要用户确认，属于中等风险的多网协同重布）：
  1. 同时重布 `EPD_PWR_EN` + `RESET_N` 的 L2 段，把 x 568–700 / y 2280–2660
     整段让给 USB 前端；
  2. 视需要把 R9/R10 与 D2/D3 摆成"CONN 侧焊盘同列、MCU 侧焊盘同列"的紧凑组；
  3. 用 `pair_router.py` 走 USB0/USB1 两条耦合对（skew 天然为 0），
    只对端点扇出做一次小蛇形补偿；
  4. 全量 DRC + 精确净空 + Gerber 复核。

---

## 第十四轮：原理图连接彻底修复（2026-09-22 下午，连接器恢复后）

### 起点与真实病根

连接器恢复后先读活体状态：P1 悬空 13（正是计划内的 NC）、P2 悬空 32，
但 `sch check` 只报 7 条 multi-net-wire + 1 条 dangling。**逐引脚对账才发现
真正的缺陷面大得多**：P1 有 40 个引脚、P2 有 19 个引脚挂在错误网络上，
全工程网表里 `3V3_MAIN / SYS / EPD_3V3 / I2C_SDA / CHG_TS` 这些网名**整个消失**，
GND 涨到 141 脚。

根因（用 `sch export-image --ids` 渲染局部 + 逐图元几何比对证实）：

* **标记的“本体”只要与异网导线相交，平台就判为连通** —— 不是端点相接，
  是符号画出来的那 10×21（GND 旗）/ 6×11（电源旗）/ 31×11（netport）矩形压到
  别人的桩线就算连上。而 GND / 3V3_MAIN 这类同名网是全局的，
  于是**一处物理相交就把整条同名网并掉**（这一轮先是被 GND 吞掉、
  修的过程中又反过来被 3V3_MAIN 吞掉，两种方向都实测到了）。
* 成因是同向密集排布的电容/电阻行（如 C22–C19–C21 在 y=990、R5–R1–R4 在 y=960）：
  相邻两脚只隔 45–70 单位，两个标记都要塞进这条缝，`autoconnect` 在
  “tainted”候选上仍会落笔（`score 984.6 warn=yes`），桩线互相重叠后被平台合并。
* `sch bridge-check`（按共享顶点分组）**看不到**这种“本体压线”的合并，
  所以必须用几何模型自己算（见 `tools/sch_untangle.py`）。

### 新增工具（都在 `tools/`，可复用）

| 工具 | 作用 |
|---|---|
| `sch_audit.py` | 逐引脚对账：live 网表 vs `design/model.json`，输出 ok/floating/wrong/extra/NC |
| `sch_diagnose.py` | 给每个错网引脚定性（标记压脚 / 标记压桩线 / 无标记…） |
| `sch_untangle.py` | **按几何**重建连通簇（共享端点 + 共线重叠 + 标记本体压线 + 引脚落在线上），列出需要整簇删除+重连的清单与工作文件 |
| `sch_place.py` | 带精确标记几何的放置规划器：只沿引脚出线方向枚举桩长，硬拒“桩线/标记压异网导线、压引脚、压器件本体”，软罚标记间重叠，并按顺序把本轮已规划对象当障碍 |
| `sch_reconnect.py` | 批量 disconnect + `autoconnect --spec` 回放（本轮改用 `sch_place` 的显式 offset） |
| `sch_nc.py` | 按权威表打显式 NC（本页/跨页自动分组） |
| `sch_deoverlap.py` | 只重排参与 marker-overlap 的标记（见下文“收益有限”） |
| `sch_verify.py` | 一键刷新 read/list/check/bridge-check + 对账 + 诊断 |

### 做了什么

1. **P1**：`sch_untangle` 找到 34 个合并簇（涉及 76 个引脚，远超 check 报的 8 条），
   整簇删掉 74 个标记 + 70 条导线，再用 `sch_place` 以 4–300 单位的桩长重连 →
   随后把连接器超时漏掉的 4 个点补齐。
2. **P2**：15 个合并簇（36 个引脚）同样处理；另有 4 个引脚
   （`R5:2 KEY3_N`、`R4:1 3V3_MAIN`、`R16:2 CHG_TS`、`R17:1 CHG_TS`）
   在 45 单位缝里**物理放不下**（一个 netport 需要 40.5 的“本体外伸”空间），
   按工程办法微调布局腾位置：`R5 -40`、`R4 +40`、`C29/C31 +45`、`C32 -25`
   （均为 `sch modify --x`，先把受影响的旧桩线/标记删除），缝宽 45 → 85–90 后即可放置。
3. 补齐 P2 剩余 13 个悬空脚、两页共 **36 个显式 NC**（与计划表逐条一致）。
4. 图签填写（两页 `Name/Drawed/Reviewed/Description`，`verified:true`），
   删除 1 个冗余的 `USB_VBUS_PROT` 标记（check 自己建议保留 726b3a37f59da653）。
5. `sch save`（两页）→ `doc reload`（两页）→ 重读复核，结果一致。

### 验收（save + reload 之后）

| 项 | P1 | P2 |
|---|---|---|
| 权威连接 | **190/190 正确**（floating 0 / wrong 0 / extra 0） | **137/137 正确** |
| 显式 NC | 13 | 23 |
| `sch check` 电气项 | 全 0（floating / multiNetWires / wireOverPins / dangling / duplicateNetMarker） | 全 0 |
| `sch bridge-check` | 0 bridge / 0 orphan（189 个导线树） | 0 / 0 |
| `sch layout-lint` | placement gate passed，0 tight / 0 off-grid / 0 out-of-sheet | 同左 |
| 官方 `sch drc` | 0 fatal / 0 error / 10 warn（聚合，无逐条明细） | 同左 |

全工程网表 70 网，之前消失的网名全部回来：
`GND 86 脚`、`3V3_MAIN 34`、`SYS 11`、`EPD_3V3 8`、`I2C_SDA 5 (R6,U1,U2,U4,U5)`、
`I2C_SCL 5`、`CHG_TS 4 (NTC1,R16,R17,U2)`、`FG_ALRT_N 3 (R22,U1,U4)`、`BAT_BUS 8`。

### 未完成 / 已知项（都是外观，不影响连接）

1. **marker-overlap 76 条（P1）/ 52 条（P2）**：标记之间/标记压器件的纯视觉重叠。
   实测**不会串网**（本轮删掉 34 簇后仍保留大量此类重叠，网表依旧干净）。
   已试过两条路都不划算：
   * `sch destagger --apply` 在本页跑到第 3 轮时恢复段卡在几何守卫，
     遗留 `J1:A7` 断线（已手工补回），且重叠只从 83 → 82；
   * 自己写的 `sch_deoverlap` 重排 82 个标记，重叠 83 → 76，收益同样有限
     （密集引脚扇出如 U1/U2/U5/J1 一带几何上就是放不开）。
2. **missing-partition 1 处（只有 P1）**：页面没有功能区虚线框。
   `design/sch-layout-A/B.json` 里 7+5 个模块的成员表还在，但当前页没有虚拟组，
   `zone-plan / zone-draw` 需要先 `sch group create` 建组（属于注释层，未做）。
3. 器件位置做过 5 处微调（见上），是**相对原 autolayout 的布局改动**，
   理由是为了让“两个网络端口对撞”的 45 单位缝可用；功能与网表不受影响。

### 下一次要动原理图时的顺序（已验证有效）

1. `easyeda update --check --exit-code` → `easyeda health --project esp32s3-board-v2.0`
2. `python tools/sch_verify.py` 拿活体基线（read/list/check/bridge-check + 对账）
3. 有错网/悬空 → `python tools/sch_untangle.py --page PX --jobs-out work/jobs-PX.json`
   → `sch_place.py --jobs … --exclude work/untangle-PX.json`（dry-run 看是否都可放置）
   → `sch_untangle.py --page PX --delete` → 刷新 list → `sch_place.py --apply`
4. 放置规划器**只认“标记本体压异网导线/引脚/器件”为硬约束**；
   一旦出现 `no collision-free candidate`，说明该处缝宽不够，先调布局再放置。
5. 收尾一定 `sch save` + `doc reload` + 重读；`sch check` 的电气项必须全 0。

---

## 第十五轮：按需求文档复核原理图 + DNP 标记 + 文档措辞修订（2026-09-22）

### 复核（对照 `PCB_INTERFACE_POSITIONS.md` 与 v1.1 冻结设计）

新工具：`tools/req_check.py`（文档表格 + BOM 对比）、`tools/pcb_netlist_check.py`
（`design/model.json` ↔ v1.1 终版 PCB 焊盘网表）。完整报告见 `REQUIREMENT_CHECK.md`，
原始输出 `work/audit/req-check.txt`、`work/audit/req-pcb-netlist.txt`。

结论：**功能与连接无缺陷**。

* v1.1 终版 PCB 110 个封装 ↔ v2 模型：102 个逐焊盘一致，另 4 个（J1/U1/U2/U4）
  差异只来自 v1.1 里**无名无网络**的机械/散热焊盘，**网络分配差异 0**。
* 文档 §7.2 GPIO 表 22/22、§5.5 microSD 14/14、FPC 24/24（= GDEM102T91 规格书 p.7）、
  §7.4/7.5/7.9 接口功能脚 24/24；§7.8 点名的 70 个网络全部存在，全工程无单脚网。
* 数据手册级复核：TUSB320 VBUS_DET 只需**一颗 900 kΩ 串阻**（R11=900 kΩ ✔，不需下臂）、
  PORT=GND→UFP、ADDR=GND→0x47；MAX17048 CTG/CELL/VDD/QSTRT 全对；
  TPS63070 PS/SYNC 经 100 kΩ（1 k–1 M）到 SYS、VSEL 下拉 + FB2 悬空、FB 470 k/150 k→3.307 V；
  TPS22918 ON=EPD_PWR_EN + 100 k 下拉；BQ25895 /CE 10 k 上拉、PMID 10 µF、TS 5.23 k/30.1 k+NTC。
* 极性用 `sch export-image` 局部渲染核对：D6 阳 EPD_SW→阴 EPD_VGH、D7 阳 EPD_X→阴 GND、
  D8 阳 EPD_VGL→阴 EPD_X、Q1 G/S/D=1/2/3 —— 与规格书 p.20 一致。

### 本轮实际改动

1. **R21 / C16 标为不装配**（沿用 v1.1 的 `Populate=DNP` 策略）：
   `easyeda sch modify --id <pid> --patch-file`（`{"addIntoBom": false,
   "otherProperty": {"Populate": "DNP"}}`），C16 在 P1、R21 在 P2，R31 保持 FIT。
   保存 + 重载后复读：`addIntoBom=False`、`Populate=DNP` 均生效，连接不变
   （P1 190/190、P2 137/137，桥接/孤儿 0）。
   *注：EasyEDA 没有原生 DNP 字段，`addIntoBom=false` 让该件不进 BOM/CPL（SMT 不会实装），
   `Populate=DNP` 保留文字意图。*
2. **L1 保持 v2 选型**（`NR5040-1.0µH`，C49581188），用户已确认不换回 v1.1 的
   `MWSA0503S-1R0MT`。
3. **`PCB_INTERFACE_POSITIONS.md` 修订 6 处措辞**（不改电路）：
   §7.2 去耦清单（C1/C2/C3/C4，C5 属 RESET_N）、§7.2 未用 GPIO 的完整 NC 清单
   （GPIO3/35/36/37/38/39/40/41/42/43/44/45/46/48，模组脚 15、16、25、26、28–37）、
   §7.3 接口（面板无 MISO/SDO，`SPI_MISO` 只给 TF 卡）、§7.8 存储（`SPI_*` ↔ `TF_*`
   经 R33/R34/R35 桥接）、§7.5 输入保护（0.1 µF 在公共 BAT_BUS 侧）、
   §7.2 GPIO 表 GPIO21 行（`SPI_MISO` 说明）。
4. **J1 料号统一为 `USB4105-GF-A-120`**（用户决定沿用 v2 料号，C5184243）：
   文档 §4 表格与 §5.1 器件行已改写为该料号，并注明早期文档的
   `USB4105-15-A-120` 属同一 USB4105 系列的另一种写法（焊盘/本体尺寸相同）。
   至此本轮复核提出的 4 项全部关闭：R21/C16 标 DNP、L1 保留、J1 料号统一、
   §7.5 电容位置按现状写入文档。

### ⚠️ 顺带发现（PCB 侧，**未改动**，待用户决定）

为确认 J1 料号，我用 `tools/mech_crosscheck.py` / `tools/gerber_j1_outline.py`
把文档第 3–5 节的受约束坐标复测了一遍（坐标基准由 `Gerber_BoardOutlineLayer.GKO`
自证为 X 0–55 / Y 0–84 mm，与文档的 `(X, 84 − Y_down)` 映射一致，H1–H4 也印证）：

| 项 | 实测 | 文档 | 偏差 |
|---|---|---|---|
| SW3/4/5、J2 焊盘 | — | — | ✓（≤0.03 mm） |
| J1 信号焊盘行 Y | 77.294 | 77.650 | **−0.356 mm** |
| J1 定位孔 Y（X 与间距 ✓） | 78.369 | 78.725 | **−0.356 mm** |
| J3 焊盘行 Y / J3.9 X | 67.650 / 34.201 | 67.475 / 34.125 | +0.175 / +0.076 |
| J4/J5 Pin1 X（Y ✓） | 7.450 | 8.400 | **−0.950 mm** |

**J1 整列同向同量内移 0.356 mm** ⇒ USB-C 本体外凸约 0.65 mm 而非文档的 1.005 mm，
外壳开孔基准会差 0.36 mm（J1 的焊盘尺寸/间距、4 个屏蔽孔、2 个 Ø0.65 定位孔及其
相互间距全部与文档一致，所以这是**整体位移**而不是封装画错）。J3/J4/J5 两处是
机械净空量级的小偏差，不影响插接。

**处置（2026-09-22，用户决定）：接受现状，PCB 不动，改文档。**

* `PCB_INTERFACE_POSITIONS.md` 新增 **§5.6 v2.0 实装坐标（实测）**：逐项列出
  J1/J2/J3/J4/J5/SW3–5 的实测值、v1.1 参考值与偏差，并说明测量基准
  （GKO 自证 0–55 / 0–84 mm，H1–H4 交叉验证）；
  §4 表与 §5.1–5.5 标注为“v1.1 参考基线”并指向 §5.6；
  §9 第 1 条改为实装外凸 **0.874 mm**，新增第 8（J4/J5 X 7.450）、第 9（J3 焊盘行 67.650）条。
* 测量脚本：`tools/mech_measure.py`（逐焊盘实测）、`tools/mech_crosscheck.py`（对照文档）、
  `tools/gerber_j1_outline.py`（Gerber 层范围）、`tools/j1_pad_compare.py`（J1 封装对比）。
* 结论：**J1 整列 −0.356 mm、J4/J5 X −0.950 mm、J3 +0.175 mm，SW3–5/J2 与参考一致**；
  若后续改版要回到 v1.1 基线，按 §5.6 的“偏差”列反向平移即可。
