#!/usr/bin/env python3
"""
TheDoom Gateway — System & Hardware Telemetry Engine
Develop by Yourhacker with ❤️

Provides real-time system metrics for Windows (and cross-platform fallbacks):
- CPU instantaneous utilization via GetSystemTimes (ctypes)
- RAM usage & memory load via GlobalMemoryStatusEx (ctypes)
- GPU adapter detection & load telemetry (NVIDIA SMI / DirectX Registry)
- Live network throughput (Rx/Tx speed counters & totals via netstat -e)
- All connected physical & virtual disks with capacity/usage
- Connected network interfaces with IP addressing (Tailscale, Ethernet, Wi-Fi)
- Active running applications & memory footprint via tasklist
"""

import os
import platform
import shutil
import socket
import subprocess
import time
import ctypes
import csv
import html

# ==================== CONSTANTS & STRUCTURES ====================

class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint), ("dwHighDateTime", ctypes.c_uint)]

def _filetime_to_int(ft):
    return (ft.dwHighDateTime << 32) + ft.dwLowDateTime

PREV_CPU_TIMES = {"idle": 0, "kernel": 0, "user": 0}
PREV_NET_THROUGHPUT = {"rx": 0, "tx": 0, "time": 0.0}

# ==================== SYSTEM UPTIME ====================

def get_system_uptime():
    """Retrieve Windows system uptime using GetTickCount64."""
    try:
        kernel32 = ctypes.windll.kernel32
        uptime_ms = kernel32.GetTickCount64()
        uptime_sec = uptime_ms // 1000
        days = uptime_sec // 86400
        hours = (uptime_sec % 86400) // 3600
        minutes = (uptime_sec % 3600) // 60
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        uptime_str = " ".join(parts) if parts else "< 1m"
        
        boot_epoch = time.time() - uptime_sec
        boot_str = time.strftime("%b %d, %Y · %I:%M %p", time.localtime(boot_epoch))
        return {
            "uptime_str": uptime_str,
            "boot_str": boot_str,
            "uptime_sec": int(uptime_sec),
            "days": int(days),
            "hours": int(hours),
            "minutes": int(minutes)
        }
    except Exception:
        return {
            "uptime_str": "Online",
            "boot_str": "System Boot Active",
            "uptime_sec": 0,
            "days": 0,
            "hours": 0,
            "minutes": 0
        }

# ==================== HARDWARE DIAGNOSTICS ====================

def get_cpu_hardware_info():
    """Retrieve detailed CPU processor model, clock, and architecture."""
    cpu_info = {
        "model": platform.processor() or "Multi-Core x86_64 Processor",
        "cores": os.cpu_count() or 4,
        "arch": platform.machine() or "x86_64",
        "mhz": ""
    }
    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            if name:
                cpu_info["model"] = name.strip()
            try:
                mhz, _ = winreg.QueryValueEx(key, "~MHz")
                if mhz:
                    cpu_info["mhz"] = f"{mhz} MHz"
            except Exception:
                pass
            winreg.CloseKey(key)
        except Exception:
            pass
    return cpu_info

# ==================== WINDOWS SERVICES WATCHDOG ====================

KEY_WINDOWS_SERVICES = [
    {"name": "Tailscale", "display": "Tailscale VPN Mesh Engine", "desc": "WireGuard peer mesh network"},
    {"name": "com.docker.service", "display": "Docker Desktop Engine", "desc": "Container virtualization runtime"},
    {"name": "wslservice", "display": "Windows Subsystem for Linux (WSL)", "desc": "Linux kernel translation service"},
    {"name": "Spooler", "display": "Print Spooler Service", "desc": "Spools print jobs and printer communication"},
    {"name": "wuauserv", "display": "Windows Update Agent", "desc": "Detects and downloads Windows patches"},
    {"name": "LanmanServer", "display": "SMB Server (File Sharing)", "desc": "Network file and named-pipe sharing"},
    {"name": "bthserv", "display": "Bluetooth Audio & Device Engine", "desc": "Discovers and manages Bluetooth devices"},
    {"name": "AudioSrv", "display": "Windows Audio Core", "desc": "Manages host audio playback stream"},
    {"name": "WSearch", "display": "Windows Search Indexer", "desc": "Content indexing for instant file lookup"},
    {"name": "sshd", "display": "OpenSSH Server Daemon", "desc": "Secure Shell remote terminal access"},
    {"name": "TermService", "display": "Remote Desktop Services (RDP)", "desc": "Remote multi-session desktop protocol"},
]

