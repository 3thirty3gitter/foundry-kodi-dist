"""Phone entry security/HTTP/Kodi tests; HTTP fixture binds loopback only."""
import http.client
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
import test_release as kodi
from modules import phone_entry as entry, phone_entry_http as web


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.now = 10
        self.visible = True
        self.received = []
        self.session = web.EntrySession(lambda text: self.received.append(text) or True,
                                        lambda: self.visible, lambda: self.now)
        self.token = self.session.token

    def test_success_unicode_empty_and_one_use(self):
        text = 'caf\u00e9 \u6620\u753b'
        self.assertEqual(self.session.submit(self.token, text), 200)
        self.assertEqual(self.received, [text])
        self.assertEqual(self.session.submit(self.token, 'again'), 410)
        self.assertEqual(self.session.token, '')
        other = web.EntrySession(lambda text: text == '', lambda: True)
        self.assertEqual(other.submit(other.token, ''), 200)

    def test_invalid_token_does_not_consume_session(self):
        for token in ('', 'wrong', '\u00e9'):
            self.assertEqual(self.session.submit(token, 'text'), 403)
        self.assertTrue(self.session.active())
        self.assertFalse(self.received)

    def test_expiry_at_boundary(self):
        self.now += web.LIFETIME
        self.assertEqual(self.session.submit(self.token, 'text'), 410)
        self.assertFalse(self.received)

    def test_dialog_closed_or_replaced(self):
        self.visible = False
        self.assertEqual(self.session.submit(self.token, 'text'), 410)
        self.assertFalse(self.received)

    def test_validation_does_not_execute_commands(self):
        for value in (None, 1, {}, 'a' * 2049, 'line\nbreak', '\x00'):
            self.assertEqual(self.session.submit(self.token, value), 400)
        self.assertEqual(self.session.submit(self.token, 'RunScript(test), "quoted" & <html>'), 200)
        self.assertEqual(len(self.received), 1)

    def test_failed_or_uncertain_delivery_is_not_retried(self):
        for deliver in (lambda text: False, lambda text: 1 / 0):
            session = web.EntrySession(deliver, lambda: True)
            token = session.token
            self.assertEqual(session.submit(token, 'text'), 409)
            self.assertEqual(session.submit(token, 'text'), 410)

    def test_networks_are_rfc1918_only(self):
        for ip in ('192.168.1.2', '10.1.2.3', '172.16.1.2', '172.31.255.254'):
            self.assertTrue(web.is_lan(ip))
        for ip in ('127.0.0.1', '0.0.0.0', '8.8.8.8', '169.254.1.2', '172.32.0.1', '::1', '100.64.1.1', 'not-ip'):
            self.assertFalse(web.is_lan(ip))
            with self.assertRaises(ValueError): web.EntryServer(ip, self.session)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.received = []
        self.session = web.EntrySession(lambda text: self.received.append(text) or True, lambda: True)
        self.token = self.session.token
        self.allowed = patch.object(web, 'is_lan', return_value=True)
        self.allowed.start(); self.addCleanup(self.allowed.stop)
        self.server = web.EntryServer('127.0.0.1', self.session)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.addCleanup(self.stop)

    def stop(self):
        self.session.close()
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)

    def request(self, method='POST', path='/text', headers=None, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        base = {'Origin': self.server.origin, 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.token}
        base.update(headers or {})
        connection.request(method, path, body if body is not None else json.dumps({'text':'hello'}), base)
        result = connection.getresponse()
        response = result.status, dict(result.getheaders()), result.read()
        connection.close()
        return response

    def test_page_private_headers_no_embedded_token(self):
        status, headers, data = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertNotIn(self.token.encode(), data)
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        self.assertIn(b'not encrypted', data)

    def test_same_origin_success_and_duplicate(self):
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.received, ['hello'])
        self.assertEqual(self.request()[0], 410)

    def test_host_rebinding_and_cross_origin_rejected(self):
        for headers in ({'Host':'evil.test'}, {'Origin':'http://evil.test'}, {'Origin':'null'}, {'Sec-Fetch-Site':'cross-site'}):
            self.assertEqual(self.request(headers=headers)[0], 403)
        self.assertFalse(self.received)

    def test_token_and_path_rejected(self):
        self.assertEqual(self.request(headers={'Authorization':'Bearer bad'})[0], 403)
        self.assertEqual(self.request(path='/text?token='+self.token)[0], 404)
        self.assertEqual(self.request('GET', '/text')[0], 404)
        self.assertFalse(self.received)

    def test_content_type_size_and_payload_rejected(self):
        for headers, body in (({'Content-Type':'text/plain'}, '{}'), ({}, 'not json'), ({}, '[]'), ({}, '{"command":"exit"}'), ({}, 'x'*9000), ({'Transfer-Encoding':'chunked'}, '{}')):
            self.assertGreaterEqual(self.request(headers=headers, body=body)[0], 400)
        self.assertFalse(self.received)

    def test_truncated_body_is_not_accepted(self):
        client = socket.create_connection(self.server.server_address, timeout=3)
        body = b'{"text":"hello"}'
        headers = ('POST /text HTTP/1.1\r\nHost: ' + self.server.authority +
                   '\r\nOrigin: ' + self.server.origin + '\r\nAuthorization: Bearer ' + self.token +
                   '\r\nContent-Type: application/json\r\nContent-Length: 99\r\n\r\n')
        client.sendall(headers.encode() + body)
        client.shutdown(socket.SHUT_WR)
        try:
            response = http.client.HTTPResponse(client)
            response.begin()
            self.assertEqual(response.status, 400)
        finally:
            client.close()
        self.assertFalse(self.received)

    def test_trickled_headers_have_absolute_deadline(self):
        client = socket.create_connection(self.server.server_address, timeout=3)
        started = time.monotonic()
        client.sendall(b'GET / HTTP/1.1\r\nHost: ')
        try:
            for _ in range(7):
                time.sleep(.35)
                try: client.sendall(b'x')
                except OSError: break
            self.assertLess(time.monotonic() - started, 2.8)
            try:
                self.assertEqual(client.recv(1), b'')
            except (ConnectionAbortedError, ConnectionResetError):
                pass  # Windows reports closed sockets as reset rather than EOF.
        finally: client.close()
        self.assertFalse(self.received)


