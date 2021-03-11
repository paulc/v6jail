
import shlex
from collections import UserDict

class JailParam(UserDict):

    def __init__(self,**values):
        self.data = self.defaults()

    def defaults(self):
        return {
            'allow.set_hostname':       False,
            'mount.devfs':              True,
            'devfs_ruleset':            4,
            'enforce_statfs':           2,
            'children.max':             0,
            'persist':                  True,
            'exec.start':               '/bin/sh /etc/rc',
        }

    def linux_defaults(self):
        return {
            'devfs_ruleset':            20,
            'linux':                    'new',
            'allow.mount.devfs':        True,
            'allow.mount.fdescfs':      True,
            'allow.mount.linprocfs':    True,
            'allow.mount.linsysfs':     True,
            'allow.mount.tmpfs':        True,
            'allow.mount.nullfs':       True,
        }

    def enable_linux(self):
        self.data.update(self.linux_defaults())

    def enable_vnet(self,interface):
        self.data.update({'vnet':'new','vnet.interface':interface})

    def enable_sysvipc(self,mode='new'):
        self.data.update({'sysvmsg':mode,'sysvsem':mode,'sysvshm':mode})

    def allow(self,param,allow=True):
        self.data[f'allow.{param}'] = allow

    def params(self):
        params = []
        for k,v in self.data.items():
            if type(v) is bool:
                params.append(f'{k}={str(v).lower()}')
            elif type(v) is int:
                params.append(f'{k}={v}')
            elif type(v) is str:
                params.append(f'{k}={shlex.quote(v)}')
            elif type(v) is list:
                params.append(f'{k}={shlex.quote(",".join(v))}')
            elif v is None:
                pass
            else:
                raise ValueError(f"Invalid value: {k}={v}")
        return params

