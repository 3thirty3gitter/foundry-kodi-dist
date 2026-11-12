"""Regression coverage for VPN, LAN and ambiguous interface selection."""
import struct
import sys
import types
import unittest
from unittest.mock import patch, MagicMock, mock_open
import test_release
from modules import phone_entry_network as net
from modules import phone_entry as entry

class AddressSelection(unittest.TestCase):
    def test_selection_matrix(self):
        cases = [
            ('10.5.0.2', [('wlan0','192.168.1.40')], {}, '192.168.1.40'),
            ('10.5.0.2', [('eth0','10.5.0.2')], {}, '10.5.0.2'),
            ('192.168.2.7', [('eth0','192.168.1.5'),('wlan0','192.168.2.7')], {'eth0':1}, '192.168.2.7'),
            ('10.5.0.2', [('eth0','192.168.1.5'),('wlan0','192.168.2.7')], {'eth0':100,'wlan0':600,'tun0':1}, '192.168.1.5'),
            ('10.5.0.2', [], {}, ''),
            ('10.5.0.2', [('wlan0','8.8.8.8')], {}, ''),
            ('10.5.0.2', [('eth0','192.168.1.5'),('wlan0','192.168.2.7')], {}, ''),
            ('10.5.0.2', [('eth0','192.168.1.5'),('wlan0','192.168.2.7')], {'eth0':100,'wlan0':100}, ''),
            ('', [('eth0','192.168.1.5'),('wlan0','192.168.1.5')], {}, '192.168.1.5'),
            ('192.168.1.5', None, {}, '192.168.1.5'),
        ]
        for kodi, interfaces, routes, expected in cases:
            with self.subTest(kodi=kodi, interfaces=interfaces, routes=routes):
                self.assertEqual(net.select_address(kodi, interfaces, routes), expected)
        for value in ('127.0.0.1','0.0.0.0','8.8.8.8','169.254.1.1','::1','bad'):
            self.assertEqual(net.select_address(value, None, {}), '')

    def test_physical_and_virtual_names(self):
        with patch.object(net.os.path, 'exists', return_value=False):
            for name in ('eth0','wlan0','en0','enp3s0','wlp2s0','wifi0'):
                self.assertTrue(net.physical_name(name), name)
            for name in ('tun0','tap0','wg0','tailscale0','docker0','veth12','virbr0','lo','ppp0','br-lan','utun2'):
                self.assertFalse(net.physical_name(name), name)

    def test_physical_route_parse_ignores_tunnel_and_non_default(self):
        data = ('Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n'
                'tun0 00000000 00000000 0001 0 0 1 00000000 0 0 0\n'
                'wlan0 00000000 0101A8C0 0003 0 0 600 00000000 0 0 0\n'
                'eth0 00000000 0102A8C0 0000 0 0 100 00000000 0 0 0\n'
                'eth0 0002A8C0 00000000 0001 0 0 100 00FFFFFF 0 0 0\n')
        with patch('builtins.open', mock_open(read_data=data)):
            self.assertEqual(net.physical_default_routes(), {'wlan0':600})
        with patch('builtins.open', side_effect=PermissionError):
            self.assertEqual(net.physical_default_routes(), {})

    def test_duplicate_routes_use_lowest_metric_in_any_order(self):
        rows = ['eth0 00000000 0101A8C0 0003 0 0 10 00000000',
                'eth0 00000000 0101A8C0 0003 0 0 900 00000000',
                'wlan0 00000000 0102A8C0 0003 0 0 100 00000000']
        for ordered in (rows, list(reversed(rows))):
            with patch('builtins.open', mock_open(read_data='\n'.join(ordered))):
                self.assertEqual(net.physical_default_routes(), {'eth0':10, 'wlan0':100})

    @patch.object(net.sys, 'platform', 'linux')
    def test_ioctl_discovers_active_physical_lan_only(self):
        interfaces = [(1,'lo'),(2,'tun0'),(3,'wlan0'),(4,'eth0'),(5,'eth1'),(6,'eth2')]
        flags = {'wlan0':0x1043,'eth0':0x1,'eth1':0x51,'eth2':0x41}
        addresses = {'wlan0':'192.168.1.40','eth2':'169.254.1.1'}
        def ioctl(fd, operation, request):
            name = request.split(b'\0')[0].decode()
            result = bytearray(256)
            if operation == 0x8913: struct.pack_into('H', result, 16, flags[name])
            else: result[20:24] = net.socket.inet_aton(addresses[name])
            return bytes(result)
        fake = types.SimpleNamespace(ioctl=MagicMock(side_effect=ioctl))
        with patch.dict(sys.modules, {'fcntl':fake}), patch.object(net.socket, 'if_nameindex', return_value=interfaces), patch.object(net.socket, 'socket') as sock:
            self.assertEqual(net.interface_addresses(), [('wlan0','192.168.1.40')])
            sock.return_value.__enter__.return_value.connect.assert_not_called()
        self.assertEqual(fake.ioctl.call_count, 6)

    @patch.object(net.sys, 'platform', 'linux')
    def test_ioctl_permission_failure_fails_closed(self):
        fake = types.SimpleNamespace(ioctl=MagicMock(side_effect=PermissionError))
        with patch.dict(sys.modules, {'fcntl':fake}), patch.object(net.socket, 'if_nameindex', return_value=[(2,'wlan0')]), patch.object(net.socket, 'socket'):
            self.assertEqual(net.interface_addresses(), [])

    @patch.object(net.sys, 'platform', 'android')
    def test_android_names_fallback(self):
        fake = types.SimpleNamespace(ioctl=MagicMock(side_effect=OSError))
        with patch.dict(sys.modules, {'fcntl':fake}), patch.object(net.socket, 'if_nameindex', side_effect=OSError), patch.object(net.os, 'listdir', return_value=['wlan0']), patch.object(net.socket, 'socket'):
            self.assertEqual(net.interface_addresses(), [])
            fake.ioctl.assert_called_once()

    def test_missing_ioctl_module_fails_closed_on_android(self):
        with patch.object(net.sys, 'platform', 'android'), patch.dict(sys.modules, {'fcntl':None}):
            self.assertEqual(net.interface_addresses(), [])

    def test_other_platforms_do_not_use_linux_ioctl(self):
        for platform in ('win32', 'darwin', 'freebsd14'):
            with patch.object(net.sys, 'platform', platform), patch.object(net.socket, 'socket') as sock:
                self.assertIsNone(net.interface_addresses())
                sock.assert_not_called()

    def test_ambiguous_network_keeps_keyboard_without_listener(self):
        home = test_release.Window(10000)
        home.clearProperty(entry.ACTIVE)
        try:
            with patch.object(entry, 'eligible', return_value=True), patch.object(entry, 'lan_address', return_value=''), patch.object(entry.xbmc, 'getIPAddress', return_value='10.5.0.2', create=True), patch.object(entry, 'EntryServer') as server:
                entry.run()
                server.assert_not_called()
            self.assertEqual(home.getProperty(entry.ACTIVE), '')
            self.assertEqual(home.getProperty(entry.IMAGE), '')
            self.assertIn('Use the TV keyboard', home.getProperty(entry.STATUS))
        finally:
            home.clearProperty(entry.STATUS)

    def test_resolver_wires_discovery(self):
        with patch.object(net, 'interface_addresses', return_value=[('eth0','192.168.1.5')]), patch.object(net, 'physical_default_routes', return_value={}):
            self.assertEqual(net.lan_address('10.5.0.2'), '192.168.1.5')

if __name__ == '__main__': unittest.main()
