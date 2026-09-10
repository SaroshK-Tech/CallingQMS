@echo off
title EQMS Kiosk System
cd /d "%~dp0"

echo ============================================
echo    EQMS Kiosk Deployment
echo ============================================
echo.

REM Find Chrome
set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if "%CHROME%"=="" (
    echo [ERROR] Google Chrome not found!
    echo Please install Chrome first.
    pause
    exit /b 1
)

echo Chrome found: %CHROME%
echo.
echo PREFERRED PRINTER CHECK:
echo   Open chrome://settings/printing and set:
echo   - Printer: your 80mm thermal printer
echo   - Paper size: 80mm
echo   - Margins: Default
echo   - Headers and footers: OFF
echo   - Scale: Default
echo.

REM Start Django server
echo Starting Django server...
start "EQMS Server" cmd /k "cd /d "%~dp0" && python manage.py runserver 0.0.0.0:8000"

echo Waiting for server...
ping -n 4 127.0.0.1 >nul

REM Start Chrome kiosk
echo Starting Chrome kiosk mode...
start "" "%CHROME%" --kiosk http://localhost:8000 --kiosk-printing --noerrdialogs --disable-session-crashed-bubble --disable-restore-session-state --disable-infobars

echo.
echo ============================================
echo    Kiosk is running!
echo ============================================
echo    URL: http://localhost:8000
echo    Admin: http://localhost:8000/admin/
echo ============================================
echo.
pause
