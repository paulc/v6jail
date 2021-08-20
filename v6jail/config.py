
import ipaddress,re,subprocess,sys
from dataclasses import dataclass,field
from enum import Enum
from ipaddress import IPv6Network,IPv6Address

from .util import Command
from .ini_encoder import IniEncoderMixin

cmd = Command()

def host_default_if():
    (default_if,) = re.search('interface: (.*)',
                              cmd('/sbin/route','-6','get','default')).groups()
    return default_if

def bridge_ipv6(bridge_if):
    (ipv6,prefixlen) = re.search('inet6 (?!fe80::)(\S*) prefixlen (\d+)',
                        cmd('/sbin/ifconfig',bridge_if,'inet6')).groups()
    return IPv6Network(f'{ipv6}/{prefixlen}',strict=False)

def bridge_mtu(bridge_if):
    (mtu,) = re.search('mtu (\d+)',
                        cmd('/sbin/ifconfig',bridge_if,'inet6')).groups()
    return int(mtu)

def host_gateway():
    (gateway,) = re.search('gateway: (.*)',
                           cmd('/sbin/route','-6','get','default')).groups()
    return gateway

@dataclass
class HostConfig(IniEncoderMixin):

    zvol:           str = 'zroot/jail'
    bridge:         str = 'bridge0'
    mtu:            int = 1500
    gateway:        str = field(default_factory=host_gateway)
    network:        IPv6Network = None
    proxy:          bool = False

    base:           str = 'base'
    mountpoint:     str = ''

    salt:           bytes = b''

    def __post_init__(self):
        if not cmd.check("/sbin/zfs","list",f"{self.zvol}/{self.base}"):
            raise ValueError(f"base not found: {self.zvol}/{self.base}")

        if not cmd.check("/sbin/ifconfig",self.bridge):
            raise ValueError(f"bridge not found: {self.bridge}")

        self.mtu = bridge_mtu(self.bridge)
        self.network = self.network or bridge_ipv6(self.bridge)
        self.mountpoint = self.mountpoint or cmd("/sbin/zfs","list","-H","-o","mountpoint",self.zvol)

@dataclass
class JailConfig(IniEncoderMixin):

    name:           str
    hash:           str
    address:        IPv6Address
    prefixlen:      int
    jname:          str
    path:           str
    zpath:          str
    base_zvol:      str
    epair_host:     str
    epair_jail:     str
    gateway:        str
    bridge:         str
    mtu:            int
    base:           str
    private:        bool = True
    proxy:          bool = False
    bpf_rule:       int = 10

