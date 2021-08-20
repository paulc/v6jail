
import base64,hashlib,ipaddress,re,os.path,struct,subprocess,time

from .util import Command
from .config import HostConfig,JailConfig

from .jail import Jail

class Host:

    def __init__(self,config:HostConfig,debug:bool=False):
        self.config = config
        self.debug = debug
        self.cmd = Command(self.debug)
        try:
            self.cmd('/sbin/zfs', 'list', '-Ho', 'name', f'{self.config.zvol}/{self.config.base}')
        except subprocess.CalledProcessError as e:
            raise ValueError(f'Invalid base: {self.config.base}')

    def generate_addr(self,name):
        digest = hashlib.blake2b(name.encode("utf8"),
                                      digest_size=8,
                                      salt=self.config.salt).digest()
        host_address = struct.unpack("L",digest)[0] & int(self.config.network.hostmask) 
        return self.config.network.network_address + host_address

    def generate_hash(self,name):
        return base64.b32encode(
                    hashlib.blake2b(name.encode("utf8"),
                                    digest_size=8,
                                    salt=self.config.salt).digest()
               ).lower().rstrip(b"=").decode()

    def generate_gateway(self,interface):
        if "%" in self.config.gateway:
            # Link local address
            return f"{self.config.gateway.split('%')[0]}%{interface}"
        else:
            # Assume gateway directly reachable via interface
            return self.config.gateway

    def generate_jail_config(self,name):
        digest = hashlib.blake2b(name.encode("utf8"),
                                 digest_size=8,
                                 salt=self.config.salt).digest()
        b32_digest = base64.b32encode(digest).lower().rstrip(b"=").decode()
        address = self.generate_addr(name)
        gateway = self.generate_gateway(f"{b32_digest}B")
        #if '%' in gateway:
        #    prefixlen = 128
        #else:
        #    prefixlen = self.config.network.prefixlen
        prefixlen = self.config.network.prefixlen

        return JailConfig(name = name,
                          hash = b32_digest,
                          address = address,
                          prefixlen = prefixlen,
                          jname = f"j_{b32_digest}",
                          path = f"{self.config.mountpoint}/{b32_digest}",
                          zpath = f"{self.config.zvol}/{b32_digest}",
                          base_zvol = f"{self.config.zvol}/{self.config.base}",
                          epair_host = f"{b32_digest}A",
                          epair_jail = f"{b32_digest}B",
                          gateway = gateway,
                          bridge = self.config.bridge,
                          mtu = self.config.mtu,
                          base = self.config.base,
                          proxy = self.config.proxy,
        )

    def name_from_hash(self,jail_hash):
        try:
            name = self.cmd("/sbin/zfs","list","-Ho","jail:name",f"{self.config.zvol}/{jail_hash}")
            if name == "-":
                raise ValueError(f"jail:name not found: {self.config.zvol}/{jail_hash}")
            return name
        except subprocess.CalledProcessError:
            pass
        raise ValueError(f"ZFS volume not found: {self.config.zvol}/{jail_hash}")

    def get_latest_snapshot(self):
        out = self.cmd("/sbin/zfs", "list", "-Hrt", "snap", "-d", "1", "-s", "creation", "-o", "name", 
                              f"{self.config.zvol}/{self.config.base}")
        if out:
            return out.split("\n")[-1]
        else:
            raise ValueError(f"No snapshots found: {self.config.zvol}/{self.config.base}")

    def snapshot_base(self):
        self.cmd("/sbin/zfs","snapshot",
                    f"{self.config.zvol}/{self.config.base}@{time.strftime('%s')}")

    def chroot_base(self,cmds=None,snapshot=True):
        self.cmd("/sbin/mount","-t","devfs","-o","ruleset=2","devfs",
                    f"{self.config.mountpoint}/{self.config.base}/dev")
        if cmds:
            subprocess.run(["/usr/sbin/chroot",
                            f"{self.config.mountpoint}/{self.config.base}","/bin/sh"],
                           input=b"\n".join([c.encode() for c in cmds]))
        else:
            subprocess.run(["/usr/sbin/chroot",
                            f"{self.config.mountpoint}/{self.config.base}","/bin/sh"])
        self.cmd("/sbin/umount","-f",f"{self.config.mountpoint}/{self.config.base}/dev")
        if snapshot:
            self.snapshot_base()

    def clone_base(self,name):
        source = self.get_latest_snapshot()
        dest = f"{self.config.zvol}/{name}"
        with subprocess.Popen(["/sbin/zfs","send",source],
                              stdout=subprocess.PIPE) as send:
            with subprocess.Popen(["/sbin/zfs","recv","-v",dest],
                                  stdin=send.stdout) as recv:
                if recv.wait() != 0:
                    send.kill()
                    raise ValueError("ZFS recv failed")
                else:
                    if send.wait() != 0:
                        raise ValueError("ZFS send failed")

    def list_jails(self,status=False):
        out = self.cmd("/sbin/zfs","list","-r","-H","-o","name,jail:name,jail:base,jail:ipv6",
                    "-s","jail:name", self.config.zvol)
        jails = re.findall("(.*)\t(.*)\t(.*)\t(.*)",out)
        if status:
            return [dict(name=name,
                         base=base,
                         volume=os.path.basename(vol),
                         jid=f"j_{os.path.basename(vol)}",
                         ipv6=ipv6,
                         running=self.cmd.check("jls","-Nj","j_"+os.path.basename(vol)))
                    for (vol,name,base,ipv6) in jails if base != "-"]
        else:
            return [dict(name=name,
                         base=base,
                         volume=os.path.basename(vol),
                         jid=f"j_{os.path.basename(vol)}",
                         ipv6=ipv6)
                    for (vol,name,base,ipv6) in jails if base != "-"]

    def jail(self,name,params=None,debug=None):
        if debug is None:
            debug = self.debug
        return Jail(self.generate_jail_config(name),params,debug)
        
