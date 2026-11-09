/* ---------------------------------------------------------------------------
 * EQMS - ESP32 + P10 (HUB12, 1/4 scan) counter display
 *
 * What it does
 *   - Shows the ticket number that the linked EQMS counter is currently calling.
 *   - Receives calls instantly over the EQMS WebSocket
 *     (ws://<server>/ws/counter-display/<counter-id>/) and reconciles with
 *     /display/api/counter/<counter-id>/ when it (re)connects.
 *   - Hold the config button (GPIO 0 by default) for ~1.5 s to start a Wi-Fi
 *     access point with a setup page where you can choose the network/password,
 *     server address, counter ID, brightness and font size.
 *
 * Required Arduino libraries (Library Manager):
 *   - FansElectronics_DMD32   (HUB12 / P10 driver)
 *   - WebSockets              (Links2004 arduinoWebSockets)
 *   - ArduinoJson             (v7)
 *
 * Wiring and first-start instructions: ../README.md
 * ------------------------------------------------------------------------ */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <FansElectronics_DMD32.h>
#include <fonts/Font5x7b.h>
#include <fonts/Font3x5.h>

#include "config.h"
#include "portal_page.h"

// ---------------------------------------------------------------------------
// Settings kept in NVS
// ---------------------------------------------------------------------------
struct DeviceSettings {
  String wifiSsid;
  String wifiPassword;
  String serverHost;
  uint16_t serverPort;
  uint16_t counterId;
  uint8_t brightness;   // 0..100 %
  uint8_t fontScale;    // 1..4
};

enum DeviceMode {
  MODE_RUN,
  MODE_CONFIG,
};

FansElectronics_DMD32 dmd;
WebServer server(80);
DNSServer dnsServer;
WebSocketsClient ws;
Preferences prefs;

DeviceSettings cfg;
DeviceMode mode = MODE_RUN;

String apSsid;
String mdnsHost;
String configText;

bool webServerStarted = false;
bool wsStarted = false;
bool wsConnected = false;
bool needSnapshot = true;

uint32_t lastSnapshotAt = 0;
uint32_t lastWifiRetryAt = 0;
uint8_t snapshotFailures = 0;

// What the panel is showing right now.
String currentTicket;
String lastLine;

bool hasTransient = false;
String transientText;
uint32_t transientUntil = 0;

uint32_t flashStart = 0;
bool lastFlashVisible = true;

// The DMD library must have update() called every ~1 ms to advance the 1/4-scan
// refresh. Calling it only from loop() means any blocking network call
// (WebSocket reconnect, HTTP snapshot, Serial) freezes the scan, which shows up
// as flicker/waveform dimming or the panel going dark for a moment.
// This task owns dmd.update() so the panel keeps scanning independently of the
// main loop. It is pinned to the same core as loop(), so they time-slice and a
// blocked loop still lets the refresh run.
TaskHandle_t displayTaskHandle = NULL;