def get_windows_services():
    """Queries key Windows services with live operational status."""
    services_data = []
    if platform.system() != "Windows":
        return services_data

    status_map = {}
    try:
        res = subprocess.run(
            ['sc.exe', 'query', 'type=', 'service', 'state=', 'all'],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        if res.returncode == 0:
            current_svc = None
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.upper().startswith("SERVICE_NAME:"):
                    current_svc = line.split(":", 1)[1].strip().lower()
                elif line.upper().startswith("STATE") and current_svc:
                    parts = line.split(":", 1)[1].strip().split()
                    st = parts[1] if len(parts) > 1 else parts[0]
                    status_map[current_svc] = st.upper()
                    current_svc = None
    except Exception:
        pass

    for ks in KEY_WINDOWS_SERVICES:
        s_name = ks["name"]
        st = status_map.get(s_name.lower())
        if not st:
            try:
                q_res = subprocess.run(
                    ['sc.exe', 'query', s_name],
                    capture_output=True, text=True, timeout=2,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
                if q_res.returncode == 0:
                    for l in q_res.stdout.splitlines():
                        if "STATE" in l.upper():
                            p = l.split(":", 1)[1].strip().split()
                            st = p[1].upper() if len(p) > 1 else p[0].upper()
                            break
            except Exception:
                pass

        # If service is not installed on this machine, DO NOT show it
        if not st:
            continue

        services_data.append({
            "name": s_name,
            "display": ks["display"],
            "desc": ks["desc"],
            "status": st
        })
    return services_data

# ==================== BATTERY & POWER TELEMETRY ====================

class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("SystemStatusFlag", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]

def get_battery_telemetry():
    """Retrieve Windows laptop battery or UPS power status via GetSystemPowerStatus."""
    if platform.system() != "Windows":
        return {
            "has_battery": False,
            "status": "AC Power",
            "percent": 100,
            "val": "Mains Power",
            "sub": "AC Line Active · Direct Feed",
            "color": "#10b981"
        }

    try:
        sps = SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
            return {
                "has_battery": False,
                "status": "AC Power",
                "percent": 100,
                "val": "Mains Power",
                "sub": "AC Line Active",
                "color": "#10b981"
            }

        no_battery = (sps.BatteryFlag & 128) != 0 or sps.BatteryLifePercent == 255
        ac_online = sps.ACLineStatus == 1

        if no_battery:
            return {
                "has_battery": False,
                "ac_online": ac_online,
                "is_charging": False,
                "percent": 100,
                "val": "Desktop AC",
                "status": "AC Mains Online",
                "sub": "Mains Line Power Active · Direct Feed",
                "color": "#10b981"
            }

        percent = int(sps.BatteryLifePercent)
        is_charging = (sps.BatteryFlag & 8) != 0

        if is_charging:
            color = "#10b981"
            val = f"{percent}% Charging"
            status = "Charging (AC)"
            sub = "AC Connected · Battery Accumulating"
        elif ac_online:
            color = "#10b981"
            val = f"{percent}% (On AC)"
            status = "Plugged In"
            sub = "AC Connected · Battery Full / Idle"
        else:
            if percent <= 15:
                color = "#df1b41"
            elif percent <= 30:
                color = "#f59e0b"
            else:
                color = "#0284c7"
            val = f"{percent}% Battery"
            status = "On Battery"
            sub = "Discharging · Running on Battery"

        if not ac_online and sps.BatteryLifeTime != 0xFFFFFFFF and sps.BatteryLifeTime > 0:
            hrs = sps.BatteryLifeTime // 3600
            mins = (sps.BatteryLifeTime % 3600) // 60
            if hrs > 0:
                sub = f"Discharging · ~{hrs}h {mins}m left"
            else:
                sub = f"Discharging · ~{mins}m left"

        return {
            "has_battery": True,
            "ac_online": ac_online,
            "is_charging": is_charging,
            "percent": percent,
            "val": val,
            "status": status,
            "sub": sub,
            "color": color
        }
    except Exception:
        return {
            "has_battery": False,
            "status": "AC Power",
            "percent": 100,
            "val": "Mains Power",
            "sub": "AC Line Active",
            "color": "#10b981"
        }

# ==================== ALL DISKS & STORAGE ====================

def get_all_disks():
    """Returns all available storage volumes with capacity, used, and free space."""
    disks = []
    if platform.system() == "Windows":
        import string
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                try:
                    total, used, free = shutil.disk_usage(drive_path)
                    if total > 0:
                        pct = int((used / total) * 100)
                        total_gb = total / (1024**3)
                        used_gb = used / (1024**3)
                        free_gb = free / (1024**3)

                        total_str = f"{total_gb / 1024:.1f} TB" if total_gb >= 1000 else f"{total_gb:.0f} GB"
                        used_str = f"{used_gb / 1024:.1f} TB" if used_gb >= 1000 else f"{used_gb:.0f} GB"
                        free_str = f"{free_gb / 1024:.1f} TB" if free_gb >= 1000 else f"{free_gb:.0f} GB"

                        label = "System Drive (C:)" if letter == "C" else f"Storage Volume ({letter}:)"
                        disks.append({
                            "drive": f"{letter}:",
                            "label": label,
                            "path": drive_path,
                            "total": total_str,
                            "used": used_str,
                            "free": free_str,
                            "percent": pct
                        })
                except Exception:
                    pass
    else:
        mounts = ["/"]
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].startswith("/dev/"):
                        mp = parts[1]
                        if mp not in mounts and not mp.startswith("/boot"):
                            mounts.append(mp)
        except Exception:
            pass
        for mp in mounts:
            try:
                total, used, free = shutil.disk_usage(mp)
                if total > 0:
                    pct = int((used / total) * 100)
                    total_gb = total / (1024**3)
                    used_gb = used / (1024**3)
                    free_gb = free / (1024**3)
                    disks.append({
                        "drive": mp,
                        "label": f"Volume {mp}",
                        "path": mp,
                        "total": f"{total_gb:.0f} GB",
                        "used": f"{used_gb:.0f} GB",
                        "free": f"{free_gb:.0f} GB",
                        "percent": pct
                    })
            except Exception:
                pass
    return disks

# ==================== NETWORK INTERFACES ====================

def get_network_interfaces(tailscale_ip=None):
    """Gathers all connected network interfaces and their IPv4 addresses without hardcoded values."""
    interfaces = []
    if platform.system() == "Windows":
        try:
            proc = subprocess.run(
                ["ipconfig.exe", "/all"],
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if proc.returncode == 0:
                current_adapter = None
                adapter_desc = ""
                is_disconnected = False
                for line in proc.stdout.splitlines():
                    trimmed = line.strip()
                    if "adapter " in line.lower() and line.rstrip().endswith(":"):
                        current_adapter = line.split("adapter ", 1)[-1].rstrip(":").strip()
                        adapter_desc = ""
                        is_disconnected = False
                    elif "media state" in line.lower() and "disconnected" in line.lower():
                        is_disconnected = True
                    elif "description" in line.lower() and ":" in line:
                        adapter_desc = line.split(":", 1)[1].strip()
                    elif ("ipv4 address" in line.lower() or "adresse ipv4" in line.lower() or "ipv4-adresse" in line.lower() or "direcci" in line.lower()) and ":" in line:
                        if current_adapter and not is_disconnected:
                            raw_ip = line.split(":", 1)[1].strip()
                            ip_val = raw_ip.split("(")[0].strip()
                            if ip_val and not ip_val.startswith("127."):
                                atype = "Ethernet"
                                cname = (current_adapter + " " + adapter_desc).lower()
                                if "tailscale" in cname or "vpn" in cname or "wireguard" in cname:
                                    atype = "Mesh VPN"
                                elif "wi-fi" in cname or "wireless" in cname or "wlan" in cname or "802.11" in cname:
                                    atype = "Wi-Fi"
                                elif "vethernet" in cname or "hyper-v" in cname or "virtual" in cname or "vmware" in cname or "vbox" in cname or "ndis" in cname:
                                    atype = "Virtual"
                                elif "bluetooth" in cname:
                                    atype = "Bluetooth"
                                interfaces.append({
                                    "name": current_adapter,
                                    "desc": adapter_desc or current_adapter,
                                    "ip": ip_val,
                                    "type": atype,
                                    "status": "Connected"
                                })
        except Exception:
            pass

    # Dynamic check for Tailscale CLI if Tailscale is running as daemon
    has_tailscale = any("tailscale" in (i["name"] + " " + i["desc"]).lower() or i["type"] == "Mesh VPN" for i in interfaces)
    if not has_tailscale:
        try:
            ts_proc = subprocess.run(
                ["tailscale.exe", "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if ts_proc.returncode == 0 and ts_proc.stdout.strip():
                ts_ip = ts_proc.stdout.strip().splitlines()[0].strip()
                if ts_ip and not ts_ip.startswith("127."):
                    interfaces.insert(0, {
                        "name": "Tailscale",
                        "desc": "Tailscale WireGuard Mesh",
                        "ip": ts_ip,
                        "type": "Mesh VPN",
                        "status": "Connected"
                    })
        except Exception:
            pass

    # Fallback to socket inspection if ipconfig produced nothing
    if not interfaces:
        try:
            hostname = socket.gethostname()
            host_ips = socket.gethostbyname_ex(hostname)[2]
            for idx, ip_str in enumerate(host_ips):
                if not ip_str.startswith("127."):
                    atype = "Ethernet"
                    if ip_str.startswith("100."):
                        atype = "Mesh VPN"
                    elif ip_str.startswith("192.168.") or ip_str.startswith("10.") or ip_str.startswith("172."):
                        atype = "LAN"
                    interfaces.append({
                        "name": f"Adapter {idx + 1}",
                        "desc": f"Host Network Interface ({hostname})",
                        "ip": ip_str,
                        "type": atype,
                        "status": "Connected"
                    })
        except Exception:
            pass

    # Deduplicate interfaces by IP
    seen_ips = set()
    unique_interfaces = []
    for iface in interfaces:
        if iface["ip"] not in seen_ips:
            seen_ips.add(iface["ip"])
            unique_interfaces.append(iface)

    return unique_interfaces

def get_system_ips():
    """
    Dynamically identifies the host system's real IP addresses:
    - lan: Real primary active IPv4 on the local network (e.g. 192.168.1.100, 10.x.x.x)
    - tailscale: Real active Tailscale IPv4 (100.x.x.x) if installed and running
    - localhost: 127.0.0.1
    - has_tailscale: bool
    Zero hardcoded IP addresses.
    """
    lan_ip = ""
    tailscale_ip = ""

    ifaces = get_network_interfaces()
    for iface in ifaces:
        ip = iface.get("ip", "")
        itype = iface.get("type", "")
        iname = (iface.get("name", "") + " " + iface.get("desc", "")).lower()

        # Tailscale check (RFC 6598 CGNAT range 100.64.0.0/10 or adapter name)
        if "tailscale" in iname or itype == "Mesh VPN" or (ip.startswith("100.") and ip.count(".") == 3):
            try:
                second_octet = int(ip.split(".")[1])
                if 64 <= second_octet <= 127:
                    if not tailscale_ip and not ip.startswith("127."):
                        tailscale_ip = ip
            except (ValueError, IndexError):
                if not tailscale_ip and not ip.startswith("127."):
                    tailscale_ip = ip

        # LAN check: active physical Ethernet or Wi-Fi (exclude loopback, APIPA, Tailscale, virtual switches if physical present)
        elif itype in ("Ethernet", "Wi-Fi", "LAN") and not ip.startswith("169.254.") and not ip.startswith("127.") and not ip.startswith("100."):
            # Prefer non-virtual adapters for primary LAN IP
            is_virtual = any(v in iname for v in ("vmware", "vbox", "vethernet", "virtual", "default switch"))
            if not lan_ip or (is_virtual is False and any(v in lan_ip for v in ("vmware", "172.29."))):
                lan_ip = ip

    # If Tailscale CLI is available on PATH, check for real IP
    if not tailscale_ip:
        try:
            ts_res = subprocess.run(
                ["tailscale.exe", "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if ts_res.returncode == 0 and ts_res.stdout.strip():
                candidate = ts_res.stdout.strip().splitlines()[0].strip()
                if candidate and not candidate.startswith("127."):
                    tailscale_ip = candidate
        except Exception:
            pass

    # If LAN IP not identified yet, detect outbound routing socket without sending packets
    if not lan_ip:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            sock_ip = s.getsockname()[0]
            s.close()
            if sock_ip and not sock_ip.startswith("127.") and not sock_ip.startswith("169.254."):
                if sock_ip.startswith("100."):
                    if not tailscale_ip:
                        tailscale_ip = sock_ip
                else:
                    lan_ip = sock_ip
        except Exception:
            pass

    # Fallback to general socket host IP resolution
    if not lan_ip:
        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    if ip.startswith("100."):
                        if not tailscale_ip:
                            tailscale_ip = ip
                    else:
                        lan_ip = ip
                        break
        except Exception:
            pass

    return {
        "localhost": "127.0.0.1",
        "lan": lan_ip or "127.0.0.1",
        "tailscale": tailscale_ip or "",
        "has_tailscale": bool(tailscale_ip)
    }

# ==================== GPU ACCELERATION ====================

def get_gpu_telemetry():
    """Gathers GPU usage, name, memory and status."""
    gpu = {
        "name": "Integrated Graphics",
        "load": "Active",
        "percent": 0,
        "memory_used": "",
        "memory_total": "",
        "temp": "",
        "status": "Hardware Accelerated"
    }
    # 1. NVIDIA-SMI
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.total,memory.used,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if proc.returncode == 0 and proc.stdout.strip():
            first_line = proc.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first_line.split(",")]
            if len(parts) >= 5:
                gpu["name"] = parts[0]
                try:
                    gpu["percent"] = int(parts[1])
                    gpu["load"] = f"{gpu['percent']}% Load"
                except ValueError:
                    gpu["load"] = "Active"
                gpu["memory_total"] = f"{int(parts[2]) / 1024:.1f} GB" if int(parts[2]) >= 1024 else f"{parts[2]} MB"
                gpu["memory_used"] = f"{int(parts[3]) / 1024:.1f} GB" if int(parts[3]) >= 1024 else f"{parts[3]} MB"
                gpu["temp"] = f"{parts[4]}°C"
                gpu["status"] = "NVIDIA Dedicated"
                return gpu
    except Exception:
        pass

    # 2. Windows Registry for Display Adapters
    if platform.system() == "Windows":
        try:
            import winreg
            key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as base_key:
                num_subkeys = winreg.QueryInfoKey(base_key)[0]
                detected_names = []
                for i in range(num_subkeys):
                    subkey_name = winreg.EnumKey(base_key, i)
                    if subkey_name.isdigit():
                        try:
                            with winreg.OpenKey(base_key, subkey_name) as subkey:
                                driver_desc, _ = winreg.QueryValueEx(subkey, "DriverDesc")
                                if driver_desc and "display" not in driver_desc.lower() and "basic" not in driver_desc.lower():
                                    detected_names.append(driver_desc)
                        except Exception:
                            pass
                if detected_names:
                    primary = detected_names[0]
                    for d in detected_names:
                        if any(k in d.lower() for k in ["rtx", "gtx", "radeon", "nvidia", "geforce", "arc"]):
                            primary = d
                            break
                    gpu["name"] = primary
                    gpu["load"] = "Active (3D Engine)"
                    gpu["status"] = "Hardware Accelerated"
                    return gpu
        except Exception:
            pass

    return gpu

# ==================== CPU UTILIZATION ====================

def get_cpu_utilization():
    """Calculates instantaneous CPU utilization percentage across all logical cores."""
    global PREV_CPU_TIMES
    try:
        idle, kern, user = FILETIME(), FILETIME(), FILETIME()
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
            i = _filetime_to_int(idle)
            k = _filetime_to_int(kern)
            u = _filetime_to_int(user)
            if PREV_CPU_TIMES["kernel"] == 0:
                PREV_CPU_TIMES["idle"] = i
                PREV_CPU_TIMES["kernel"] = k
                PREV_CPU_TIMES["user"] = u
                time.sleep(0.06)
                ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
                i = _filetime_to_int(idle)
                k = _filetime_to_int(kern)
                u = _filetime_to_int(user)

            d_idle = i - PREV_CPU_TIMES["idle"]
            d_kern = k - PREV_CPU_TIMES["kernel"]
            d_user = u - PREV_CPU_TIMES["user"]
            PREV_CPU_TIMES["idle"] = i
            PREV_CPU_TIMES["kernel"] = k
            PREV_CPU_TIMES["user"] = u

            d_total = d_kern + d_user
            if d_total > 0:
                pct = int(((d_total - d_idle) / d_total) * 100)
                return max(0, min(100, pct))
    except Exception:
        pass
    return 8

# ==================== NETWORK THROUGHPUT ====================

def get_network_throughput():
    """Calculates live upload/download speed and cumulative transferred bytes."""
    global PREV_NET_THROUGHPUT
    now = time.time()
    rx_bytes = 0
    tx_bytes = 0
    try:
        res = subprocess.run(
            ["netstat.exe", "-e"],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "bytes" in line.lower():
                    parts = line.split()
                    if len(parts) >= 3:
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[2])
                    break
    except Exception:
        pass

    rx_speed = 0.0
    tx_speed = 0.0
    if PREV_NET_THROUGHPUT["time"] > 0 and now > PREV_NET_THROUGHPUT["time"]:
        dt = now - PREV_NET_THROUGHPUT["time"]
        if rx_bytes >= PREV_NET_THROUGHPUT["rx"]:
            rx_speed = (rx_bytes - PREV_NET_THROUGHPUT["rx"]) / dt
        if tx_bytes >= PREV_NET_THROUGHPUT["tx"]:
            tx_speed = (tx_bytes - PREV_NET_THROUGHPUT["tx"]) / dt

    PREV_NET_THROUGHPUT["rx"] = rx_bytes
    PREV_NET_THROUGHPUT["tx"] = tx_bytes
    PREV_NET_THROUGHPUT["time"] = now

    def _fmt_speed(bps):
        if bps >= 1024 * 1024:
            return f"{bps / (1024 * 1024):.1f} MB/s"
        elif bps >= 1024:
            return f"{bps / 1024:.0f} KB/s"
        else:
            return f"{int(bps)} B/s"

    def _fmt_total(b):
        if b >= 1024**3:
            return f"{b / (1024**3):.1f} GB"
        elif b >= 1024**2:
            return f"{b / (1024**2):.0f} MB"
        else:
            return f"{b / 1024:.0f} KB"

    return {
        "rx_speed": _fmt_speed(rx_speed),
        "tx_speed": _fmt_speed(tx_speed),
        "total_rx": _fmt_total(rx_bytes),
        "total_tx": _fmt_total(tx_bytes),
        "rx_bytes": rx_bytes,
        "tx_bytes": tx_bytes
    }

def get_system_telemetry(tailscale_ip=None, port=6969, access_mode="lan"):
    """Gathers real-time host telemetry: CPU, GPU, RAM, Throughput, Disks, and Network without hardcoded values."""
    node = platform.node() or "TheDoom"
    os_name = f"{platform.system()} {platform.release()}"
    cpu_cores = os.cpu_count() or 4
    cpu_percent = get_cpu_utilization()
    throughput = get_network_throughput()

    uptime_data = get_system_uptime()
    uptime_val = uptime_data.get("uptime_str", "Online") if isinstance(uptime_data, dict) else str(uptime_data)
    boot_str = uptime_data.get("boot_str", "System Boot Active") if isinstance(uptime_data, dict) else "System Boot Active"

    # Dynamically detect host system's real IP addresses
    sys_ips = get_system_ips()
    actual_ts_ip = tailscale_ip if tailscale_ip else sys_ips.get("tailscale", "")
    actual_lan_ip = sys_ips.get("lan", "127.0.0.1")

    telemetry = {
        "hostname": node,
        "os": os_name,
        "uptime": uptime_val,
        "boot_time": boot_str,
        "access_mode": access_mode,
        "tailscale_ip": actual_ts_ip,
        "lan_ip": actual_lan_ip,
        "has_tailscale": bool(actual_ts_ip),
        "port": port,
        "cpu_percent": cpu_percent,
        "cpu_cores": cpu_cores,
        "ram_used_gb": "0",
        "ram_total_gb": "0",
        "ram_avail_gb": "0",
        "ram_percent": 0,
        "disk_free_gb": "0",
        "disk_total_gb": "0",
        "disk_percent": 0,
        "primary_disk_free": "0 GB",
        "primary_disk_total": "0 GB",
        "primary_disk_percent": 0,
        "disks": [],
        "interfaces": [],
        "primary_ip": actual_lan_ip,
        "net_rx_speed": throughput["rx_speed"],
        "net_tx_speed": throughput["tx_speed"],
        "net_total_rx": throughput["total_rx"],
        "net_total_tx": throughput["total_tx"],
        "gpu": {
            "name": "Integrated Graphics",
            "load": "Active",
            "percent": 0,
            "memory_used": "",
            "memory_total": "",
            "temp": "",
            "status": "Hardware Accelerated"
        },
        "process_count": 0,
        "top_processes": []
    }

    # 1. Windows RAM via GlobalMemoryStatusEx
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_gb = stat.ullTotalPhys / (1024**3)
            avail_gb = stat.ullAvailPhys / (1024**3)
            used_gb = total_gb - avail_gb
            telemetry["ram_used_gb"] = f"{used_gb:.1f}"
            telemetry["ram_total_gb"] = f"{total_gb:.1f}"
            telemetry["ram_avail_gb"] = f"{avail_gb:.1f}"
            telemetry["ram_percent"] = int(stat.dwMemoryLoad)
    except Exception:
        pass

    # 2. All Disks & Storage Space
    all_disks = get_all_disks()
    telemetry["disks"] = all_disks
    if all_disks:
        telemetry["disk_free_gb"] = all_disks[0]["free"].replace(" GB", "").replace(" TB", "")
        telemetry["disk_total_gb"] = all_disks[0]["total"].replace(" GB", "").replace(" TB", "")
        telemetry["disk_percent"] = all_disks[0]["percent"]
        telemetry["primary_disk_free"] = all_disks[0]["free"]
        telemetry["primary_disk_total"] = all_disks[0]["total"]
        telemetry["primary_disk_percent"] = all_disks[0]["percent"]

    # 3. Network Interfaces with IP
    all_ifaces = get_network_interfaces(actual_ts_ip)
    telemetry["interfaces"] = all_ifaces

    if access_mode == "localhost":
        primary_ip = "127.0.0.1"
    elif access_mode == "tailscale" and actual_ts_ip:
        primary_ip = actual_ts_ip
    else:  # "lan" (Default: Local Network)
        primary_ip = actual_lan_ip

    telemetry["primary_ip"] = primary_ip or actual_lan_ip or "127.0.0.1"

    has_mesh = bool(actual_ts_ip) or any(i.get("type") == "Mesh VPN" or "tailscale" in (i.get("name", "") + " " + i.get("desc", "")).lower() for i in all_ifaces)
    telemetry["mesh_status"] = f"Tailscale Active ({actual_ts_ip})" if actual_ts_ip else ("Tailscale WireGuard" if has_mesh else "Local Network Direct")

    # 4. GPU Telemetry
    telemetry["gpu"] = get_gpu_telemetry()

    # 5. Active Processes via tasklist.exe
    try:
        proc = subprocess.run(
            ["tasklist.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if proc.returncode == 0:
            lines = proc.stdout.strip().splitlines()
            telemetry["process_count"] = len(lines)
            apps = {}
            for row in csv.reader(lines):
                if len(row) >= 5:
                    pname = row[0].strip()
                    pid = row[1].strip()
                    mem_str = row[4].replace(" K", "").replace(",", "").replace(".", "").replace("\xa0", "").strip()
                    try:
                        mem_kb = int(mem_str)
                    except ValueError:
                        mem_kb = 0
                    if pname not in apps or mem_kb > apps[pname]["mem_kb"]:
                        apps[pname] = {"pid": pid, "mem_kb": mem_kb}

            sorted_apps = sorted(apps.items(), key=lambda x: x[1]["mem_kb"], reverse=True)[:50]
            colors = ["#3b82f6", "#0284c7", "#6366f1", "#10b981", "#f59e0b", "#64748b", "#ec4899", "#8b5cf6"]
            formatted = []
            for idx, (name, data) in enumerate(sorted_apps):
                mem_kb = data["mem_kb"]
                if mem_kb >= 1024 * 1024:
                    mem_label = f"{mem_kb / (1024 * 1024):.1f} GB"
                else:
                    mem_label = f"{mem_kb / 1024:.0f} MB"
                formatted.append({
                    "name": name,
                    "pid": data["pid"],
                    "memory": mem_label,
                    "color": colors[idx % len(colors)]
                })
            telemetry["top_processes"] = formatted
    except Exception:
        pass

    # 6. Battery & Power Status
    telemetry["battery"] = get_battery_telemetry()

    # 7. Windows Services Watchdog
    telemetry["services"] = get_windows_services()

    # 8. Hardware Diagnostics
    telemetry["hardware"] = get_cpu_hardware_info()

    return telemetry
 
# ==================== HTML TEMPLATE RENDERING ====================

def render_disks_html(disks):
    if not disks:
        return '<div style="color: var(--text-muted); font-size: 12px; padding: 12px;">No disk drives detected.</div>'
    cards = []
    for d in disks:
        drive = html.escape(str(d.get('drive', 'Drive')))
        mount = html.escape(str(d.get('path') or d.get('mount') or d.get('label') or drive))
        total = html.escape(str(d.get('total', '0 GB')))
        used = html.escape(str(d.get('used', '0 GB')))
        free = html.escape(str(d.get('free', '0 GB')))
        percent = d.get('percent', 0)
        card = f'''<div style="background: #ffffff; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 24px; height: 24px; border-radius: 6px; background: rgba(10,37,64,0.05); display: flex; align-items: center; justify-content: center; color: var(--text-navy);">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
                    </div>
                    <div>
                        <div style="font-weight: 700; font-size: 13px; color: var(--text-navy);">{drive}</div>
                        <div style="font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">Mount: {mount}</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text-navy);">{free} Free</div>
                    <div style="font-size: 11px; color: var(--text-muted);">{used} used of {total}</div>
                </div>
            </div>
            <div class="progress-bar-thin" style="height: 6px; background: #e6ebf1; border-radius: 3px; overflow: hidden;">
                <div class="bar-fill fill-emerald" style="width: {percent}%; height: 100%; border-radius: 3px;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-light);">
                <span>Volume Load: {percent}%</span>
                <span>Total: {total}</span>
            </div>
        </div>'''
        cards.append(card)
    return '\n'.join(cards)


def render_interfaces_html(interfaces):
    if not interfaces:
        return '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:14px;">No active interfaces found.</td></tr>'
    rows = []
    for iface in interfaces:
        name = html.escape(str(iface.get('name', 'Interface')))
        desc = html.escape(str(iface.get('desc', '')))
        ip = html.escape(str(iface.get('ip', '')))
        itype = html.escape(str(iface.get('type', 'Ethernet')))
        status = html.escape(str(iface.get('status', 'Connected')))
        dot_color = '#00ff66' if 'mesh' in itype.lower() or 'tailscale' in name.lower() else '#8898aa'
        
        row = f'''<tr>
            <td>
                <div class="proc-name-cell">
                    <span class="proc-dot" style="background: {dot_color};"></span>
                    <div>
                        <div style="font-weight: 600; color: var(--text-navy); font-size: 13px;">{name}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">{desc}</div>
                    </div>
                </div>
            </td>
            <td>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span class="ip-pill">{ip}</span>
                    <button type="button" class="btn-copy-ip" onclick="navigator.clipboard.writeText('{ip}'); this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy', 1500);">Copy</button>
                </div>
            </td>
            <td>
                <span style="font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; background: rgba(99,91,255,0.08); color: var(--stripe-blurple); border: 1px solid rgba(99,91,255,0.2);">{itype}</span>
            </td>
            <td>
                <span class="tag-active" style="display: inline-flex; align-items: center; gap: 4px;">
                    <span style="width: 6px; height: 6px; border-radius: 50%; background: #10b981; display: inline-block;"></span>
                    <span>{status}</span>
                </span>
            </td>
        </tr>'''
        rows.append(row)
    return '\n'.join(rows)

def render_services_html(services):
    """Renders HTML rows for the Windows Services Manager."""
    if not services:
        return '<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 18px;">No service watchdog telemetry available</td></tr>'
    rows = []
    for s in services:
        name = html.escape(str(s.get('name', '')))
        display = html.escape(str(s.get('display', name)))
        desc = html.escape(str(s.get('desc', '')))
        status = str(s.get('status', 'STOPPED')).upper()
        
        is_running = (status == 'RUNNING')
        dot_color = '#10b981' if is_running else '#64748b'
        badge_class = 'tag-svc-running' if is_running else 'tag-svc-stopped'
        
        btn_action = f'''
        <button type="button" class="btn-svc-action btn-svc-restart" onclick="controlService('{name}', 'restart')" title="Restart {display}">Restart</button>
        '''
        if is_running:
            btn_action += f'''<button type="button" class="btn-svc-action btn-svc-stop" onclick="controlService('{name}', 'stop')" title="Stop {display}">Stop</button>'''
        else:
            btn_action += f'''<button type="button" class="btn-svc-action btn-svc-start" onclick="controlService('{name}', 'start')" title="Start {display}">Start</button>'''
            
        row = f'''<tr id="svc-row-{name}">
            <td>
                <div class="proc-name-cell">
                    <span class="proc-dot" style="background: {dot_color};"></span>
                    <div>
                        <div style="font-weight: 600; color: var(--text-navy); font-size: 13px;">{display}</div>
                        <div style="font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">{name} · {desc}</div>
                    </div>
                </div>
            </td>
            <td><span class="{badge_class}">{status}</span></td>
            <td style="text-align: right; white-space: nowrap;">
                {btn_action}
            </td>
        </tr>'''
        rows.append(row)
    return '\n'.join(rows)

def render_processes_html(processes):
    if not processes:
        return '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 18px;">No active process telemetry available</td></tr>'
    rows = []
    for p in processes:
        name = html.escape(str(p.get('name', '')))
        pid = html.escape(str(p.get('pid', '')))
        memory = html.escape(str(p.get('memory', '')))
        color = html.escape(str(p.get('color', '#3b82f6')))
        row = f'''<tr id="proc-row-{pid}">
            <td>
                <div class="proc-name-cell">
                    <span class="proc-dot" style="background: {color};"></span>
                    <span style="font-weight: 600;">{name}</span>
                </div>
            </td>
            <td><span style="font-family: \'JetBrains Mono\', monospace; font-size: 12px; color: var(--text-muted);">{pid}</span></td>
            <td class="proc-mem-cell">{memory}</td>
            <td><span class="tag-active">Active</span></td>
            <td style="text-align: right;">
                <button type="button" class="btn-kill-proc" onclick="confirmKillProcess(\'{pid}\', \'{name}\')" title="Terminate process {name}">End Task</button>
            </td>
        </tr>'''
        rows.append(row)
    return '\n'.join(rows)

def get_template_replacements(tailscale_ip=None, port=6969, access_mode="lan"):
    t = get_system_telemetry(tailscale_ip, port, access_mode)
    hostname = html.escape(t.get('hostname', 'Host'))
    interfaces = t.get('interfaces', [])
    disks = t.get('disks', [])
    top_proc = t.get('top_processes', [])
    gpu = t.get('gpu', {})

    lan_ip = t.get('lan_ip', '127.0.0.1')
    ts_ip = t.get('tailscale_ip', '')
    ts_display = ts_ip if ts_ip else "Not Connected"
    ts_desc = f"Encrypted WireGuard peer-to-peer connection via Tailscale IP ({ts_ip})" if ts_ip else "Tailscale was not detected on this machine. You can connect Tailscale or enter IP manually."
    
    cpu_pct = t.get('cpu_percent', 0)
    cpu_cores = t.get('cpu_cores', 1)
    ram_used = t.get('ram_used_gb', '0')
    ram_total = t.get('ram_total_gb', '0')
    ram_avail = t.get('ram_avail_gb', '0')
    ram_pct = t.get('ram_percent', 0)
    
    gpu_name = html.escape(gpu.get('name', 'Integrated Graphics'))
    gpu_pct = gpu.get('percent', 100) or 100
    gpu_sub = f"{html.escape(gpu.get('status', 'Active'))} · {html.escape(gpu.get('load', 'Active'))}"
    
    rx_speed = html.escape(t.get('net_rx_speed', '0 B/s'))
    tx_speed = html.escape(t.get('net_tx_speed', '0 B/s'))
    net_speed_html = f'<span style="color: #10b981;">↓ {rx_speed}</span>  <span style="color: #0284c7;">↑ {tx_speed}</span>'
    net_total_sub = f"Total: {html.escape(t.get('net_total_rx', '0 MB'))} In · {html.escape(t.get('net_total_tx', '0 MB'))} Out"
    
    disk_free = html.escape(t.get('primary_disk_free', '0 GB'))
    disk_total = html.escape(t.get('primary_disk_total', '0 GB'))
    disk_pct = t.get('primary_disk_percent', 0)

    bat = t.get('battery', {})
    power_val = html.escape(str(bat.get('val', 'Mains Power')))
    power_sub = html.escape(str(bat.get('sub', 'AC Line Active')))
    power_pct = bat.get('percent', 100)
    power_color = bat.get('color', '#10b981')
    power_spec = f"{power_val} · {html.escape(str(bat.get('status', 'Connected')))}"
    
    services = t.get('services', [])
    running_svcs = sum(1 for s in services if s.get('status') == 'RUNNING')
    hw = t.get('hardware', {})
    uptime_val = html.escape(str(t.get('uptime', 'Online')))
    boot_str = html.escape(str(t.get('boot_time', 'System Boot Active')))
    
    return {
        '{{HOSTNAME}}': hostname,
        '{{IFACE_COUNT}}': str(len(interfaces)),
        '{{CPU_VAL}}': f"{cpu_pct}% Load",
        '{{CPU_PERCENT}}': str(cpu_pct),
        '{{CPU_SUB}}': f"{cpu_cores} Cores Active · Kernel Low-Latency",
        '{{RAM_VAL}}': f"{ram_used} / {ram_total} GB",
        '{{RAM_PERCENT}}': str(ram_pct),
        '{{RAM_SUB}}': f"{ram_pct}% load · {ram_avail} GB available",
        '{{GPU_NAME}}': gpu_name,
        '{{GPU_PERCENT}}': str(gpu_pct),
        '{{GPU_SUB}}': gpu_sub,
        '{{NET_SPEED_VAL}}': net_speed_html,
        '{{NET_TOTAL_SUB}}': net_total_sub,
        '{{PRIMARY_DISK_VAL}}': f"{disk_free} Free",
        '{{PRIMARY_DISK_PERCENT}}': str(disk_pct),
        '{{PRIMARY_DISK_SUB}}': f"{disk_pct}% used of {disk_total} total",
        '{{POWER_VAL}}': power_val,
        '{{POWER_SUB}}': power_sub,
        '{{POWER_PERCENT}}': str(power_pct),
        '{{POWER_COLOR}}': power_color,
        '{{POWER_SPEC}}': power_spec,
        '{{PROC_COUNT}}': str(t.get('process_count', len(top_proc))),
        '{{PROC_ROWS}}': render_processes_html(top_proc),
        '{{DISK_COUNT}}': str(len(disks)),
        '{{DISKS_HTML}}': render_disks_html(disks),
        '{{IFACES_ROWS}}': render_interfaces_html(interfaces),
        '{{PRIMARY_IP}}': html.escape(str(t.get('primary_ip', lan_ip))),
        '{{DETECTED_LAN_IP}}': html.escape(lan_ip),
        '{{DETECTED_TAILSCALE_IP}}': html.escape(ts_display),
        '{{TAILSCALE_DESC}}': html.escape(ts_desc),
        '{{PORT}}': str(port),
        '{{CPU_CORES}}': str(cpu_cores),
        '{{CPU_ARCH}}': html.escape(platform.machine() or 'x86_64'),
        '{{OS_NAME}}': html.escape(t.get('os', 'Windows')),
        '{{MESH_STATUS}}': html.escape(str(t.get('mesh_status', 'Local Network Direct'))),
        '{{UPTIME_VAL}}': uptime_val,
        '{{BOOT_TIMESTAMP}}': boot_str,
        '{{CPU_MODEL}}': html.escape(str(hw.get('model', 'Multi-Core Processor'))),
        '{{CPU_MHZ}}': html.escape(str(hw.get('mhz', ''))),
        '{{SERVICES_COUNT}}': str(len(services)),
        '{{SERVICES_RUNNING_COUNT}}': str(running_svcs),
        '{{SERVICES_ROWS}}': render_services_html(services)
    }
