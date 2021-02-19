
import ipaddress,re,sys
from dataclasses import dataclass,field
from enum import Enum

from .util import Command
from .ini_encoder import IniEncoderMixin

cmd = Command()

def host_default_if():
    (default_if,) = re.search('interface: (.*)',
                              cmd('/sbin/route','-6','get','default')).groups()
    return default_if

def host_ipv6(default_if):
    (ipv6,) = re.search('inet6 (?!fe80::)(\S*)',
                        cmd('/sbin/ifconfig',default_if,'inet6')).groups()
    return ipv6

def host_gateway():
    (gateway,) = re.search('gateway: (.*)',
                           cmd('/sbin/route','-6','get','default')).groups()
    return gateway

Mode = Enum('Mode','BRIDGED ROUTED')

@dataclass
class HostConfig(IniEncoderMixin):

    zvol:           str = 'zroot/jail'
    mode:           Mode = Mode.BRIDGED
    bridge:         str = 'bridge0'
    hostif:         str = field(default_factory=host_default_if)
    gateway:        str = field(default_factory=host_gateway)
    hostipv6:       str = None
    prefix:         str = None
    vnet:           bool = True

    base:           str = 'base'
    mountpoint:     str = None

    salt:           bytes = b''

    def __post_init__(self):
        self.hostipv6 = self.hostipv6 or host_ipv6(self.hostif)
        self.prefix = self.prefix or ipaddress.IPv6Address(self.hostipv6).exploded[:19]
        self.mountpoint = cmd("/sbin/zfs","list","-H","-o","mountpoint",self.zvol)

        if not cmd.check("/sbin/zfs","list",f"{self.zvol}/{self.base}"):
            raise ValueError(f"base not found: {self.zvol}/{self.base}")

        if not cmd.check("/sbin/ifconfig",self.bridge):
            raise ValueError(f"bridge not found: {self.bridge}")

@dataclass
class JailConfig(IniEncoderMixin):

    name:           str
    hash:           str
    ipv6:           str
    jname:          str
    path:           str
    zpath:          str
    epair_host:     str
    epair_jail:     str
    gateway:        str
    bridge:         str
    hostipv6:       str
    base:           str

