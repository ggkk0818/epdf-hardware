// =====================================================================
//  ESP32-S3 墨水屏主板 v2.0 - 板级自检 Demo (PlatformIO + Arduino)
//
//  默认行为（安全，不改板状态）：
//    1. I2C 总线扫描
//    2. 读 BQ25895 状态/故障（只读，不使能充电）
//    3. 读 MAX17048 电压与 SOC
//    4. 读 TUSB320 器件 ID 与检测到的电流档位
//    5. 读三颗用户按键 + 卡检测
//    6. 点亮 LED1（若安装了 Adafruit NeoPixel）
//    7. loop 循环：每分钟上报一次 MAX17048 状态，LED 随充电状态变化
//       （充电中 = 红色常亮，充满 = 绿色常亮，其余 = 呼吸换色）
//    8. loop 循环：每 5 s 在墨水屏上刷新一屏调试信息
//       （3 个 I2C 器件 + microSD 卡 + 电池/充电状态；仅在 ENABLE_EPD_DEBUG = 1 时）
//
//  可选开关（默认关闭，确认无误后再打开）：
//    ENABLE_CHARGING  : 配置 BQ25895 并拉低 /CE 允许充电
//    DEMO_EPD_POWER   : 开关一次墨水屏电源（不点亮屏幕）
//    ENABLE_EPD_DEBUG : 墨水屏输出调试信息（0=关闭 1=开启）
//                       开关与面板选择定义在 include/epd_debug.h，见下面的“开关”一节
// =====================================================================

#include <Arduino.h>
#include <Wire.h>
#include "board_pins.h"
#include "epd_debug.h"      // 墨水屏调试输出（开关 ENABLE_EPD_DEBUG / 面板选择都在这里）

// 可选依赖：安装了 Adafruit NeoPixel 才编译 LED 演示
#if __has_include(<Adafruit_NeoPixel.h>)
  #include <Adafruit_NeoPixel.h>
  #define HAVE_NEOPIXEL 1
#endif

// ----------------------------- 开关 ------------------------------
// 墨水屏输出开关（0 = 关闭，1 = 开启）定义在 include/epd_debug.h：
//     #define ENABLE_EPD_DEBUG 0
// 那里同时放面板选择：默认 GDEY042T81；要换 GDEM102T91，在 platformio.ini 的
// build_flags 里加 -DEPD_PANEL_GDEM102T91=1。两个值必须让 epd_debug.cpp 也看到，
// 所以不放本文件（编译单元之间只能通过头文件或 -D 共享宏）。
#define ENABLE_CHARGING   1     // 1 = 初始化充电参数并使能充电
#define DEMO_EPD_POWER    0     // 1 = 演示 EPD_3V3 通断一次（ENABLE_EPD_DEBUG=1 时自动跳过）
#define ICHG_REG_VALUE    0x0E  // 896 mA = 14 × 64 mA（按硬件热设计）
#define IINLIM_REG_VALUE  0x10  // 900 mA = 100 mA + 16 × 50 mA
#define ITERM_REG_VALUE   0x11  // IPRECHG 128 mA / ITERM 128 mA
#define VREG_REG_VALUE    0x5E  // 4.208 V（默认值，单节锂电）

// -------------------------- I2C 辅助 -----------------------------
static bool i2cWrite8(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

static bool i2cRead(uint8_t addr, uint8_t reg, uint8_t *buf, size_t len) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, (int)len) != (int)len) return false;
  for (size_t i = 0; i < len; i++) buf[i] = Wire.read();
  return true;
}

static uint8_t i2cRead8(uint8_t addr, uint8_t reg, bool *ok) {
  uint8_t v = 0;
  bool r = i2cRead(addr, reg, &v, 1);
  if (ok) *ok = r;
  return v;
}

static uint16_t i2cRead16(uint8_t addr, uint8_t reg, bool *ok) {
  uint8_t b[2] = {0, 0};
  bool r = i2cRead(addr, reg, b, 2);
  if (ok) *ok = r;
  return ((uint16_t)b[0] << 8) | b[1];
}

