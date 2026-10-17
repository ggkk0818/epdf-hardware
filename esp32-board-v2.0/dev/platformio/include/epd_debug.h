// =====================================================================
//  epd_debug.h - 墨水屏调试信息输出（3 个 I2C 器件 + microSD 卡）
//
//  ---- 开关 ----
//    ENABLE_EPD_DEBUG    0 = 关闭（默认）    1 = 开启
//    也可以不改本文件，在 platformio.ini 的 build_flags 里加
//        -DENABLE_EPD_DEBUG=1
//
//  ---- 面板 ----
//    默认：GDEY042T81（4.2 英寸 400x300，SSD1683）
//    可选：GDEM102T91（10.2 英寸 960x640，SSD1677）
//          在 platformio.ini 的 build_flags 里加 -DEPD_PANEL_GDEM102T91=1
//    两块面板用同样的 4 根控制线（CS=10 / DC=9 / RST=8 / BUSY=7），
//    SCLK/MOSI 与 microSD 共用，只是驱动 IC 与分辨率不同。
//
//  ---- 依赖（platformio.ini 的 lib_deps）----
//    zinggjm/GxEPD2                    面板驱动（含上面两块面板的驱动类）
//    adafruit/Adafruit GFX Library     GxEPD2 的绘图基类
//    olikraus/U8g2_for_Adafruit_GFX    中文点阵字体（屏幕上的中文标签）
//
//  ---- 开启后的行为 ----
//    1. GPIO6（EPD_PWR_EN）保持高电平，EPD_3V3 常开（TPS22918 一直使能）；
//    2. 首帧全屏刷新，之后每 EPD_DEBUG_REFRESH_MS 毫秒局部刷新一次；
//    3. 每 EPD_DEBUG_FULL_EVERY 次局部刷新插一次全屏刷新，用来消除残影；
//    4. 每次刷新结束调用 display.powerOff()：只关面板驱动电压，不断 EPD_3V3。
//
//    注意：刷新是阻塞的（4.2 英寸局部约 0.4 s / 全刷约 1.2 s；
//    10.2 英寸局部约 0.8 s / 全刷约 5.5 s），期间按键与串口响应会顺延。
//
//  关闭本开关时下面两个接口都是空操作，main.cpp 不需要再包 #if。
// =====================================================================
#pragma once

#include <Arduino.h>

#ifndef ENABLE_EPD_DEBUG
#define ENABLE_EPD_DEBUG 1
#endif

#define EPD_DEBUG_REFRESH_MS  5000UL   // 局部刷新间隔（毫秒）
#define EPD_DEBUG_FULL_EVERY  20       // 每 N 次局部刷新插一次全屏刷新

// 面板选择：不定义 EPD_PANEL_GDEM102T91 时用默认的 GDEY042T81
#if defined(EPD_PANEL_GDEM102T91)
#define EPD_PANEL_IS_1020 1
#else
#define EPD_PANEL_IS_1020 0
#endif

#if ENABLE_EPD_DEBUG
// 上电 + 初始化面板并画出第一屏；请在 setup() 里 Wire.begin() 之后调用
void epdDebugBegin();
// 在 loop() 里反复调用；内部按 EPD_DEBUG_REFRESH_MS 节流
void epdDebugUpdate();
#else
inline void epdDebugBegin() {}
inline void epdDebugUpdate() {}
#endif