void displayRefreshTask(void *param) {
  (void)param;
  for (;;) {
    dmd.update();
    // 1 FreeRTOS tick = 1 ms: matches the library's refresh interval and also
    // yields to the idle/watchdog task.
    vTaskDelay(1);
  }
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
static uint8_t percentToDuty(uint8_t percent) {
  return (uint8_t)((uint16_t)constrain((int)percent, 0, 100) * 255u / 100u);
}

static String htmlEscape(const String &value) {
  String out;
  out.reserve(value.length() + 8);
  for (size_t i = 0; i < value.length(); ++i) {
    char c = value.charAt(i);
    switch (c) {
      case '&': out += F("&amp;"); break;
      case '<': out += F("&lt;"); break;
      case '>': out += F("&gt;"); break;
      case '"': out += F("&quot;"); break;
      case '\'': out += F("&#39;"); break;
      default: out += c; break;
    }
  }
  return out;
}

static String normalizeHost(String host, uint16_t &port) {
  host.trim();
  if (host.startsWith("http://")) host = host.substring(7);
  else if (host.startsWith("https://")) host = host.substring(8);

  int slash = host.indexOf('/');
  if (slash >= 0) host = host.substring(0, slash);

  int colon = host.lastIndexOf(':');
  if (colon > 0) {
    long parsedPort = host.substring(colon + 1).toInt();
    if (parsedPort > 0 && parsedPort <= 65535) {
      port = (uint16_t)parsedPort;
      host = host.substring(0, colon);
    }
  }
  host.trim();
  return host;
}

// ---------------------------------------------------------------------------
// NVS
// ---------------------------------------------------------------------------
void loadSettings() {
  prefs.begin("eqms", true);
  cfg.wifiSsid = prefs.getString("ssid", DEFAULT_WIFI_SSID);
  cfg.wifiPassword = prefs.getString("pass", DEFAULT_WIFI_PASSWORD);
  cfg.serverHost = prefs.getString("host", DEFAULT_SERVER_HOST);
  cfg.serverPort = prefs.getUShort("port", DEFAULT_SERVER_PORT);
  cfg.counterId = prefs.getUShort("counter", DEFAULT_COUNTER_ID);
  cfg.brightness = prefs.getUChar("bright", DEFAULT_BRIGHTNESS);
  // "scale2" is the current key. Older firmware stored "scale" but never
  // applied it, so honour the legacy value only if it was explicitly raised;
  // otherwise use the new, larger default.
  if (prefs.isKey("scale2")) {
    cfg.fontScale = prefs.getUChar("scale2", DEFAULT_FONT_SCALE);
  } else {
    const uint8_t legacyScale = prefs.getUChar("scale", 0);
    cfg.fontScale = legacyScale > 1 ? legacyScale : DEFAULT_FONT_SCALE;
  }
  prefs.end();

  cfg.wifiSsid.trim();
  cfg.serverHost = normalizeHost(cfg.serverHost, cfg.serverPort);
  cfg.serverPort = (uint16_t)constrain((int)cfg.serverPort, 1, 65535);
  cfg.counterId = (uint16_t)constrain((int)cfg.counterId, 1, 65535);
  cfg.brightness = (uint8_t)constrain((int)cfg.brightness, 0, 100);
  cfg.fontScale = (uint8_t)constrain((int)cfg.fontScale, 1, 4);
}

void saveSettings() {
  prefs.begin("eqms", false);
  prefs.putString("ssid", cfg.wifiSsid);
  prefs.putString("pass", cfg.wifiPassword);
  prefs.putString("host", cfg.serverHost);
  prefs.putUShort("port", cfg.serverPort);
  prefs.putUShort("counter", cfg.counterId);
  prefs.putUChar("bright", cfg.brightness);
  prefs.putUChar("scale2", cfg.fontScale);
  prefs.end();
}

void clearSettings() {
  prefs.begin("eqms", false);
  prefs.clear();
  prefs.end();
}

// ---------------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------------
// Largest whole-number factor that keeps `base` pixels inside `available`.
static uint8_t fitScale(int base, int available) {
  if (base <= 0 || available <= 0) return 1;
  const int scale = available / base;
  return (uint8_t)(scale < 1 ? 1 : scale);
}

bool flashActive() {
  return flashStart != 0 && (uint32_t)(millis() - flashStart) < FLASH_DURATION_MS;
}

bool flashVisible() {
  if (!flashActive()) return true;
  return ((millis() - flashStart) / FLASH_STEP_MS) % 2u == 0;
}

void showTransient(const String &text, uint32_t durationMs) {
  transientText = text;
  transientUntil = millis() + durationMs;
  hasTransient = true;
}

String lineToShow() {
  if (mode == MODE_CONFIG) return configText;

  if (hasTransient) {
    if ((int32_t)(millis() - transientUntil) < 0) return transientText;
    hasTransient = false;
  }
  return currentTicket.length() ? currentTicket : String(F("---"));
}

// Renders `text` at 1x into a small scratch bitmap, then copies every lit pixel
// onto the panel as an sx*sy block. The library fonts are fixed-size bitmaps,
// so this is how the panel gets larger text.
static void drawScaledText(const String &text, FansElectronics_Bitmap::Font font,
                           uint8_t sx, uint8_t sy) {
  dmd.setFont(font);
  const int w = dmd.textWidth(text);
  const int h = dmd.textHeight();
  if (w <= 0 || h <= 0) return;

  FansElectronics_Bitmap scratch(w, h);
  if (!scratch.isValid()) {
    // No heap for the scratch bitmap: draw unscaled rather than nothing.
    dmd.drawText(0, 0, text);
    return;
  }

  scratch.setFont(font);
  scratch.setTextColor(FansElectronics_Bitmap::White);
  scratch.drawText(0, 0, text);

  int originX = (dmd.width() - w * sx) / 2;
  int originY = (dmd.height() - h * sy) / 2;
  if (originX < 0) originX = 0;
  if (originY < 0) originY = 0;

  for (int y = 0; y < h; ++y) {
    for (int x = 0; x < w; ++x) {
      if (scratch.pixel(x, y) == FansElectronics_Bitmap::White) {
        dmd.fill(originX + x * sx, originY + y * sy, sx, sy,
                 FansElectronics_Bitmap::White);
      }
    }
  }
}

void renderFrame(const String &line) {
  dmd.clear();
  dmd.setTextColor(FansElectronics_Bitmap::White);

  // Prefer the normal 5x7 font. If the ticket is wider than the panel (for
  // example a 2-letter prefix plus 4 digits), fall back to the narrow 3x5 font
  // so the whole number stays visible instead of being clipped.
  FansElectronics_Bitmap::Font font = Font5x7b;
  dmd.setFont(font);
  int baseW = dmd.textWidth(line);
  if (baseW > dmd.width()) {
    font = Font3x5;
    dmd.setFont(font);
    baseW = dmd.textWidth(line);
  }
  const int baseH = dmd.textHeight();
  if (baseW <= 0 || baseH <= 0) return;

  // Scale width and height independently: fill the panel vertically, and only
  // widen when the text still fits. cfg.fontScale (1..2) is an upper limit.
  const uint8_t sx = (uint8_t)min((int)fitScale(baseW, dmd.width()),
                                  (int)cfg.fontScale);
  const uint8_t sy = (uint8_t)min((int)fitScale(baseH, dmd.height()),
                                  (int)cfg.fontScale);

  drawScaledText(line, font, sx, sy);
}

void updateDisplay() {
  const String line = lineToShow();

  if (line != lastLine) {
    lastLine = line;
    renderFrame(line);
  }

  // Panel refresh is serviced by displayRefreshTask(); updateDisplay() only
  // redraws the framebuffer when the text changes.
}

void applyBrightness() {
  dmd.setBrightness(percentToDuty(cfg.brightness));
}

// ---------------------------------------------------------------------------
// EQMS connection
// ---------------------------------------------------------------------------
bool fetchSnapshot() {
  if (WiFi.status() != WL_CONNECTED || cfg.serverHost.length() == 0) {
    return false;
  }

  String url = F("http://");
  url += cfg.serverHost;
  url += ':';
  url += String(cfg.serverPort);
  url += F("/display/api/counter/");
  url += String(cfg.counterId);
  url += '/';

  HTTPClient http;
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.begin(url);
  const int code = http.GET();
  if (code != 200) {
    http.end();
    if (code == 404) {
      // Counter id not found / disabled in Django.
      showTransient(F("NO COUNTER"), 4000);
    }
    return false;
  }

  const String body = http.getString();
  http.end();

  JsonDocument doc;
  if (deserializeJson(doc, body) != DeserializationError::Ok) {
    return false;
  }
  if ((uint16_t)(doc["counter_id"] | 0) != cfg.counterId) {
    return false;
  }

  const bool active = doc["active"] | false;
  const String number = doc["ticket_number"] | "";
  if (active && number.length()) {
    currentTicket = number;
  } else {
    currentTicket = "";
  }

  Serial.printf("[EQMS] snapshot: active=%d ticket=%s\n", active ? 1 : 0, currentTicket.c_str());
  return true;
}

void handleWsMessage(const char *json, size_t length) {
  JsonDocument doc;
  if (deserializeJson(doc, json, length) != DeserializationError::Ok) {
    return;
  }

  if ((uint16_t)(doc["counter_id"] | 0) != cfg.counterId) {
    return;
  }

  const String type = doc["type"] | "";
  const String number = doc["ticket_number"] | "";
  if (number.length() == 0) {
    return;
  }

  if (type == "ticket_called" || type == "ticket_recalled") {
    currentTicket = number;
    flashStart = millis();
    lastFlashVisible = true;
    Serial.printf("[EQMS] %s: %s\n", type.c_str(), number.c_str());
  } else if (type == "ticket_served" || type == "ticket_no_show" ||
             type == "ticket_cancelled") {
    if (currentTicket == number) {
      currentTicket = "";
    }
    // The server is the source of truth; confirm the change on the next loop.
    needSnapshot = true;
    Serial.printf("[EQMS] %s: %s\n", type.c_str(), number.c_str());
  }
}

void onWebSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      wsConnected = true;
      needSnapshot = true;
      Serial.println(F("[EQMS] WebSocket connected"));
      break;

    case WStype_DISCONNECTED:
      wsConnected = false;
      Serial.println(F("[EQMS] WebSocket disconnected - will retry"));
      break;

    case WStype_TEXT:
      handleWsMessage((const char *)payload, length);
      break;

    default:
      break;
  }
}