class KodiIntegration(unittest.TestCase):
    def setUp(self):
        self.home = kodi.Window(10000)
        self.home.setProperty(entry.ACTIVE, 'owner')
        self.addCleanup(self.home.clearProperty, entry.ACTIVE)

    def test_hidden_numeric_inactive_wrong_skin_or_owner_rejected(self):
        for keyboard, hidden, numeric, skin, owner in ((False,False,False,'skin.foundry','owner'), (True,True,False,'skin.foundry','owner'), (True,False,True,'skin.foundry','owner'), (True,False,False,'other','owner'), (True,False,False,'skin.foundry','old')):
            values = {'Window.IsActive(virtualkeyboard)':keyboard, 'System.HasHiddenInput':hidden, 'Window.IsVisible(numericinput)':numeric}
            with patch.object(kodi.xbmc, 'getCondVisibility', side_effect=lambda q: values.get(q,False)), patch.object(kodi.xbmc, 'getSkinDir', return_value=skin), patch.object(kodi.xbmc, 'executeJSONRPC') as rpc:
                self.assertFalse(entry.deliver(self.home, owner, 'text'))
                rpc.assert_not_called()

    def test_text_is_json_data_and_never_auto_confirmed(self):
        with patch.object(kodi.xbmc, 'getCondVisibility', side_effect=lambda q: q == 'Window.IsActive(virtualkeyboard)'), patch.object(kodi.xbmc, 'executeJSONRPC', return_value='{"result":"OK"}') as rpc:
            self.assertTrue(entry.deliver(self.home, 'owner', 'a "quoted" caf\u00e9'))
            request = json.loads(rpc.call_args.args[0])
            self.assertEqual(request['method'], 'Input.SendText')
            self.assertEqual(request['params'], {'text':'a "quoted" caf\u00e9','done':False})

    def test_second_click_revokes_without_starting_server(self):
        with patch.object(entry, 'EntryServer') as server:
            entry.run(); server.assert_not_called()
        self.assertEqual(self.home.getProperty(entry.ACTIVE), '')

    def test_keyboard_xml_clears_session_and_keeps_native_defaults(self):
        root = ET.parse(kodi.SKIN / 'xml/DialogKeyboard.xml').getroot()
        self.assertEqual(root.findtext('defaultcontrol'), '300')
        for event in ('onload','onunload'):
            self.assertIn('ClearProperty(foundry.phone_entry.active,home)', [n.text for n in root.findall(event)])
        button = next(n for n in root.iter('include') if n.find("param[@name='id'][@value='95301']") is not None)
        self.assertIn('!System.HasHiddenInput', button.find("param[@name='visible']").get('value'))

    def test_qr_local_png_has_quiet_zone(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'qr.png'
            entry.render_qr('http://192.168.1.2:12345/#'+'x'*43, str(path))
            with Image.open(path) as image:
                self.assertEqual(image.format, 'PNG')
                self.assertEqual(image.getpixel((0,0)), (255,255,255))
                self.assertEqual(image.getpixel((24,24)), (0,0,0))
