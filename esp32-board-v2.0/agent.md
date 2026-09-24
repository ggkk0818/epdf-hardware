# esp32-board-v2.0 任务交接说明（EasyEDA Agent）

> 本文件用于跨会话继续任务。**开始前请先完整阅读本文件、`PCB_INTERFACE_POSITIONS.md`，
> 以及 `../esp32-board-v1.1/agent.md`（同源工程的历史交接）。**

## 一、用户任务

> 请使用 easyeda-agent，根据 `C:\Code\epdf-hardware\esp32-board-v2.0\PCB\_INTERFACE\_POSITIONS.md`
> 的需求，在项目 **esp32s3-board-v2.0** 中完成一块 ESP32-S3 系统板。请自行选型并核对数据手册，
> 从原理图、布局、布线、铺铜、丝印一直做到 DRC 和保存完成。

路径说明：需求文档实际位于 **`esp32-board-v2.0\PCB_INTERFACE_POSITIONS.md`**
（用户 prompt 中写的 `PCB\_INTERFACE\_POSITIONS.md` 不存在）。文件名内容一致：
《ESP32-S3 墨水屏主板 — PCB 外框、接口位置与功能需求说明》，共 10 节
（板框 55 × 84 mm / R2、四角 M2 孔、J1 USB-C、J2 24P FPC、J3 microSD、
J4/J5 双电池、SW3/SW4/SW5、禁布区、功能需求、自由度说明）。

目标工程：**esp32s3-board-v2.0**（嘉立创EDA专业版，projectUuid
`c4799361d2dd4e09bdd31ddc8a57a1ba`），2026-09-20 时已在编辑器中打开。

## 二、easyeda-agent 环境状态（2026-09-20 由上一会话升级完成）

| 组件 | 版本 | 位置 / 状态 |
|---|---|---|
| CLI | **v1.5.2** | `C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe` |
| Skill | **v1.5.2** | `~/.codex/skills/easyeda-agent`、`~/.agents/skills/easyeda-agent`、`~/.claude/skills/easyeda-agent` |
| daemon | **v1.5.2** | 监听 `127.0.0.1:60832` |
| Connector | 待用户更新 | 旧 v1.4.8 与新 daemon **不兼容**，必须重新侧载 |

说明：

- 原 CLI 位于 `C:\Program Files\KiCad\10.0\bin\easyeda.exe`（v1.4.8），该目录非管理员不可写、
  本机 Windows `sudo` 已禁用，因此 v1.5.2 装到用户自有目录
  `%LOCALAPPDATA%\Python\bin`（**该目录在 PATH 中且排在 KiCad 之前，`easyeda` 已解析到 v1.5.2**）。
  Program Files 里的 v1.4.8 副本保留未动，可作备份；如需“干净”状态，可在管理员 PowerShell 中把
  `%LOCALAPPDATA%\Python\bin\easyeda.exe` 覆盖回该路径。
- **连接器必须由用户在 GUI 完成**（CLI 只能报告、不能侧载）：

  1. 打开 EasyEDA 扩展管理器，卸载旧的 easyeda-agent 侧载项；
  2. 导入 `C:\Users\ggkk2\Downloads\easyeda-agent-connector-1.5.2.eext`；
  3. **完全退出并重开 EasyEDA**（只重新导入不够，已打开页面仍跑旧运行时代码）；
  4. 打开工程 `esp32s3-board-v2.0`，在扩展设置里启用“允许外部交互”。

## 三、会话门禁（强制）

每个新 Agent 会话的第一条命令必须是：

```powershell
easyeda update --check --exit-code   # 只有输出 READY 且 exit 0 才能开始 EDA 工作
```

2026-09-20 本次升级已经替换过 CLI / Skill / daemon，按 Skill 规定**当前会话不得继续**，
必须关闭当前会话、新开会话后重新过门禁。连接器尚未更新时门禁会停在
`connector no-window`（exit 10），先完成第二节的 GUI 步骤。

## 四、参考材料（离线可用）

- **同源工程 v1.1**：`C:\Code\epdf-hardware\esp32-board-v1.1` —— 同一套接口位置与功能，
  已做到 ERC 0 / DRC 0 Error 0 Warning、unconnected 0，最终文件
  `esp32-board-v1.1_final_drc_20260920.kicad_pcb`（v2.0 的需求文档即以它为数据源）。
- **数据手册**（直接复用，免联网）：`esp32-board-v1.1\datasheets\`
  —— `esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf`、`bq25895.pdf`、`tps63070.pdf`、
  `MAX17048-MAX17049.pdf`、`tusb320li.pdf`、`tps22918.pdf`、`SSD1677.pdf`、
  `GDEM102T91.pdf`、`X05B20U24T.pdf`、`X05B20U24T_easyeda.json`（立创 C437036 CAD 数据）、
  `DESPI-C102_SCH.pdf` 等；4 层叠层参数见 `C:\Users\ggkk2\Downloads\4层stackup.jpg`。
- **v1.1 交接与笔记**：`esp32-board-v1.1\agent.md`、`SCHEMATIC_NOTES.md`、
  `PCB_LAYOUT_NOTES.md`、`ROUTING_NOTES.md`、`bom.csv`。
- **接口位置图**：`esp32-board-v2.0\render\pcb_interface_map.png`。
- 设计文档全集：`C:\Users\ggkk2\Downloads\ESP32S3_GDEM102T91_*.md`。

## 五、下一步（新会话）

1. 用户完成第二节 GUI 步骤并新开会话；新会话先跑第三节门禁。
2. `easyeda health --project esp32s3-board-v2.0` → `easyeda doc ls --project esp32s3-board-v2.0`
   确认工程与活动页，然后按 `SKILL.md` 的任务表加载参考
   （`design-flow.md` → `part-selection.md` → `schematic*.md` → `pcb*.md`）。
3. 流程：选型 / 数据手册核对 → 原理图 → ERC → 布局（严守第 6 节禁布区与第 4 节接口机械约束）
   → 布线（POWER / USB 90 Ω 差分 / SPI / I2C / GPIO / EPD 高压）→ 铺铜 → 丝印 → DRC → 保存。
4. 交付前确认层叠、GND、电源、丝印与导出文件，并按 Skill 的“验证交付”逐项报告。