void startWebSocket() {
  if (wsStarted || cfg.serverHost.length() == 0) return;

  String path = F("/ws/counter-display/");
  path += String(cfg.counterId);
  path += '/';

  Serial.printf("[EQMS] WebSocket ws://%s:%u%s\n", cfg.serverHost.c_str(), cfg.serverPort, path.c_str());
  ws.begin(cfg.serverHost.c_str(), cfg.serverPort, path.c_str());
  ws.onEvent(onWebSocketEvent);
  ws.setReconnectInterval(WS_RECONNECT_INTERVAL_MS);
  ws.enableHeartbeat(30000, 5000, 3);
  wsStarted = true;
}

bool connectWiFi() {
  if (cfg.wifiSsid.length() == 0) return false;

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(mdnsHost.c_str());
  WiFi.setAutoReconnect(true);
  WiFi.begin(cfg.wifiSsid.c_str(), cfg.wifiPassword.c_str());

  const uint32_t startedAt = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if ((uint32_t)(millis() - startedAt) > WIFI_CONNECT_TIMEOUT_MS) {
      return false;
    }
    // The display refresh task keeps the panel scanning while we wait.
    delay(20);
  }

  Serial.print(F("[EQMS] Wi-Fi connected, IP: "));
  Serial.println(WiFi.localIP());
  return true;
}

