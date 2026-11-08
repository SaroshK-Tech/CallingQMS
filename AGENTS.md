# AGENTS.md

## Project

EQMS-AlgoriSync: Real-time multi-counter queue management system (Django + Channels). Ticket generation at kiosk, live display boards, counter stations, and user dashboards.

## Tech Stack

- **Backend**: Django 6.1 + Django Channels (WebSocket support)
- **Frontend**: Vanilla HTML/CSS/JS with WebSocket communication
- **Database**: SQLite (development), easily swappable
- **ASGI Server**: Daphne
- **Static files**: WhiteNoise (serves `/static/` under Daphne; requires `collectstatic`)
- **Audio**: pre-generated files — English via gTTS, Urdu via edge-tts neural voice (`ur-PK-UzmaNeural`), trimmed with ffmpeg

## Project Structure

```
eqms/           # Django project settings
core/           # Shared models, admin config
accounts/       # Login/logout, user management
kiosk/          # Ticket generation kiosk screen
counter/        # Counter dashboard, WebSocket consumers
display/        # Full display board (1:3 calls:ads ratio)
esp32_display/  # ESP32 + P10 (HUB12) counter display firmware
static/         # CSS, JS, images, audio files
templates/      # All HTML templates
```

## Key URLs

| Path | Description |
|------|-------------|
| `/` | Kiosk screen (public, ticket generation) |
| `/accounts/login/` | Counter user login |
| `/accounts/` | Dashboard redirect |
| `/counter/dashboard/` | Counter control panel (requires login) |
| `/counter/display/<id>/` | Single counter display |
| `/display/` | Full display board |
| `/display/api/counter/<id>/` | Current call for one counter (JSON, used by the ESP32 panel) |
| `/feedback/<ticket_number>/` | Public per-ticket feedback page |
| `/admin/` | Django admin |

## Default Credentials

- **Admin**: `admin` / `admin123`
- **Counter 1 User**: `user1` / `user123`
- **Counter 2 User**: `user2` / `user123`

## Commands

```bash
# Setup once (creates .venv, installs deps, migrates DB)
start_server.bat                # Windows double-click launcher

# Or manually with the virtual environment
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate

# Run development server
.venv\Scripts\python manage.py runserver

# Run with Daphne (WebSocket support), bound to all interfaces
.venv\Scripts\daphne -b 0.0.0.0 -p 8000 eqms.asgi:application

# Generate audio files
.venv\Scripts\python generate_audio.py

# Create superuser
.venv\Scripts\python manage.py createsuperuser
```

## Deployment on a LAN / different IPs

The server binds to `0.0.0.0` so any machine on the network can reach it; pages/open
WebSockets use relative host detection, so they work from any IP automatically.

1. Run `start_server.bat` on the host machine (creates/uses `.venv`, installs deps, migrates, starts Daphne).
2. Find the host's LAN IP (e.g. `ipconfig`) and open:
   - Kiosk: `http://<host-ip>:8000/`
   - Display: `http://<host-ip>:8000/display/`
   - Counter login: `http://<host-ip>:8000/accounts/login/`
3. Optional env vars (set before running `start_server.bat`):
   - `EQMS_HOST` — bind address (default `0.0.0.0`)
   - `EQMS_PORT` — port (default `8000`)
   - `EQMS_DEBUG` — `True`/`False`
   - `EQMS_ALLOWED_HOSTS` — comma list of hosts/IPs (default `*`)
   - `EQMS_CSRF_TRUSTED_ORIGINS` — comma list, e.g. `http://192.168.1.10:8000`
   - `EQMS_SECRET_KEY`, `EQMS_DB_PATH`
   Full list is documented at the top of `eqms/settings.py`.
4. For production set `EQMS_DEBUG=False`, a real `EQMS_SECRET_KEY`, firewall port 8000 (or the chosen port) open for the LAN.

### Ready-made launchers

- `start_server_on_host.bat` — server launcher on the HOST machine. Detects the machine's
  LAN IP automatically (`scripts/get_ip.ps1`), shows the URLs for it, binds `0.0.0.0`
  (override port with `EQMS_PORT`). Use this on the server PC.
- `kiosk.bat` — kiosk launcher on any CLIENT PC. First run asks for the server's IP and
  stores it in `kiosk_config.txt`; later runs reuse it silently. To change the server IP,
  delete `kiosk_config.txt` (or edit it). Opens the kiosk `http://<server-ip>:<port>/` in
  fullscreen kiosk mode (Chrome, else Edge). Port can be overridden with `EQMS_PORT`
  (must match the server).

## Audio System

- Files stored in `static/audio/` as MP3
- Naming: `{lang}_{type}.mp3` (e.g., `en_ticket.mp3`, `ur_A.mp3`, `en_counter_counter_1.mp3`)
- Numbers are spoken as whole numbers built from word clips: `{lang}_n_{token}.mp3`
  (e.g. `en_n_20.mp3` = "twenty", `ur_n_21.mp3` = "اکیس"). Token lists come from
  `core/number_words.py` (321 → EN `3,100,and,20,1`, UR `3,100,21`).
- Regenerate with `python generate_audio.py` when adding new counters
- For production: replace gTTS with professional voice service