// MAX17048 挂在 BAT_BUS 上，必须真电池接上才应答；电池拔掉 / 电池线断开时 0x36 会消失。
// 注意：BQ25895 在“电池缺失”时会把 BAT 脚稳到充电调节电压（≈VREG 4.2 V），
// 所以“BAT 脚有电压”不能用来判断电池是否在，只有电量计应答才可信。
//
// 先用最轻的“地址探测”（只发地址看 ACK）判断在不在：器件不存在时 NACK 不会让
// ESP-IDF 打印 i2c_master_transmit_receive failed 的报错；确认在了再做寄存器回读。
static bool i2cPing(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static bool batteryPresent() {
  if (!i2cPing(ADDR_MAX17048)) return false;
  bool ok = false;
  (void)i2cRead16(ADDR_MAX17048, MAX_REG_VCELL, &ok);
  return ok;
}

// -------------------------- 各器件读取 ---------------------------
static void scanI2C() {
  Serial.println(F("[I2C] 扫描 0x08-0x77 ..."));
  uint8_t found = 0;
  for (uint8_t a = 0x08; a <= 0x77; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      const char *name = "";
      if (a == ADDR_BQ25895) name = "BQ25895 充电器";
      else if (a == ADDR_MAX17048) name = "MAX17048 电量计";
      else if (a == ADDR_TUSB320) name = "TUSB320LI Type-C";
      Serial.printf("  发现 0x%02X  %s\n", a, name);
      found++;
    }
  }
  Serial.printf("[I2C] 共 %u 个器件（期望 3 个：0x6A / 0x36 / 0x47）\n", found);
}

static void readCharger() {
  bool ok = false;
  uint8_t st = i2cRead8(ADDR_BQ25895, BQ_REG_STATUS, &ok);
  if (!ok) { Serial.println(F("[BQ25895] 无响应")); return; }

  const char *vbusStat;
  switch ((st >> 5) & 0x07) {
    case 0: vbusStat = "无输入";          break;
    case 1: vbusStat = "USB SDP(100mA)";  break;
    case 2: vbusStat = "USB CDP(500mA)";  break;
    case 3: vbusStat = "USB DCP";         break;
    case 5: vbusStat = "未知适配器";       break;
    case 7: vbusStat = "可调压适配器";     break;
    default: vbusStat = "保留";           break;
  }
  static const char *chrgStat[] = {"未充电", "预充", "快充", "充电完成"};
  uint8_t cs = (st & BQ_STATUS_CHRG_MASK) >> BQ_STATUS_CHRG_SHIFT;

  Serial.printf("[BQ25895] 输入=%s  充电=%s  电源OK=%d  电池低=%d\n",
                vbusStat, chrgStat[cs & 0x03],
                (st & BQ_STATUS_PG) ? 1 : 0,
                (st & 0x01) ? 1 : 0);

  uint8_t r0 = i2cRead8(ADDR_BQ25895, BQ_REG_INPUT_LIMIT, &ok);
  uint8_t r4 = i2cRead8(ADDR_BQ25895, BQ_REG_ICHG, &ok);
  uint8_t r6 = i2cRead8(ADDR_BQ25895, BQ_REG_VREG, &ok);
  uint8_t r7 = i2cRead8(ADDR_BQ25895, BQ_REG_TERM_TIMER, &ok);
  uint16_t iinlim = 100 + (r0 & 0x3F) * 50;              // mA
  uint16_t ichg   = (r4 & 0x7F) * 64;                    // mA
  uint16_t vreg   = 3840 + ((r6 >> 2) & 0x3F) * 16;      // mV
  Serial.printf("[BQ25895] REG00=0x%02X(IINLIM %umA, EN_ILIM=%d) REG04=0x%02X(ICHG %umA)\n",
                r0, iinlim, (r0 >> 6) & 1, r4, ichg);
  Serial.printf("[BQ25895] REG06=0x%02X(VREG %umV) REG07=0x%02X(看门狗=%s)\n",
                r6, vreg, r7, (((r7 >> 4) & 0x03) == 0) ? "关闭" : "开启(40/80s)");

  // 故障寄存器：连续读两次才清标志
  uint8_t f1 = i2cRead8(ADDR_BQ25895, BQ_REG_FAULT, &ok);
  uint8_t f2 = i2cRead8(ADDR_BQ25895, BQ_REG_FAULT, &ok);
  if (f1 || f2) {
    Serial.printf("[BQ25895] FAULT=0x%02X (看门狗=%d 升压=%d 充电=%d 电池=%d NTC=%d)\n",
                  f2, (f2 >> 7) & 1, (f2 >> 6) & 1, (f2 >> 4) & 0x03,
                  (f2 >> 3) & 1, f2 & 0x07);
  } else {
    Serial.println(F("[BQ25895] 无故障标志"));
  }
}