// ---------------------------------------------------------------------------
// Configuration portal
// ---------------------------------------------------------------------------
String buildStatusHtml() {
  if (mode == MODE_CONFIG) {
    return String(F("Configuration mode.<br>Join <code>")) + htmlEscape(apSsid) +
           F("</code> with password <code>" CONFIG_AP_PASSWORD "</code>, then open "
             "<code>http://192.168.4.1/</code>.");
  }
  return String(F("Connected to <code>")) + htmlEscape(cfg.wifiSsid) +
         F("</code><br>Open <code>http://") + WiFi.localIP().toString() +
         F("/</code> or <code>http://") + mdnsHost + F(".local/</code>");
}

String buildPortalPage() {
  String page = FPSTR(PORTAL_HTML);
  page.replace(F("%%STATUS%%"), buildStatusHtml());
  page.replace(F("%%SSID%%"), htmlEscape(cfg.wifiSsid));
  page.replace(F("%%PASS_PLACEHOLDER%%"),
               cfg.wifiPassword.length() ? String(F("Saved - leave blank to keep"))
                                         : String(F("No password set")));
  page.replace(F("%%HOST%%"), htmlEscape(cfg.serverHost));
  page.replace(F("%%PORT%%"), String(cfg.serverPort));
  page.replace(F("%%COUNTER%%"), String(cfg.counterId));
  page.replace(F("%%BRIGHTNESS%%"), String(cfg.brightness));
  page.replace(F("%%FONTSCALE%%"), String(cfg.fontScale));
  page.replace(F("%%MAXSCALE%%"), String((int)max(1, dmd.height() / 7)));
  page.replace(F("%%APSSID%%"), htmlEscape(apSsid));
  page.replace(F("%%AP_PASSWORD%%"), F(CONFIG_AP_PASSWORD));
  return page;
}

