
import binascii,configparser,ipaddress,re,sys
from dataclasses import dataclass,field,asdict

from .util import Command

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

DEFAULT_PARAMS = {
        "allow.set_hostname":   False,
        "allow.raw_sockets":    True,
        "allow.socket_af":      True,
        "allow.sysvipc":        True,
        "allow.chflags":        True,
        "mount.devfs":          True,
        "devfs_ruleset":        4,
        "enforce_statfs":       2,
        "sysvmsg":              "new",
        "sysvsem":              "new",
        "sysvshm":              "new",
        "children.max":         0,
        "osrelease":            "",
        "vnet":                 "new",
        "vnet.interface":       "",
        "persist":              True,
        "exec.start":           "/bin/sh /etc/rc",
}

@dataclass
class Config:

    zroot:          str = 'zroot/jail'
    bridge:         str = 'bridge0'
    hostif:         str = field(default_factory=host_default_if)
    gateway:        str = field(default_factory=host_gateway)
    hostipv6:       str = None
    prefix:         str = None

    base:           str = 'base'
    mountpoint:     str = 'zroot/jail'

    salt:           bytes = b''

    def __post_init__(self):
        self.hostipv6 = self.hostipv6 or host_ipv6(self.hostif)
        self.prefix = self.prefix or ipaddress.IPv6Address(self.hostipv6).exploded[:19]

        if not cmd.check("/sbin/zfs","list",f"{self.zroot}/{self.base}"):
            raise ValueError(f"base not found: {self.zroot}/{self.base}")

        if not cmd.check("/sbin/ifconfig",self.bridge):
            raise ValueError(f"bridge not found: {self.bridge}")

    def write_ini(self,f=sys.stdout):
        c = configparser.ConfigParser(interpolation=None)
        c['v6jail'] = asdict(self)
        # Fix bytes value for salt
        c['v6jail']['salt'] = binascii.hexlify(self.salt).decode('ascii')
        c.write(f)

    @classmethod
    def read_ini(cls,f):
        c = configparser.ConfigParser(interpolation=None)
        c.read_file(f)
        p = dict(c['v6jail'])
        # Fix bytes value for salt
        if 'salt' in p:
            p['salt'] = binascii.unhexlify(p['salt'])
        return cls(**p)

