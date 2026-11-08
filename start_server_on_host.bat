@echo off
REM EQMS server launcher on the HOST machine.
REM Detects this machine's LAN IP automatically and starts the server bound to
REM 0.0.0.0 so any client (kiosk/display/counter) can reach it.
REM
REM First run creates .venv, installs requirements and migrates the database.
REM Optional env vars:
REM   EQMS_PORT   port to listen on (default 8000)
setlocal
cd /d "%~dp0"

set "PORT=%EQMS_PORT%"
if "%PORT%"=="" set "PORT=8000"

REM --- Detect this machine's LAN IP automatically ---
for /f %%i in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\get_ip.ps1"') do set "LAN_IP=%%i"
if "%LAN_IP%"=="" (
    echo Could not detect the LAN IP automatically.
    echo Check network settings or set the IP manually before this script runs.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :err
)

if not exist ".venv\Scripts\daphne.exe" (
    echo [2/4] Installing requirements...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 goto :err
)

echo [3/4] Collecting static files and running migrations...
".venv\Scripts\python.exe" manage.py collectstatic --noinput
if errorlevel 1 goto :err
".venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 goto :err

echo [4/4] Starting EQMS server on host IP %LAN_IP%:%PORT%
echo.
echo   Kiosk:      http://%LAN_IP%:%PORT%/
echo   Display:    http://%LAN_IP%:%PORT%/display/
echo   Counter:    http://%LAN_IP%:%PORT%/accounts/login/
echo   Admin:      http://%LAN_IP%:%PORT%/admin/
echo.
echo   Cancel with Ctrl+C
".venv\Scripts\daphne.exe" -b 0.0.0.0 -p %PORT% eqms.asgi:application
goto :eof

:err
echo.
echo Setup or startup failed. Check the error above.
pause
exit /b 1