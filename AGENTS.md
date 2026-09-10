# AGENTS.md

## Project

EQMS-AlgoriSync: Real-time multi-counter queue management system (Django + Channels). Ticket generation at kiosk, live display boards, counter stations, and user dashboards.

## Tech Stack

- **Backend**: Django 6.1 + Django Channels (WebSocket support)
- **Frontend**: Vanilla HTML/CSS/JS with WebSocket communication
- **Database**: SQLite (development), easily swappable
- **ASGI Server**: Daphne
- **Audio**: gTTS pre-generated files (English + Urdu)

## Project Structure

```
eqms/           # Django project settings
core/           # Shared models, admin config
accounts/       # Login/logout, user management
kiosk/          # Ticket generation kiosk screen
counter/        # Counter dashboard, WebSocket consumers
display/        # Full display board (1:3 calls:ads ratio)
static/         # CSS, JS, images, audio files
templates/      # All HTML templates
```

## Key URLs

| Path | Description |
|------|-------------|
| `/` | Kiosk screen (public, ticket generation) |
| `/accounts/login/` | Counter user login |
| `/accounts/` | Dashboard redirect |
| `/counter/dashboard/` | Counter user dashboard (requires login) |
| `/counter/display/<id>/` | Single counter display |
| `/display/` | Full display board |
| `/admin/` | Django admin |

## Default Credentials

- **Admin**: `admin` / `admin123`
- **Counter 1 User**: `user1` / `user123`
- **Counter 2 User**: `user2` / `user123`

## Commands

```bash
# Run development server
python manage.py runserver

# Run with Daphne (WebSocket support)
daphne -b 0.0.0.0 -p 8000 eqms.asgi:application

# Generate audio files
python generate_audio.py

# Create superuser
python manage.py createsuperuser

# Run migrations
python manage.py makemigrations
python manage.py migrate
```

## Audio System

- Files stored in `static/audio/` as MP3
- Naming: `{lang}_{type}.mp3` (e.g., `en_ticket.mp3`, `ur_A.mp3`, `en_counter_counter_1.mp3`)
- Regenerate with `python generate_audio.py` when adding new counters
- For production: replace gTTS with professional voice service

## Models

- **Service**: Queue type (General=A, VIP=B, etc.)
- **Counter**: Physical counter/station
- **CounterService**: Links counters to services with sequence order
- **Ticket**: Generated ticket with number, status, current counter
- **TicketCall**: Audit log of ticket calls/recalls
- **CounterUser**: Links User to Counter
- **Advertisement**: Display board ads (images/videos)

## WebSocket Groups

- `dashboard_{counter_id}`: Counter user dashboard updates
- `display_board`: Full display board broadcasts
- `counter_display_{counter_id}`: Single counter display

## Key Features

1. **Kiosk**: Brand screen with logo, single button ticket generation, silent receipt printing
2. **Display Board**: 1/4 recent calls + 3/4 advertising, auto-refresh via WebSocket
3. **Counter Dashboard**: Select tickets from queue, call/recall/complete, next/prev navigation
4. **Audio Announcements**: English + Urdu, parametric generation for dynamic counter names
5. **Single Counter Display**: Shows current ticket for waiting area

## Setup Notes

1. First run: `python manage.py migrate && python manage.py createsuperuser`
2. Create services and counters in Django admin
3. Create user accounts and link to counters via admin
4. Generate audio files: `python generate_audio.py`
5. Run with Daphne for WebSocket support

## Development

- WebSocket consumers in `counter/consumers.py`
- Real-time updates broadcast to all connected clients
- Audio playback in `static/js/main.js` via AudioAnnouncer class
