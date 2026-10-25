#!/usr/bin/env python3
"""
TheDoom Gateway — Minimalist Remote Telemetry & Control Server
Develop by Yourhacker with ❤️

Features:
- Native Windows Account Authentication via Win32 LogonUserW (Zero external dependencies)
- Automatic password updates (reflects Windows password changes live)
- Pre-login startup support (runs at boot via Task Scheduler before desktop sign-in)
- Full hardware telemetry and remote power control deck
"""

import os
import sys

# Configure UTF-8 stdout to avoid Windows charmap / cp1252 UnicodeEncodeError
class _NullWriter:
    def write(self, *a, **k): pass
    def flush(self, *a, **k): pass

if sys.stdout is None:
    sys.stdout = _NullWriter()
elif hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = _NullWriter()
elif hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import time
import json
import zlib
import hmac
import html
import secrets
import subprocess
import ctypes
import platform
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

# Import telemetry engine
try:
    import telemetry
except ImportError:
    print('[ERROR] telemetry.py is required in the same directory.')
    sys.exit(1)

# ============== CONFIGURATION & PERSISTENCE ==============

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(CONFIG_DIR, 'gateway_config.json')
if not os.path.isfile(CONFIG_FILE) and os.path.isfile(os.path.join(BASE_DIR, 'gateway_config.json')):
    CONFIG_FILE = os.path.join(BASE_DIR, 'gateway_config.json')

AUDIT_FILE = os.path.join(LOGS_DIR, 'audit_log.json')
if not os.path.isfile(AUDIT_FILE) and os.path.isfile(os.path.join(BASE_DIR, 'audit_log.json')):
    AUDIT_FILE = os.path.join(BASE_DIR, 'audit_log.json')

SESSION_LIFETIME = 8 * 60 * 60
SESSIONS = {}
MAX_AUDIT_ENTRIES = 50

def load_gateway_config():
    sys_ips = telemetry.get_system_ips()
    default_ts_ip = sys_ips.get('tailscale', '')
    default_lan_ip = sys_ips.get('lan', '127.0.0.1')

    cfg = {
        'access_mode': 'lan',  # Local Network by default on installation
        'custom_ip': default_ts_ip,
        'port': int(os.getenv('PORT', '6969')),
        'tailscale_ip': default_ts_ip,
        'lan_ip': default_lan_ip
    }
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception:
            pass

    # Ensure system IP addresses are dynamically populated
    if not cfg.get('lan_ip'):
        cfg['lan_ip'] = default_lan_ip
    if not cfg.get('tailscale_ip'):
        cfg['tailscale_ip'] = default_ts_ip

    return cfg

def save_gateway_config(cfg):
    """Persists gateway network access mode and port configuration."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception as e:
        print(f"[WARN] Failed to save gateway config: {e}")
        return False

GATEWAY_CONFIG = load_gateway_config()
SYS_IPS = telemetry.get_system_ips()
TAILSCALE_IP = GATEWAY_CONFIG.get('custom_ip') or GATEWAY_CONFIG.get('tailscale_ip') or SYS_IPS.get('tailscale', '')
PORT = int(GATEWAY_CONFIG.get('port', 6969))
CURRENT_BOUND_IP = '0.0.0.0'

# ============== SECURITY AUDIT TRAIL ==============

def get_audit_log():
    if os.path.isfile(AUDIT_FILE):
        try:
            with open(AUDIT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def log_audit(event_type, action_name, user="System", ip="127.0.0.1", status="SUCCESS", details=""):
    """Records an event in the persistent audit trail."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "time_epoch": int(time.time()),
        "event_type": event_type,  # 'AUTH', 'SERVICE', 'POWER', 'PROCESS', 'CONFIG'
        "action": action_name,
        "user": user or "System",
        "ip": ip or "127.0.0.1",
        "status": status,
        "details": details
    }
    entries = get_audit_log()
    entries.insert(0, entry)
    entries = entries[:MAX_AUDIT_ENTRIES]
    try:
        with open(AUDIT_FILE, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2)
    except Exception:
        pass
    return entry

# ============== BOOT AUTO-START SERVICE MANAGER ==============