#if ENABLE_CHARGING
static void startCharging() {
  // 没有电池时绝对不要使能充电：BQ25895 会把 BAT 脚稳到调节电压、反复“充完→重充”，
  // CHRG_STAT 就在 快充(2) / 充电完成(3) 之间抖动，日志被刷屏、LED 也红绿乱闪。
  if (!batteryPresent()) {
    digitalWrite(PIN_CHG_CE, HIGH);
    Serial.println(F("[BQ25895] 未检测到电池（MAX17048 0x36 无应答）→ 跳过充电使能"));
    return;
  }

  bool ok = false;
  Serial.println(F("[BQ25895] 配置并使能充电 ..."));
  i2cWrite8(ADDR_BQ25895, BQ_REG_TERM_TIMER, 0x8D);      // 关看门狗
  i2cWrite8(ADDR_BQ25895, BQ_REG_MODE_CFG,   BQ_MODE_CFG_OTG_OFF_CHG_ON);  // 关 OTG(bit5=0)，开充电(bit4=1)
  i2cWrite8(ADDR_BQ25895, BQ_REG_INPUT_LIMIT, IINLIM_REG_VALUE);
  i2cWrite8(ADDR_BQ25895, BQ_REG_ICHG,        ICHG_REG_VALUE);
  i2cWrite8(ADDR_BQ25895, BQ_REG_ITERM_IPRE,  ITERM_REG_VALUE);
  i2cWrite8(ADDR_BQ25895, BQ_REG_VREG,        VREG_REG_VALUE);

  // 回读校验
  uint8_t r0 = i2cRead8(ADDR_BQ25895, BQ_REG_INPUT_LIMIT, &ok);
  uint8_t r4 = i2cRead8(ADDR_BQ25895, BQ_REG_ICHG, &ok);
  uint8_t r7 = i2cRead8(ADDR_BQ25895, BQ_REG_TERM_TIMER, &ok);
  if (!ok || r0 != IINLIM_REG_VALUE || r4 != ICHG_REG_VALUE || ((r7 >> 4) & 0x03) != 0) {
    Serial.println(F("[BQ25895] 回读不匹配，保持禁充"));
    return;
  }
  digitalWrite(PIN_CHG_CE, LOW);                          // 允许充电
  Serial.println(F("[BQ25895] 已使能充电（/CE 拉低）"));
}

static void stopCharging(const __FlashStringHelper *why) {
  digitalWrite(PIN_CHG_CE, HIGH);
  Serial.printf("[BQ25895] 停止充电：%s（/CE 拉高）\n", why);
}

// 按电池在位情况决定是否配置/使能充电（仅在状态变化时动作）
static void updateChargeEnable(bool present) {
  static int8_t last = -1;                 // -1=未知 0=无电池 1=有电池
  int8_t now = present ? 1 : 0;
  if (now == last) return;
  last = now;
  if (present) startCharging();
  else         stopCharging(F("电池已拔出或电池支路断开"));
}

// setup() 里调用：显式给出初始状态，保证首次一定会执行一次
static void startChargingIfBatteryPresent() {
  updateChargeEnable(batteryPresent());
}
#endif
// ------------------------- 充电状态查询 ---------------------------
// CHRG_STAT[1:0]（BQ25895 REG0B bit4:3）：0=未充电 1=预充 2=快充 3=充电完成
enum ChgState : uint8_t {
  CHG_NOT_CHARGING = 0,
  CHG_PRE_CHARGE   = 1,
  CHG_FAST_CHARGE  = 2,
  CHG_DONE         = 3,
  CHG_UNKNOWN      = 0xFF,   // I2C 读取失败
};

static const char *chgStateName(ChgState s) {
  switch (s) {
    case CHG_PRE_CHARGE:   return "预充";
    case CHG_FAST_CHARGE:  return "快充";
    case CHG_DONE:         return "充满";
    case CHG_NOT_CHARGING: return "未充电";
    default:               return "未知";
  }
}

static ChgState readChargeState() {
  bool ok = false;
  uint8_t st = i2cRead8(ADDR_BQ25895, BQ_REG_STATUS, &ok);
  if (!ok) return CHG_UNKNOWN;
  return (ChgState)((st & BQ_STATUS_CHRG_MASK) >> BQ_STATUS_CHRG_SHIFT);
}

