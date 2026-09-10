@echo off
REM ============================================
REM EQMS Kiosk Mode Launcher
REM Run this on the dedicated kiosk PC
REM ============================================

REM Set the URL of your EQMS server
set EQMS_URL=http://localhost:8000

REM Find Chrome path (adjust if needed)
set CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME_PATH%" set CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME_PATH%" set CHROME_PATH=%LocalAppData%\Google\Chrome\Application\chrome.exe

REM Check if Chrome exists
if not exist "%CHROME_PATH%" (
    echo Chrome not found! Please install Google Chrome.
    pause
    exit /b 1
)

REM Start Chrome in kiosk mode with auto-print
echo Starting EQMS Kiosk Mode...
start "" "%CHROME_PATH%" --kiosk "%EQMS_URL%" --kiosk-printing --noerrdialogs --disable-session-crashed-bubble --disable-restore-session-state --disable-infobars

echo Kiosk started. Press Ctrl+Alt+Del to exit if needed.
