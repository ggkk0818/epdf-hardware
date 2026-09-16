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
网络 69（不含 GND）：已布线 57，未完成 12
线段 689，信号过孔 75，GND 缝合过孔 145（30 焊盘 + 115 网格）
ERC  0 violations
DRC  5 violations：2 × clearance(error) + 3 × track_dangling(warning)
     unconnected 93 项（= 15 个未完成网络 + GND 铺铜孤岛）
tools/check_routing.py：线-线 / 线-过孔间距 0 问题
```

线宽分布（0.8 mm = 主干加宽段；0.5/0.4 mm = POWER 与 SWITCH_NODE；
0.3 mm = HV_EPD；0.24 mm = USB 差分；0.2 mm = 默认；0.15–0.25 mm = 焊盘收颈）：

```
0.80 mm : 20 段（BAT1_RAW / BAT2_RAW / BAT_BUS / USB_VBUS_RAW / USB_VBUS_PROT）
0.50 mm : 73   0.40 mm : 9    0.30 mm : 42   0.25 mm : 48
0.20 mm : 401  0.24 mm : 32   0.15 mm : 25
```

### 3.1 未完成的 15 个网络

| 网络 | 位置 |
|---|---|
| `3V3_MAIN` | 34 个焊盘跨全板，U1/U3/U5 附近引脚被封 |
| `SYS` | U2 ↔ U3 之间 0.5 mm 间距引出 |
| `I2C_SCL` / `I2C_SDA` | U2 左列 + U4/U5 |
| `CHG_CE` / `CHG_INT_N` / `CHG_OTG` / `CHG_DSEL` / `CHG_REGN` | U2 左列与顶行 |
| `TPS_L2` | U3 10 脚 ↔ L2 |
| `SPI_SCLK` / `TF_SCLK` | U1 底部焊盘 / R33 |
| `TF_CS_N` / `TYPEC_INT_N` / `EPD_VGH` / `USB_DN_CONN` | J3 / U5.6 / D6↔J2.21 / J1→D3 |

均位于密集引脚区（BQ25895 左列、TPS63070 左列、TUSB320、ESP32 底部、USB-C / FPC 扇出）的
最后 1–2 段，部分位置四条 0.2 mm 走线必须共用不到 1 mm 的走廊。建议用 KiCad 交互布线收尾
（自动布线器已尽量把这些通道留出）。

### 3.2 其余 5 个 DRC 项

| 类型 | 位置 | 说明 |
|---|---|---|
| clearance (error) | EPD_GDR / EPD_RESE，X≈3.6、Y 46.7–47.5 | 两条 HV 走线并行 0.4 mm，实测 0.125 < 0.2 mm |
| clearance (error) | EPD_3V3 ↔ C31 Pad2 (GND)，(10.7, 44.7) | 实测 0.127 < 0.2 mm，收尾时把该段移开即可 |
| track_dangling ×3 | EPD_BUSY / EPD_RESE / SPI_SCLK 的 0.1 mm 残段 | 走线末端停在焊盘外 0.1 mm |

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

1. **窄颈规则区** `PWR_NECK_1..5`（矩形由真实窄段包围盒 + 0.35 mm 生成），区域内允许
   POWER / SWITCH_NODE / HV_EPD 网络低于网络类线宽（最小 0.15 mm）。这是 IC 焊盘处的
   常规收颈，规则不会覆盖到窄段以外。
2. **USB 差分对**：`USB_DP/DN`、`USB_DP/DN_CONN` 全程 L1 微带（0.24 mm），耦合间距因
   0.1 mm 栅格量化为 0.26–0.40 mm，与 0.18 mm 目标略有差异。
3. **GND** 不布独立走线，靠四层铺铜 + 138 个缝合过孔连通（含每个 GND 焊盘附近的过孔）。

---

## 5. 下一步

1. 人工收尾 §3.1 的 15 个网络（建议顺序：U2 左列 → U3 左列 → I2C → SPI/TF → 电源）。
2. 修掉 §3.2 的 2 个间距 + 3 个悬空线头。
3. 打开 `track_not_centered_on_via`、`tuning_profile_track_geometries` 检查后重跑 DRC。
4. 板厂按实际叠层复算 USB 90 Ω（当前 0.24 mm 线宽，目标间距 0.18 mm）。
5. 生成 Gerber / 钻孔 / 贴片坐标（命名见 `PCB_LAYOUT_NOTES.md` §13）。
