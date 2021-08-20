
import configparser,functools,io,os,pathlib,re,shutil,subprocess,tempfile

from .util import Command
from .config import JailConfig
from .jailparam import JailParam

# Use decorators to check state
def check_running(f):
    @functools.wraps(f)
    def _wrapper(self,*args,**kwargs):
        if not self.is_running():
            raise ValueError(f"Jail not running: {self.config.name} ({self.config.jname})")
        return f(self,*args,**kwargs)
    return _wrapper

def check_not_running(f):
    @functools.wraps(f)
    def _wrapper(self,*args,**kwargs):
        if self.is_running():
            raise ValueError(f"Jail running: {self.config.name} ({self.config.jname})")
        return f(self,*args,**kwargs)
    return _wrapper

def check_fs_exists(f):
    @functools.wraps(f)
    def _wrapper(self,*args,**kwargs):
        if not self.check_fs():
            raise ValueError(f"Jail FS not found: {self.config.name} ({self.config.zpath})")
        return f(self,*args,**kwargs)
    return _wrapper

class Jail:

    @classmethod
    def from_config(cls,f,jail_section="jail",jailparam_section="jail_params",debug=False):
        c = configparser.ConfigParser(interpolation=None)
        c.read_file(f)
        config = JailConfig.read_config(jail_section,c=c)
        params = JailParam.read_config(jailparam_section,c=c)
        return cls(config,params,debug)

    def __init__(self,config,params=None,debug=False):

        # Jail params
        self.config = config
        self.debug = debug
        self.params = params or self.generate_jail_params()

        self.cmd = Command(self.debug)

        # Useful commands
        self.ifconfig       = lambda *args: self.cmd("/sbin/ifconfig",*args)
        self.route6         = lambda *args: self.cmd("/sbin/route","-6",*args)
        self.jail_route6    = lambda *args: self.cmd("/usr/sbin/jexec",
                                                "-l",self.config.jname,"/sbin/route","-6",*args)
        self.zfs_clone      = lambda *args: self.cmd("/sbin/zfs","clone",*args)
        self.zfs_set        = lambda *args: self.cmd("/sbin/zfs","set",*args,self.config.zpath)
        self.jail_start     = lambda *args: self.cmd("/usr/sbin/jail","-cv",*args)
        self.jail_stop      = lambda : self.cmd("/usr/sbin/jail","-Rv",self.config.jname)
        self.useradd        = lambda user:  self.cmd("/usr/sbin/pw","-R",self.config.path,
                                                "useradd","-n",user,"-m","-s","/bin/sh","-h","-")
        self.usershow       = lambda user:  self.cmd("/usr/sbin/pw","-R",self.config.path,
                                                "usershow","-n",user).split(":")
        self.usermod        = lambda user,*args: self.cmd("/usr/sbin/pw","-R",self.config.path,
                                                "usermod","-n",user,*args)
        self.umount_devfs   = lambda : self.cmd("/sbin/umount",f"{self.config.path}/dev")
        self.osrelease      = lambda : self.cmd("/usr/bin/uname","-r")
        self.mounted_fs     = lambda : self.cmd("/sbin/mount")
        self.umount_fs      = lambda args : self.cmd("/sbin/mount","-f",*args)

    def write_jail_file(self,jail_path,contents,mode=0o644,binary=False):
        if jail_path.startswith('/'):
            jail_path = jail_path[1:]
        dest = pathlib.Path(self.config.path,jail_path)
        if binary:
            dest.write_bytes(contents)
        else:
            dest.write_text(contents)
        dest.chmod(mode)

    def get_latest_snapshot(self):
        out = self.cmd("/sbin/zfs", "list", "-Hrt", "snap", "-d", "1", "-s", "creation", "-o", "name", 
                              f"{self.config.base_zvol}")
        if out:
            return out.split("\n")[-1]
        else:
            raise ValueError(f"No snapshots found: {self.config.base_zvol}")

    def generate_jail_params(self):
        params = JailParam.default()
        params.enable_vnet(self.config.epair_jail)
        params.enable_sysvipc()
        params.allow("raw_sockets")
        params.allow("socket_af")
        params.allow("chflags")
        params.set("name",self.config.jname)
        params.set("path",self.config.path)
        params.set("host.hostname",self.config.name)
        params.set("host.hostuuid",self.config.name)
        return params

    def create_epair(self):
        if self.check_epair():
            self.destroy_epair()
        epair = self.ifconfig("epair","create")[:-1]
        self.ifconfig(f"{epair}a","name",self.config.epair_host)
        self.ifconfig(f"{epair}b","name",self.config.epair_jail)
        # If bridge has IPv6 address can't configure link-local address
        self.ifconfig(self.config.epair_host,"inet6","-auto_linklocal","mtu",str(self.config.mtu),"up")
        self.ifconfig(self.config.epair_jail,"inet6","auto_linklocal","-ifdisabled","mtu",str(self.config.mtu),"up")
        if self.config.private:
            self.ifconfig(self.config.bridge,"addm",self.config.epair_host,
                                             "private",self.config.epair_host)
        else:
            self.ifconfig(self.config.bridge,"addm",self.config.epair_host)

    def destroy_epair(self):
        self.ifconfig(self.config.epair_host,"destroy")

    def remove_vnet(self):
        self.ifconfig(self.config.epair_jail,"-vnet",self.config.jname)

    def umount_local(self):
        if os.path.exists(f"{self.config.path}/etc/fstab"):
            self.jexec("umount","-af")

    def force_umount(self):
        fs = re.findall(f".* on ({self.config.path}/.*) \(.*\)",self.mounted_fs())
        if fs:
            self.umount_fs(fs)

    def get_lladdr(self,interface,jail=False):
        (lladdr,) = re.search("inet6 (fe80::.*?)%",
                              self.jexec('/sbin/ifconfig',interface) if jail else self.ifconfig(interface)
                    ).groups()
        return lladdr

    def get_ether(self,interface):
        (ether,) = re.search("ether (.*)",
                             self.ifconfig(interface)
                   ).groups()
        return ether

    def get_gateway(self,address):
        (gateway,) = re.search("gateway: (.*)",
                               self.route6("get",address)
                     ).groups()
        return gateway

    def add_proxy_route(self,lladdr_jail,ether_jail):
        self.route6("add",str(self.config.address),f"{lladdr_jail}%{self.config.bridge}")
        #self.cmd('/usr/sbin/ndp','-ns',f"{lladdr_jail}%{self.config.bridge}",ether_jail)
        #self.jexec('/usr/sbin/ndp','-ns',str(self.config.gateway),self.get_ether(self.config.bridge))

    def delete_proxy_route(self):
        gw = self.get_gateway(str(self.config.address))
        #self.route6("delete",str(self.config.address))
        #self.cmd('/usr/sbin/ndp','-nd',gw)

    def is_running(self):
        return self.cmd.check("jls","-Nj",self.config.jname)

    def check_fs(self):
        return self.cmd.check("zfs","list",self.config.zpath)

    def check_epair(self):
        return self.cmd.check("ifconfig",self.config.epair_host)

    def check_devfs(self):
        out = self.cmd("mount","-t","devfs")
        return re.search(f"{self.config.path}/dev",out) is not None

    def is_vnet(self):
        try:
            return self.cmd("/usr/sbin/jls","-j",self.config.jname,"vnet") == "1"
        except subprocess.CalledProcessError:
            return False

    @check_running
    def jexec(self,*args,capture=False,check=False):
        return subprocess.run(["/usr/sbin/jexec","-l",self.config.jname,*args],
                              capture_output=capture,check=check)

    @check_fs_exists
    def sysrc(self,*args):
        return self.cmd("/usr/sbin/sysrc","-R",self.config.path,*args)

    @check_fs_exists
    def install(self,source,dest,mode="0755",user=None,group=None):
        try:
            if isinstance(source,str):
                s = io.BytesIO(source.encode())
            elif isinstance(source,bytes):
                s = io.BytesIO(source)
            elif hasattr(source,"read"):
                s = source
            else:
                raise ValueError("Invalid source")

            if isinstance(dest,str):
                d = open(f"{self.config.path}{dest}","wb")
                os.chmod(f"{self.config.path}{dest}",int(mode,8))
                if user or group:
                    shutil.chown(f"{self.config.path}{dest}",user,group)
            elif isinstance(dest,int):
                d = os.fdopen(dest,"wb")
            else:
                raise ValueError("Invalid destination")

            return d.write(s.read())

        finally:
            s.close()
            d.close()

    @check_fs_exists
    def mkstemp(self,suffix=None,prefix=None,dir=None,text=False):
        jdir = f"{self.config.path}/{dir}" if dir else f"{self.config.path}/tmp"
        fd,path = tempfile.mkstemp(suffix,prefix,jdir,text)
        return (fd, path[len(self.config.path):])

    @check_fs_exists
    def adduser(self,user,pk):
        if user == "root":
            # Just add ssh key
            try:
                os.mkdir(f"{self.config.path}/root/.ssh",mode=0o700)
            except FileExistsError:
                pass
            with open(f"{self.config.path}/root/.ssh/authorized_keys","a") as f:
                f.write(f"\n{pk}\n")
            os.chmod(f"{self.config.path}/root/.ssh/authorized_keys",0o600)
        else:
            self.useradd(user)
            (name,_,uid,gid,*_) = self.usershow(user)
            try:
                os.mkdir(f"{self.config.path}/home/{user}/.ssh",mode=0o700)
            except FileExistsError:
                pass
            with open(f"{self.config.path}/home/{user}/.ssh/authorized_keys","a") as f:
                f.write(f"\n{pk}\n")
            os.chown(f"{self.config.path}/home/{user}/.ssh",int(uid),int(gid))
            os.chown(f"{self.config.path}/home/{user}/.ssh/authorized_keys",int(uid),int(gid))
            os.chmod(f"{self.config.path}/home/{user}/.ssh/authorized_keys",0o600)

    def fastboot_script(self,services=None,cmds=None):
        services = [f"service {s} start" for s in services]
        cmds = cmds or []
        cmds = ";\n".join([*services,*cmds])
        return f"""\
            ifconfig lo0 inet6 up;
            ifconfig lo0 inet 127.0.0.1;
            ifconfig {self.config.epair_jail} inet6 {self.config.address} prefixlen {self.config.prefixlen} auto_linklocal;
            route -6 add default {self.config.gateway};
            route -6 add fe80:: -prefixlen 10 ::1 -reject;
            route -6 add ::ffff:0.0.0.0 -prefixlen 96 ::1 -reject;
            route -6 add ::0.0.0.0 -prefixlen 96 ::1 -reject; 
            route -6 add ff02:: -prefixlen 16 ::1 -reject; 
            uname -a > /etc/motd;
            [ -f /etc/fstab ] && mount -al;
            {cmds}
        """

    def write_fastboot(self,services=None,cmds=None):
        self.write_jail_file("/etc/fastboot",self.fastboot_script(services,cmds),0o755)

    def create_fs(self):
        if self.check_fs():
            raise ValueError(f"Jail FS exists: {self.config.name} ({self.config.zpath})")
        self.zfs_clone(self.get_latest_snapshot(),self.config.zpath)
        self.zfs_set(f"jail:name={self.config.name}",
                     f"jail:ipv6={self.config.address}",
                     f"jail:base={self.config.base}")
        self.zfs_set(f"jail:config={self.get_config()}")

    def get_config(self):
        c = self.config.write_config("jail")
        c = self.params.write_config("jail_params",c)
        with io.StringIO('w') as f:
            c.write(f)
            f.seek(0)
            return f.read()

    @check_fs_exists
    def configure_vnet(self):
        self.sysrc(f"network_interfaces=lo0 {self.config.epair_jail}",
                   f"ifconfig_{self.config.epair_jail}_ipv6=inet6 {self.config.address}/{self.config.prefixlen}",
                   f"ipv6_defaultrouter={self.config.gateway}",
                   f"ifconfig_lo0=up",
                   f"ifconfig_lo0_ipv6=inet6 up")

    @check_fs_exists
    @check_not_running
    def start(self):
        self.create_epair()
        self.configure_vnet()
        flags = "-cv" if self.debug else "-c"
        lladdr_jail = self.get_lladdr(self.config.epair_jail)
        ether_jail = self.get_ether(self.config.epair_jail)
        subprocess.run(["/usr/sbin/jail",flags,*self.params.jail_params()],
                       check=True)
        if self.config.proxy:
            self.add_proxy_route(lladdr_jail,ether_jail)

    @check_running
    def stop(self):
        self.umount_local()
        self.remove_vnet()
        self.destroy_epair()
        self.jail_stop()
        self.umount_devfs()
        self.force_umount()
        if self.config.proxy:
            self.delete_proxy_route()

    @check_fs_exists
    def destroy_fs(self):
        self.cmd("/sbin/zfs","destroy","-f",self.config.zpath)

    def remove(self,force=False):
        if self.is_running():
            if force:
                self.stop()
            else:
                raise ValueError(f"Jail running: {self.config.name} ({self.config.jname})")
        if self.check_devfs():
            self.umount_devfs()
        if self.check_epair():
            self.destroy_epair()
        self.destroy_fs()

    def cleanup(self,force=False,destroy_fs=False):
        if self.is_running() and force:
            self.stop()
        else:
            raise ValueError(f"Jail running: {self.config.name} ({self.config.jname})")
        if self.check_devfs():
            self.umount_devfs()
        if self.check_epair():
            self.destroy_epair()
        if self.check_fs() and destroy_fs:
            self.destroy_fs()

