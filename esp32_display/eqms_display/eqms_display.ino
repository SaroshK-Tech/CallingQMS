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
#include "fonts/Font5x7.h"

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
  cfg.fontScale = prefs.getUChar("scale", DEFAULT_FONT_SCALE);
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
  prefs.putUChar("scale", cfg.fontScale);
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
uint8_t effectiveScale() {
  uint8_t maxScale = (uint8_t)max(1, dmd.height() / 5);
  return (uint8_t)constrain((int)cfg.fontScale, 1, (int)maxScale);
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

void renderFrame(const String &line, uint8_t scale) {
  dmd.clear();
  dmd.setFont(Font5x7);
  dmd.setTextColor(FansElectronics_Bitmap::White);

  int textW = dmd.textWidth(line);
  int textH = dmd.textHeight();
  int startX = (dmd.width() - textW) / 2;
  int startY = (dmd.height() - textH) / 2;

  if (startX < 0) startX = 0;
  if (startY < 0) startY = 0;

  dmd.drawText(startX, startY, line);
}

void updateDisplay() {
  const String line = lineToShow();

  if (line != lastLine) {
    lastLine = line;
    renderFrame(line, effectiveScale());
  }

  dmd.update();
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
      Serial.println(F("[EQMS] WebSocket disconnected"));
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
  ws.enableHeartbeat(15000, 3000, 2);
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
    dmd.update();
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
  page.replace(F("%%MAXSCALE%%"), String((int)max(1, dmd.height() / 5)));
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

  pinMode(CONFIG_BUTTON_PIN, INPUT_PULLUP);

  renderFrame(F("---"), effectiveScale());

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
        } else if (++snapshotFailures >= 2 && currentTicket.length() == 0) {
          showTransient(F("NO SERVER"), 2500);
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