void handleRoot() {
  server.send(200, "text/html", buildPortalPage());
}

void handleScan() {
  JsonDocument doc;
  JsonArray networks = doc.to<JsonArray>();

  // Scanning briefly drops the station connection, so only do it in setup mode
  // (where the device is an access point anyway). In run mode the operator can
  // still type the SSID manually.
  if (mode == MODE_CONFIG) {
    const int found = WiFi.scanNetworks();
    for (int i = 0; i < found; ++i) {
      JsonObject item = networks.add<JsonObject>();
      item["ssid"] = WiFi.SSID(i);
      item["rssi"] = WiFi.RSSI(i);
      item["secure"] = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
    }
    WiFi.scanDelete();
  }

  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

void handleApply() {
  if (!server.hasArg("bright") || !server.hasArg("scale")) {
    server.send(400, "application/json", "{\"ok\":false,\"error\":\"missing fields\"}");
    return;
  }

  cfg.brightness = (uint8_t)constrain(server.arg("bright").toInt(), 0, 100);
  cfg.fontScale = (uint8_t)constrain(server.arg("scale").toInt(), 1, 4);
  saveSettings();
  applyBrightness();

  server.send(200, "application/json", "{\"ok\":true}");
}

void handleSave() {
  String ssid = server.hasArg("ssid") ? server.arg("ssid") : cfg.wifiSsid;
  ssid.trim();
  if (ssid.length() == 0) {
    server.send(400, "application/json", "{\"ok\":false,\"error\":\"Wi-Fi name is required\"}");
    return;
  }

  String host = server.hasArg("host") ? server.arg("host") : cfg.serverHost;
  uint16_t port = cfg.serverPort;
  host = normalizeHost(host, port);
  if (host.length() == 0) {
    server.send(400, "application/json", "{\"ok\":false,\"error\":\"Server address is required\"}");
    return;
  }

  const bool openNetwork = server.hasArg("open") && server.arg("open") == "1";
  const String password = server.hasArg("pass") ? server.arg("pass") : String();

  cfg.wifiSsid = ssid;
  if (openNetwork) {
    cfg.wifiPassword = "";
  } else if (password.length() > 0) {
    cfg.wifiPassword = password;
  }

  cfg.serverHost = host;
  cfg.serverPort = (uint16_t)constrain((int)(server.hasArg("port") ? server.arg("port").toInt() : port), 1, 65535);
  cfg.counterId = (uint16_t)constrain(server.hasArg("counter") ? server.arg("counter").toInt() : (int)cfg.counterId, 1, 65535);
  cfg.brightness = (uint8_t)constrain(server.hasArg("bright") ? server.arg("bright").toInt() : (int)cfg.brightness, 0, 100);
  cfg.fontScale = (uint8_t)constrain(server.hasArg("scale") ? server.arg("scale").toInt() : (int)cfg.fontScale, 1, 4);

  saveSettings();
  applyBrightness();

  Serial.printf("[EQMS] saved: ssid=%s host=%s:%u counter=%u bright=%u scale=%u\n",
                cfg.wifiSsid.c_str(), cfg.serverHost.c_str(), cfg.serverPort,
                cfg.counterId, cfg.brightness, cfg.fontScale);

  server.send(200, "application/json", "{\"ok\":true}");
  delay(400);
  ESP.restart();
}

void handleReboot() {
  server.send(200, "application/json", "{\"ok\":true}");
  delay(300);
  ESP.restart();
}

void handleReset() {
  clearSettings();
  server.send(200, "application/json", "{\"ok\":true}");
  delay(300);
  ESP.restart();
}

void startWebServer() {
  if (webServerStarted) return;

  server.on("/", HTTP_GET, handleRoot);
  server.on("/scan", HTTP_GET, handleScan);
  server.on("/apply", HTTP_POST, handleApply);
  server.on("/save", HTTP_POST, handleSave);
  server.on("/reboot", HTTP_GET, handleReboot);
  server.on("/reboot", HTTP_POST, handleReboot);
  server.on("/reset", HTTP_POST, handleReset);
  server.onNotFound(handleRoot);  // makes Android/iOS captive portals open the page
  server.begin();
  webServerStarted = true;
}

void enterConfigMode() {
  if (mode == MODE_CONFIG) return;
  mode = MODE_CONFIG;

  wsConnected = false;
  if (wsStarted) {
    ws.disconnect();
    wsStarted = false;
  }

  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSsid.c_str(), CONFIG_AP_PASSWORD);

  // Answer every DNS query with the ESP32 IP so phones open the setup page by
  // themselves (captive portal behaviour).
  dnsServer.start(53, "*", WiFi.softAPIP());

  configText = String(F("SETUP  JOIN ")) + apSsid +
               F("  PASS " CONFIG_AP_PASSWORD "  OPEN http://192.168.4.1");
  startWebServer();

  Serial.println(F("[EQMS] configuration mode"));
  Serial.print(F("[EQMS] AP: "));
  Serial.print(apSsid);
  Serial.print(F(" / "));
  Serial.println(CONFIG_AP_PASSWORD);
  Serial.print(F("[EQMS] URL: http://"));
  Serial.println(WiFi.softAPIP());
}

