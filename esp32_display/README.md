# EQMS ESP32 + P10 counter display

Firmware for a single-color **P10 / HUB12 (1/4 scan)** LED panel driven by an
ESP32. It shows the ticket number that one linked EQMS counter is currently
calling, and updates the moment the counter calls or recalls a ticket.

The panel also has a **configuration button**: hold it for about 1.5 seconds and
the ESP32 starts its own Wi-Fi access point with a setup page where you can pick
the Wi-Fi network + password, set the EQMS server address, choose the counter,
change the **font size** and change the **brightness in percent**.

```
esp32_display/
├── platformio.ini              PlatformIO project (optional)
├── README.md                   this file
├── wiring.md                   pin table, power, level shifter, checklist
└── eqms_display/
    ├── eqms_display.ino        firmware (open this in the Arduino IDE)
    ├── config.h                pins, defaults, timings
    └── portal_page.h           embedded setup page (HTML/CSS/JS)
```

---

## 1. What it does

| Event on the counter | Panel reaction |
|---|---|
| Ticket called (`Call`, `Next`, `Done & Next`) | Shows the ticket number and flashes it for ~1.4 s |
| Ticket recalled (`Recall`) | Shows/flashes the same number again |
| Ticket done / no-show / cancelled | Clears the number (shows `---`) |
| Nothing active | Shows `---` |
| Text wider than the panel | Scrolls left continuously |

Realtime updates come from the EQMS WebSocket
`ws://<server>:<port>/ws/counter-display/<counter-id>/`.
On boot and whenever the WebSocket (re)connects, the firmware also reads
`GET http://<server>:<port>/display/api/counter/<counter-id>/` to recover the
current state. It polls that snapshot every 30 s while the socket is healthy and
every 3 s while it is down, so the panel recovers by itself after a network
glitch or a server restart.

---

## 2. Hardware

* ESP32 DevKit (ESP32-WROOM-32 / ESP32-DevKitC). ESP32-S3 also works if you keep
  the same pin numbers valid for your board.
* P10 single-color LED module, 32 × 16 px, **HUB12** connector, **1/4 scan**.
* 5 V power supply sized for the panel (a 32 × 16 P10 module can draw ~1.5–2 A
  at full brightness; use 5 V / 3 A or more, and add a large capacitor near the
  panel if the supply is weak).
* Optional but recommended: **74HCT245** level shifter (or another 3.3 V → 5 V
  buffer) between the ESP32 and the HUB12 inputs.
* Momentary push button between the config GPIO and GND (the on-board `BOOT`
  button on GPIO 0 can be reused).

### 2.1 Wiring (defaults in `config.h`)

| HUB12 signal | Typical IDC pin | `config.h` macro | Default ESP32 GPIO |
|---|---|---|---|
| `OE` / `EN` (output enable, active low) | 1 | `PIN_OE` | **4** |
| `A` (row address) | 2 | `PIN_A` | **16** |
| `B` (row address) | 3 | `PIN_B` | **14** |
| `GND` | 4, 6, 8, 10–16 | — | **GND** |
| `R` / `DATA` (serial data) | 5 | `PIN_DATA` | **23** |
| `CLK` (shift clock) | 7 | `PIN_SCK` | **18** |
| `LAT` / `STB` (latch) | 9 | `PIN_LATCH` | **19** |
| `C`, `D` | — | `PIN_C`, `PIN_D` | not used (`-1`) |

HUB12 is not as strictly standardized as HUB75: a few modules shuffle the
control pins. **Check the silkscreen / datasheet of your module** and, if
needed, only change the `#define PIN_*` values in `config.h`.

> **Power and ground**
> * Power the panel from the 5 V supply, **not** from the ESP32 3.3 V pin.
> * Connect the ESP32 GND, the panel GND and the 5 V supply GND together.
> * Never feed 5 V into an ESP32 GPIO.
>
> **Logic level**
> The panel expects 5 V logic. Many boards work with the ESP32's 3.3 V outputs
> over short wires, but if you see missing rows, flicker, ghosting or a blank
> panel, put a **74HCT245** (HCT, not HC) running at 5 V on `A`, `B`, `CLK`,
> `LAT`, `OE` and `DATA`. This is the most common cause of unstable P10 panels.

