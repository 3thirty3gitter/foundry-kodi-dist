import ctypes
import importlib.util
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import test_release
from modules import phone_entry_network as net

class RestrictedAndroid(unittest.TestCase):
    def fallback(self, names, length_delta=0, fail=False):
        stride=40 if struct.calcsize('P')==8 else 32
        def ioctl(fd, op, request):
            self.assertEqual(op,0x8912)
            if fail: raise PermissionError()
            capacity, pointer=struct.unpack('iP',request)
            data=b''.join(n.encode().ljust(16,b'\0')+b'\0'*(stride-16) for n in names)
            ctypes.memmove(pointer,data,min(len(data),capacity))
            return struct.pack('iP',len(data)+length_delta,pointer)
        with patch.object(net.socket,'if_nameindex',side_effect=PermissionError), patch.object(net.os,'listdir',side_effect=PermissionError):
            return net.interface_names(MagicMock(),ioctl)
    def test_restricted_discovery_finds_physical_and_tunnel(self):
        self.assertEqual(self.fallback(['wlan0','tun0','lo']),['lo','tun0','wlan0'])
        self.assertFalse(net.physical_name('tun0'))
    def test_duplicate_alias_deduplicated(self):
        self.assertEqual(self.fallback(['wlan0','wlan0']),['wlan0'])
    def test_truncation_and_invalid_length_fail_closed(self):
        self.assertEqual(self.fallback(['eth0']*128),[])
        self.assertEqual(self.fallback(['eth0'],1),[])
        self.assertEqual(self.fallback([], -1),[])
    def test_permission_failure_fails_closed(self):
        self.assertEqual(self.fallback([],fail=True),[])
    def test_successful_discovery_never_calls_fallback(self):
        fn=MagicMock()
        with patch.object(net.socket,'if_nameindex',return_value=[(1,'wlan0')]):
            self.assertEqual(net.interface_names(MagicMock(),fn),['wlan0'])
        fn.assert_not_called()
    def test_empty_primary_uses_sysfs(self):
        with patch.object(net.socket,'if_nameindex',return_value=[]),patch.object(net.os,'listdir',return_value=['eth0']):
            self.assertEqual(net.interface_names(MagicMock(),MagicMock()),['eth0'])

if __name__=='__main__': unittest.main()
