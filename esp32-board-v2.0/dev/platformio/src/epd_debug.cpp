// =====================================================================
//  epd_debug.cpp - 墨水屏调试信息输出（ENABLE_EPD_DEBUG = 1 时生效）
//
//  屏幕上显示：
//    板级基础信息（型号 / 固件时间 / 主频 / RAM / PSRAM / 运行时间）
//    3 个 I2C 器件（BQ25895 0x6A / MAX17048 0x36 / TUSB320 0x47）
//    microSD 卡（类型 / 容量 / FAT / 扇区 / 簇 / 根目录项数 / 挂载状态）
//    电池电压 / SOC / 充电状态
//    10.2 英寸屏幕（行数够）时再补一屏寄存器级信息
//
//  开关、面板选择与刷新策略见 epd_debug.h。
//  本文件只在 ENABLE_EPD_DEBUG = 1 时参与编译。
// =====================================================================
#include "epd_debug.h"

#if ENABLE_EPD_DEBUG

#include <SPI.h>
#include <SD.h>
#include <Wire.h>
#include <stdarg.h>
#include <string.h>

#include <GxEPD2_BW.h>
#include <U8g2_for_Adafruit_GFX.h>

#include "board_pins.h"

// ------------------------------ 面板 --------------------------------
// 两块面板的控制线完全一致：CS=10 / DC=9 / RST=8 / BUSY=7
//
// 行距与首行基线取自字体的实际字形范围（字体头里的 max_char_height 与 y_offset）：
//   字形顶端 = 基线 - (max_char_height + y_offset)
//   wqy12：max_char_height 13、y_offset -2 → 字形占 [基线-11, 基线+2]
//   wqy16：max_char_height 18、y_offset -4 → 字形占 [基线-14, 基线+4]
// 所以首行基线要比“字形高度 + y_offset”再留 2~4 px 余量，行距取字形高度 + 3 px。
#if EPD_PANEL_IS_1020
typedef GxEPD2_1020_GDEM102T91 EpdPanel;                 // 960 x 640，SSD1677
#define EPD_MODEL_TEXT    "GDEM102T91 10.2in 960x640"
#define EPD_FONT          u8g2_font_wqy16_t_gb2312
#define EPD_LINE_STEP     21                              // 字形 18 px + 3 px 行间
#define EPD_FIRST_BASELINE 20                             // 字形顶端 = 20 - 14 = 6 px
#else
typedef GxEPD2_420_GDEY042T81 EpdPanel;                  // 400 x 300，SSD1683
#define EPD_MODEL_TEXT    "GDEY042T81 4.2in 400x300"
#define EPD_FONT          u8g2_font_wqy12_t_gb2312
#define EPD_LINE_STEP     16                              // 字形 13 px + 3 px 行间
#define EPD_FIRST_BASELINE 15                             // 字形顶端 = 15 - 11 = 4 px
#endif

// 整屏缓存由 GxEPD2_BW 用静态数组提供：
//   4.2 英寸 400 x 300 / 8 = 15 000 B，10.2 英寸 960 x 640 / 8 = 76 800 B
static GxEPD2_BW<EpdPanel, EpdPanel::HEIGHT> display(
    EpdPanel(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));
static U8G2_FOR_ADAFRUIT_GFX epdFonts;

// --------------------------- 屏幕文本缓冲 -----------------------------
// 基础信息 17 行 + 10.2 英寸附加信息最多 9 行 = 26 行，留 2 行余量
#define EPD_LINE_MAX    64
#define EPD_LINE_COUNT  28

static char    s_lines[EPD_LINE_COUNT][EPD_LINE_MAX];
static uint8_t s_lineCount = 0;

// ----------------------------- 运行状态 ------------------------------
static bool     s_ready          = false;   // 面板初始化完成
static bool     s_firstFrameDone = false;   // 首帧全屏刷新是否已做
static uint32_t s_lastRefreshMs  = 0;       // 上次刷新结束时刻
static uint16_t s_partialCount   = 0;       // 距上次全刷已做几次局部刷新
static bool     s_sdMounted      = false;   // microSD 是否已挂载
static uint32_t s_sdRetryMs      = 0;       // 上次尝试挂载的时刻
static uint32_t s_refreshCount   = 0;       // 已刷新屏数（10.2 英寸页脚显示）

