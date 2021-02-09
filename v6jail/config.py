
import binascii,configparser,ipaddress,re,sys
from dataclasses import dataclass,field,fields,asdict
from enum import Enum

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

Mode = Enum('Mode','BRIDGED ROUTED')

@dataclass
class HostConfig:

    zroot:          str = 'zroot/jail'
    mode:           Mode = Mode.BRIDGED
    bridge:         str = 'bridge0'
    hostif:         str = field(default_factory=host_default_if)
    gateway:        str = field(default_factory=host_gateway)
    hostipv6:       str = None
    prefix:         str = None
    vnet:           bool = True

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

    def _encode(self,field):
        if field.type in [str,int,bool]:
            return str(getattr(self,field.name))
        elif field.type is Mode:
            return getattr(self,field.name).name
        elif field.type is bytes:
            return binascii.hexlify(getattr(self,field.name)).decode('ascii')
        else:
            raise ValueError("Invalid field type:", field) 

    def write_config(self,c=None,f=sys.stdout):
        c = c or configparser.ConfigParser(interpolation=None)
        c['v6jail.host'] = { f.name:self._encode(f) for f in fields(self) }
        c.write(f)
        return c

    @classmethod
    def read_config(cls,c=None,f=None):
        if c is None:
            c = configparser.ConfigParser(interpolation=None)
            c.read_file(f)
        params = dict(c['v6jail.host'])
        field_types = { f.name:f for f in fields(cls) }
        for k,v in params.items():
            f = field_types[k]
            if f.type is str:
                pass
            elif f.type is int:
                params[k] = int(v)
            elif f.type is bytes:
                params[k] = binascii.unhexlify(v)
            elif f.type is bool:
                params[k] = (v.lower() == 'true')
            elif f.type is Mode:
                params[k] = Mode[v]
            else:
                raise ValueError("Unsupported type:",f)
        return cls(**params)

if __name__ == '__main__':

    c = HostConfig()
    c.write_config()
