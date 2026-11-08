@echo off
cd /d "%~dp0"
start "EQMS Server" cmd /k "python manage.py runserver 0.0.0.0:8000"
ping -n 3 127.0.0.1 >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk http://localhost:8000 --kiosk-printing
