# TheDoom Gateway — Remote PC Control & Live System Monitor

> **Develop by YourHacker with ❤️**  
> A lightweight, zero-dependency web dashboard to monitor your Windows PC hardware in real-time and control it remotely from any phone, tablet, or computer.

---

## ⚡ What Can You Do With This?

TheDoom Gateway turns your Windows computer into a remotely manageable machine through any modern web browser. You don't need to install any heavy software, install Python packages (`pip`), or sign up for cloud services.

### 🎮 1. Remote PC Power & Process Controls
Control your PC's power state and active programs from your phone or another laptop:
* **Remote Shutdown**: Shut down your PC remotely with an automatic 30-second warning countdown.
* **Remote Restart**: Reboot your PC remotely whenever it needs a clean restart.
* **Emergency Abort / Cancel**: Accidentally pressed Shutdown or Restart? Click **Abort** within 30 seconds to immediately cancel it.
* **Lock Screen**: Lock your Windows desktop instantly when walking away from your desk. All open programs remain running safely.
* **Hibernate**: Put your PC into low-power hibernate mode without losing your open windows and documents.
* **End Task / Kill Process**: Terminate hung applications, frozen software, or heavy background processes with 1 click directly from the apps table.

### 📊 2. Real-Time Hardware Telemetry
Monitor your computer's health and performance live from anywhere:
* **CPU & RAM Load**: Live percentage gauges showing processor load and memory used vs. free (e.g., `11.4 / 32.0 GB`).
* **Graphics Card (GPU)**: Real-time detection of dedicated graphics cards (NVIDIA / AMD / Intel) with live load percentages.
* **Power & Battery (UPS / Laptop)**: Real-time battery percentage, AC power status (`Plugged In` vs `On Battery`), charging state, and remaining battery runtime.
* **Live Network Speeds**: Real-time download (`↓`) and upload (`↑`) throughput counters, plus total data consumed.
* **Active Running Apps**: View top memory-consuming applications with a **live instant search filter** and **1-Click End Task** kill buttons.
* **Hard Drive Storage**: Visual breakdown of all connected drives (`C:`, `D:`, external USB drives) with free space and color-coded progress bars.
* **Network & IP Addresses**: Displays all network adapters (Wi-Fi, Ethernet, Tailscale) with a **1-Click Copy IP** button for each adapter.

### 🛠️ 3. Windows Services Watchdog & Manager
Inspect and control background Windows services right from the web browser:
* **Service Status**: View active and installed Windows services and system daemons.
* **1-Click Service Controls**: Start, Stop, or Restart Windows services directly from the dashboard.
* **Live Search Filter**: Quickly filter through services (e.g., `Tailscale`, `WinDefend`, `spooler`).
* **Clean Display**: Automatically hides uninstalled or unavailable services to keep your list clean and actionable.

### 🩺 4. Advanced Hardware Health & Diagnostics
Deep silicon telemetry and operational statistics:
* **Hardware Specs**: Detailed CPU architecture, core count, frequency (MHz), and GPU accelerator models.
* **System Uptime & Boot Time**: Displays system uptime (`2d 4h 18m`) and precise system boot timestamps.
* **Kernel Diagnostics**: Real-time Win32 low-latency API health verification.

### 📜 5. Security Audit Trail & Activity Log
Complete transparency and security logging:
* **Audit Trail**: Immutable record of all administrative operations performed through the gateway.
* **Event Logging**: Logs sign-in successes/failures, client IP addresses, remote power commands, and service start/stop operations with exact timestamps.
* **Log Controls**: Live refresh and clear log buttons directly inside the dashboard widget.

### 🌗 6. Theme Toggle & Fluid Responsive UI
Tailored for desktop monitors, tablets, and mobile screens:
* **Light & Dark Mode**: Default crisp Light theme with an instant high-contrast Dark Mode toggle button.
* **Zero Horizontal Scroll**: Locked column layouts ensure tables and widgets fit cleanly on mobile and laptop screens without horizontal sliders.
* **Persistent Preferences**: Saves your theme choice automatically in your browser's local storage.