### 2.2 Config button

| Setting | Default |
|---|---|
| GPIO | `CONFIG_BUTTON_PIN` = **0** (the `BOOT` button on most DevKits) |
| Hold time | `CONFIG_BUTTON_HOLD_MS` = **1500 ms** |
| Wiring | button between the GPIO and GND (internal pull-up is enabled) |

Do not hold the button while resetting/powering the board (GPIO 0 low at boot is
the ESP32 download-mode pin). Hold it only while the firmware is already
running.

---

## 3. Build and flash

### Option A — Arduino IDE

1. Install **ESP32 board support** (Boards Manager → `esp32` by Espressif).
2. Library Manager → install:
   * **FansElectronics_DMD32** (by `vean`, version **1.1.0**) — HUB12/P10 driver
   * **WebSockets** (by Markus Sattler, **2.7.x**) — realtime connection
   * **ArduinoJson** (**7.x**) — JSON parsing
3. Open `eqms_display/eqms_display.ino`. The folder name must stay
   `eqms_display` so the IDE treats `config.h` and `portal_page.h` as tabs.
4. Board: **ESP32 Dev Module**, upload speed 921600 (drop to 115200 if upload
   is unreliable), then **Upload**.
5. If the upload cannot connect, hold **BOOT**, tap **EN/RST**, release **BOOT**,
   and upload again.

### Option B — PlatformIO

```bash
cd esp32_display
pio run                 # build
pio run -t upload       # flash
pio device monitor      # serial log at 115200
```

`platformio.ini` already lists the same three libraries.

### Serial log

Open the serial monitor at **115200 baud**. On boot you should see something
like:

```
[EQMS] booting ESP32 P10 display
[EQMS] counter=1 server=192.168.1.10:8000 bright=70 scale=2
[EQMS] Wi-Fi connected, IP: 192.168.1.42
[EQMS] WebSocket ws://192.168.1.10:8000/ws/counter-display/1/
[EQMS] WebSocket connected
[EQMS] snapshot: active=0 ticket=
```

---

## 4. First-time setup

1. Power the ESP32 + panel. With no saved Wi-Fi the board starts in
   configuration mode immediately (otherwise hold the config button for ~1.5 s).
2. On a phone or laptop, connect to the access point:
   * SSID: **`EQMS-Display-XXXX`** (`XXXX` = last two bytes of the ESP32 MAC)
   * Password: **`eqms1234`**
3. Open **`http://192.168.4.1/`** (most phones open it automatically; a captive
   portal DNS server is running).
4. Fill in:
   * **Wi-Fi network** — pick from the scan list or type the SSID
   * **Wi-Fi password** — leave blank to keep the previous one; tick
     *Open network* for an unsecured network
   * **Server IP or hostname** — the PC running EQMS, e.g. `192.168.1.10`
     (a port can be included as `192.168.1.10:8000`)
   * **Port** — `8000` by default
   * **Counter ID** — the numeric Django `Counter` id, the same number used in
     `/counter/display/<id>/`
   * **Font size** — 1× … (maximum depends on panel height)
   * **Brightness** — 0–100 %
5. Press **Save & restart**. The panel joins the network and connects to EQMS.
6. The serial log prints the device IP. The same setup page is also available
   later at `http://<device-ip>/` or `http://eqms-display-xxxx.local/` while the
   device is on the LAN.

### Portal buttons

| Button | Action |
|---|---|
| **Save & restart** | Saves everything (Wi-Fi, server, counter, display) and reboots |
| **Apply display settings** | Applies brightness + font size immediately, without rebooting |
| **Restart** | Reboots the device |
| **Factory reset** | Erases Wi-Fi/server/counter/display settings and reboots into setup mode |

---

## 5. Font size and brightness

* The firmware renders text with the library's **3 × 5 pixel font** and scales
  it by the selected factor (1×–4×).
* The effective maximum is `panel height / 5`:
  * 16 px panel (single P10) → up to **3×**
  * 32 px panel (two rows) → up to **4×**