// 详细充电状态上报：CHRG_STAT 只在“变化”时才打印，若只靠变化事件，
// 排查“插了 USB 到底有没有在充”会看不到任何输出。这里做周期性全量上报。
static void reportChargeStatus() {
  bool ok = false;
  uint8_t st   = i2cRead8(ADDR_BQ25895, BQ_REG_STATUS, &ok);
  if (!ok) { Serial.println(F("[BQ25895] REG0B 读取失败（I2C 无应答）")); return; }
  uint8_t r3   = i2cRead8(ADDR_BQ25895, BQ_REG_MODE_CFG, &ok);
  uint8_t r0   = i2cRead8(ADDR_BQ25895, BQ_REG_INPUT_LIMIT, &ok);
  uint8_t r4   = i2cRead8(ADDR_BQ25895, BQ_REG_ICHG, &ok);

  static const char *vbusName[] = {
    "无输入", "USB SDP(100mA)", "USB CDP(500mA)", "USB DCP",
    "保留", "未知适配器(500mA)", "保留", "可调压适配器"
  };
  static const char *chrgName[] = {"未充电", "预充", "快充", "充电完成"};
  uint8_t vs = (st >> 5) & 0x07;
  uint8_t cs = (st & BQ_STATUS_CHRG_MASK) >> BQ_STATUS_CHRG_SHIFT;

  Serial.printf("[充电] VBUS=%s  PG=%d  CHRG_STAT=%s(%u)  VSYS_STAT=%d  IINLIM=%umA  ICHG=%umA\n",
                vbusName[vs], (st & BQ_STATUS_PG) ? 1 : 0,
                chrgName[cs & 0x03], cs, st & 0x01,
                100 + (r0 & 0x3F) * 50, (r4 & 0x7F) * 64);
  // REG03: bit4 = CHG_CONFIG(1=允许充电)，bit5 = OTG_CONFIG(1=升压输出)；正确值 0x1A = 关 OTG、开充电
  Serial.printf("[充电] REG03=0x%02X  CHG_CONFIG(bit4)=%u  OTG_CONFIG(bit5)=%u  /CE(GPIO47)=%d(0=允许充电)\n",
                r3, (unsigned)((r3 >> 4) & 1), (unsigned)((r3 >> 5) & 1), digitalRead(PIN_CHG_CE));
  if (vs == 0) {
    Serial.println(F("[充电] 判定：BQ25895 认为 VBUS 无输入 → 检查 USB 线/口、F1、U2.VIN"));
  } else if (!batteryPresent()) {
    Serial.println(F("[充电] 判定：未检测到电池 → 已保持禁充（/CE 高）。此状态下 BAT 脚会被稳到"
                     "≈4.2 V，MAX17048 读数（如 SOC>100%）是假值，可忽略"));
  } else if (cs == 0) {
    Serial.println(F("[充电] 判定：VBUS 正常且电池在位，但没有充电电流 → 查电池(BAT)支路、"
                     "电芯保护板、温控(TS)、以及 U2.BAT 到电池座是否通路"));
  }
}

// 读取电量计（MAX17048）：电压 / SOC / 充放电速率 / STATUS / ALRT
static void readFuelGauge() {
  if (!i2cPing(ADDR_MAX17048)) {
    Serial.println(F("[MAX17048] 无响应（未装电池 / 电池支路断开）"));
    return;
  }
  bool ok = false;
  uint16_t vcell = i2cRead16(ADDR_MAX17048, MAX_REG_VCELL, &ok);
  if (!ok) { Serial.println(F("[MAX17048] 无响应（未装电池 / 电池支路断开）")); return; }
  uint16_t soc    = i2cRead16(ADDR_MAX17048, MAX_REG_SOC, &ok);
  int16_t  crate  = (int16_t)i2cRead16(ADDR_MAX17048, MAX_REG_CRATE, &ok);
  uint16_t status = i2cRead16(ADDR_MAX17048, MAX_REG_STATUS, &ok);
  float rate = crate * 0.208f;                 // %/h：正=充电，负=放电
  bool alert = (digitalRead(PIN_FG_ALRT) == LOW);
  Serial.printf("[MAX17048] 电池 %.3f V   SOC %.2f%%  速率 %+.1f %%/h(%s)  STATUS=0x%04X  ALRT=%s\n",
                vcell * 78.125e-6, soc / 256.0, rate, (rate >= 0.0f) ? "充电" : "放电",
                status, alert ? "低(报警)" : "高(正常)");
}

