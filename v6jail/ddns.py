
from dataclasses import dataclass,field

from .util import Command
from .ini_encoder import IniEncoderMixin

cmd = Command()

def host_domain():
    return cmd('/bin/hostname').rstrip('.') + '.'

@dataclass
class DDNSConfig(IniEncoderMixin):

    server:         str = "::1"
    zone:           str = field(default_factory=host_domain)
    ttl:            int = 60
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

