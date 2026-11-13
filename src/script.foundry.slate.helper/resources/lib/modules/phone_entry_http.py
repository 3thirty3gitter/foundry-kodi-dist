"""One-shot, explicit LAN text entry. No remote control, logging or persistence.

HTTP is deliberately limited to ordinary text on trusted Wi-Fi, not credentials.
The integration must reject hidden input and revalidate the same dialog at send.
"""
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time
from threading import Timer
from http.server import BaseHTTPRequestHandler, HTTPServer

LIFETIME = 120
MAX_TEXT = 2048
MAX_BODY = 8192
NETWORKS = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def is_lan(address):
    try:
        ip = ipaddress.ip_address(address)
        return any(ip in network for network in NETWORKS)
    except ValueError:
        return False


SCRIPT = """const token = location.hash.slice(1);
history.replaceState(null, '', '/');
const form = document.querySelector('form'), field = document.querySelector('textarea');
const status = document.querySelector('#status'), button = document.querySelector('button');
form.addEventListener('submit', async event => {
 event.preventDefault(); button.disabled = true;
 try {
  const response = await fetch('/text', {method:'POST', credentials:'omit', cache:'no-store',
   headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
   body:JSON.stringify({text:field.value})});
  field.value = '';
  status.textContent = response.ok ? 'Text sent. Review it and press OK on your TV.' : 'Session closed or unavailable. Start again on your TV.';
 } catch (_) { field.value = ''; status.textContent = 'Could not confirm delivery. Check your TV before trying again.'; }
});
window.addEventListener('pagehide', () => { field.value = ''; });
setTimeout(() => { field.value = ''; button.disabled = true; status.textContent = 'Session expired. Start again on your TV.'; }, 120000);
"""
PAGE = ('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Foundry phone keyboard</title><style>body{max-width:34rem;margin:3rem auto;padding:1rem;background:#15171a;color:#fff;font:18px system-ui}textarea,button{box-sizing:border-box;width:100%;padding:1rem;font:inherit}textarea{min-height:8rem}button{margin-top:1rem}p{line-height:1.5}</style>
<h1>Type on your phone</h1><p>Trusted Wi-Fi only. This local connection is not encrypted. Do not enter passwords, API keys, payment details or other private information.</p>
<form autocomplete="off"><label for="text">Text for your TV</label><textarea id="text" maxlength="2048" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"></textarea><button>Send to TV</button></form>
<p id="status" role="status">One use. Expires after two minutes. Keep the TV keyboard open.</p><script>''' + SCRIPT + '</script></html>').encode('utf-8')


class EntrySession:
    def __init__(self, deliver, eligible, clock=time.monotonic):
        self.token = secrets.token_urlsafe(32)
        self.clock = clock
        self.deadline = clock() + LIFETIME
        self.deliver = deliver
        self.eligible = eligible
        self.closed = False

    def active(self):
        return not self.closed and self.clock() < self.deadline and self.eligible()

    def submit(self, token, text):
        if not self.active():
            return 410
        if not hmac.compare_digest(token.encode('utf-8'), self.token.encode('ascii')):
            return 403
        if not isinstance(text, str) or len(text) > MAX_TEXT or any(ord(c) < 32 for c in text):
            return 400
        self.closed = True  # consume before delivery; uncertain delivery must not repeat
        self.token = ''
        try:
            return 200 if self.deliver(text) else 409
        except Exception:
            return 409  # Never log errors which might contain text.

    def close(self):
        self.closed = True
        self.token = ''


class EntryServer(HTTPServer):
    allow_reuse_address = False
    request_queue_size = 2

    def __init__(self, address, session):
        if not is_lan(address):
            raise ValueError('A private IPv4 LAN address is required')
        self.session = session
        self.request_timers = {}
        super().__init__((address, 0), EntryHandler)
        self.timeout = 0.15
        self.authority = '{}:{}'.format(*self.server_address)
        self.origin = 'http://' + self.authority

    def verify_request(self, request, client_address):
        return is_lan(client_address[0])

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(1)
        # Idle socket timeouts alone do not bound a client trickling bytes.
        remaining = max(0.01, self.session.deadline - self.session.clock())
        timer = Timer(min(2.0, remaining), self._interrupt, args=(request,))
        timer.daemon = True
        self.request_timers[request] = timer
        timer.start()
        return request, address

    @staticmethod
    def _interrupt(request):
        try:
            request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def shutdown_request(self, request):
        timer = self.request_timers.pop(request, None)
        if timer:
            timer.cancel()
        super().shutdown_request(request)

    def server_close(self):
        for request, timer in list(self.request_timers.items()):
            timer.cancel()
            self._interrupt(request)
        super().server_close()

    def handle_error(self, request, client_address):
        pass  # Never send tokens, request content or traceback to logs.


class EntryHandler(BaseHTTPRequestHandler):
    server_version = 'Foundry'
    sys_version = ''

    def log_message(self, *args):
        pass

    def respond(self, status, body=b'', html=False):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store, max-age=0')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        import base64
        digest = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'sha256-" + digest + "'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'")
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def valid_host(self):
        return self.headers.get_all('Host', []) == [self.server.authority]

    def do_GET(self):
        if not self.valid_host():
            return self.respond(403)
        if self.path != '/':
            return self.respond(404)
        if not self.server.session.active():
            return self.respond(410)
        self.respond(200, PAGE, html=True)

    def do_POST(self):
        if (not self.valid_host() or self.headers.get_all('Origin', []) != [self.server.origin]
                or self.headers.get('Sec-Fetch-Site', 'same-origin') != 'same-origin'):
            return self.respond(403)
        if self.path != '/text':
            return self.respond(404)
        if self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
            return self.respond(400)
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= MAX_BODY:
            return self.respond(413)
        auth = self.headers.get_all('Authorization', [])
        if len(auth) != 1 or not auth[0].startswith('Bearer '):
            return self.respond(403)
        try:
            raw = self.rfile.read(int(lengths[0]))
            if len(raw) != int(lengths[0]):
                return self.respond(400)
            payload = json.loads(raw.decode('utf-8'))
            if not isinstance(payload, dict) or set(payload) != {'text'}:
                return self.respond(400)
            status = self.server.session.submit(auth[0][7:], payload['text'])
        except (ValueError, UnicodeError, socket.timeout):
            status = 400
        self.respond(status)
