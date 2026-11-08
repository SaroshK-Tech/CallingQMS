@echo off
REM EQMS server launcher (Windows).
REM First run creates a virtual environment, installs requirements, migrates
REM the database, and starts the server bound to 0.0.0.0 so any machine on the
REM network can reach it.
REM
REM Optional environment variables:
REM   EQMS_HOST   bind address            (default 0.0.0.0)
REM   EQMS_PORT   bind port               (default 8000)
REM   EQMS_DEBUG  True/False              (default True)
setlocal
cd /d "%~dp0"

set "HOST=%EQMS_HOST%"
if "%HOST%"=="" set "HOST=0.0.0.0"
set "PORT=%EQMS_PORT%"
if "%PORT%"=="" set "PORT=8000"

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

echo [4/4] Starting EQMS on %HOST%:%PORT%
echo       Kiosk:      http://%HOST%:%PORT%/
echo       Display:    http://%HOST%:%PORT%/display/
echo       Counter:    http://%HOST%:%PORT%/accounts/login/
echo       Cancel with Ctrl+C
".venv\Scripts\daphne.exe" -b %HOST% -p %PORT% eqms.asgi:application
goto :eof

:err
echo.
echo Setup or startup failed. Check the error above.
exit /b 1