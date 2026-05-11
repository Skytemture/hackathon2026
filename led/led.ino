#include <FastLED.h>

#define LED_PIN_1 6
#define LED_PIN_2 7

#define NUM_LEDS 30

CRGB leds1[NUM_LEDS];
CRGB leds2[NUM_LEDS];

void setup() {
  FastLED.addLeds<WS2812B, LED_PIN_1, GRB>(leds1, NUM_LEDS);
  FastLED.addLeds<WS2812B, LED_PIN_2, GRB>(leds2, NUM_LEDS);

  FastLED.setBrightness(180);
}

void loop() {
  static uint8_t hue = 0;

  for (int i = 0; i < NUM_LEDS; i++) {

    // 第一條 正方向
    leds1[i] = CHSV(hue + i * 8, 255, 255);

    // 第二條 反方向
    leds2[NUM_LEDS - 1 - i] =
        CHSV(hue + i * 8, 255, 255);
  }

  FastLED.show();

  hue++;
  delay(20);
}