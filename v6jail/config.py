
import binascii,configparser,ipaddress,re,sys
from dataclasses import dataclass,field,fields,asdict
from datetime import datetime
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

class IniEncoderMixin:

    """
        Mixin for dataclass which supports automatic encoding/decoding
        to/from INI file using type hints from dataclass fields
    """

    def _encode(self,field):
        if field.type in [str,int,float,bool]:
            return str(getattr(self,field.name))
        elif field.type is bytes:
            return binascii.hexlify(getattr(self,field.name)).decode('ascii')
        elif field.type is datetime:
            return getattr(self,field.name).isoformat()
        elif issubclass(field.type,Enum):
            return getattr(self,field.name).name
        else:
            raise ValueError("Invalid field type:", field) 

    def _decode(self,field,value):
        if field.type in (str,int,float):
            return field.type(value)
        elif field.type is bool:
            return (value.lower() == 'true')
        elif field.type is bytes:
            return binascii.unhexlify(value)
        elif field.type is datetime:
            return datetime.fromisoformat(value)
        elif issubclass(field.type,Enum):
            return field.type[value]
        else:
            raise ValueError("Unsupported type:",field)

    def write_config(self,section,c=None,f=None):
        if all([c,f]) or not any([c,f]):
            raise TypeError("Must specify either c:ConfigParser or f:typing.TextIO")
        c = c or configparser.ConfigParser(interpolation=None)
        c[section] = { f.name:self._encode(f) for f in fields(self) }
        if f:
            c.write(f)
        return c

    @classmethod
    def read_config(cls,section,c=None,f=None):
        if all([c,f]) or not any([c,f]):
            raise TypeError("Must specify either c:ConfigParser or f:typing.TextIO")
        if c is None:
            c = configparser.ConfigParser(interpolation=None)
            c.read_file(f)
        params = dict(c[section])
        fieldmap = { f.name:f for f in fields(cls) }
        return cls(**{k:cls._decode(cls,fieldmap[k],v) for k,v in params.items()})

@dataclass
class HostConfig(IniEncoderMixin):

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


if __name__ == '__main__':

    c = HostConfig()
    c.write_config()
