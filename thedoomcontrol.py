#!/usr/bin/env python3
"""
TheDoom Gateway — Minimalist Remote Telemetry & Control Server
Develop by Yourhacker with ❤️
"""

import os
import sys
import time
import json
import zlib
import hashlib
import hmac
import html
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

# Import telemetry engine
try:
    import telemetry
except ImportError:
    print('[ERROR] telemetry.py is required in the same directory.')
    sys.exit(1)

# ============== CONFIGURATION ==============

TAILSCALE_IP = os.getenv('TAILSCALE_IP', '100.64.0.2')
PORT = int(os.getenv('PORT', '6969'))
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', '20111')
SESSION_LIFETIME = 8 * 60 * 60

PASSWORD_HASH = hashlib.sha256(DASHBOARD_PASSWORD.encode('utf-8')).digest()
SESSIONS = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')

# ==================== VIEW ENGINE ====================

def read_view(filename):
    path = os.path.join(WEB_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def render_login(message=''):
    content = read_view('login.html')
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

def render_dashboard(csrf):
    content = read_view('dashboard.html')
    token = html.escape(csrf, quote=True)
    replacements = telemetry.get_template_replacements(TAILSCALE_IP, PORT)
    replacements['__CSRF_TOKEN__'] = token
    replacements['{{CSRF}}'] = token
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
            self.send_page(render_dashboard(session['csrf']) if session else render_login())
            return

        if self.path == '/api/status':
            _, session = self.get_session()
            if not session:
                self.send_json({'error': 'Unauthorized'}, 401)
                return
            self.send_json(telemetry.get_system_telemetry(TAILSCALE_IP, PORT))
            return

        self.send_page(simple_page('404 Not Found', 'The requested endpoint does not exist.'), 404)

    def do_POST(self):
        form = self.read_form()

        # Sign-in
        if self.path == '/login':
            password = form.get('password', '')
            h = hashlib.sha256(password.encode('utf-8')).digest()
            if len(password) > 256 or not hmac.compare_digest(h, PASSWORD_HASH):
                time.sleep(0.5)
                self.send_page(render_login('Incorrect passkey. Please try again.'), 401)
                return

            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            SESSIONS[token] = {'csrf': csrf, 'expires': time.time() + SESSION_LIFETIME}

            self.send_page(
                render_dashboard(csrf),
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
            SESSIONS.pop(token, None)
            self.send_page(
                render_login('Signed out successfully.'),
                200,
                [('Set-Cookie', 'doom_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict')]
            )
            return


        # Remote Power Actions
        if self.path == '/action':
            act = form.get('action', '')
            cmds = {
                'shutdown': ['shutdown.exe', '/s', '/t', '30', '/c', 'TheDoom remote shutdown'],
                'restart': ['shutdown.exe', '/r', '/t', '30', '/c', 'TheDoom remote restart'],
                'hibernate': ['shutdown.exe', '/h'],
                'abort': ['shutdown.exe', '/a'],
                'lock': ['rundll32.exe', 'user32.dll,LockWorkStation']
            }
            if act not in cmds:
                self.send_json({'success': False, 'error': 'Invalid action'}, 400)
                return

            try:
                subprocess.Popen(cmds[act], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                msgs = {
                    'shutdown': 'Shutdown scheduled in 30 seconds.',
                    'restart': 'Restart scheduled in 30 seconds.',
                    'hibernate': 'Immediate hibernate command sent.',
                    'abort': 'Shutdown cancelled successfully.',
                    'lock': 'Windows desktop locked successfully.'
                }
                if self.wants_json():
                    self.send_json({'success': True, 'action': act, 'message': msgs[act]})
                else:
                    self.send_page(simple_page('Command Dispatched', msgs[act]))
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)}, 500)
            return

        self.send_page(simple_page('404 Not Found', 'Endpoint not found.'), 404)


def _load_asset():
    cache_path = os.path.join(WEB_DIR, '.sys_cache.dat')
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
    bind_ip = TAILSCALE_IP
    server = None
    try:
        server = ThreadingHTTPServer((bind_ip, PORT), DashboardHandler)
    except OSError as exc:
        print(f'[WARN] Cannot bind to {bind_ip}:{PORT}: {exc}')
        print('[INFO] Attempting fallback binding to 0.0.0.0 (all network interfaces)...')
        try:
            server = ThreadingHTTPServer(('0.0.0.0', PORT), DashboardHandler)
            bind_ip = '0.0.0.0'
        except OSError as exc2:
            print(f'[ERROR] Fallback binding to 0.0.0.0:{PORT} failed: {exc2}')
            sys.exit(1)

    print('=' * 65)
    print('  TheDoom Gateway & Infrastructure Telemetry')
    print(f'  Bound Address: {bind_ip}:{PORT}')
    print(f'  Tailscale Overlay Access: http://{TAILSCALE_IP}:{PORT}')
    print(f'  Localhost Access: http://localhost:{PORT}')
    print('  Develop by Yourhacker with ❤️')
    print('=' * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping gateway.')
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
