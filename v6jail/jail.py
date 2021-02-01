
import functools,os,re,shutil,subprocess,tempfile

# For epair
HOST,JAIL = 0,1

# Use decorators to check state
def check_running(f):
    @functools.wraps(f)
    def _wrapper(self,*args,**kwargs):
        if not self.is_running():
            raise ValueError(f"Jail not running: {self.name} ({self.jname})")
        return f(self,*args,**kwargs)
    return _wrapper

def check_not_running(f):
    @functools.wraps(f)
    def _wrapper(self,*args,**kwargs):
        if self.is_running():
            raise ValueError(f"Jail running: {self.name} ({self.jname})")
        return f(self,*args,**kwargs)
    return _wrapper

def check_fs_exists(f):
    @functools.wraps(f)
    def _wrapper(self,*args,**kwargs):
        if not self.check_fs():
            raise ValueError(f"Jail FS not found: {self.name} ({self.zpath})")
        return f(self,*args,**kwargs)
    return _wrapper

class Jail:

    def __init__(self,name,host=None):

        # Jail params
        self.name = name
        self.host = host
        self.hash = self.host.generate_hash(name)
        self.ipv6 = self.host.generate_addr(name)
        self.jname = f"j_{self.hash}"
        self.path = f"{self.host.mountpoint}/{self.hash}"
        self.zpath = f"{self.host.zroot}/{self.hash}"
        self.epair = (f"{self.hash}A",f"{self.hash}B")
        self.gateway = self.host.generate_gateway(self.epair[JAIL])

        # Useful commands
        self.ifconfig       = lambda *args: self.host.cmd("/sbin/ifconfig",*args)
        self.route6         = lambda *args: self.host.cmd("/sbin/route","-6",*args)
        self.jail_route6    = lambda *args: self.host.cmd("/usr/sbin/jexec",
                                                "-l",self.jname,"/sbin/route","-6",*args)
        self.zfs_clone      = lambda *args: self.host.cmd("/sbin/zfs","clone",*args)
        self.zfs_set        = lambda *args: self.host.cmd("/sbin/zfs","set",*args,self.zpath)
        self.jail_start     = lambda *args: self.host.cmd("/usr/sbin/jail","-cv",*args)
        self.useradd        = lambda user:  self.host.cmd("/usr/sbin/pw","-R",self.path,
                                                "useradd","-n",user,"-m","-s","/bin/sh","-h","-")
        self.usershow       = lambda user:  self.host.cmd("/usr/sbin/pw","-R",self.path,
                                                "usershow","-n",user).split(":")
        self.jail_stop      = lambda : self.host.cmd("/usr/sbin/jail","-Rv",self.jname)
        self.umount_devfs   = lambda : self.host.cmd("/sbin/umount",f"{self.path}/dev")
        self.osrelease      = lambda : self.host.cmd("/usr/bin/uname","-r")
        self.mounted_fs     = lambda : self.host.cmd("/sbin/mount")
        self.umount_fs      = lambda args : self.host.cmd("/sbin/mount","-f",*args)

    def create_epair(self,private=True):
        if self.check_epair():
            self.destroy_epair()
        epair = self.ifconfig("epair","create")[:-1]
        epair_host,epair_jail = self.epair
        self.ifconfig(f"{epair}a","name",epair_host)
        self.ifconfig(f"{epair}b","name",epair_jail)
        self.ifconfig(epair_host,"inet6","auto_linklocal","up")
        if private:
            self.ifconfig(self.host.bridge,"addm",epair_host,"private",epair_host)
        else:
            self.ifconfig(self.host.bridge,"addm",epair_host)

    def remove_vnet(self):
        self.ifconfig(self.epair[JAIL],"-vnet",self.jname)

    def umount_local(self):
        if os.path.exists(f"{self.path}/etc/fstab"):
            self.jexec("umount","-af")

    def force_umount(self):
        fs = re.findall(f".* on ({self.path}/.*) \(.*\)",self.mounted_fs())
        if fs:
            self.umount_fs(fs)


    def destroy_epair(self):
        self.ifconfig(self.epair[HOST],"destroy")

    def get_lladdr(self):
        (lladdr_host,) = re.search("inet6 (fe80::.*?)%",self.ifconfig(self.epair[HOST])).groups()
        lladdr_jail = lladdr_host[:-1] + "b"
        return (lladdr_host,lladdr_jail)

    def local_route(self):
        epair_host,epair_jail = self.epair
        lladdr_host,lladdr_jail = self.get_lladdr()
        self.route6("add",self.ipv6,f"{lladdr_jail}%{epair_host}")
        self.jail_route6("add",self.host.hostipv6,f"{lladdr_host}%{epair_jail}")

    def is_running(self):
        return self.host.check_cmd("jls","-Nj",self.jname)

    def check_fs(self):
        return self.host.check_cmd("zfs","list",self.zpath)

    def check_epair(self):
        return self.host.check_cmd("ifconfig",self.epair[HOST])

    def check_devfs(self):
        out = self.host.cmd("mount","-t","devfs")
        return re.search(f"{self.path}/dev",out) is not None

    def is_vnet(self):
        try:
            return self.host.cmd("/usr/sbin/jls","-j",self.jname,"vnet") == "1"
        except subprocess.CalledProcessError:
            return False

    @check_running
    def jexec(self,*args):
        return subprocess.run(["/usr/sbin/jexec","-l",self.jname,*args])

    @check_fs_exists
    def sysrc(self,*args):
        return self.host.cmd("/usr/sbin/sysrc","-R",self.path,*args)

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
                d = open(f"{self.path}{dest}","wb")
                os.chmod(f"{self.path}{dest}",int(mode,8))
                if user or group:
                    shutil.chown(f"{self.path}{dest}",user,group)
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
        jdir = f"{self.path}/{dir}" if dir else f"{self.path}/tmp"
        fd,path = tempfile.mkstemp(suffix,prefix,jdir,text)
        return (fd, path[len(self.path):])

    @check_fs_exists
    def adduser(self,user,pk):
        if user == "root":
            # Just add ssh key
            os.mkdir(f"{self.path}/root/.ssh",mode=0o700)
            with open(f"{self.path}/root/.ssh/authorized_keys","a") as f:
                f.write(f"\n{pk}\n")
            os.chmod(f"{self.path}/root/.ssh/authorized_keys",0o600)
        else:
            self.useradd(user)
            (name,_,uid,gid,*_) = self.usershow(user)
            os.mkdir(f"{self.path}/home/{user}/.ssh",mode=0o700)
            with open(f"{self.path}/home/{user}/.ssh/authorized_keys","a") as f:
                f.write(f"\n{pk}\n")
            os.chown(f"{self.path}/home/{user}/.ssh",int(uid),int(gid))
            os.chown(f"{self.path}/home/{user}/.ssh/authorized_keys",int(uid),int(gid))
            os.chmod(f"{self.path}/home/{user}/.ssh/authorized_keys",0o600)

    def fastboot_script(self,services=None,cmds=None):
        epair_host,epair_jail = self.epair
        services = [f"service {s} start" for s in (services or ["syslogd","cron","sshd"])]
        cmds = cmds or []
        cmds = ";\n".join([*services,*cmds])
        return f"""
            ifconfig lo0 inet 127.0.0.1/8;
            ifconfig lo0 inet6 ::1 auto_linklocal;
            ifconfig {epair_jail} inet6 {self.ipv6} auto_linklocal;
            route -6 add default fe80::1%{epair_jail};
            route -6 add fe80:: -prefixlen 10 ::1 -reject;
            route -6 add ::ffff:0.0.0.0 -prefixlen 96 ::1 -reject;
            route -6 add ::0.0.0.0 -prefixlen 96 ::1 -reject; 
            route -6 add ff02:: -prefixlen 16 ::1 -reject; 
            [ -f /etc/fstab ] && mount -al;
            {cmds}
        """

    def create_fs(self):
        if self.check_fs():
            raise ValueError(f"Jail FS exists: {self.name} ({self.zpath})")
        self.zfs_clone(self.host.get_latest_snapshot(),self.zpath)
        self.zfs_set(f"jail:name={self.name}",
                     f"jail:ipv6={self.ipv6}",
                     f"jail:base={self.host.base}")

    @check_fs_exists
    def configure_vnet(self):
        epair_host,epair_jail = self.epair
        self.sysrc(f"network_interfaces=lo0 {epair_jail}",
                   f"ifconfig_{epair_jail}_ipv6=inet6 {self.ipv6}/64",
                   f"ipv6_defaultrouter={self.gateway}",
                   f"ifconfig_lo0_ipv6=inet6 up")

    @check_fs_exists
    @check_not_running
    def start(self,private=True,jail_params=None,param_set=None):
        if param_set:
            params = param_set.copy()
        else:
            params = self.host.DEFAULT_PARAMS.copy()
        params["name"] = self.jname
        params["path"] = self.path
        params["vnet.interface"] = self.epair[JAIL]
        params["host.hostname"] = self.name
        params["osrelease"] = self.osrelease()
        params.update(jail_params or {})
        self.create_epair(private)
        self.configure_vnet()
        subprocess.run(["/usr/sbin/jail","-cv",*[f"{k}={v}" for k,v in params.items()]],
                       check=True)
        self.local_route()

    @check_running
    def stop(self):
        self.umount_local()
        self.remove_vnet()
        self.destroy_epair()
        self.jail_stop()
        self.umount_devfs()
        self.force_umount()

    @check_fs_exists
    def destroy_fs(self):
        self.host.cmd("/sbin/zfs","destroy","-f",self.zpath)

    def remove(self,force=False):
        if self.is_running():
            if force:
                self.stop()
            else:
                raise ValueError(f"Jail running: {self.name} ({self.jname})")
        if self.check_devfs():
            self.umount_devfs()
        if self.check_epair():
            self.destroy_epair()
        self.destroy_fs()

    def cleanup(self,force=False,destroy_fs=False):
        if self.is_running() and force:
            self.stop()
        else:
            raise ValueError(f"Jail running: {self.name} ({self.jname})")
        if self.check_devfs():
            self.umount_devfs()
        if self.check_epair():
            self.destroy_epair()
        if self.check_fs() and destroy_fs:
            self.destroy_fs()