static void readTypeC() {
  // 器件 ID：寄存器 0x06..0x00 依次为 'T','U','S','B','3','2','0'
  char id[8] = {0};
  for (int i = 0; i < 7; i++) {
    bool ok = false;
    id[i] = (char)i2cRead8(ADDR_TUSB320, 6 - i, &ok);
    if (!ok) { Serial.println(F("[TUSB320] 无响应")); return; }
  }
  bool ok = false;
  uint8_t cur = i2cRead8(ADDR_TUSB320, TYPEC_REG_CURRENT, &ok);
  uint8_t att = i2cRead8(ADDR_TUSB320, TYPEC_REG_ATTACH, &ok);
  static const char *det[] = {"默认(500/900mA)", "中(1.5A)", "充电配件(500mA)", "高(3A)"};
  Serial.printf("[TUSB320] ID=\"%s\"  检测电流档=%s  已连接=%d\n",
                id, det[(cur >> 4) & 0x03], att & 0x01);
  if (att & 0x10) i2cWrite8(ADDR_TUSB320, TYPEC_REG_ATTACH, att);  // 写1清中断标志
}

static void readKeys() {
  Serial.printf("[按键] KEY1=%d KEY2=%d KEY3=%d (1=松开, 0=按下)  插卡=%d\n",
                digitalRead(PIN_KEY1), digitalRead(PIN_KEY2), digitalRead(PIN_KEY3),
                digitalRead(PIN_SD_CD) == LOW ? 1 : 0);
}

// ------------------------------- LED ------------------------------
// 状态语义：充电中 = 红色常亮，充满 = 绿色常亮，其余 = 呼吸换色（见 loop）
#define LED_BRIGHT        32    // WS2812 整体亮度（0-255）
#define LED_BREATH_LEVEL  16    // 呼吸/换色时的 RGB 分量（暗）
#define LED_STEADY_LEVEL  255   // 常亮时的 RGB 分量（亮）

static void setLed(uint8_t r, uint8_t g, uint8_t b, uint8_t bright = LED_BRIGHT) {
#ifdef HAVE_NEOPIXEL
  static Adafruit_NeoPixel px(1, PIN_LED_DIN, NEO_GRB + NEO_KHZ800);
  static bool init = false;
  if (!init) { px.begin(); init = true; }
  px.setBrightness(bright);
  px.setPixelColor(0, px.Color(r, g, b));
  px.show();
#else
  (void)r; (void)g; (void)b; (void)bright;
  Serial.println(F("[LED] 未安装 Adafruit NeoPixel 库，跳过（见 platformio.ini 注释）"));
#endif
}

// LED 显示模式：呼吸换色 / 充电中（红常亮）/ 充满（绿常亮）/ 未装电池（黄慢闪）
enum LedMode : uint8_t { LED_MODE_BREATH = 0, LED_MODE_CHARGING, LED_MODE_FULL, LED_MODE_NOBAT };

static LedMode ledModeFor(ChgState s, bool battPresent) {
  if (!battPresent) return LED_MODE_NOBAT;   // 没电池时 CHRG_STAT 会抖动，优先按“无电池”显示
  if (s == CHG_PRE_CHARGE || s == CHG_FAST_CHARGE) return LED_MODE_CHARGING;
  if (s == CHG_DONE) return LED_MODE_FULL;
  return LED_MODE_BREATH;                  // 未充电 / I2C 读取失败
}

static void applyLedMode(LedMode m) {
  if (m == LED_MODE_CHARGING)     setLed(LED_STEADY_LEVEL, 0, 0);   // 红色常亮
  else if (m == LED_MODE_FULL)    setLed(0, LED_STEADY_LEVEL, 0);   // 绿色常亮
  // LED_MODE_BREATH / LED_MODE_NOBAT 的逐帧刷新由 loop 处理
}

