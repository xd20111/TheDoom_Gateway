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

## 🔑 Native Windows Authentication (Zero Password Setup)

You don't need to create or remember a separate dashboard passkey:
* **Uses Your Real Windows Password**: Sign in using your existing Windows account username and password.
* **Auto-Updates with Windows**: If you change your Windows password, it automatically reflects immediately on the web dashboard.
* **Pre-Login Startup Support**: If configured to start on boot, you can access the dashboard and log in from your phone even when the PC is sitting on the Windows lock screen before anyone has physically signed in.

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

### Step 3: Sign In with Your Windows Account
1. The **Windows Username** is pre-filled automatically (e.g. `xD.Tak`).
2. Type your **Windows Account Password**.
3. Click **Sign In to Node**, and your live dashboard will appear!

---

## ⏰ How to Run on Startup (Before Desktop Login)

If you want TheDoom Gateway to start automatically when your computer powers on—even before anyone physically logs into Windows:

1. Press `Win + R`, type `taskschd.msc`, and press **Enter** to open **Task Scheduler**.
2. Click **Create Task** (on the right pane).
3. Under the **General** tab:
   * Name: `TheDoom Gateway`
   * Check **"Run whether user is logged on or not"**
   * Check **"Run with highest privileges"**
4. Under the **Triggers** tab:
   * Click **New...** -> Begin the task: **At startup**.
5. Under the **Actions** tab:
   * Click **New...** -> Action: **Start a program**.
   * Program/script: `python` (or full path to your python.exe).
   * Add arguments: `thedoomcontrol.py`
   * Start in: `c:\Users\xD.Tak\Downloads\TheDoom_Gateway` (or full path to theDoom_Gateway folder).
6. Click **OK** and enter your Windows password.

Now, whenever your computer boots up, TheDoom Gateway will be online and accessible from your phone before anyone logs in!

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

## ⚙️ Custom Settings

You can customize the port or Tailscale IP before starting the server:

### In PowerShell:
```powershell
# Change the port (default is 6969)
$env:PORT = "8080"

# Change the Tailscale bind IP (optional)
$env:TAILSCALE_IP = "100.64.0.2"

# Start the server
python thedoomcontrol.py
```

---

## 📁 Files Included

* **`thedoomcontrol.py`** — The main server script with native Windows authentication and power dispatchers.
* **`telemetry.py`** — Handles real-time system monitoring (CPU, RAM, GPU, network, disks).
* **`web/dashboard.html`** — The clean, modern dashboard interface.
* **`web/login.html`** — The login screen with 3D animation and Windows account login.

---

## 🔒 Privacy & Safety

* **100% Private**: Runs entirely on your own PC. No third-party servers, no analytics, no external accounts.
* **Zero Installation**: Uses only built-in Windows and Python tools. No `pip install` required.
* **Windows Security**: Passwords are authenticated directly through the Windows Security subsystem (SAM/LSA) and never saved or logged.

---

**Develop by Yourhacker with ❤️**
