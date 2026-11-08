# HUB12 wiring and configuration (ESP32 P10 counter display)

This project uses one **32x16 single-colour P10** panel with a **HUB12** input
and **1/4 scan**. Only `OE`, `A`, `B`, `CLK`, `LAT`/`STB`, and `DATA`/`R` are
needed; `C` and `D` are unused at 1/4 scan.

Firmware: `eqms_display/eqms_display.ino` · Settings: `eqms_display/config.h`

## ESP32 pin assignment used by the sketch

These are the values currently in `config.h` (the compiled defaults):

| ESP32 GPIO | `config.h` macro | HUB12 signal | HUB12 IDC pin |
|-----------:|------------------|--------------|--------------:|
| GPIO4  | `PIN_OE`    | `OE` / `EN` (active low) | 1 |
| GPIO25 | `PIN_A`     | `A` (row address)        | 2 |
| GPIO26 | `PIN_B`     | `B` (row address)        | 3 |
| GPIO23 | `PIN_DATA`  | `DATA` / `R`             | 5 |
| GPIO18 | `PIN_SCK`   | `CLK`                    | 7 |
| GPIO27 | `PIN_LATCH` | `LAT` / `STB`            | 9 |
| —      | `PIN_C` / `PIN_D` = `-1` | `C`, `D` (not used) | — |
| GND    | —           | `GND`                    | 4, 6, 8, 10–16 |

