"""Opt-in phone entry for the current non-hidden native Kodi keyboard only."""
import json
import os
import secrets
import tempfile

import xbmc
import xbmcgui
import xbmcvfs

from modules.phone_entry_http import EntryServer, EntrySession, is_lan
from modules.phone_entry_network import lan_address

ACTIVE = 'foundry.slate.phone_entry.active'
IMAGE = 'foundry.slate.phone_entry.image'
STATUS = 'foundry.slate.phone_entry.status'
KEYBOARD = 10103


def eligible(home, owner):
    return (home.getProperty(ACTIVE) == owner and xbmc.getSkinDir() == 'skin.foundry.slate'
            and xbmc.getCondVisibility('Window.IsActive(virtualkeyboard)')
            and not xbmc.getCondVisibility('System.HasHiddenInput')
            and not xbmc.getCondVisibility('Window.IsVisible(numericinput)'))


def deliver(home, owner, text):
    if not eligible(home, owner):
        return False
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': 'Input.SendText',
        'params': {'text': text, 'done': False}})))
    return response.get('result') == 'OK' and 'error' not in response


def render_qr(url, path):
    from modules.vendor.qrcodegen import QrCode
    from PIL import Image
    qr = QrCode.encode_text(url, QrCode.Ecc.MEDIUM)
    side = qr.get_size() + 8  # mandatory quiet zone on every side
    image = Image.new('RGB', (side, side), 'white')
    pixels = image.load()
    for y in range(qr.get_size()):
        for x in range(qr.get_size()):
            if qr.get_module(x, y):
                pixels[x + 4, y + 4] = (0, 0, 0)
    image.resize((side * 6, side * 6), Image.NEAREST).save(path, 'PNG')


def run():
    home = xbmcgui.Window(10000)
    # A second click revokes the current session rather than opening another.
    if home.getProperty(ACTIVE):
        home.clearProperty(ACTIVE)
        # The owning run revokes the listener, then retains only the invalid QR
        # briefly so the skin can finish its reverse slide.
        home.setProperty(STATUS, 'Phone session cancelled')
        return
    owner = secrets.token_hex(16)
    home.clearProperty(IMAGE)
    home.setProperty(ACTIVE, owner)
    server = session = None
    path = None
    try:
        if not eligible(home, owner):
            return
        address = lan_address(xbmc.getIPAddress())
        if not is_lan(address):
            home.setProperty(STATUS, 'No clear Wi-Fi/Ethernet address. Use the TV keyboard.')
            return
        session = EntrySession(lambda text: deliver(home, owner, text), lambda: eligible(home, owner))
        server = EntryServer(address, session)
        # No permanent service and no changes to Kodi remote-control or firewall settings.
        folder = xbmcvfs.translatePath('special://temp/')
        fd, path = tempfile.mkstemp(prefix='foundry-phone-', suffix='.png', dir=folder)
        os.close(fd)
        render_qr(server.origin + '/#' + session.token, path)
        if not eligible(home, owner):
            return
        home.setProperty(IMAGE, path)
        home.setProperty(STATUS, 'Scan to type | Trusted Wi-Fi only | 2 minutes')
        monitor = xbmc.Monitor()
        while not monitor.abortRequested() and session.active():
            server.handle_request()
        if home.getProperty(ACTIVE) == owner:
            home.setProperty(STATUS, 'Session ended. Review text on TV.')
    except Exception:
        # Exceptions could contain URLs or entered text. Do not log them.
        if home.getProperty(ACTIVE) == owner:
            home.setProperty(STATUS, 'Phone entry unavailable. Use the TV keyboard.')
    finally:
        if session:
            session.close()
        if server:
            server.server_close()
        if home.getProperty(ACTIVE) == owner:
            home.clearProperty(ACTIVE)
        # Security ends before visual dismissal. Never clear a newer session's
        # image, including when Phone is clicked again during the reverse slide.
        if path and home.getProperty(IMAGE) == path:
            xbmc.sleep(350)
            if home.getProperty(IMAGE) == path:
                home.clearProperty(IMAGE)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