// --------------------------- I2C 读寄存器 ----------------------------
static bool i2cPing(uint8_t addr)
{
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static bool i2cRead8(uint8_t addr, uint8_t reg, uint8_t &val)
{
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, 1) != 1) return false;
  val = (uint8_t)Wire.read();
  return true;
}

static bool i2cRead16(uint8_t addr, uint8_t reg, uint16_t &val)
{
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, 2) != 2) return false;
  const uint8_t hi = (uint8_t)Wire.read();
  const uint8_t lo = (uint8_t)Wire.read();
  val = ((uint16_t)hi << 8) | (uint16_t)lo;
  return true;
}

// ------------------------------ 文字表 -------------------------------
// BQ25895 REG0B：CHRG_STAT[1:0] = 0 未充电 / 1 预充 / 2 快充 / 3 充电完成
static const char *chgStateText(uint8_t reg0b)
{
  switch ((reg0b & BQ_STATUS_CHRG_MASK) >> BQ_STATUS_CHRG_SHIFT) {
    case 0:  return "未充电";
    case 1:  return "预充";
    case 2:  return "快充";
    default: return "充满";
  }
}

// BQ25895 REG0B：VBUS_STAT[2:0]
static const char *vbusStateText(uint8_t reg0b)
{
  switch ((reg0b >> 5) & 0x07) {
    case 0:  return "无输入";
    case 1:  return "SDP";
    case 2:  return "CDP";
    case 3:  return "DCP";
    case 5:  return "适配器";
    case 7:  return "可调压";
    default: return "保留";
  }
}

static const char *cardTypeText(uint8_t type)
{
  switch (type) {
    case CARD_MMC:  return "MMC";
    case CARD_SD:   return "SDSC";
    case CARD_SDHC: return "SDHC";      // SDXC 也报这个
    case CARD_NONE: return "无卡";
    default:        return "未知";
  }
}

static void formatSize(uint64_t bytes, char *out, size_t n)
{
  if (bytes >= (uint64_t)1024 * 1024 * 1024) {
    snprintf(out, n, "%.1fGB", (double)bytes / (1024.0 * 1024.0 * 1024.0));
  } else if (bytes >= (uint64_t)1024 * 1024) {
    snprintf(out, n, "%.1fMB", (double)bytes / (1024.0 * 1024.0));
  } else {
    snprintf(out, n, "%luKB", (unsigned long)(bytes / 1024));
  }
}

// ---------------------------- 数据采集 -------------------------------
struct EpdData {
  // I2C 三个器件
  bool     bqOk, fgOk, typecOk;
  uint8_t  bqStatus;      // REG0B
  uint8_t  bqReg00, bqReg03, bqReg04, bqReg06;
  uint16_t fgVcell, fgSoc, fgStatus;
  int16_t  fgCrate;
  uint8_t  typecCur, typecAttach;
  // microSD
  bool     sdPresent, sdMounted;
  uint8_t  sdCardType, sdFat;
  uint64_t sdBytes;
  uint16_t sdSectorBytes;
  uint32_t sdClusterBytes;
  uint32_t sdRootCount;
};

static uint32_t countRootEntries()
{
  File root = SD.open("/");
  if (!root) return 0;
  uint32_t n = 0;
  File entry = root.openNextFile();
  while (entry && n < 9999) {
    n++;
    entry = root.openNextFile();
  }
  root.close();
  return n;
}

// 直接从引导扇区（第 0 扇区）读 BPB：SD 库没有 fatType() 接口
static void readSdBootSector(EpdData &d)
{
  uint8_t boot[512];
  if (!SD.readRAW(boot, 0)) return;

  d.sdSectorBytes  = (uint16_t)boot[11] | ((uint16_t)boot[12] << 8);
  d.sdClusterBytes = (uint32_t)d.sdSectorBytes * (uint32_t)boot[13];

  if (memcmp(boot + 82, "FAT32", 5) == 0)      d.sdFat = 32;
  else if (memcmp(boot + 54, "FAT16", 5) == 0) d.sdFat = 16;
  else if (memcmp(boot + 54, "FAT12", 5) == 0) d.sdFat = 12;
  else                                        d.sdFat = 0;   // exFAT / 未知
}