void checkConfigButton() {
  static bool down = false;
  static uint32_t downAt = 0;

  const bool pressed = digitalRead(CONFIG_BUTTON_PIN) == LOW;
  if (pressed && !down) {
    down = true;
    downAt = millis();
  } else if (!pressed) {
    down = false;
  } else if ((uint32_t)(millis() - downAt) >= CONFIG_BUTTON_HOLD_MS) {
    down = false;
    enterConfigMode();
  }
}

// ---------------------------------------------------------------------------
// Setup / loop
// ---------------------------------------------------------------------------
DmdPins panelPins() {
  DmdPins pins;
  pins.pin_A = PIN_A;
  pins.pin_B = PIN_B;
  pins.pin_C = PIN_C;
  pins.pin_D = PIN_D;
  pins.pin_latch = PIN_LATCH;
  pins.pin_sck = PIN_SCK;
  pins.pin_oe = PIN_OE;
  pins.pin_data1 = PIN_DATA;  // alias: pin_mosi
  pins.pin_data2 = -1;
  pins.pin_data3 = -1;
  pins.pin_data4 = -1;
  return pins;
}

void buildDeviceNames() {
  // The Wi-Fi driver must be running before the MAC address can be read.
  WiFi.mode(WIFI_STA);
  delay(20);

  uint8_t mac[6] = {0, 0, 0, 0, 0, 0};
  WiFi.macAddress(mac);

  char suffix[5];
  snprintf(suffix, sizeof(suffix), "%02X%02X", mac[4], mac[5]);
  apSsid = String(CONFIG_AP_PREFIX) + suffix;

  String lowerSuffix = String(suffix);
  lowerSuffix.toLowerCase();
  mdnsHost = String(F("eqms-display-")) + lowerSuffix;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println(F("[EQMS] booting ESP32 P10 display"));

  buildDeviceNames();
  loadSettings();
  Serial.printf("[EQMS] counter=%u server=%s:%u bright=%u scale=%u\n",
                cfg.counterId, cfg.serverHost.c_str(), cfg.serverPort,
                cfg.brightness, cfg.fontScale);

  dmd.begin(PANEL_HUB12, PANEL_MODULES_WIDE, PANEL_MODULES_HIGH, panelPins());
  applyBrightness();

  // Refresh the panel from its own task so blocking network I/O in loop()
  // cannot starve the scan. Keep dmd.update() out of loop() so only this task
  // touches the SPI bus.
  xTaskCreatePinnedToCore(displayRefreshTask, "dmd_refresh", 4096, NULL, 1,
                          &displayTaskHandle, ARDUINO_RUNNING_CORE);

  pinMode(CONFIG_BUTTON_PIN, INPUT_PULLUP);

  renderFrame(F("---"));

  if (cfg.wifiSsid.length() == 0) {
    Serial.println(F("[EQMS] no Wi-Fi saved, starting setup AP"));
    enterConfigMode();
    return;
  }

  if (connectWiFi()) {
    MDNS.begin(mdnsHost.c_str());
    MDNS.addService("http", "tcp", 80);

    startWebServer();
    startWebSocket();
    fetchSnapshot();
    lastSnapshotAt = millis();
  } else {
    Serial.println(F("[EQMS] Wi-Fi connection failed, starting setup AP"));
    enterConfigMode();
  }
}