// ----------------------------- 主流程 -----------------------------
void setup() {
  // 先把所有板级控制脚置于安全状态
  pinMode(PIN_LED_DIN, OUTPUT);   digitalWrite(PIN_LED_DIN, LOW);
  pinMode(PIN_EPD_PWR_EN, OUTPUT);digitalWrite(PIN_EPD_PWR_EN, LOW);   // 面板先断电，EPD 调试输出时由 epdDebugBegin() 拉高并常开
  pinMode(PIN_EPD_CS, OUTPUT);    digitalWrite(PIN_EPD_CS, HIGH);
  pinMode(PIN_EPD_DC, OUTPUT);    digitalWrite(PIN_EPD_DC, LOW);
  pinMode(PIN_EPD_RST, OUTPUT);   digitalWrite(PIN_EPD_RST, HIGH);
  pinMode(PIN_SD_CS, OUTPUT);     digitalWrite(PIN_SD_CS, HIGH);
  pinMode(PIN_CHG_CE, OUTPUT);    digitalWrite(PIN_CHG_CE, HIGH);      // 禁止充电（安全默认）

  pinMode(PIN_KEY1, INPUT_PULLUP);
  pinMode(PIN_KEY2, INPUT_PULLUP);
  pinMode(PIN_KEY3, INPUT_PULLUP);
  pinMode(PIN_SD_CD, INPUT_PULLUP);
  pinMode(PIN_CHG_INT, INPUT_PULLUP);
  pinMode(PIN_TYPEC_INT, INPUT_PULLUP);
  pinMode(PIN_FG_ALRT, INPUT_PULLUP);

  Serial.begin(115200);
#if ARDUINO_USB_CDC_ON_BOOT
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0) < 5000) delay(10);
#endif
  delay(2000);

  Serial.println();
  Serial.println(F("=================================================="));
  Serial.println(F(" ESP32-S3 墨水屏主板 v2.0 自检"));
  Serial.printf (" 芯片=%s  主频=%lu MHz  PSRAM=%u KB\n",
                 BOARD_NAME, (unsigned long)(getCpuFrequencyMhz()),
                 (unsigned)(ESP.getPsramSize() / 1024));
  Serial.printf (" 墨水屏调试输出=%s\n", ENABLE_EPD_DEBUG ? "开启" : "关闭");
  Serial.println(F("=================================================="));

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_FREQ_HZ);
  delay(50);

  scanI2C();
  readCharger();
  readFuelGauge();
  readTypeC();
  readKeys();
  setLed(0, 0, LED_BREATH_LEVEL);   // 蓝色微亮（进入 loop 后由充电状态接管）

#if ENABLE_CHARGING
  // 按电池在位情况决定是否使能充电（没电池时保持 /CE 高电平）
  startChargingIfBatteryPresent();
#endif

  // 墨水屏调试输出：面板上电（EPD_PWR_EN 保持高电平）+ 首帧全屏刷新。
  // ENABLE_EPD_DEBUG = 0 时这是空函数，不产生任何代码。
  epdDebugBegin();

  // 电源脉冲演示与“EPD 调试输出”互斥：调试输出要求 EPD_3V3 常开，不能再断电
#if DEMO_EPD_POWER && !ENABLE_EPD_DEBUG
  Serial.println(F("[EPD] 上电脉冲演示（不刷新屏幕）"));
  digitalWrite(PIN_EPD_PWR_EN, HIGH); delay(50);
  digitalWrite(PIN_EPD_PWR_EN, LOW);
#endif

  if (digitalRead(PIN_CHG_INT) == LOW)    Serial.println(F("[提示] BQ25895 /INT 处于低电平，有事件待读"));
  if (digitalRead(PIN_TYPEC_INT) == LOW)  Serial.println(F("[提示] TUSB320 INT_N 处于低电平，有事件待读"));
  if (digitalRead(PIN_FG_ALRT) == LOW)    Serial.println(F("[提示] MAX17048 ALRT 处于低电平（低电量/报警）"));
  Serial.println(F("--- 自检结束，进入按键轮询 ---"));
}

