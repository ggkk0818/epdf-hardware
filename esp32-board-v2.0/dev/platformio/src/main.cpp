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
//
//  可选开关（默认关闭，确认无误后再打开）：
//    ENABLE_CHARGING  : 配置 BQ25895 并拉低 /CE 允许充电
//    DEMO_EPD_POWER   : 开关一次墨水屏电源（不点亮屏幕）
// =====================================================================

#include <Arduino.h>
#include <Wire.h>
#include "board_pins.h"

// 可选依赖：安装了 Adafruit NeoPixel 才编译 LED 演示
#if __has_include(<Adafruit_NeoPixel.h>)
  #include <Adafruit_NeoPixel.h>
  #define HAVE_NEOPIXEL 1
#endif

// ----------------------------- 开关 ------------------------------
#define ENABLE_CHARGING   0     // 1 = 初始化充电参数并使能充电
#define DEMO_EPD_POWER    0     // 1 = 演示 EPD_3V3 通断一次
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
  bool ok = false;
  Serial.println(F("[BQ25895] 配置并使能充电 ..."));
  i2cWrite8(ADDR_BQ25895, BQ_REG_TERM_TIMER, 0x8D);      // 关看门狗
  i2cWrite8(ADDR_BQ25895, BQ_REG_MODE_CFG,   0x2A);      // 关 OTG，开充电
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
#endif

static void readFuelGauge() {
  bool ok = false;
  uint16_t vcell = i2cRead16(ADDR_MAX17048, MAX_REG_VCELL, &ok);
  if (!ok) { Serial.println(F("[MAX17048] 无响应")); return; }
  uint16_t soc = i2cRead16(ADDR_MAX17048, MAX_REG_SOC, &ok);
  Serial.printf("[MAX17048] 电池 %.3f V   SOC %.2f%%\n",
                vcell * 78.125e-6, soc / 256.0);
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

static void setLed(uint8_t r, uint8_t g, uint8_t b) {
#ifdef HAVE_NEOPIXEL
  static Adafruit_NeoPixel px(1, PIN_LED_DIN, NEO_GRB + NEO_KHZ800);
  static bool init = false;
  if (!init) { px.begin(); px.setBrightness(32); init = true; }
  px.setPixelColor(0, px.Color(r, g, b));
  px.show();
#else
  (void)r; (void)g; (void)b;
  Serial.println(F("[LED] 未安装 Adafruit NeoPixel 库，跳过（见 platformio.ini 注释）"));
#endif
}

// ----------------------------- 主流程 -----------------------------
void setup() {
  // 先把所有板级控制脚置于安全状态
  pinMode(PIN_LED_DIN, OUTPUT);   digitalWrite(PIN_LED_DIN, LOW);
  pinMode(PIN_EPD_PWR_EN, OUTPUT);digitalWrite(PIN_EPD_PWR_EN, LOW);   // 面板保持断电
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
  while (!Serial && (millis() - t0) < 3000) delay(10);
#endif
  delay(200);

  Serial.println();
  Serial.println(F("=================================================="));
  Serial.println(F(" ESP32-S3 墨水屏主板 v2.0 自检"));
  Serial.printf (" 芯片=%s  主频=%lu MHz  PSRAM=%u KB\n",
                 BOARD_NAME, (unsigned long)(getCpuFrequencyMhz()),
                 (unsigned)(ESP.getPsramSize() / 1024));
  Serial.println(F("=================================================="));

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_FREQ_HZ);
  delay(50);

  scanI2C();
  readCharger();
  readFuelGauge();
  readTypeC();
  readKeys();
  setLed(0, 0, 16);   // 蓝色微亮

#if ENABLE_CHARGING
  startCharging();
#endif

#if DEMO_EPD_POWER
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
  static uint32_t tKey = 0, tLed = 0;
  static uint8_t ledStep = 0;

  if (millis() - tKey > 500) {
    tKey = millis();
    static int last1 = 1, last2 = 1, last3 = 1;
    int k1 = digitalRead(PIN_KEY1), k2 = digitalRead(PIN_KEY2), k3 = digitalRead(PIN_KEY3);
    if (k1 != last1) { Serial.printf("KEY1 %s\n", k1 ? "松开" : "按下"); last1 = k1; }
    if (k2 != last2) { Serial.printf("KEY2 %s\n", k2 ? "松开" : "按下"); last2 = k2; }
    if (k3 != last3) { Serial.printf("KEY3 %s\n", k3 ? "松开" : "按下"); last3 = k3; }
  }

  if (millis() - tLed > 1000) {          // 呼吸/换色示意
    tLed = millis();
    static const uint8_t seq[3][3] = {{16, 0, 0}, {0, 16, 0}, {0, 0, 16}};
    setLed(seq[ledStep][0], seq[ledStep][1], seq[ledStep][2]);
    ledStep = (ledStep + 1) % 3;
  }
}