---

## 🔑 Native Windows Authentication (Zero Password Setup)

You do not need to create or manage a separate password for the gateway:
* **Uses Your Real Windows Account**: Sign in using your existing Windows account username and password.
* **Auto-Updates with Windows**: Changing your Windows password automatically updates access on the web dashboard immediately.
* **Pre-Login Boot Support**: When configured to run at boot, you can access the dashboard and log in from your phone even when the PC is at the Windows lock screen before anyone has signed in.

---

## 🚀 How to Use It

Getting started takes just one click:

### Option A: 1-Click Instant Run (Quick Start)
Use this option to start the dashboard immediately on your PC:
1. Double-click **`run_gateway.bat`**.
2. Click **Yes** on the Windows Administrator prompt (UAC).
3. The gateway launches silently in the background, your web browser opens automatically to `http://localhost:6969`, and the terminal window automatically closes.

### Option B: 1-Click Windows Background Service Installer (Runs at Boot)
Use this option to set up the gateway to start automatically every time your PC turns on:
1. Double-click **`install_service.bat`** (or right-click and select **Run as Administrator**).
2. Click **Yes** on the Windows Administrator prompt (UAC).
3. The installer automatically:
   * Sets **Local Network (LAN)** mode as default (`0.0.0.0:6969`).
   * Automatically discovers and binds your machine's local IP address (zero hardcoded IPs).
   * Registers auto-start in **Windows Startup** and **Task Scheduler** with highest elevation privileges.
   * Starts the background service silently and opens your browser.
   * The installer terminal automatically closes once complete.

> [!TIP]
> **1-Click Boot Removal on Dashboard**: You do not need any separate uninstall script! You can enable or remove the boot auto-start service with 1 click directly inside the **Web Dashboard** under **Gateway & Boot Configuration**.

---

### Step 2: Access from Your Phone, Tablet, or Another PC

Once the gateway is running, open any web browser (Chrome, Safari, Edge, Firefox) on your device:

* **On the same PC**: Go to `http://localhost:6969`
* **On your phone / any device on your Wi-Fi or LAN (DEFAULT)**: Go to `http://<YOUR-SYSTEM-IP>:6969` (for example, `http://192.168.1.100:6969` — visible on your dashboard under Interfaces)
* **From anywhere outside your home (via Tailscale Mesh)**: Go to `http://<YOUR-TAILSCALE-IP>:6969`

---

### Step 3: Sign In with Your Windows Account

1. The **Windows Username** field is pre-filled automatically with your active Windows username.
2. Enter your **Windows Password**.
3. Click **Sign In to Node** to access the live dashboard!

---

## 🎮 Remote Power Controls Explained

| Button | What It Does | Can You Cancel It? |
| :--- | :--- | :--- |
| **Shutdown** | Initiates a 30-second shutdown timer on your PC with full warning. | **Yes** — Click **Abort** on the dashboard within 30 seconds. |
| **Restart** | Initiates a 30-second reboot timer on your PC. | **Yes** — Click **Abort** on the dashboard within 30 seconds. |
| **Abort Shutdown** | Immediately cancels any pending shutdown or restart timer. | N/A |
| **Lock Workstation** | Instantly locks your Windows screen. Running apps stay open. | Unlock with your standard Windows PIN or password. |
| **Hibernate** | Puts your PC into low-power hibernate mode, saving open work to disk. | Press your PC power button to resume. |

---


---

## 🔒 Privacy & Security

* **100% Private**: Runs entirely on your local machine. No external servers, no third-party telemetry, no cloud accounts.
* **Zero Dependency**: Built exclusively with the Python Standard Library and native Windows APIs. No `pip install` required.
* **Native Security**: Passwords are authenticated directly against the Windows Local Security Authority (LSA / SAM) and are never stored or logged in plaintext.

---

**Develop by YourHacker with ❤️**