* At the default **2×** on a single 32 × 16 panel, a normal 4-character ticket
  (`A007`) fits without scrolling. Longer numbers (e.g. `VIP001`) scroll left.
* Brightness is a real percentage (0 % = off, 100 % = maximum) mapped to the
  panel's 8-bit PWM dimming.
* Both settings are stored in NVS and survive power loss.

---

## 6. Multiple P10 modules (optional)

`config.h`:

```cpp
#define PANEL_PIXEL_WIDTH   32
#define PANEL_PIXEL_HEIGHT  16
#define PANEL_MODULES_WIDE  1   // e.g. 2 for two modules side by side
#define PANEL_MODULES_HIGH  1
```

The default scan mode is **zig-zag daisy-chain** (one HUB12 cable per row, the
library's `SCAN_ZIGZAG`). For parallel HUB12 rows the library also supports
`SCAN_PARALLEL`, but that needs extra data wires and is beyond this firmware's
default configuration. See the library's `DoubleBuffer` example.

Everything else (Wi-Fi, counter selection, font, brightness) works unchanged.

---

## 7. Backend pieces used

The firmware depends on two public EQMS endpoints:

| Purpose | URL |
|---|---|
| Realtime events | `ws://<server>:<port>/ws/counter-display/<counter-id>/` |
| Current-call snapshot | `GET http://<server>:<port>/display/api/counter/<counter-id>/` |

The snapshot endpoint was added in `display/views.py`
(`api_counter_now_serving`) and routed in `display/urls.py`. It returns:

```json
{
  "counter_id": 1,
  "counter_name": "Cash Counter",
  "active": true,
  "ticket_id": 42,
  "ticket_number": "A007",
  "service": "General",
  "service_prefix": "A",
  "called_at": "14:32:05",
  "called_at_iso": "2026-11-08T14:32:05+05:00",
  "recall_count": 0,
  "server_time": "2026-11-08T14:32:31+05:00"
}
```

The WebSocket emits the same data used by the browser display:
`ticket_called`, `ticket_recalled`, `ticket_served`, `ticket_no_show`,
`ticket_cancelled`, each with `counter_id` and `ticket_number`.

The EQMS server must be reachable from the panel's network and must be running
through ASGI (Daphne/Channels), for example `start_server_on_host.bat` or:

```bash
.venv\Scripts\daphne -b 0.0.0.0 -p 8000 eqms.asgi:application
```

---

## 8. Troubleshooting

| Symptom | What to check |
|---|---|
| Panel stays dark | 5 V supply and GND; `OE` pin; brightness > 0; `PIN_*` matches your wiring |
| Random dots / ghosting / missing rows | Add a 74HCT245 level shifter; shorten wires; add a capacitor across the panel's 5 V/GND; lower brightness |
| Shows `---` although a ticket is called | `Counter ID` must match the **Django** counter id; the ticket must be today's and active at that counter |
| Connects to Wi-Fi but no ticket updates | Server IP/port wrong, panel and server on different networks, or the server is not running through Daphne/Channels |
| Serial shows `WebSocket disconnected` repeatedly | WebSocket blocked by a firewall/proxy, or the server was started with a plain WSGI runner |
| Cannot enter setup mode | Hold the button ~1.5 s while the board is running; check `CONFIG_BUTTON_PIN` and the GND connection |
| Setup AP not visible | Wi-Fi credentials were already saved — hold the button, or press **Factory reset** from the web page |
| Text is cut off | Increase font scale or let it scroll; at 3× a long ticket will always scroll on a 32 px wide panel |
| Upload fails | Hold `BOOT`, tap `EN`, release `BOOT`; lower the upload speed to 115200 |

### Factory reset without the web page

Hold the config button while powering the board. On the next boot the ESP32
starts its setup AP again. (If your board routes GPIO 0 to the `BOOT` button,
the same physical button works.)

---

## 9. Security note

The setup page has no password beyond the AP password (`eqms1234`), and while
the device is in run mode the same page is reachable on the LAN. Treat the
display as a trusted-LAN device. Change `CONFIG_AP_PASSWORD` in `config.h`
before deploying if the AP password should be site-specific.
