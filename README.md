# Wi-Fi File Share 

In this program:

- Phone to Windows file transfer over local Wi-Fi
- 6-digit temporary PIN protection
- QR code connection
- Multiple-file upload
- Upload progress and live transfer speed
- Search
- Download
- Delete with confirmation
- Automatic LAN IP detection
- Dark mode support
- Duplicate filename protection

## Easiest Windows start

Double-click:

```text
START_WIFI_SHARE.bat
```

On the first run it creates a virtual environment and installs the required packages.

Then PowerShell/Command Prompt shows:

```text
Laptop: http://127.0.0.1:5000
Other device: http://192.168.x.x:5000
PIN:    123456
```

Open the laptop URL in your browser. The page displays a QR code.

Scan the QR code using the iPhone Camera app and enter the displayed PIN.

## Manual start

```powershell
cd wifi_file_share
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Uploaded files are saved inside:

```text
uploads
```

## Important security note

The PIN prevents casual access, but this version still uses plain HTTP.
Use it only on a trusted local Wi-Fi network.

For stronger security, a future version should add HTTPS/TLS and stronger device pairing.
Made by:WMPG.