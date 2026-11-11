"""Keyboard layout and revocation-before-animation regression checks."""
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET
import test_release as kodi
from modules import phone_entry as entry


class KeyboardLayout(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(kodi.SKIN / 'xml/DialogKeyboard.xml').getroot()

    def test_full_size_default_and_reversible_active_transform(self):
        keyboard = self.root.find(".//control[@id='78500']")
        self.assertEqual(keyboard.findtext('centerleft'), '50%')
        animations = [a for a in keyboard.findall('animation') if 'phone_entry.active' in a.get('condition', '')]
        self.assertEqual({a.get('effect') for a in animations}, {'slide', 'zoom'})
        for animation in animations:
            self.assertEqual(animation.get('time'), '300')
            self.assertEqual(animation.get('reversible'), 'true')
            self.assertIn('!String.IsEmpty(Window(Home).Property(foundry.phone_entry.image))', animation.get('condition'))
            self.assertIn('!System.HasHiddenInput', animation.get('condition'))
            self.assertIn('!Window.IsVisible(numericinput)', animation.get('condition'))
        self.assertEqual(next(a for a in animations if a.get('effect') == 'zoom').get('start'), '100,100')

    def test_qr_slides_from_offscreen_and_keeps_remote_focus(self):
        panel = self.root.find(".//control[@id='95300']")
        animation = panel.find('animation')
        self.assertEqual(animation.get('start'), '-430,0')
        self.assertEqual(animation.get('end'), '0,0')
        self.assertEqual(animation.get('reversible'), 'true')
        self.assertEqual(self.root.findtext('defaultcontrol'), '300')
        self.assertEqual(self.root.find(".//control[@id='95200']").findtext('onleft'), '78500')


class KeyboardLifecycle(unittest.TestCase):
    def test_cancel_revokes_immediately_but_retains_invalid_image(self):
        home = kodi.Window(10000)
        home.setProperty(entry.ACTIVE, 'owner')
        home.setProperty(entry.IMAGE, 'old.png')
        try:
            with patch.object(entry, 'EntryServer') as server:
                entry.run()
                server.assert_not_called()
            self.assertEqual(home.getProperty(entry.ACTIVE), '')
            self.assertEqual(home.getProperty(entry.IMAGE), 'old.png')
        finally:
            home.clearProperty(entry.ACTIVE)
            home.clearProperty(entry.IMAGE)
            home.clearProperty(entry.STATUS)

    def _run_finished(self, replace):
        home = kodi.Window(10000)
        home.clearProperty(entry.ACTIVE)
        events = []
        server = Mock(origin='http://192.168.1.2:12345')
        server.server_close.side_effect = lambda: events.append('server_closed')
        session = Mock(token='fixture')
        session.active.return_value = False
        session.close.side_effect = lambda: events.append('token_revoked')
        def sleep(milliseconds):
            self.assertEqual(milliseconds, 350)
            self.assertEqual(events, ['token_revoked', 'server_closed'])
            self.assertEqual(home.getProperty(entry.ACTIVE), '')
            self.assertTrue(Path(home.getProperty(entry.IMAGE)).exists())
            if replace:
                home.setProperty(entry.ACTIVE, 'new-owner')
                home.setProperty(entry.IMAGE, 'new.png')
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            stack.enter_context(patch.object(entry.xbmc, 'getIPAddress', return_value='192.168.1.2', create=True))
            for target, name, kwargs in [
                (entry, 'eligible', {'return_value': True}),
                (entry, 'lan_address', {'return_value': '192.168.1.2'}),
                (entry, 'EntryServer', {'return_value': server}),
                (entry, 'EntrySession', {'return_value': session}),
                (entry, 'render_qr', {'return_value': None}),
                (entry.xbmcvfs, 'translatePath', {'return_value': folder}),
                (entry.xbmc, 'sleep', {'side_effect': sleep}),
                (entry.xbmc, 'Monitor', {'return_value': Mock(abortRequested=lambda: False)}),
            ]:
                stack.enter_context(patch.object(target, name, **kwargs))
            entry.run()
            self.assertEqual(events, ['token_revoked', 'server_closed'], home.getProperty(entry.STATUS))
            self.assertEqual(list(Path(folder).iterdir()), [])
        self.assertEqual(home.getProperty(entry.IMAGE), 'new.png' if replace else '')
        self.assertEqual(home.getProperty(entry.ACTIVE), 'new-owner' if replace else '')
        home.clearProperty(entry.ACTIVE)
        home.clearProperty(entry.IMAGE)
        home.clearProperty(entry.STATUS)

    def test_security_closed_before_visual_delay(self):
        self._run_finished(False)

    def test_old_cleanup_does_not_clear_new_session(self):
        self._run_finished(True)
