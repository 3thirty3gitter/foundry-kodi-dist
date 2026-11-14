"""Select a local Wi-Fi/Ethernet address without following a VPN route.

Never send a discovery packet, change routes, or bind all interfaces. On Linux/Android,
interface IPv4 addresses come from local kernel ioctls (also works on Android).
Kodi's address is only a tie-breaker among physical interfaces when discovery
is available. Unsupported platforms retain Kodi's single-address behavior.
"""
import array
import os
import re
import socket
import struct
import sys

from modules.phone_entry_http import is_lan

_PHYSICAL = re.compile(r'^(?:eth\d|en\d|en[opsx]|wlan\d|wlp|wlx|wifi\d)')
_VIRTUAL = re.compile(r'^(?:lo$|tun|tap|wg|tailscale|zt|docker|veth|virbr|br-|utun|ipsec|ppp|dummy)')


def physical_name(name):
    if _VIRTUAL.match(name):
        return False
    return bool(_PHYSICAL.match(name) or
                os.path.exists('/sys/class/net/{}/device'.format(name)))


def interface_names(sock, ioctl):
    """Enumerate locally even when Android blocks netlink and sysfs.

    SIOCGIFCONF supplies IPv4 interface records without remote traffic. The
    bounded buffer must not be full: truncation could hide a second network.
    Addresses are still independently verified below with flags/address ioctls.
    """
    try:
        names = [name for _, name in socket.if_nameindex()]
        if names:
            return names
    except (AttributeError, OSError):
        pass
    try:
        names = os.listdir('/sys/class/net')
        if names:
            return names
    except OSError:
        pass
    stride = 40 if struct.calcsize('P') == 8 else 32
    capacity = stride * 128
    buffer = array.array('B', b'\0' * capacity)
    try:
        request = struct.pack('iP', capacity, buffer.buffer_info()[0])
        response = ioctl(sock.fileno(), 0x8912, request)  # SIOCGIFCONF
        length = struct.unpack_from('i', response)[0]
        if length < 0 or length > capacity - stride or length % stride:
            return []
        data = buffer.tobytes()
        return sorted({data[i:i + 16].split(b'\0', 1)[0].decode('ascii')
                       for i in range(0, length, stride)
                       if data[i:i + 16].split(b'\0', 1)[0]})
    except (OSError, ValueError, UnicodeError, struct.error):
        return []


def interface_addresses():
    """Return physical (name, IPv4) pairs, or None on unsupported platforms.

    Empty means discovery worked but no active physical RFC1918 interface was
    found. Do not fall back to a tunnel just because it has a private address.
    """
    if not (sys.platform.startswith('linux') or sys.platform == 'android'):
        return None
    try:
        import fcntl
    except ImportError:
        return []  # A restricted Linux/Android runtime must not select a tunnel.
    result = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        names = interface_names(sock, fcntl.ioctl)
        for name in sorted(names):
            if not physical_name(name):
                continue
            request = struct.pack('256s', name.encode('utf-8')[:15])
            try:
                flags = struct.unpack_from('H', fcntl.ioctl(sock.fileno(), 0x8913, request), 16)[0]
                # UP and RUNNING; not LOOPBACK or POINTOPOINT (including VPNs).
                if flags & 0x41 != 0x41 or flags & 0x18:
                    continue
                data = fcntl.ioctl(sock.fileno(), 0x8915, request)
                address = socket.inet_ntoa(data[20:24])
                if is_lan(address):
                    result.append((name, address))
            except OSError:
                continue
    return result


def physical_default_routes():
    """Read metrics for physical IPv4 default routes; Android may deny this."""
    result = {}
    try:
        with open('/proc/net/route', encoding='ascii') as source:
            for line in source:
                fields = line.split()
                if len(fields) < 8 or fields[1] != '00000000' or fields[7] != '00000000':
                    continue
                try:
                    if int(fields[3], 16) & 1 and physical_name(fields[0]):
                        metric = int(fields[6])
                        result[fields[0]] = min(result.get(fields[0], metric), metric)
                except ValueError:
                    continue
    except OSError:
        pass
    return result


def select_address(kodi_address, interfaces, routes):
    """Fail closed on ambiguous physical networks instead of guessing a subnet."""
    if interfaces is None:
        return kodi_address if is_lan(kodi_address) else ''
    candidates = [(name, address) for name, address in interfaces if is_lan(address)]
    if kodi_address in {address for _, address in candidates}:
        return kodi_address
    addresses = {address for _, address in candidates}
    if len(addresses) == 1:
        return next(iter(addresses))
    ranked = [(routes[name], address) for name, address in candidates if name in routes]
    if ranked:
        best = min(metric for metric, _ in ranked)
        winners = {address for metric, address in ranked if metric == best}
        if len(winners) == 1:
            return next(iter(winners))
    return ''


def lan_address(kodi_address):
    return select_address(kodi_address, interface_addresses(), physical_default_routes())