void loop() {
  static uint32_t tKey = 0, tLed = 0, tChg = 0, tGauge = 0, tChgReport = 0, tBatt = 0;
  static uint8_t ledStep = 0;
  static ChgState chgState = CHG_UNKNOWN;
  static LedMode  ledMode  = LED_MODE_BREATH;
  // 状态变化去抖：没电池时 BQ25895 会在 快充/充电完成 之间抖动，
  // 直接打印会把日志刷屏，必须先连续稳定一段时间再采纳。
  static ChgState candState = CHG_UNKNOWN;
  static uint32_t candSince = 0;
  static bool battPresent = false;

  // ---- 按键事件（每 500 ms 轮询一次电平变化）----
  if (millis() - tKey > 500) {
    tKey = millis();
    static int last1 = 1, last2 = 1, last3 = 1;
    int k1 = digitalRead(PIN_KEY1), k2 = digitalRead(PIN_KEY2), k3 = digitalRead(PIN_KEY3);
    if (k1 != last1) { Serial.printf("KEY1 %s\n", k1 ? "松开" : "按下"); last1 = k1; }
    if (k2 != last2) { Serial.printf("KEY2 %s\n", k2 ? "松开" : "按下"); last2 = k2; }
    if (k3 != last3) { Serial.printf("KEY3 %s\n", k3 ? "松开" : "按下"); last3 = k3; }
  }

  // ---- 电池在位检测 + 充电使能（每 3 s，用地址探测，不产生 I2C 报错）----
  if (millis() - tBatt > 3000) {
    tBatt = millis();
    bool now = batteryPresent();
    if (now != battPresent) {
      battPresent = now;
      Serial.printf("[电池] %s\n", battPresent ? "检测到电池" : "未检测到电池（MAX17048 0x36 无应答）");
    }
#if ENABLE_CHARGING
    updateChargeEnable(battPresent);
#endif
  }

  // ---- 充电状态（每 500 ms 采样，连续稳定 1.5 s 才认定并打印）----
  if (millis() - tChg > 500) {
    tChg = millis();
    ChgState s = readChargeState();
    if (s != candState) { candState = s; candSince = millis(); }
    bool stable = (s != CHG_UNKNOWN) && (millis() - candSince >= 1500);
    // 没有电池时不报告“快充/充满”这类变化（此时数值必然抖动，没有意义）；
    // 只允许把 CHG_UNKNOWN 归一成“未充电”一次，让状态有初值
    bool firstInit  = (chgState == CHG_UNKNOWN && s == CHG_NOT_CHARGING);
    bool reportable = firstInit || (battPresent && s != chgState);
    if (stable && reportable) {
      Serial.printf("[BQ25895] 充电状态：%s -> %s\n",
                    chgStateName(chgState), chgStateName(s));
      chgState = s;
    }
  }

  // ---- 每 5 s 做一次全量充电状态上报（不依赖“变化”事件，便于插拔 USB 观察）----
  if (millis() - tChgReport > 5000) {
    tChgReport = millis();
    reportChargeStatus();
  }

  // ---- LED：充电中=红常亮，充满=绿常亮，无电池=黄色慢闪，其余=呼吸换色 ----
  LedMode want = ledModeFor(chgState, battPresent);
  if (want != ledMode) {
    ledMode = want;
    ledStep = 0;
    if (ledMode == LED_MODE_BREATH)      tLed = millis() - 1000;   // 回到呼吸时立刻刷新一帧
    else if (ledMode == LED_MODE_NOBAT)  tLed = millis() - 500;    // 立刻刷一帧黄色
    else                                 applyLedMode(ledMode);
  }

  if (ledMode == LED_MODE_BREATH && millis() - tLed > 1000) {   // 呼吸/换色示意
    tLed = millis();
    static const uint8_t seq[3][3] = {{LED_BREATH_LEVEL, 0, 0},
                                      {0, LED_BREATH_LEVEL, 0},
                                      {0, 0, LED_BREATH_LEVEL}};
    setLed(seq[ledStep][0], seq[ledStep][1], seq[ledStep][2]);
    ledStep = (ledStep + 1) % 3;
  } else if (ledMode == LED_MODE_NOBAT && millis() - tLed > 500) {   // 黄色慢闪：没装电池
    tLed = millis();
    ledStep ^= 1;
    if (ledStep) setLed(LED_BREATH_LEVEL, LED_BREATH_LEVEL, 0);
    else         setLed(0, 0, 0);
  }

  // ---- 每分钟上报一次 MAX17048 状态 ----
  if (millis() - tGauge >= 60000UL) {
    tGauge = millis();
    Serial.printf("---- 周期上报 t=%lus ----\n", (unsigned long)(millis() / 1000));
    readFuelGauge();
  }

  // ---- 墨水屏调试信息（每 5 s 一屏；刷新期间会阻塞几百毫秒~几秒）----
  // ENABLE_EPD_DEBUG = 0 时这是空函数，不产生任何代码。
  epdDebugUpdate();
}
