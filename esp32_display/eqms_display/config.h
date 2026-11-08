// ---------------------------------------------------------------------------
// EQMS P10 / HUB12 display panel - hardware and default settings
//
// Change the pin numbers here to match your ESP32 board and wiring.
// The values below are safe for a plain ESP32 DevKit (ESP32-WROOM-32).
// ---------------------------------------------------------------------------
#pragma once

// Size of ONE P10 module in pixels (32 x 16 is the normal HUB12 P10 panel).
#define PANEL_PIXEL_WIDTH 32
#define PANEL_PIXEL_HEIGHT 16

// How many P10 modules are chained. Keep 1 x 1 for a single board.
// For 2 modules side by side use 2 and 1.
#define PANEL_MODULES_WIDE 1
#define PANEL_MODULES_HIGH 1

// HUB12 connector wiring (ESP32 GPIO -> HUB12 pin).
//   A / B   : row address (1/4 scan)
//   LAT/STB : latch
//   CLK/SCK : shift clock
//   OE      : output enable (brightness PWM)
//   DATA/R1 : serial data
// Pin C and D are not used by HUB12 panels.
#define PIN_A 25
#define PIN_B 26
#define PIN_C -1
#define PIN_D -1
#define PIN_LATCH 27
#define PIN_SCK 18
#define PIN_OE 4
#define PIN_DATA 23

// Push button between this GPIO and GND. Hold it for ~1.5 s while the device
// is running to start the Wi-Fi configuration access point.
// GPIO 0 is the BOOT button on most ESP32 DevKit boards.
#define CONFIG_BUTTON_PIN 0
#define CONFIG_BUTTON_HOLD_MS 1500

// Captive configuration access point. The last 4 hex digits of the MAC address
// are appended to the SSID, e.g. EQMS-Display-3F21.
#define CONFIG_AP_PREFIX "EQMS-Display-"
#define CONFIG_AP_PASSWORD "eqms1234"

// Defaults used on a factory-fresh board. Leave the Wi-Fi SSID empty so the
// board starts in configuration mode on first boot.
#define DEFAULT_WIFI_SSID ""
#define DEFAULT_WIFI_PASSWORD ""
#define DEFAULT_SERVER_HOST ""
#define DEFAULT_SERVER_PORT 8000
#define DEFAULT_COUNTER_ID 1
#define DEFAULT_BRIGHTNESS 70      // percent, 0..100
#define DEFAULT_FONT_SCALE 2       // 1..4 (2 = readable on a single 32x16 panel)

// Networking timings (milliseconds).
#define WIFI_CONNECT_TIMEOUT_MS 20000
#define WS_RECONNECT_INTERVAL_MS 5000
#define SNAPSHOT_INTERVAL_WS_MS 30000   // WebSocket is live: reconcile rarely
#define SNAPSHOT_INTERVAL_NO_WS_MS 3000 // WebSocket down: poll faster
#define HTTP_TIMEOUT_MS 2500

// Display timings (milliseconds).
#define SCROLL_STEP_MS 55
#define FLASH_DURATION_MS 1400
#define FLASH_STEP_MS 200
