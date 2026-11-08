@echo off
REM EQMS kiosk launcher.
REM Asks for the server machine's IP once, stores it in kiosk_config.txt, then
REM opens the kiosk screen in fullscreen kiosk mode (Chrome if available, else Edge).
REM
REM Optional env var:
REM   EQMS_PORT   server port (default 8000) - must match the server's port
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "CONFIG=%~dp0kiosk_config.txt"
set "PORT=%EQMS_PORT%"
if "%PORT%"=="" set "PORT=8000"

if exist "%CONFIG%" goto :have_config

:ask
echo Enter the server machine's IP address (e.g. 192.168.1.10):
set /p SERVER_IP="Server IP: "
if "!SERVER_IP!"=="" goto :ask
echo !SERVER_IP!>"%CONFIG%"
goto :launch

:have_config
set /p STORED_IP=<"%CONFIG%"
echo Stored server IP: !STORED_IP!
set SERVER_IP=!STORED_IP!

:launch
if "!SERVER_IP!"=="" (
    echo No server IP configured.
    pause
    exit /b 1
)

set "URL=http://!SERVER_IP!:!PORT!/"
echo Opening kiosk: !URL!

REM --- Prefer Chrome, fall back to Edge, then default browser ---
set "CHROME="
where chrome >nul 2>nul && set "CHROME=chrome"
if not defined CHROME if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if defined CHROME (
    start "" "!CHROME!" --kiosk "!URL!" --kiosk-printing --noerrdialogs --disable-session-crashed-bubble --disable-restore-session-state --no-first-run --disable-infobars --autoplay-policy=no-user-gesture-required
    exit /b 0
)

set "EDGE="
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not defined EDGE if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if defined EDGE (
    start "" "!EDGE!" --kiosk --edge-kiosk-type=fullscreen "!URL!"
    exit /b 0
)

start "" "!URL!"
exit /b 0