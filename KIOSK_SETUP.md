# EQMS Kiosk PC Setup Guide

## Prerequisites

1. **Windows PC** (Windows 10/11)
2. **Google Chrome** installed
3. **Python 3.8+** installed
4. **Thermal printer** connected (80mm recommended)

## Quick Start

### Option 1: One-Click Launch
1. Double-click `deploy_kiosk.bat`
2. The system will start Django server + Chrome kiosk mode automatically

### Option 2: Manual Setup

#### Step 1: Start Django Server
```bash
cd E:\agentProjects\EQMS-AlgoriSync
python manage.py runserver 0.0.0.0:8000
```

#### Step 2: Launch Chrome Kiosk Mode
```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk http://localhost:8000
```

## Auto-Start on Windows Boot

### Method 1: Startup Folder
1. Press `Win+R`, type `shell:startup`, press Enter
2. Create a shortcut to `deploy_kiosk.bat` in this folder

### Method 2: Task Scheduler (Recommended)
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: "When the computer starts"
4. Action: Start program → `deploy_kiosk.bat`
5. Check "Run with highest privileges"

## Chrome Kiosk Mode Flags

| Flag | Purpose |
|------|---------|
| `--kiosk` | Full screen kiosk mode |
| `--noerrdialogs` | Suppress error dialogs |
| `--disable-session-crashed-bubble` | No crash restore prompt |
| `--disable-restore-session-state` | Clean session start |
| `--disable-infobars` | Hide Chrome bars |
| `--disable-features=TranslateUI` | Disable translate popup |

## Exiting Kiosk Mode

- Press `Ctrl+Alt+Del` → Task Manager
- Or `Alt+F4` if keyboard is enabled
- Or create a hidden exit shortcut:
  ```
  chrome://settings
  ```

## Printer Setup

1. Install thermal printer drivers
2. Set as default printer in Windows
3. Configure paper size: **80mm**
4. **Critical Chrome print settings** (once, so `--kiosk-printing` reuses them):

   **Option A - by printing once:**
   1. Open kiosk page, press GET TICKET once (dialog appears)
   2. In the print dialog:
      - Printer: your thermal printer
      - Paper size: **80mm**
      - Margins: **Default**
      - **Uncheck "Headers and footers"**
      - **Uncheck "Background graphics"** (optional)
      - Scale: **Default** (100%)
   3. Click "Save" / close the dialog
   4. Chrome remembers these settings for silent `--kiosk-printing`

   **Option B - via chrome://settings:**
   1. Open `chrome://settings/printing`
   2. Make sure same options are set as above

5. Verify no headers/footers appear in the printed output

## Network Setup (Multi-PC)

If running kiosk + display boards on separate PCs:

1. Find server PC's IP address:
   ```bash
   ipconfig
   ```
2. Update `deploy_kiosk.bat`:
   ```batch
   set EQMS_URL=http://192.168.1.100:8000
   ```
3. Ensure firewall allows port 8000

## Troubleshooting

### Receipt has headers/footers (URL, date) on pages
- `--kiosk-printing` reuses the last print settings in Chrome
- Do ONE manual print (Ctrl+P) first with margins: **Default** and **Headers and footers unchecked**
- Chrome will then apply those settings to silent prints
- Alternatively open `chrome://settings/printing` and confirm the same

### Receipt prints on multiple pages
- Check printer paper size is set to **80mm** (not A4)
- Ensure scale is at 100% instead of fit-to-page
- Try printing manually first to verify

### Chrome won't start in kiosk mode
- Close all Chrome windows first
- Try: `taskkill /f /im chrome.exe`

### Receipt prints on multiple pages
- Check printer paper size settings
- Ensure "Fit to page" is disabled
- Try printing manually first to verify

### Server not starting
- Check if port 8000 is in use
- Try different port: `python manage.py runserver 0.0.0.0:8001`