// 卡座检测 + 挂载（支持运行中插拔：拔卡卸载，插卡自动重试）
static void pollSdCard()
{
  const bool present = (digitalRead(PIN_SD_CD) == LOW);   // 插卡 = 低
  if (!present) {
    if (s_sdMounted) {
      SD.end();
      s_sdMounted = false;
      Serial.println(F("[SD] 卡已拔出"));
    }
    return;
  }
  if (s_sdMounted) return;
  // 最多 2 s 试一次；s_sdRetryMs 为 0 表示还没试过（开机首次必须真的试一次，
  // 否则 millis() < 2000 时会被这行直接跳过，首屏会误报“未挂载”）
  if (s_sdRetryMs != 0 && (millis() - s_sdRetryMs < 2000)) return;
  s_sdRetryMs = millis();
  s_sdMounted = SD.begin(PIN_SD_CS, SPI, 4000000);        // 与墨水屏共用 SPI，先用 4 MHz
  Serial.printf("[SD] %s\n", s_sdMounted ? "挂载成功" : "挂载失败（检查卡/格式）");
}

static EpdData collectData()
{
  EpdData d = {};

  d.bqOk    = i2cPing(ADDR_BQ25895);
  d.fgOk    = i2cPing(ADDR_MAX17048);
  d.typecOk = i2cPing(ADDR_TUSB320);

  if (d.bqOk) {
    i2cRead8(ADDR_BQ25895, BQ_REG_STATUS,      d.bqStatus);
    i2cRead8(ADDR_BQ25895, BQ_REG_INPUT_LIMIT, d.bqReg00);
    i2cRead8(ADDR_BQ25895, BQ_REG_MODE_CFG,    d.bqReg03);
    i2cRead8(ADDR_BQ25895, BQ_REG_ICHG,        d.bqReg04);
    i2cRead8(ADDR_BQ25895, BQ_REG_VREG,        d.bqReg06);
  }
  if (d.fgOk) {
    uint16_t raw = 0;
    i2cRead16(ADDR_MAX17048, MAX_REG_VCELL,  d.fgVcell);
    i2cRead16(ADDR_MAX17048, MAX_REG_SOC,    d.fgSoc);
    i2cRead16(ADDR_MAX17048, MAX_REG_STATUS, d.fgStatus);
    if (i2cRead16(ADDR_MAX17048, MAX_REG_CRATE, raw)) d.fgCrate = (int16_t)raw;
  }
  if (d.typecOk) {
    i2cRead8(ADDR_TUSB320, TYPEC_REG_CURRENT, d.typecCur);
    i2cRead8(ADDR_TUSB320, TYPEC_REG_ATTACH,  d.typecAttach);
  }

  d.sdPresent = (digitalRead(PIN_SD_CD) == LOW);
  d.sdMounted = s_sdMounted;
  if (s_sdMounted) {
    d.sdCardType = (uint8_t)SD.cardType();
    d.sdBytes    = SD.cardSize();
    readSdBootSector(d);
    d.sdRootCount = countRootEntries();
  }
  return d;
}

// ---------------------------- 文本排版 -------------------------------
static void addLine(const char *fmt, ...)
{
  if (s_lineCount >= EPD_LINE_COUNT) return;
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(s_lines[s_lineCount], EPD_LINE_MAX, fmt, ap);
  va_end(ap);
  s_lineCount++;
}

static int16_t lineStep()
{
  return EPD_LINE_STEP;
}

static int16_t firstBaseline()
{
  return EPD_FIRST_BASELINE;
}

// 当前面板能放下多少行（决定要不要显示“附加寄存器信息”）
// 4.2 英寸：(300 - 2 - 15) / 16 + 1 = 18 行（刚好放 17 行基础信息）
// 10.2 英寸：(640 - 2 - 20) / 21 + 1 = 30 行（够放 23 行）
static uint8_t screenLineCapacity()
{
  const int16_t usable = (int16_t)display.height() - 2 - firstBaseline();
  if (usable <= 0) return 1;
  return (uint8_t)(usable / lineStep() + 1);
}