def get_startup_vbs_paths():
    paths = []
    appdata = os.environ.get('APPDATA', '')
    if appdata:
        paths.append(os.path.join(appdata, r'Microsoft\Windows\Start Menu\Programs\Startup\TheDoom_Gateway.vbs'))
    progdata = os.environ.get('PROGRAMDATA', '')
    if progdata:
        paths.append(os.path.join(progdata, r'Microsoft\Windows\Start Menu\Programs\Startup\TheDoom_Gateway.vbs'))
    return paths

def check_boot_task_status():
    """Checks whether TheDoom_Gateway is registered in Task Scheduler or Startup folder."""
    if platform.system() != 'Windows':
        return False
    # 1. Check Startup Folder shortcut
    for p in get_startup_vbs_paths():
        if os.path.isfile(p):
            return True
    # 2. Check Task Scheduler
    try:
        res = subprocess.run(
            ['schtasks.exe', '/query', '/tn', 'TheDoom_Gateway'],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        return res.returncode == 0
    except Exception:
        return False

def configure_boot_task(enable=True):
    """Enables or removes Windows auto-start at boot / sign-in."""
    if platform.system() != 'Windows':
        return False, "Startup configuration is only supported on Windows."
    
    vbs_paths = get_startup_vbs_paths()
    launcher_vbs = os.path.join(BASE_DIR, 'bin', 'start_gateway.vbs')
    if not os.path.isfile(launcher_vbs):
        launcher_vbs = os.path.join(BASE_DIR, 'start_gateway.vbs')

    if not enable:
        # Remove from Startup folder
        for p in vbs_paths:
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass
        # Remove from Task Scheduler
        try:
            subprocess.run(
                ['schtasks.exe', '/delete', '/tn', 'TheDoom_Gateway', '/f'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
        except Exception:
            pass

        return True, "Auto-start at Windows boot/sign-in removed successfully."
    else:
        # Enable: Register Task Scheduler and Windows Startup folder
        task_registered = False
        if os.path.isfile(launcher_vbs):
            tr_cmd = f'wscript.exe "{launcher_vbs}"'
        else:
            py_bin = sys.executable
            pyw_bin = os.path.join(os.path.dirname(py_bin), 'pythonw.exe')
            if os.path.isfile(pyw_bin):
                py_bin = pyw_bin
            tr_cmd = f'"{py_bin}" "{os.path.join(BASE_DIR, "thedoomcontrol.py")}"'

        # 1. Try Task Scheduler (onlogon with HIGHEST)
        try:
            res = subprocess.run(
                ['schtasks.exe', '/create', '/tn', 'TheDoom_Gateway', '/tr', tr_cmd, '/sc', 'onlogon', '/rl', 'HIGHEST', '/f'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            if res.returncode == 0:
                task_registered = True
        except Exception:
            pass

        # 2. Register in Windows Startup folder (guaranteed fallback)
        startup_ok = False
        if vbs_paths and os.path.isfile(launcher_vbs):
            try:
                target_path = vbs_paths[0]
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run "wscript.exe ""{launcher_vbs}""", 0, False\n')
                startup_ok = True
            except Exception:
                pass

        if task_registered or startup_ok:
            return True, "Auto-start registered successfully (Task Scheduler & Windows Startup)."
        else:
            return False, "Failed to register auto-start. Please run install_service.bat as Administrator."

# ============== WINDOWS SERVICE CONTROL ==============

def control_service(service_name, action):
    """Start, stop, or restart a Windows service."""
    if platform.system() != 'Windows':
        return False, "Services manager is only available on Windows."
    safe_name = "".join(c for c in service_name if c.isalnum() or c in "._-")
    if not safe_name:
        return False, "Invalid service name."
    
    try:
        if action == 'start':
            res = subprocess.run(['sc.exe', 'start', safe_name], capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if res.returncode == 0 or 'already running' in (res.stderr or res.stdout or '').lower():
                return True, f"Service '{safe_name}' started successfully."
            err = (res.stderr or res.stdout or f"Failed to start service").strip()
            return False, err
        elif action == 'stop':
            res = subprocess.run(['sc.exe', 'stop', safe_name], capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if res.returncode == 0 or 'not running' in (res.stderr or res.stdout or '').lower():
                return True, f"Service '{safe_name}' stopped successfully."
            err = (res.stderr or res.stdout or f"Failed to stop service").strip()
            return False, err
        elif action == 'restart':
            subprocess.run(['sc.exe', 'stop', safe_name], capture_output=True, timeout=6, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            time.sleep(1.5)
            res = subprocess.run(['sc.exe', 'start', safe_name], capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if res.returncode == 0 or 'already running' in (res.stderr or res.stdout or '').lower():
                return True, f"Service '{safe_name}' restarted successfully."
            err = (res.stderr or res.stdout or f"Failed to restart service").strip()
            return False, err
        return False, f"Unknown action '{action}'."
    except Exception as e:
        return False, str(e)

# ============== WINDOWS NATIVE AUTHENTICATION ==============

def get_default_username():
    """Detect current Windows username, or primary user account if running at system boot."""
    # 1. Active user environment variable
    u = os.environ.get('USERNAME', '').strip()
    if u and u.upper() not in ('SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE', ''):
        return u

    # 2. Windows registry: LastUsedUsername / DefaultUserName (works at boot before login)
    if platform.system() == 'Windows':
        try:
            import winreg
            for key_path in (
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\LogonUI"
            ):
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                        for val_name in ("LastLoggedOnUser", "LastUsedUsername", "DefaultUserName"):
                            try:
                                val, _ = winreg.QueryValueEx(k, val_name)
                                if val:
                                    if '\\' in val:
                                        val = val.split('\\', 1)[1]
                                    if val and val.upper() not in ('SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE'):
                                        return val
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

        # 3. Inspect C:\Users folders for primary interactive user
        try:
            users_dir = os.environ.get('SystemDrive', 'C:') + '\\Users'
            if os.path.isdir(users_dir):
                excluded = {'ALL USERS', 'DEFAULT', 'DEFAULT USER', 'PUBLIC', 'DESKTOP.INI'}
                candidates = [
                    d for d in os.listdir(users_dir)
                    if os.path.isdir(os.path.join(users_dir, d)) and d.upper() not in excluded
                ]
                if candidates:
                    candidates.sort(key=lambda d: os.path.getmtime(os.path.join(users_dir, d)), reverse=True)
                    return candidates[0]
        except Exception:
            pass

    return ''


def verify_windows_credentials(username, password):
    """
    Authenticate against Windows Local Security Authority (LSA) / SAM via LogonUserW.
    Live validation: instantly reflects changed Windows passwords.
    Works before login (at boot) and within active desktop sessions.
    """
    if not username:
        return False, "Windows username is required."
    if not password:
        return False, "Windows password is required."

    if platform.system() != 'Windows':
        return False, "Windows authentication is only available on Windows."

    try:
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32

        # Configure ctypes signature for pointer and 64-bit safety
        advapi32.LogonUserW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p)
        ]
        advapi32.LogonUserW.restype = ctypes.c_int

        token = ctypes.c_void_p()

        domain = None
        user = username
        if '\\' in username:
            domain, user = username.split('\\', 1)
        elif '@' in username:
            user, domain = username.split('@', 1)

        domains_to_try = [domain if domain else '.']
        # If user entered an email-style address, also try MicrosoftAccount provider
        if '@' in username and not domain:
            domains_to_try.append('MicrosoftAccount')

        # LOGON32_LOGON_NETWORK (3) -> fast, standard remote network auth
        # LOGON32_LOGON_INTERACTIVE (2) -> interactive console fallback
        for dom in domains_to_try:
            for logon_type in (3, 2):
                res = advapi32.LogonUserW(
                    user,
                    dom,
                    password,
                    logon_type,
                    0,  # LOGON32_PROVIDER_DEFAULT
                    ctypes.byref(token)
                )
                if res:
                    kernel32.CloseHandle(token)
                    return True, "Authenticated"

        err = kernel32.GetLastError()
        if err == 1326:
            return False, "Incorrect Windows username or password."
        elif err == 1327:
            return False, "Account restriction: Blank passwords cannot sign in remotely."
        elif err == 1909:
            return False, "This Windows account is locked out."
        elif err == 1331:
            return False, "This Windows account is currently disabled."
        elif err == 1330:
            return False, "The password for this Windows account has expired."
        else:
            return False, f"Windows authentication failed (Error code {err})."
    except Exception as exc:
        return False, f"Authentication error: {exc}"


# ==================== VIEW ENGINE ====================

def find_web_file(filename):
    candidates = [
        os.path.join(WEB_DIR, filename),
        os.path.join(BASE_DIR, 'web', filename),
        os.path.join(os.path.dirname(BASE_DIR), 'web', filename),
        os.path.join(BASE_DIR, filename),
        os.path.join(os.getcwd(), 'web', filename),
        os.path.join(os.getcwd(), 'core', 'web', filename),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return os.path.join(WEB_DIR, filename)

def read_view(filename):
    path = find_web_file(filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def render_login(message='', prefill_user=None):
    content = read_view('login.html')
    default_user = prefill_user if prefill_user is not None else get_default_username()
    content = content.replace('{{DEFAULT_USERNAME}}', html.escape(default_user, quote=True))

    err_html = ''
    if message:
        is_ok = 'success' in message.lower() or 'signed out' in message.lower()
        color = '#00ff66' if is_ok else '#ff6b81'
        bg = 'rgba(0, 255, 102, 0.1)' if is_ok else 'rgba(223, 27, 65, 0.12)'
        border = 'rgba(0, 255, 102, 0.35)' if is_ok else 'rgba(223, 27, 65, 0.35)'
        err_html = f'<div style="padding:10px 14px;background:{bg};border:1px solid {border};color:{color};font-size:12px;border-radius:6px;margin-bottom:16px;font-family:monospace;">{html.escape(message)}</div>'
    if '{{ERROR_HTML}}' in content:
        return content.replace('{{ERROR_HTML}}', err_html)
    return content.replace('<form method="post"', f'{err_html}\n<form method="post"') if err_html else content

def render_dashboard(csrf, user=''):
    content = read_view('dashboard.html')
    token = html.escape(csrf, quote=True)
    cfg = load_gateway_config()
    access_mode = cfg.get('access_mode', 'lan')
    
    replacements = telemetry.get_template_replacements(TAILSCALE_IP, PORT, access_mode)
    replacements['__CSRF_TOKEN__'] = token
    replacements['{{CSRF}}'] = token
    replacements['{{AUTH_USER}}'] = html.escape(user) if user else 'Administrator'
    
    is_boot_active = check_boot_task_status()
    replacements['{{ACCESS_MODE}}'] = html.escape(access_mode)
    replacements['{{ACCESS_MODE_LOCALHOST_CHECKED}}'] = 'checked' if access_mode == 'localhost' else ''
    replacements['{{ACCESS_MODE_LAN_CHECKED}}'] = 'checked' if access_mode == 'lan' else ''
    replacements['{{ACCESS_MODE_TAILSCALE_CHECKED}}'] = 'checked' if access_mode == 'tailscale' else ''
    replacements['{{CONFIG_PORT}}'] = str(cfg.get('port', PORT))
    replacements['{{BOUND_IP}}'] = html.escape(CURRENT_BOUND_IP)
    replacements['{{BOOT_STATUS_TEXT}}'] = "Active (System Boot)" if is_boot_active else "Disabled / Manual"
    replacements['{{BOOT_STATUS_BADGE}}'] = "tag-svc-running" if is_boot_active else "tag-svc-stopped"
    replacements['{{BOOT_BTN_ACTION}}'] = "remove" if is_boot_active else "enable"
    replacements['{{BOOT_BTN_TEXT}}'] = "Remove Auto-Start at Boot" if is_boot_active else "Enable Auto-Start at Boot"
    replacements['{{BOOT_BTN_CLASS}}'] = "btn-action-danger" if is_boot_active else "btn-action-primary"
    
    for k, v in replacements.items():
        content = content.replace(k, str(v))
    return content

def simple_page(title, body_text, status=200):
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{html.escape(title)} — TheDoom</title>"
        f"<style>body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f6f9fc;color:#0a2540;}}"
        f".box{{background:#fff;padding:40px;border-radius:12px;box-shadow:0 13px 27px -5px rgba(50,50,93,.1);text-align:center;max-width:440px;}}"
        f"h2{{margin-top:0;}}a{{color:#635bff;text-decoration:none;font-weight:600;}}</style></head>"
        f"<body><div class='box'><h2>{html.escape(title)}</h2><p>{html.escape(body_text)}</p>"
        f"<p style='margin-top:24px;'><a href='/'>&larr; Return to Dashboard</a></p></div></body></html>"
    )

# ==================== HTTP HANDLER ====================

class DashboardHandler(BaseHTTPRequestHandler):
    server_version = 'TheDoom/6.0-FullInfrastructure'

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except Exception as exc:
            try:
                self.send_page(simple_page('500 Server Error', str(exc)), 500)
            except Exception:
                pass

    def log_message(self, fmt, *args):
        print(f'{self.client_address[0]} - {fmt % args}')

    def send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def send_page(self, content, status=200, extra_headers=None):
        data = content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Frame-Options', 'DENY')
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def read_form(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if 0 < length <= 8192:
                raw = self.rfile.read(length).decode('utf-8', errors='replace')
                return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}
        except Exception:
            pass
        return {}

    def get_session(self):
        cookie = self.headers.get('Cookie', '')
        for item in cookie.split(';'):
            name, _, val = item.strip().partition('=')
            if name == 'doom_session' and val in SESSIONS:
                s = SESSIONS[val]
                if s['expires'] > time.time():
                    return val, s
                SESSIONS.pop(val, None)
        return None, None

    def wants_json(self):
        return 'application/json' in self.headers.get('Accept', '')

    def do_GET(self):
        # Serve obfuscated logo directly from memory buffer
        if self.path in ('/YourHacker logo.png', '/YourHacker%20logo.png', '/logo.png', '/favicon.ico'):
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(LOGO_BYTES)))
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            self.wfile.write(LOGO_BYTES)
            return

        if self.path in ('/', '/index.html'):
            _, session = self.get_session()
            self.send_page(render_dashboard(session['csrf'], session.get('user', '')) if session else render_login())
            return

        if self.path == '/api/status':
            _, session = self.get_session()
            if not session:
                self.send_json({'error': 'Unauthorized'}, 401)
                return
            cfg = load_gateway_config()
            access_mode = cfg.get('access_mode', 'lan')
            self.send_json(telemetry.get_system_telemetry(TAILSCALE_IP, PORT, access_mode))
            return

        if self.path == '/api/audit':
            _, session = self.get_session()
            if not session:
                self.send_json({'error': 'Unauthorized'}, 401)
                return
            self.send_json({'success': True, 'entries': get_audit_log()})
            return

        if self.path == '/api/gateway_status':
            _, session = self.get_session()
            if not session:
                self.send_json({'error': 'Unauthorized'}, 401)
                return
            cfg = load_gateway_config()
            self.send_json({
                'success': True,
                'access_mode': cfg.get('access_mode', 'lan'),
                'custom_ip': cfg.get('custom_ip', TAILSCALE_IP),
                'bound_ip': CURRENT_BOUND_IP,
                'port': PORT,
                'tailscale_ip': TAILSCALE_IP,
                'boot_task_active': check_boot_task_status()
            })
            return

        self.send_page(simple_page('404 Not Found', 'The requested endpoint does not exist.'), 404)

    def do_POST(self):
        form = self.read_form()

        # Sign-in via native Windows credentials
        if self.path == '/login':
            username = form.get('username', '').strip()
            password = form.get('password', '')

            if not username:
                username = get_default_username()

            success, err_msg = verify_windows_credentials(username, password)
            client_ip = self.client_address[0]
            if not success:
                log_audit('AUTH', 'Sign In Failed', username, client_ip, 'FAILED', err_msg)
                time.sleep(0.5)
                self.send_page(render_login(err_msg, username), 401)
                return

            log_audit('AUTH', 'Sign In Succeeded', username, client_ip, 'SUCCESS', 'Authenticated via Win32 LSA')
            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            SESSIONS[token] = {'csrf': csrf, 'expires': time.time() + SESSION_LIFETIME, 'user': username}

            self.send_page(
                render_dashboard(csrf, username),
                200,
                [('Set-Cookie', f'doom_session={token}; Path=/; Max-Age={SESSION_LIFETIME}; HttpOnly; SameSite=Strict')]
            )
            return

        token, session = self.get_session()
        if not session:
            msg = 'Session expired. Please sign in again.'
            if self.wants_json():
                self.send_json({'success': False, 'error': msg}, 401)
            else:
                self.send_page(render_login(msg), 401)
            return

        if not hmac.compare_digest(form.get('csrf', ''), session['csrf']):
            msg = 'Security validation failed. Reload page.'
            if self.wants_json():
                self.send_json({'success': False, 'error': msg}, 403)
            else:
                self.send_page(simple_page('403 Forbidden', msg), 403)
            return

        # Sign-out
        if self.path == '/logout':
            user = session.get('user', 'User') if session else 'User'
            log_audit('AUTH', 'Signed Out', user, self.client_address[0], 'SUCCESS')
            SESSIONS.pop(token, None)
            self.send_page(
                render_login('Signed out successfully.'),
                200,
                [('Set-Cookie', 'doom_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict')]
            )
            return

        # Windows Service Action (Start / Stop / Restart)
        if self.path == '/service_action':
            svc_name = form.get('service', '').strip()
            action = form.get('action', '').strip()
            user = session.get('user', 'User')
            client_ip = self.client_address[0]
            success, msg = control_service(svc_name, action)
            log_audit('SERVICE', f"Service {action.title()}", user, client_ip, 'SUCCESS' if success else 'FAILED', f"{svc_name}: {msg}")
            self.send_json({'success': success, 'service': svc_name, 'action': action, 'message': msg})
            return

        # Boot Auto-Start Service Configuration (Enable / Remove)
        if self.path == '/api/boot_config':
            action = form.get('action', '').strip()  # 'enable' or 'remove'
            user = session.get('user', 'User')
            client_ip = self.client_address[0]
            enable = (action == 'enable')
            success, msg = configure_boot_task(enable=enable)
            log_audit('CONFIG', 'Boot Auto-Start Configured' if enable else 'Boot Auto-Start Removed', user, client_ip, 'SUCCESS' if success else 'FAILED', msg)
            self.send_json({
                'success': success,
                'action': action,
                'message': msg,
                'boot_task_active': check_boot_task_status()
            })
            return

        # Network Access Mode Configuration (Tailscale, LAN, Localhost)
        if self.path == '/api/network_mode':
            mode = form.get('access_mode', 'lan').strip()
            custom_ip = form.get('custom_ip', '').strip()
            port_str = form.get('port', '').strip()
            user = session.get('user', 'User')
            client_ip = self.client_address[0]
            
            cfg = load_gateway_config()
            if mode in ('tailscale', 'lan', 'localhost'):
                cfg['access_mode'] = mode
            if custom_ip:
                cfg['custom_ip'] = custom_ip
            if port_str and port_str.isdigit() and 1024 <= int(port_str) <= 65535:
                cfg['port'] = int(port_str)
            save_gateway_config(cfg)
            
            log_audit('CONFIG', 'Network Access Mode Updated', user, client_ip, 'SUCCESS', f"Mode: {mode.upper()} · IP: {custom_ip or 'auto'} · Port: {cfg.get('port')}")
            self.send_json({
                'success': True,
                'message': f"Access mode updated to '{mode.upper()}'. Please restart the gateway to bind to the new interface.",
                'config': cfg
            })
            return

        # Clear Audit Log
        if self.path == '/api/audit/clear':
            user = session.get('user', 'User')
            client_ip = self.client_address[0]
            try:
                with open(AUDIT_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f)
            except Exception:
                pass
            log_audit('CONFIG', 'Audit Log Cleared', user, client_ip, 'SUCCESS', 'Log history wiped by user')
            self.send_json({'success': True, 'message': 'Audit log cleared.'})
            return

        # Remote Power Actions & Process Termination
        if self.path == '/action':
            act = form.get('action', '')
            user = session.get('user', 'User')
            client_ip = self.client_address[0]

            # Terminate running process by PID
            if act == 'kill_process':
                raw_pid = form.get('pid', '')
                pid = str(raw_pid).replace('"', '').replace("'", "").strip()
                pname = str(form.get('name', '')).strip()
                if not pid or not pid.isdigit():
                    self.send_json({'success': False, 'error': f'Invalid Process ID (PID): "{pid}"'}, 400)
                    return
                # Prevent terminating critical Windows core PIDs (0=Idle, 4=System)
                if int(pid) <= 4:
                    self.send_json({'success': False, 'error': f'Cannot terminate protected Windows System PID {pid}'}, 400)
                    return
                try:
                    cmd = ['taskkill.exe', '/PID', str(pid), '/F']
                    res = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                    )
                    if res.returncode == 0:
                        msg = f"Process {pname or pid} (PID {pid}) terminated successfully."
                        log_audit('PROCESS', 'End Task', user, client_ip, 'SUCCESS', f"Terminated {pname} (PID {pid})")
                        self.send_json({'success': True, 'action': 'kill_process', 'pid': pid, 'message': msg})
                    else:
                        err = (res.stderr or res.stdout or "Taskkill failed (Access Denied or Process already terminated).").strip()
                        log_audit('PROCESS', 'End Task Failed', user, client_ip, 'FAILED', f"PID {pid} ({pname}): {err}")
                        self.send_json({'success': False, 'error': err})
                except Exception as e:
                    self.send_json({'success': False, 'error': str(e)}, 500)
                return

            # Lock Desktop Session via native Win32 API
            if act == 'lock':
                try:
                    import ctypes
                    locked = ctypes.windll.user32.LockWorkStation()
                    if locked == 0:
                        subprocess.run(['rundll32.exe', 'user32.dll,LockWorkStation'], timeout=4, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    msg = 'Windows desktop session locked successfully.'
                    log_audit('POWER', 'Desktop Session Locked', user, client_ip, 'SUCCESS')
                    if self.wants_json():
                        self.send_json({'success': True, 'action': 'lock', 'message': msg})
                    else:
                        self.send_page(simple_page('Session Locked', msg))
                    return
                except Exception as e:
                    log_audit('POWER', 'Desktop Lock Failed', user, client_ip, 'FAILED', str(e))
                    self.send_json({'success': False, 'error': f'Failed to lock session: {e}'}, 500)
                    return

            # Remote Power Actions (shutdown, restart, hibernate, abort)
            system_root = os.environ.get('SystemRoot', r'C:\Windows')
            shutdown_bin = os.path.join(system_root, 'System32', 'shutdown.exe')
            if not os.path.isfile(shutdown_bin):
                shutdown_bin = 'shutdown.exe'

            cmds = {
                'shutdown': [shutdown_bin, '/s', '/f', '/t', '30', '/c', 'TheDoom remote shutdown'],
                'restart': [shutdown_bin, '/r', '/f', '/t', '30', '/c', 'TheDoom remote restart'],
                'hibernate': [shutdown_bin, '/h'],
                'abort': [shutdown_bin, '/a']
            }
            if act not in cmds:
                self.send_json({'success': False, 'error': f'Unknown action "{act}"'}, 400)
                return

            try:
                # If scheduling shutdown/restart, first abort any existing scheduled shutdown (avoids Windows 1190 error)
                if act in ('shutdown', 'restart'):
                    subprocess.run([shutdown_bin, '/a'], capture_output=True, timeout=3, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

                res = subprocess.run(
                    cmds[act],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )

                if res.returncode == 0:
                    msgs = {
                        'shutdown': 'Shutdown scheduled in 30 seconds. A cancellation banner is active.',
                        'restart': 'Restart scheduled in 30 seconds. System will reboot and restore services.',
                        'hibernate': 'Immediate host hibernation command dispatched.',
                        'abort': 'Pending shutdown/restart was successfully cancelled.'
                    }
                    msg = msgs.get(act, f'Action {act} dispatched successfully.')
                    log_audit('POWER', f"Power Action: {act.title()}", user, client_ip, 'SUCCESS', msg)
                    if self.wants_json():
                        self.send_json({'success': True, 'action': act, 'message': msg})
                    else:
                        self.send_page(simple_page('Command Dispatched', msg))
                else:
                    err = (res.stderr or res.stdout or f'Windows shutdown utility exited with code {res.returncode}').strip()
                    log_audit('POWER', f"Power Action Failed: {act.title()}", user, client_ip, 'FAILED', err)
                    self.send_json({'success': False, 'error': err}, 500)
            except Exception as e:
                log_audit('POWER', f"Power Error: {act.title()}", user, client_ip, 'ERROR', str(e))
                self.send_json({'success': False, 'error': str(e)}, 500)
            return

        self.send_page(simple_page('404 Not Found', 'Endpoint not found.'), 404)


def _load_asset():
    cache_path = find_web_file('.sys_cache.dat')
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                raw = f.read()
            return zlib.decompress(bytes(b ^ 0x3F for b in raw))
        except Exception:
            pass
    # Fallback 1x1 transparent PNG
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

LOGO_BYTES = _load_asset()

# ============== MAIN LAUNCHER ==============

def main():
    global CURRENT_BOUND_IP, TAILSCALE_IP, PORT, GATEWAY_CONFIG

    # Quick initialization CLI helper for installers (zero batch quoting headaches)
    if '--init-config' in sys.argv:
        cfg = load_gateway_config()
        cfg['access_mode'] = 'lan'
        save_gateway_config(cfg)
        sys_ips = telemetry.get_system_ips()
        print(sys_ips.get('lan', '127.0.0.1'))
        return

    GATEWAY_CONFIG = load_gateway_config()
    
    access_mode = GATEWAY_CONFIG.get('access_mode', 'lan')
    PORT = int(GATEWAY_CONFIG.get('port', os.getenv('PORT', '6969')))
    
    sys_ips = telemetry.get_system_ips()
    detected_lan_ip = sys_ips.get('lan', '127.0.0.1')
    detected_ts_ip = sys_ips.get('tailscale', '')
    TAILSCALE_IP = GATEWAY_CONFIG.get('custom_ip') or GATEWAY_CONFIG.get('tailscale_ip') or detected_ts_ip

    if access_mode == 'localhost':
        bind_ip = '127.0.0.1'
    elif access_mode == 'tailscale':
        bind_ip = TAILSCALE_IP if TAILSCALE_IP else '0.0.0.0'
    else:  # 'lan' (Default)
        bind_ip = '0.0.0.0'

    server = None
    try:
        server = ThreadingHTTPServer((bind_ip, PORT), DashboardHandler)
        CURRENT_BOUND_IP = bind_ip
    except OSError as exc:
        print(f'[WARN] Cannot bind to {bind_ip}:{PORT}: {exc}')
        print('[INFO] Attempting fallback binding to 0.0.0.0 (all network interfaces)...')
        try:
            server = ThreadingHTTPServer(('0.0.0.0', PORT), DashboardHandler)
            CURRENT_BOUND_IP = '0.0.0.0'
            bind_ip = '0.0.0.0'
        except OSError as exc2:
            print(f'[ERROR] Fallback binding to 0.0.0.0:{PORT} failed: {exc2}')
            sys.exit(1)

    detected_user = get_default_username()
    is_boot = check_boot_task_status()
    print('=' * 68)
    print('  TheDoom Gateway & Infrastructure Telemetry (v6.5-Enterprise)')
    print(f'  Default Mode       : LOCAL NETWORK (LAN)')
    print(f'  Active Mode        : {access_mode.upper()}')
    print(f'  Bound Address      : {bind_ip}:{PORT}')
    print(f'  LAN Access URL     : http://{detected_lan_ip}:{PORT}')
    print(f'  Localhost Access   : http://localhost:{PORT}')
    if detected_ts_ip:
        print(f'  Tailscale Mesh URL : http://{detected_ts_ip}:{PORT}')
    else:
        print('  Tailscale Status   : Not Connected / Not Installed')
    print(f'  Boot Auto-Start    : {"ACTIVE (SYSTEM Service)" if is_boot else "Disabled / Manual"}')
    print(f'  Auth Engine        : Native Windows LSA (User: {detected_user or "Dynamic"})')
    print('  Develop by Yourhacker with <3')
    print('=' * 68)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping gateway.')
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
