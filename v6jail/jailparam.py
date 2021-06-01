
import configparser,shlex
from collections import UserDict

def check(k,v,t):
    if not isinstance(v,t):
        raise ValueError(f'Invalid jail param: {k}={v} (expecting {t})')
    return v

class JailParam(UserDict):

    _int_params = {
            'jid', 'securelevel', 'devfs_ruleset', 'children.max', 
            'children.cur', 'cpuset.id', 'parent', 'enforce_statfs'
    }

    _str_params = {
            'name', 'path', 'host.hostname', 'host.domainname', 
            'host.hostuuid', 'host.hostid', 'osrelease', 'osreldate', 
            'linux.osname', 'linux.osrelease', 'linux.oss_version'
    }

    # new/inherit/disable  
    _control_params = {
            'ip4', 'ip6', 'vnet', 'host', 'linux', 
            'sysvmsg', 'sysvsem', 'sysvshm'
    }

    _list_params = {
            'ip4.addr', 'ip6.addr'
    }

    _bool_params = {
            'ip4.saddrsel', 'ip6.saddrsel', 'persist',
            'dying', 'allow.set_hostname', 'allow.sysvipc',
            'allow.raw_sockets', 'allow.chflags', 'allow.mount',
            'allow.mount.devfs', 'allow.quotas', 'allow.read_msgbuf',
            'allow.socket_af', 'allow.mlock', 'allow.reserved_ports',
            'allow.mount.fdescfs', 'allow.mount.fusefs', 'allow.mount.nullfs',
            'allow.mount.procfs', 'allow.mount.linprocfs',
            'allow.mount.linsysfs', 'allow.mount.tmpfs','allow.mount.zfs',
            'allow.vmm',
            # Pseudo bool params
            'mount.devfs', 'mount.fdescfs', 'mount.procfs', 'exec.clean'
    } 

    _pseudo_params = {
            'exec.prepare', 'exec.prestart', 'exec.created', 'exec.start',
            'command', 'exec.poststart', 'exec.prestop', 'exec.stop',
            'exec.poststop', 'exec.release', 'exec.jail_user',
            'exec.system_jail_user', 'exec.system_user', 'exec.timeout',
            'exec.consolelog', 'exec.fib', 'stop.timeout', 'interface',
            'vnet.interface', 'ip_hostname', 'mount', 'mount.fstab',
            'allow.dying', 'depend'
    }

    def __init__(self,**values):
        self.data = {}
        self.update(values)

    def __setitem__(self,k,v):
        if k in self._int_params:
            self.data[k] = check(k,v,int)
        elif k in self._str_params | self._pseudo_params:
            self.data[k] = check(k,v,str)
        elif k in self._bool_params:
            self.data[k] = check(k,v,bool)
        elif k in self._control_params:
            if v in ('new','inherit','disable'):
                self.data[k] = v
            else:
                raise ValueError(f'Invalid jail param: {k}={v} (expecting new|inherit|disable)')
        elif k in self._list_params:
            for i in v:
                check(k,i,str)
            self.data[k] = v
        else:
            raise ValueError(f'Invalid jail param: {k}={v} (key not found)')

    def __getattr__(self,k):
        if k == 'data':
            return self.data
        else:
            return self[k]

    def __setattr__(self,k,v):
        if k == 'data':
            object.__setattr__(self,'data',v)
        else:
            if v is None:
                del self[k]
            else:
                self[k] = v

    def update(self,*args,**kwargs):
        for a in args:
            for k,v in a.items():
                self[k] = a[k]
        for k,v in kwargs.items():
            self[k] = v

    def defaults(self):
        return {
            'allow.set_hostname':       False,
            'mount.devfs':              True,
            'devfs_ruleset':            4,
            'enforce_statfs':           2,
            'children.max':             0,
            'persist':                  True,
            'exec.start':               '/bin/sh /etc/rc',
            'exec.clean':               True,
        }

    def linux_defaults(self):
        return {
            'devfs_ruleset':            20,
            'linux':                    'new',
            'enforce_statfs':           1,
            'allow.mount':              True,
            'allow.mount.devfs':        True,
            'allow.mount.fdescfs':      True,
            'allow.mount.linprocfs':    True,
            'allow.mount.linsysfs':     True,
            'allow.mount.tmpfs':        True,
            'allow.mount.nullfs':       True,
        }

    def set_default(self):
        self.update(self.defaults())
        return self

    def enable_linux(self):
        self.update(self.linux_defaults())
        return self

    def enable_vnet(self,interface):
        self.update({'vnet':'new','vnet.interface':interface})
        return self

    def enable_sysvipc(self,mode='new'):
        self.update({'sysvmsg':mode,'sysvsem':mode,'sysvshm':mode})
        return self

    def allow(self,param,allow=True):
        self[f'allow.{param}'] = allow
        return self

    def set(self,k,v):
        self[k] = v
        return self

    def set_kvpair(self,kv):
        k,v = kv.split('=',maxsplit=1)
        if k in self._bool_params:
            self.data[k] = v.lower == 'true'
        elif k in self._int_params:
            self.data[k] = int(v)
        elif k in self._list_params:
            self.data[k] = v.split(',')
        elif k in self._str_params|self._pseudo_params|self._control_params:
            self.data[k] = v
        else:
            raise ValueError(f"Invalid value: {k}={v}")

    def jail_params(self):
        params = []
        for k,v in self.data.items():
            if k in self._bool_params:
                params.append(f'{k}={str(v).lower()}')
            elif k in self._int_params:
                params.append(f'{k}={v}')
            elif k in self._str_params|self._pseudo_params|self._control_params:
                params.append(f'{k}={v}')
            elif k in self._list_params:
                params.append(f'{k}={",".join(v)}')
            else:
                raise ValueError(f"Invalid value: {k}={v}")
        return params

    def write_config(self,section,c=None):
        c = c or configparser.ConfigParser(interpolation=None)
        params = {}
        for k,v in self.data.items():
            if k in self._bool_params    |\
                    self._int_params     |\
                    self._str_params     |\
                    self._pseudo_params  |\
                    self._control_params:
                params[k] = str(v)
            elif k in self._list_params:
                params[k] = ','.join(v)
            else:
                raise ValueError(f"Invalid value: {k}={v}")
        c[section] = params
        return c

    @classmethod
    def default(cls):
        j = cls()
        return j.set_default()

    @classmethod
    def read_config(cls,section,c=None,f=None):
        if all([c,f]) or not any([c,f]):
            raise TypeError("Must specify either c:ConfigParser or f:typing.TextIO")
        if c is None:
            c = configparser.ConfigParser(interpolation=None)
            c.read_file(f)
        j = cls()
        params = {}
        for k,v in dict(c[section]).items():
            if k in cls._bool_params:
                j[k] = (v == 'True')
            elif k in cls._int_params:
                j[k] = int(v)
            elif k in cls._str_params|cls._pseudo_params|cls._control_params:
                j[k] = v
            elif k in cls._list_params:
                j[k] = v.split(',')
            else:
                raise ValueError(f"Invalid value: {k}={v}")
        return j