> If your panel is already wired to different pins, change the `PIN_*` values in
> `config.h` to match the wiring instead of re-wiring. See
> [Changing pins](#changing-pins) for the pins to avoid.

## HUB12 is not fully standardised

The 2x8 IDC connector looks the same on many panels, but manufacturers do not
all use the same pin order. **Match signal names, not pin numbers.** Two layouts
seen on common 32x16 P10 panels are:

### Layout A - interleaved grounds (common on P10 panels)

| Pin | Signal | Pin | Signal |
|----:|--------|----:|--------|
| 1 | `OE` | 2 | `A` |
| 3 | GND | 4 | `B` |
| 5 | GND | 6 | `C` (NC) |
| 7 | GND | 8 | `CLK` |
| 9 | GND | 10 | `LAT` / `STB` |
| 11 | GND | 12 | `DATA` / `R` |
| 13 | GND | 14 | `G` (NC on single colour) |
| 15 | GND | 16 | NC |

### Layout B - signals on pins 1-10, grounds after

| Pin | Signal | Pin | Signal |
|----:|--------|----:|--------|
| 1 | `OE` | 2 | `A` |
| 3 | `B` | 4 | GND |
| 5 | `DATA` / `R` | 6 | GND |
| 7 | `CLK` | 8 | GND |
| 9 | `LAT` / `STB` | 10 | GND |
| 11-16 | GND / NC | | |

Some panels instead put the signals sequentially on pins 1-8
(`OE, A, B, C, D, DATA, CLK, LAT`) and use pins 9-16 for ground. If your panel
has no silkscreen, identify the ground pins with a multimeter first: all ground
pins are electrically connected. The remaining pins are the signals. Tracing
them to the 74HC245/74HC138 on the panel is more reliable than trying layouts
blind.

**Never apply 5 V to a HUB12 signal pin.** On a standard P10 panel the HUB12
connector carries signals and ground only; panel power is a separate 4-pin
connector (often 5 V, GND, 5 V, GND). Verify the power connector polarity before
plugging it in.

## Power

- 5 V supply, **3 A minimum, 5 A recommended**; allow up to ~4 A for a 32x16
  single-colour panel at full white.
- 1000 uF electrolytic + 100 nF ceramic across the panel's 5 V/GND, close to the
  panel.
- Common ground between the 5 V supply, ESP32, level shifter, and panel.
- Do not power the panel from the ESP32's 5 V/VIN pin or from USB.
- Never feed 5 V into an ESP32 GPIO.

## Level shifter (recommended)

The panel expects 5 V logic; the ESP32 outputs 3.3 V. A **74HCT245** (or
74AHCT245) powered at 5 V is a simple unidirectional level shifter:

```
ESP32 GPIO  ->  A input
B output    ->  HUB12 signal
VCC         ->  5 V
GND         ->  common ground
DIR         ->  5 V   (A -> B)
/OE         ->  GND
```

Use one channel per signal. Suggested channel assignment for a 74HCT245:

| ESP32 GPIO | 74HCT245 A pin | 74HCT245 B pin | HUB12 signal |
|-----------:|---------------:|---------------:|--------------|
| GPIO4  | A1 (pin 2) | B1 (pin 18) | `OE` |
| GPIO25 | A2 (pin 3) | B2 (pin 17) | `A` |
| GPIO26 | A3 (pin 4) | B3 (pin 16) | `B` |
| GPIO18 | A4 (pin 5) | B4 (pin 15) | `CLK` |
| GPIO27 | A5 (pin 6) | B5 (pin 14) | `LAT` / `STB` |
| GPIO23 | A6 (pin 7) | B6 (pin 13) | `DATA` / `R` |

74HCT245 power/control pins: VCC = pin 20 (5 V), GND = pin 10, `DIR` = pin 1
(5 V for A->B), `/OE` = pin 19 (GND). Tie unused A inputs to GND and leave
unused B outputs open.

A 74HC245 or 74HC125 will **not** work reliably here: with a 5 V supply their
inputs are not 3.3 V compatible. Use the HCT/AHCT variant.

If you do not use a level shifter, keep wires very short and expect possible
instability; 3.3 V drive is outside the panel's specification.

## Config button

| Setting | Default |
|---|---|
| GPIO | `CONFIG_BUTTON_PIN` = **0** (the `BOOT` button on most DevKits) |
| Hold time | `CONFIG_BUTTON_HOLD_MS` = **1500 ms** |
| Wiring | momentary button between GPIO 0 and GND (internal pull-up enabled) |

Hold the button ~1.5 s **while the firmware is running** to start the Wi-Fi
setup access point. Do **not** hold it while resetting or powering the board -
GPIO 0 low at boot puts the ESP32 into download/flash mode.

Factory reset without the web page: hold the config button while powering the
board; the next boot starts the setup AP again.

## First-time setup (access point)

1. Power the ESP32 + panel. With no saved Wi-Fi the board starts in
   configuration mode immediately; otherwise hold the config button ~1.5 s.
2. Connect a phone/laptop to:
   - SSID: **`EQMS-Display-XXXX`** (`XXXX` = last bytes of the ESP32 MAC)
   - Password: **`eqms1234`**
3. Open `http://192.168.4.1/` (a captive-portal DNS server usually opens it).
4. Fill in:
   - **Wi-Fi network** - pick from the scan list or type the SSID
   - **Wi-Fi password** - blank keeps the previous one; tick *Open network*
     for an unsecured network
   - **Server IP or hostname** - the PC running EQMS, e.g. `192.168.1.10`
     (a port can be included as `192.168.1.10:8000`)
   - **Port** - `8000` by default
   - **Counter ID** - the numeric Django `Counter` id, the same number used in
     `/counter/display/<id>/`
   - **Font size** - 1x … (maximum depends on panel height)
   - **Brightness** - 0–100 %
5. Press **Save & restart**.
6. The same page is later available at `http://<device-ip>/` or
   `http://eqms-display-xxxx.local/` while the device is on the LAN.

### Portal buttons

| Button | Action |
|---|---|
| **Save & restart** | Saves everything (Wi-Fi, server, counter, display) and reboots |
| **Apply display settings** | Applies brightness + font size immediately, without rebooting |
| **Restart** | Reboots the device |
| **Factory reset** | Erases Wi-Fi/server/counter/display settings and reboots into setup mode |

## Network endpoints used

| Purpose | URL |
|---|---|
| Realtime events | `ws://<server>:<port>/ws/counter-display/<counter-id>/` |
| Current-call snapshot | `GET http://<server>:<port>/display/api/counter/<counter-id>/` |

The snapshot is read on boot and on every WebSocket (re)connect, then polled
every 30 s while the socket is healthy and every 3 s while it is down.

The server must run through ASGI (Daphne/Channels), for example
`start_server_on_host.bat` or:

```bash
.venv\Scripts\daphne -b 0.0.0.0 -p 8000 eqms.asgi:application
```

## Font size and brightness

- Text uses the library's **3x5 pixel font**, scaled 1x–4x.
- Effective maximum = `panel height / 5`:
  - 16 px panel (single P10) -> up to **3x**
  - 32 px panel (two rows) -> up to **4x**
- Default **2x** on a single 32x16 panel: a 4-character ticket (`A007`) fits
  without scrolling; longer text scrolls left.
- Brightness 0–100 % maps to the panel's 8-bit PWM dimming.
- Both values are stored in NVS and survive power loss.

## Multiple P10 modules (optional)

In `config.h`:

```cpp
#define PANEL_PIXEL_WIDTH   32
#define PANEL_PIXEL_HEIGHT  16
#define PANEL_MODULES_WIDE  1   // e.g. 2 for two modules side by side
#define PANEL_MODULES_HIGH  1
```

The default scan is zig-zag daisy-chain (`SCAN_ZIGZAG`): one HUB12 cable per
row. `SCAN_PARALLEL` is supported by the library but needs extra data wires and
is beyond this firmware's default configuration.

## Firmware defaults (config.h)

```cpp
#define DEFAULT_WIFI_SSID       ""      // empty = start in setup mode
#define DEFAULT_WIFI_PASSWORD   ""
#define DEFAULT_SERVER_HOST     ""      // server IP/hostname
#define DEFAULT_SERVER_PORT     8000
#define DEFAULT_COUNTER_ID      1
#define DEFAULT_BRIGHTNESS      70      // percent, 0..100
#define DEFAULT_FONT_SCALE      2       // 1..4
#define CONFIG_AP_PREFIX        "EQMS-Display-"
#define CONFIG_AP_PASSWORD      "eqms1234"

#define WIFI_CONNECT_TIMEOUT_MS      20000
#define WS_RECONNECT_INTERVAL_MS      5000
#define SNAPSHOT_INTERVAL_WS_MS      30000
#define SNAPSHOT_INTERVAL_NO_WS_MS    3000
#define HTTP_TIMEOUT_MS               2500
#define SCROLL_STEP_MS                  55
#define FLASH_DURATION_MS             1400
#define FLASH_STEP_MS                  200
```

## Changing pins

Edit only these lines in `eqms_display/config.h`, then rebuild:

```cpp
#define PIN_A      25
#define PIN_B      26
#define PIN_C      -1
#define PIN_D      -1
#define PIN_LATCH  27
#define PIN_SCK    18
#define PIN_OE      4
#define PIN_DATA   23
#define CONFIG_BUTTON_PIN 0
```

Rules:

- Avoid ESP32 strapping pins for panel signals when possible (GPIO 0, 2, 5, 12,
  15 have boot-time functions).
- GPIO 6–11 are used by the internal SPI flash - never use them.
- Input-only pins (34–39) cannot drive the panel outputs.
- Keep `PIN_C` / `PIN_D` at `-1` for HUB12 (1/4 scan).

## Build and flash

PlatformIO (recommended):

```bash
cd esp32_display
pio run                        # build
pio run -t upload              # flash (add --upload-port COM4 on Windows)
pio device monitor             # serial log at 115200
```

Arduino IDE:

1. Install ESP32 board support (Espressif).
2. Library Manager: **FansElectronics_DMD32 1.1.0**, **WebSockets 2.7.x**,
   **ArduinoJson 7.x**.
3. Open `eqms_display/eqms_display.ino` - the folder name must stay
   `eqms_display` so `config.h` and `portal_page.h` open as tabs.
4. Board: **ESP32 Dev Module**, upload speed 921600 (use 115200 if unstable).
5. If upload cannot connect: hold **BOOT**, tap **EN/RST**, release **BOOT**,
   and upload again.

Expected serial log on boot:

```
[EQMS] booting ESP32 P10 display
[EQMS] counter=1 server=192.168.1.10:8000 bright=70 scale=2
[EQMS] Wi-Fi connected, IP: 192.168.1.42
[EQMS] WebSocket ws://192.168.1.10:8000/ws/counter-display/1/
[EQMS] WebSocket connected
[EQMS] snapshot: active=0 ticket=
```

## Quick continuity check

With the panel unpowered:

1. Confirm which pins are GND: they should all beep together.
2. Confirm the 5 V power pins are **not** connected to any HUB12 signal pin.
3. Check that the ribbon/breakout is not reversed (pin 1 to pin 1).
4. Only then apply 5 V and connect the ESP32 signals.

## Install checklist

- [ ] 5 V supply on the panel power connector (not the ESP32, not USB)
- [ ] ESP32 GND, panel GND and 5 V GND tied together
- [ ] No 5 V signal on an ESP32 GPIO
- [ ] `OE`, `A`, `B`, `CLK`, `LAT`, `DATA` match the `PIN_*` values in `config.h`
- [ ] 74HCT245 installed (5 V VCC, `/OE` to GND, `DIR` to 5 V) if unstable
- [ ] 1000 uF + 100 nF across the panel 5 V/GND
- [ ] Counter ID matches the Django `Counter` id
- [ ] The ticket is today's and active at that counter
- [ ] Server reachable from the panel network, running via Daphne/Channels
- [ ] Brightness > 0 and font scale valid

## Troubleshooting

| Symptom | What to check |
|---|---|
| Panel stays dark | 5 V supply and GND; `OE` pin; brightness > 0; `PIN_*` mapping |
| Random dots / ghosting / missing rows | 74HCT245 level shifter; shorter wires; capacitor; lower brightness |
| Shows `---` although a ticket is called | `Counter ID` must match the Django counter id; the ticket must be today's and active at that counter |
| Connects to Wi-Fi but no ticket updates | Server IP/port wrong, different networks, or server not running through Daphne/Channels |
| `WebSocket disconnected` repeatedly | Firewall/proxy blocking WS, or a plain WSGI runner |
| Cannot enter setup mode | Hold the button ~1.5 s while running; check `CONFIG_BUTTON_PIN` and GND |
| Setup AP not visible | Wi-Fi credentials already saved - hold the button, or use **Factory reset** |
| Text is cut off | Increase font scale or let it scroll; at 3x a long ticket always scrolls on a 32 px wide panel |
| Upload fails | Hold `BOOT`, tap `EN`, release `BOOT`; lower the upload speed to 115200 |
