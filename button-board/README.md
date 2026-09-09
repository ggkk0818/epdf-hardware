# button-board

这是一个面向华秋 KiCad（KiCad 10 兼容）的按键板原理图工程。

原理图 `button-board.kicad_sch` 已包含：

- 3 个贴片轻触开关 `TS3315A`：`SW1=UP`、`SW2=DWN`、`SW3=ENT`，开关公共端共地。
- 1 个 SH1.0 4P 卧贴母座 `WAFER-SH1.0-4PWB`，引脚顺序为 `1=UP`、`2=DWN`、`3=ENT`、`4=G`。
- 信号网络标签：`UP`、`DWN`、`ENT`、`G`。

PCB `button-board.kicad_pcb` 已包含：

- 板框 12 x 114 mm，四角圆角 R2，板厚 1.2 mm，2 层板。
- 三个 `TS3315A` 贴片轻触开关中心：`SW1=(6,30)`、`SW2=(6,84)`、`SW3=(6,57)`。
- 两个定位孔：`(6,4)`、`(6,110)`，直径 2.2 mm，NPTH。
- `WAFER-SH1.0-4PWB` 卧贴母座 `J1` 位于 `(2,100)`，接线方向朝右（+x，相对原方向顺时针旋转 180°）。
- 连接器丝印线序（从上到下）：`4 G`、`3 ENT`、`2 DWN`、`1 UP`。

## 器件

- 轻触开关：TS3315A，`button-board:TS3315A`，华秋器件库链接：https://item.hqchip.com/2500431492.html
- SH1.0 母座：WAFER-SH1.0-4PWB，`button-board:WAFER-SH1.0-4PWB`，华秋器件库链接：https://item.hqchip.com/2500435391.html

## 打开方式

1. 启动华秋 KiCad。
2. 选择“打开工程”，打开本目录下的 `button-board.kicad_pro`。
3. 在工程管理器中分别打开 `button-board.kicad_sch` 和 `button-board.kicad_pcb`。
4. 如果华秋 KiCad 此前已经打开该原理图或 PCB，请先关闭并重新打开对应文件，以加载本文件的最新内容。

## 华秋器件库

华秋器件库通过华秋 KiCad 内置的“华秋库面板 / Component Search”提供，工程内不需要保存云端账号信息。打开原理图后，可在工具栏中打开华秋器件搜索面板，搜索型号、参数或描述，然后将器件直接摆放到原理图中。
