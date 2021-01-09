
import base64,hashlib,ipaddress,re,os.path,struct,subprocess,time

from .jail import Jail

class Host:

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

    def __init__(self,hostif=None,hostipv6=None,prefix=None,gateway=None,
                    base="base",zroot="zroot/jail",bridge="bridge0",salt=b'',debug=False):
        self.debug = debug
        self.zroot = zroot
        self.bridge = bridge
        self.base = base
        self.hostif = hostif or self.host_default_if()
        self.hostipv6 = hostipv6 or self.host_ipv6(self.hostif)
        self.gateway = gateway or self.host_gateway()
        self.prefix = prefix or ipaddress.IPv6Address(self.hostipv6).exploded[:19]
        self.salt = salt
        self.mountpoint = self.get_mountpoint(self.zroot)

        if not self.check_cmd("/sbin/zfs","list",f"{self.zroot}/{self.base}"):
            raise ValueError(f"base not found: {self.zroot}/{self.base}")

        if not self.check_cmd("/sbin/ifconfig",self.bridge):
            raise ValueError(f"bridge not found: {self.bridge}")

    def cmd(self,*args):
        try:
            result = subprocess.run(args,capture_output=True,check=True)
            out = result.stdout.strip().decode()
            if self.debug:
                print("CMD:",args)
                if out:
                    print("\n".join([f"   | {l}" for l in out.split("\n")]))
            return out
        except subprocess.CalledProcessError as e:
            if self.debug:
                err = e.stderr.strip().decode("utf8","ignore")
                print("ERR:",args)
                if err:
                    print("\n".join([f"   ! {l}" for l in err.split("\n")]))
            raise

    def check_cmd(self,*args):
        try:
            self.cmd(*args)
            return True
        except subprocess.CalledProcessError:
            return False

    def host_default_if(self):
        (default_if,) = re.search("interface: (.*)",
                                    self.cmd("/sbin/route","-6","get","default")).groups()
        return default_if

    def host_ipv6(self,default_if):
        (ipv6,) = re.search("inet6 (?!fe80::)(\S*)",
                                    self.cmd("/sbin/ifconfig",default_if,"inet6")).groups()
        return ipv6

    def host_gateway(self):
        (gateway,) = re.search("gateway: (.*)",
                                    self.cmd("/sbin/route","-6","get","default")).groups()
        return gateway

    def get_mountpoint(self,vol):
        return self.cmd("/sbin/zfs","list","-H","-o","mountpoint",vol)

    def generate_addr(self,name):
        a,b,c,d = struct.unpack("4H",
                    hashlib.blake2b(name.encode("utf8"),digest_size=8,salt=self.salt).digest()
                  )
        return "{}:{:x}:{:x}:{:x}:{:x}".format(self.prefix,a,b,c,d)

    def generate_hash(self,name):
        return base64.b32encode(
                    hashlib.blake2b(name.encode("utf8"),digest_size=8,salt=self.salt).digest()
               ).lower().rstrip(b"=").decode()

    def generate_gateway(self,interface):
        if "%" in self.gateway:
            # Link local address
            return f"{self.gateway.split('%')[0]}%{interface}"
        else:
            # Assume gateway directly reachable via interface
            return self.gateway

    def name_from_hash(self,jail_hash):
        try:
            name = self.cmd("/sbin/zfs","list","-Ho","jail:name",f"{self.zroot}/{jail_hash}")
            if name == "-":
                raise ValueError(f"jail:name not found: {self.zroot}/{jail_hash}")
            return name
        except subprocess.CalledProcessError:
            pass
        raise ValueError(f"ZFS volume not found: {self.zroot}/{jail_hash}")

    def get_latest_snapshot(self):
        out = self.cmd("/sbin/zfs", "list", "-Hrt", "snap", "-s", "creation", "-o", "name", 
                              f"{self.zroot}/{self.base}")
        if out:
            return out.split("\n")[-1]
        else:
            raise ValueError(f"No snapshots found: {self.zroot}/{self.base}")

    def snapshot_base(self):
        self.cmd("/sbin/zfs","snapshot",f"{self.zroot}/{self.base}@{time.strftime('%s')}")

    def chroot_base(self,cmds=None,snapshot=True):
        self.cmd("/sbin/mount","-t","devfs","-o","ruleset=2","devfs",
                    f"{self.mountpoint}/{self.base}/dev")
        if cmds:
            subprocess.run(["/usr/sbin/chroot",f"{self.mountpoint}/{self.base}","/bin/sh"],
                    input=b"\n".join([c.encode() for c in cmds]))
        else:
            subprocess.run(["/usr/sbin/chroot",f"{self.mountpoint}/{self.base}","/bin/sh"])
        self.cmd("/sbin/umount","-f",f"{self.mountpoint}/{self.base}/dev")
        if snapshot:
            self.snapshot_base()

    def list_jails(self,status=False):
        out = self.cmd("/sbin/zfs","list","-r","-H","-o","name,jail:name,jail:base,jail:ipv6",
                    "-s","jail:name", self.zroot)
        jails = re.findall("(.*)\t(.*)\t(.*)\t(.*)",out)
        if status:
            return [dict(name=name,
                         base=base,
                         volume=os.path.basename(vol),
                         jid=f"j_{os.path.basename(vol)}",
                         ipv6=ipv6,
                         running=self.check_cmd("jls","-Nj","j_"+os.path.basename(vol)))
                    for (vol,name,base,ipv6) in jails if base != "-"]
        else:
            return [dict(name=name,
                         base=base,
                         volume=os.path.basename(vol),
                         jid=f"j_{os.path.basename(vol)}",
                         ipv6=ipv6)
                    for (vol,name,base,ipv6) in jails if base != "-"]

    def jail(self,name):
        return Jail(name,self)
        
    def jail_from_hash(self,jail_hash):
        return Jail(self.name_from_hash(jail_hash),self)


