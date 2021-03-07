
import binascii,configparser
from datetime import datetime
from enum import Enum

from dataclasses import fields
from ipaddress import IPv6Network,IPv6Address

class IniEncoderMixin:

    """
        Mixin for dataclass which supports automatic encoding/decoding
        to/from INI file using type hints from dataclass fields
    """

    def _encode(self,field):
        if field.type in (str,int,float,bool):
            return str(getattr(self,field.name))
        elif field.type is bytes:
            return binascii.hexlify(getattr(self,field.name)).decode('ascii')
        elif field.type is datetime:
            return getattr(self,field.name).isoformat()
        elif field.type in (IPv6Network,IPv6Address):
            return str(getattr(self,field.name))
        elif issubclass(field.type,Enum):
            return getattr(self,field.name).name
        else:
            raise ValueError("Invalid field type:", field) 

    def write_config(self,section,c=None):
        c = c or configparser.ConfigParser(interpolation=None)
        c[section] = { f.name:self._encode(f) for f in fields(self) }
        return c

    @classmethod
    def _decode(cls,field,value):
        if field.type in (str,int,float):
            return field.type(value)
        elif field.type is bool:
            return (value.lower() == 'true')
        elif field.type is bytes:
            return binascii.unhexlify(value)
        elif field.type is datetime:
            return datetime.fromisoformat(value)
        elif field.type in (IPv6Network,IPv6Address):
            return field.type(value)
        elif issubclass(field.type,Enum):
            return field.type[value]
        else:
            raise ValueError("Unsupported type:",field)

    @classmethod
    def read_config(cls,section,c=None,f=None):
        if all([c,f]) or not any([c,f]):
            raise TypeError("Must specify either c:ConfigParser or f:typing.TextIO")
        if c is None:
            c = configparser.ConfigParser(interpolation=None)
            c.read_file(f)
        params = dict(c[section])
        fieldmap = { f.name:f for f in fields(cls) }
        return cls(**{k:cls._decode(fieldmap[k],v) for k,v in params.items()})

