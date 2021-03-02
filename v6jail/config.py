
import ipaddress,re,subprocess,sys
from dataclasses import dataclass,field
from enum import Enum

from .util import Command
from .ini_encoder import IniEncoderMixin

cmd = Command()

def host_default_if():
    (default_if,) = re.search('interface: (.*)',
                              cmd('/sbin/route','-6','get','default')).groups()
    return default_if

def bridge_ipv6(bridge_if):
    (ipv6,) = re.search('inet6 (?!fe80::)(\S*)',
                        cmd('/sbin/ifconfig',bridge_if,'inet6')).groups()
    return ipv6

def host_gateway():
    (gateway,) = re.search('gateway: (.*)',
                           cmd('/sbin/route','-6','get','default')).groups()
    return gateway

def host_domain():
    return cmd('/bin/hostname').rstrip('.') + '.'

@dataclass
class HostConfig(IniEncoderMixin):

    zvol:           str = 'zroot/jail'
    bridge:         str = 'bridge0'
    gateway:        str = field(default_factory=host_gateway)
    prefix:         str = ''
    vnet:           bool = True

    base:           str = 'base'
    mountpoint:     str = ''

    salt:           bytes = b''

    def __post_init__(self):
        if not cmd.check("/sbin/zfs","list",f"{self.zvol}/{self.base}"):
            raise ValueError(f"base not found: {self.zvol}/{self.base}")

        if not cmd.check("/sbin/ifconfig",self.bridge):
            raise ValueError(f"bridge not found: {self.bridge}")

        self.prefix = self.prefix or ipaddress.IPv6Address(bridge_ipv6(self.bridge)).exploded[:19]
        self.mountpoint = cmd("/sbin/zfs","list","-H","-o","mountpoint",self.zvol)


@dataclass
class JailConfig(IniEncoderMixin):

    name:           str
    hash:           str
    ipv6:           str
    jname:          str
    path:           str
    zpath:          str
    base_zvol:      str
    epair_host:     str
    epair_jail:     str
    gateway:        str
    bridge:         str
    base:           str

@dataclass
class DDNSConfig(IniEncoderMixin):

    server:         str = "::1"
    zone:           str = field(default_factory=host_domain)
    ttl:            int = 0
    tsig:           str = ''
    nsupdate:       str = '/usr/local/bin/knsupdate'
    debug:          bool = False

    def __post_init__(self):
        self.cmd = Command(self.debug)

    def update(self,*cmds):
        request = [ f'server {self.server}'.encode(),
                    f'zone {self.zone}'.encode(),
                    f'origin {self.zone}'.encode(),
                    f'ttl {self.ttl}'.encode(),
                  ]
        if self.tsig:
            request.append(f'key {self.tsig}'.encode())
        for c in cmds:
            request.append(c.encode())
        request.append(b'send')
        request.append(b'answer')
        return self.cmd(self.nsupdate,input=b'\n'.join(request))