static void buildLines(const EpdData &d)
{
  s_lineCount = 0;

  addLine("墨水屏调试输出");
  addLine("EPD " EPD_MODEL_TEXT);
  addLine("FW " __DATE__ " " __TIME__);
  addLine("CPU %luMHz RAM %lu/%luKB",
          (unsigned long)getCpuFrequencyMhz(),
          (unsigned long)(ESP.getFreeHeap() / 1024),
          (unsigned long)(ESP.getHeapSize() / 1024));
  addLine("PSRAM %luKB free %luKB",
          (unsigned long)(ESP.getPsramSize() / 1024),
          (unsigned long)(ESP.getFreePsram() / 1024));
  addLine("Uptime %lus", (unsigned long)(millis() / 1000));
  addLine("------------------------------------");

  const unsigned found = (unsigned)((d.bqOk ? 1 : 0) + (d.fgOk ? 1 : 0) + (d.typecOk ? 1 : 0));
  addLine("I2C 器件 %u/3", found);
  addLine(" 0x%02X %-9s %s", (unsigned)ADDR_BQ25895, "BQ25895",  d.bqOk    ? "OK" : "NG");
  addLine(" 0x%02X %-9s %s", (unsigned)ADDR_MAX17048, "MAX17048", d.fgOk    ? "OK" : "NG");
  addLine(" 0x%02X %-9s %s", (unsigned)ADDR_TUSB320, "TUSB320",  d.typecOk ? "OK" : "NG");
  addLine("------------------------------------");

  if (d.sdMounted) {
    char sizeText[16];
    formatSize(d.sdBytes, sizeText, sizeof(sizeText));
    addLine("SD 卡 %s %s", cardTypeText(d.sdCardType), sizeText);
    addLine("状态 已挂载 根%lu项", (unsigned long)d.sdRootCount);
    if (d.sdFat) {
      addLine("FAT%u 扇%uB 簇%luKB", (unsigned)d.sdFat, (unsigned)d.sdSectorBytes,
              (unsigned long)(d.sdClusterBytes / 1024));
    } else {
      addLine("FAT? 扇%uB 簇%luKB", (unsigned)d.sdSectorBytes,
              (unsigned long)(d.sdClusterBytes / 1024));
    }
  } else if (d.sdPresent) {
    addLine("SD 卡 已插入 未挂载");
    addLine("状态 挂载失败");
    addLine("提示 查 CS=GPIO14/卡格式");
  } else {
    addLine("SD 卡 未检测到");
    addLine("状态 卡座空 CD=GPIO2");
    addLine("提示 插卡后自动重试");
  }
  addLine("------------------------------------");

  const char *chgText = d.bqOk ? chgStateText(d.bqStatus) : "--";
  if (d.fgOk) {
    unsigned soc = (unsigned)(d.fgSoc / 256);
    if (soc > 100) soc = 100;
    addLine("电池 %.3fV %u%% 充电 %s", d.fgVcell * 78.125e-6, soc, chgText);
  } else if (d.bqOk) {
    addLine("电池 无(0x36 无应答) 充电 %s", chgText);
  } else {
    addLine("电池 -- I2C 无应答");
  }

  // 屏幕够高（10.2 英寸）时，补一屏寄存器级信息
  if (screenLineCapacity() >= s_lineCount + 9) {
    if (d.bqOk) {
      addLine("BQ REG00=0x%02X IINLIM=%umA", (unsigned)d.bqReg00,
              (unsigned)(100 + (d.bqReg00 & 0x3F) * 50));
      addLine("BQ REG04=0x%02X ICHG=%umA", (unsigned)d.bqReg04,
              (unsigned)((d.bqReg04 & 0x7F) * 64));
      addLine("BQ REG03=0x%02X REG06=%umV", (unsigned)d.bqReg03,
              (unsigned)(3840 + ((d.bqReg06 >> 2) & 0x3F) * 16));
      addLine("BQ VBUS=%s CHRG=%s", vbusStateText(d.bqStatus), chgStateText(d.bqStatus));
    }
    if (d.fgOk) {
      addLine("GAUGE CRATE=%+.1f%%/h ST=0x%04X", d.fgCrate * 0.208f, (unsigned)d.fgStatus);
    }
    if (d.typecOk) {
      addLine("TUSB CUR=%u ATTACH=%u", (unsigned)((d.typecCur >> 4) & 0x03),
              (unsigned)(d.typecAttach & 0x01));
    }
    addLine("KEY1=%d KEY2=%d KEY3=%d", digitalRead(PIN_KEY1),
            digitalRead(PIN_KEY2), digitalRead(PIN_KEY3));
    if (d.sdMounted) {
      char usedText[16];
      char totalText[16];
      formatSize(SD.usedBytes(), usedText, sizeof(usedText));
      formatSize(d.sdBytes, totalText, sizeof(totalText));
      addLine("SD 已用 %s / %s", usedText, totalText);
    }
    addLine("I2C %lukHz SPI 4MHz 刷新%lu次",
            (unsigned long)(I2C_FREQ_HZ / 1000UL), (unsigned long)s_refreshCount);
  }
}

