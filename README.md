# TheDoom Gateway — Remote PC Control & Live System Monitor

> **Develop by Yourhacker with ❤️**  
> A simple, lightweight web dashboard to monitor your Windows PC and control it remotely from your phone, tablet, or another computer.

---

## ⚡ What Can You Do With This?

TheDoom Gateway turns your computer into a remotely manageable machine through your web browser. You don't need to install any heavy software or sign up for cloud services.

### 🎮 1. Remote PC Power Controls
Control your PC's power from your phone or another laptop:
* **Remote Shutdown**: Shut down your PC remotely with a 30-second warning countdown.
* **Remote Restart**: Reboot your PC remotely whenever it feels slow or needs a restart.
* **Emergency Abort / Cancel**: Accidentally pressed Shutdown or Restart? Click **Abort** within 30 seconds to immediately stop it.
* **Lock Screen**: Lock your Windows desktop instantly if you walked away from your desk. All your programs stay running safely.
* **Hibernate**: Put your PC into low-power hibernate mode without losing your open windows and files.

### 📊 2. Real-Time PC Activity Monitoring
Keep an eye on what your computer is doing from anywhere:
* **CPU & RAM Load**: Live percentage gauges showing processor load and memory used vs. free (e.g., `11.4 / 32.0 GB`).
* **Graphics Card (GPU)**: See your graphics card model and active load.
* **Live Internet Speeds**: Live download (`↓`) and upload (`↑`) speeds, plus total data used.
* **Active Running Apps**: View the top programs using memory (Chrome, games, background apps) with a **live search bar** to find any running app by name or PID.
* **Hard Drive Storage**: See all connected drives (`C:`, `D:`, USB drives) with free space and color-coded progress bars.
* **Network & IP Addresses**: Displays all network adapters (Wi-Fi, Ethernet, Tailscale) with a **1-Click Copy** button for each IP address.
* **Uptime & System Info**: See how long your computer has been running (`Uptime: 2d 4h 18m`) and Windows version.

---

## 🚀 How to Use It

### Step 1: Start the Dashboard on Your Windows PC
Open Command Prompt or PowerShell in this folder and run:
```powershell
python thedoomcontrol.py
```

### Step 2: Open the Dashboard on Any Device
Open your web browser (Chrome, Safari, Edge, etc.) on your phone, tablet, or laptop:

* **On the same PC**: Go to `http://localhost:6969`
* **On your phone (connected to the same Wi-Fi)**: Go to `http://<YOUR-PC-IP>:6969` (for example, `http://192.168.1.50:6969`)
* **From anywhere in the world (via Tailscale)**: Go to `http://100.64.0.2:6969` (or your PC's Tailscale IP)

### Step 3: Sign In
Enter the default passkey:
```text
20111
```
Click **Authenticate Gateway**, and your live dashboard will appear!

---

## 🎮 Remote Power Controls Explained

| Button | What It Does | Can You Cancel It? |
| :--- | :--- | :--- |
| **Shutdown** | Starts a 30-second timer on your PC before shutting down. | **Yes** — Click **Abort** on the dashboard within 30 seconds. |
| **Restart** | Starts a 30-second timer before rebooting your PC. | **Yes** — Click **Abort** on the dashboard within 30 seconds. |
| **Abort Shutdown** | Immediately cancels a pending shutdown or reboot. | N/A |
| **Lock Workstation** | Instantly locks your Windows screen. Running apps stay open. | Unlock with your normal Windows PIN/password. |
| **Hibernate** | Puts your PC to sleep, saving your open work to disk. | Press your PC power button to resume. |

---

## ⚙️ Changing Passkey & Settings

If you want to change your password or port, you can set them before starting the program:

### In PowerShell:
```powershell
# Change the login passkey
$env:DASHBOARD_PASSWORD = "MyNewPassword123"

# Change the port (default is 6969)
$env:PORT = "8080"

# Start the server
python thedoomcontrol.py
```

### In Command Prompt (CMD):
```cmd
set DASHBOARD_PASSWORD=MyNewPassword123
set PORT=8080
python thedoomcontrol.py
```

---

## 📁 Files Included

* **`thedoomcontrol.py`** — The main server script (run this to start the dashboard).
* **`telemetry.py`** — Handles real-time system monitoring (CPU, RAM, GPU, network, disks).
* **`web/dashboard.html`** — The clean, modern dashboard interface.
* **`web/login.html`** — The login screen with 3D animation.

---

## 🔒 Privacy & Safety

* **100% Private**: Runs entirely on your own PC. No third-party servers, no analytics, no external accounts.
* **Zero Installation**: Uses only built-in Windows and Python tools. No `pip install` required.
* **Protected**: Locked with your private passkey.

---

**Develop by Yourhacker with ❤️**