void loop() {
  const uint32_t now = millis();

  // Refresh the panel first to catch up on any timer ticks missed while the
  // previous loop iteration was blocked on network I/O. The DMD32 library's
  // 1/4-scan refresh relies on update() being called every ~1 ms; blocking
  // calls (HTTP snapshot, WebSocket, server.handleClient) can stall for much
  // longer, leaving the panel stuck on one scan phase (partial rows).
  updateDisplay();

  if (mode == MODE_CONFIG) {
    dnsServer.processNextRequest();
    server.handleClient();
  } else {
    checkConfigButton();

    updateDisplay();
    server.handleClient();
    updateDisplay();

    if (WiFi.status() == WL_CONNECTED) {
      if (!wsStarted) {
        startWebSocket();
      }
      ws.loop();
      updateDisplay();

      const uint32_t interval = wsConnected ? SNAPSHOT_INTERVAL_WS_MS
                                            : SNAPSHOT_INTERVAL_NO_WS_MS;
      if (needSnapshot || (uint32_t)(now - lastSnapshotAt) >= interval) {
        needSnapshot = false;
        lastSnapshotAt = now;

        updateDisplay();
        if (fetchSnapshot()) {
          snapshotFailures = 0;
        } else {
          Serial.print(F("[EQMS] Snapshot poll failed (failures="));
          Serial.print(++snapshotFailures);
          Serial.println(F(")"));
          if (snapshotFailures >= 2 && currentTicket.length() == 0) {
            showTransient(F("NO SERVER"), 2500);
          }
        }
        updateDisplay();
      }
    } else if ((uint32_t)(now - lastWifiRetryAt) >= 10000) {
      lastWifiRetryAt = now;
      Serial.println(F("[EQMS] Wi-Fi lost, reconnecting"));
      WiFi.reconnect();
    }
  }

  updateDisplay();
  delay(1);
}