## ESP32 / P10 Counter Display Firmware

`esp32_display/` holds an Arduino/PlatformIO firmware for a physical per-counter
display: ESP32 + single-color **P10 / HUB12 (1/4 scan)** panel just like the
browser's single counter display.

- **Realtime**: WebSocket `ws://<server>:<port>/ws/counter-display/<counter-id>/`
  (`SingleCounterConsumer`); initial/reconnect state from
  `GET /display/api/counter/<counter-id>/` (`display.views.api_counter_now_serving`).
  Snapshot polling: 30 s with WS up, 3 s without.
- **Display**: ticket number, flash on call/recall, `---` when idle, left scroll
  when the text is wider than the panel. Font = library `Font3x5` scaled 1×–4×
  (effective max `panel height / 5`, so 3× on a 16 px panel).
- **Config button** (default GPIO 0, hold ~1.5 s): starts AP
  `EQMS-Display-XXXX` / `eqms1234`, captive-portal DNS, page at
  `http://192.168.4.1/` for Wi-Fi + password, server host/port, counter id,
  font size and brightness %. Same page also reachable at the device's LAN IP.
- **Stack**: `FansElectronics_DMD32` (v1.1.0), `WebSockets` (Links2004),
  `ArduinoJson` v7. Pins/defaults live in `esp32_display/eqms_display/config.h`.
- **Backend tests**: `display/tests.py::CounterDisplayApiTests` covers the JSON
  snapshot endpoint.
- Full wiring, flashing, setup, panel sizing and troubleshooting:
  `esp32_display/README.md`.

## Models

- **Service**: Ticket category (A=General, B=VIP, …). `is_usual=True` means the
  category is callable at every active counter; otherwise it is exceptional and only
  callable at the counters linked through `CounterService`
- **Counter**: Physical counter/station
- **CounterService**: Links counters to services with sequence order (admin routing)
- **Ticket**: Generated ticket with number, status, current counter, `no_show_count`;
  `created_at` is the dispensing time used on the dashboard
- **TicketCall**: Audit log of calls/recalls, with `served_at`, `duration_seconds`
  (time on station), `no_show` and `recall_count`
- **Feedback**: One per ticket (1–5 stars + comment), from the counter or the public page
- **CounterUser**: Links User to Counter
- **Advertisement**: Display board ads (images/videos)

## WebSocket Groups

- `dashboard_{counter_id}`: Counter user dashboard updates
- `all_dashboards`: Every counter control panel (queue changes, no-shows, done)
- `display_board`: Full display board broadcasts
- `counter_display_{counter_id}`: Single counter display

## Key Features

1. **Kiosk**: Brand screen with one button per active category (admin-defined), ticket
   popup + silent receipt with the public feedback URL
2. **Display Board**: cash-counter card + three fixed station rows (Blood Collection, X-ray, Physical Examination), auto-refresh via WebSocket; ads are admin/API only; no-show calls are removed
3. **Counter Control Panel**: three columns — waiting queue (dispensing time, `No show` badge), called clients (time on station), and the active client with a live timer and `No Show` / `Done & Next` / `Recall`
4. **Queue rules** (`core/queueing.py`): usual categories everywhere, exceptional ones only where assigned; **every counter owns its queue** — a ticket leaves a counter's waiting list only when *that* counter calls or finishes it, so the same ticket can be served at several counters (one `TicketCall` duration per station); a no-show is per counter (ticket returns to that counter's list with a `No show` badge and sorts first); Done & Next completes the current client at that counter and calls the next; Recall re-announces without resetting the timer
5. **Feedback**: public `/feedback/<ticket>/` page only (link printed on the kiosk ticket); Done & Next never prompts for a rating
6. **Audio Announcements**: English + Urdu, parametric generation for dynamic counter names
7. **Single Counter Display**: Shows current ticket for waiting area
8. **Same-day only**: Waiting lists, display board, and selection show only today's tickets (no back-dates, regardless of status)
9. **ESP32 P10 Counter Display**: physical single-color P10/HUB12 panel per counter; shows the called ticket in realtime over `ws/counter-display/<id>/`, with a config button that opens a Wi-Fi setup portal (network/password, server, counter, font size, brightness)

## Setup Notes

1. First run: `python manage.py migrate && python manage.py createsuperuser`
2. Create services and counters in Django admin
3. Create user accounts and link to counters via admin
4. Generate audio files: `python generate_audio.py`
5. Run with Daphne for WebSocket support

## Development

- Queue rules live in `core/queueing.py`; the dashboard page, `/counter/api/state/`
  and the WebSocket consumer all go through it (single source of truth)
- WebSocket consumers in `counter/consumers.py`
- Real-time updates broadcast to all connected clients (`all_dashboards`, `display_board`)
- Audio playback in `static/js/main.js` via AudioAnnouncer class; call/recall announcements are triggered server-side
- ESP32/P10 firmware lives in `esp32_display/` (see its `README.md`); its state
  endpoint is `display/api/counter/<id>/` and it listens on the same
  `counter-display` WebSocket as the browser's single counter display
- Tests: `python manage.py test` (queueing, dashboard API, public feedback, kiosk, WebSocket broadcasts, display board, single-counter JSON API)
