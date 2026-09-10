# EQMS Kiosk Launcher (PowerShell)
# Right-click > Run with PowerShell

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "       EQMS Kiosk Launcher" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Find Chrome
$ChromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$Chrome = $ChromePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Chrome) {
    Write-Host "[ERROR] Google Chrome not found!" -ForegroundColor Red
    Write-Host "Please install Chrome from: https://www.google.com/chrome/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Chrome: $Chrome" -ForegroundColor Green
Write-Host ""

# Start Django server
Write-Host "Starting Django server..." -ForegroundColor Yellow
Start-Process -FilePath "cmd" -ArgumentList "/k", "cd /d `"$ProjectDir`" && python manage.py runserver 0.0.0.0:8000" -WindowStyle Normal

Write-Host "Waiting for server to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Start Chrome kiosk
Write-Host "Starting Chrome kiosk mode..." -ForegroundColor Yellow
Start-Process -FilePath $Chrome -ArgumentList "--kiosk", "http://localhost:8000", "--kiosk-printing", "--noerrdialogs", "--disable-session-crashed-bubble", "--disable-restore-session-state", "--disable-infobars"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "       Kiosk is running!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "URL:   http://localhost:8000" -ForegroundColor White
Write-Host "Admin: http://localhost:8000/admin/" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to close this window"