// ------------------------------ 刷新 ---------------------------------
static void renderScreen(bool fullRefresh)
{
  pollSdCard();
  s_refreshCount++;
  buildLines(collectData());

  epdFonts.begin(display);                       // 必须绑定绘图目标，否则画字时 gfx 是空指针
  epdFonts.setFont(EPD_FONT);
  epdFonts.setFontMode(1);                       // 1 = 透明背景（不填黑底）
  epdFonts.setForegroundColor(GxEPD_BLACK);
  epdFonts.setBackgroundColor(GxEPD_WHITE);

  // 首帧和“防残影”帧整屏刷新，其余刷新只翻整屏窗口的局部刷新
  if (fullRefresh) display.setFullWindow();
  else             display.setPartialWindow(0, 0, display.width(), display.height());

  const int16_t step  = lineStep();
  const int16_t limit = (int16_t)display.height() - 2;

  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    int16_t y = firstBaseline();
    for (uint8_t i = 0; i < s_lineCount && y <= limit; i++) {
      epdFonts.setCursor(4, y);
      epdFonts.print(s_lines[i]);               // 逐字节 UTF-8 解码，可显示中文
      y += step;
    }
  } while (display.nextPage());

  display.setFullWindow();                       // 复位窗口，避免影响下一次刷新
  display.powerOff();                            // 只关面板驱动电压，EPD_3V3 不断
}

// ----------------------------- 对外接口 ------------------------------
void epdDebugBegin()
{
  Serial.println(F("[EPD] 开启墨水屏调试输出 ..."));

  // 1) EPD_3V3 常开：TPS22918 使能脚保持高电平（板上 100k 下拉，默认断电）
  pinMode(PIN_EPD_PWR_EN, OUTPUT);
  digitalWrite(PIN_EPD_PWR_EN, HIGH);
  delay(20);                                     // 等 EPD_3V3 建立（面板要求 > 10 ms）

  // 2) SPI 与 microSD 共用：SCLK=12 / MISO=13 / MOSI=11（面板不用 MISO）
  SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI, PIN_EPD_CS);

  // 3) 面板初始化。传 0 关掉 GxEPD2 的串口诊断，否则它会 Serial.begin() 改掉波特率
  display.init(0);
  s_ready = true;
  Serial.printf("[EPD] 面板 %s 已初始化，EPD_PWR_EN(GPIO%d) 保持高电平\n",
                EPD_MODEL_TEXT, (int)PIN_EPD_PWR_EN);

  renderScreen(true);                            // 首帧全屏刷新
  s_firstFrameDone = true;
  s_lastRefreshMs  = millis();
  s_partialCount   = 0;
}

void epdDebugUpdate()
{
  if (!s_ready) return;
  if (s_firstFrameDone && (millis() - s_lastRefreshMs < EPD_DEBUG_REFRESH_MS)) return;

  const bool full = (!s_firstFrameDone) || (s_partialCount >= EPD_DEBUG_FULL_EVERY);
  renderScreen(full);

  s_lastRefreshMs  = millis();                   // 以刷新结束时刻重新计时
  s_firstFrameDone = true;
  s_partialCount   = full ? 0 : (uint16_t)(s_partialCount + 1);
}

#endif  // ENABLE_EPD_DEBUG
