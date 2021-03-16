#!/usr/bin/env python3

import code,shlex,subprocess,sys
import click,tabulate

from .host import Host
from .jail import Jail
from .config import HostConfig,JailConfig

proc_err = lambda e: e.stderr.strip().decode() if e.stderr else ''

@click.group()
@click.option("--debug",is_flag=True)
@click.option("--config",type=click.File("r"))
@click.option("--base")
@click.pass_context
def cli(ctx,debug,base,config):
    try:
        ctx.ensure_object(dict)
        if config:
            host_config = HostConfig.read_config("host",f=config)
        else:
            if base:
                host_config = HostConfig(base=base)
            else:
                host_config = HostConfig()
        ctx.obj["host"] = Host(host_config,debug)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.option("--dump","option",flag_value="hostconfig")
@click.pass_context
def config(ctx,option):
    if option == "hostconfig":
        ctx.obj["host"].config.write_config("host").write(sys.stdout)



@cli.command()
@click.argument("name",nargs=1)
@click.pass_context
def new(ctx,name):
    try:
        jail = ctx.obj["host"].jail(name)
        jail.create_fs()
        click.secho(f"Created jail: {jail.config.name} (id={jail.config.jname})",fg="green")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

def _cli_config(jail,jail_params,linux,fastboot,fastboot_service,fastboot_cmd,write_fastboot=True):
    for p in jail_params:
        jail.params.set_kvpair(p)
    if fastboot:
        if write_fastboot:
            jail.write_fastboot(services=fastboot_service,cmds=fastboot_cmd)
        jail.params.set("exec.start","/bin/sh /etc/fastboot")
    if linux:
        jail.params.enable_linux()

@cli.command()
@click.argument("name",nargs=1)
@click.option("--jail-params",multiple=True)
@click.option("--linux",is_flag=True)
@click.option("--fastboot",is_flag=True)
@click.option("--fastboot-service",multiple=True)
@click.option("--fastboot-cmd",multiple=True)
@click.pass_context
def genconfig(ctx,name,jail_params,linux,fastboot,fastboot_service,fastboot_cmd):
    try:
        jail = ctx.obj["host"].jail(name)
        # XXX Do something with fastboot
        _cli_config(jail,jail_params,linux,fastboot,fastboot_service,fastboot_cmd,write_fastboot=False)
        click.echo(jail.get_config())
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.option("--jail-config",type=click.File("r"))
@click.pass_context
def fromconfig(ctx,jail_config):
    try:
        jail = Jail.from_config(jail_config)
        click.echo(jail.get_config())
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.argument("name",nargs=1)
@click.option("--jail-params",multiple=True)
@click.option("--linux",is_flag=True)
@click.option("--shell",is_flag=True)
@click.option("--force-ndp",is_flag=True)
@click.option("--jexec")
@click.option("--fastboot",is_flag=True)
@click.option("--fastboot-service",multiple=True)
@click.option("--fastboot-cmd",multiple=True)
@click.option("--adduser",nargs=2,multiple=True)
@click.pass_context
def run(ctx,name,jail_params,linux,fastboot,force_ndp,
            fastboot_service,fastboot_cmd,adduser,shell,jexec):
    try:
        jail = ctx.obj["host"].jail(name)
        if not jail.check_fs():
            jail.create_fs()
        if jail.is_running():
            raise click.UsageError(f"Jail {name} running")
        for (user,pk) in adduser:
            jail.adduser(user=user,pk=pk)
        _cli_config(jail,jail_params,linux,fastboot,fastboot_service,fastboot_cmd)
        jail.start()
        click.secho(f"Started jail: {jail.config.name} " \
                    f"(id={jail.config.jname} " \
                    f"ipv6={jail.config.address})",
                    fg="green")
        if force_ndp:
            jail.jexec('/bin/sh','-c',f'''
                for i in $(/usr/bin/jot 10); 
                    do ping6 -o {jail.config.gateway} >/dev/null 2>&1 && break; 
                    sleep 1; 
                done &''')
        if jexec:
            jail.jexec(*shlex.split(jexec))
        if shell:
            jail.jexec("login","-f","root")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.argument("name",nargs=1)
@click.option("--jail-params",multiple=True)
@click.option("--linux",is_flag=True)
@click.option("--fastboot",is_flag=True)
@click.option("--fastboot-service",multiple=True)
@click.option("--fastboot-cmd",multiple=True)
@click.pass_context
def start(ctx,name,jail_params,linux,fastboot,fastboot_service,fastboot_cmd):
    try:
        jail = ctx.obj["host"].jail(name)
        _cli_config(jail,jail_params,linux,fastboot,fastboot_service,fastboot_cmd)
        jail.start()
        click.secho(f"Started jail: {jail.config.name} " \
                    f"(id={jail.config.jname} " \
                    f"ipv6={jail.config.address})",
                    fg="green")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.argument("name",nargs=1)
@click.pass_context
def stop(ctx,name):
    try:
        jail = ctx.obj["host"].jail(name)
        jail.stop()
        click.secho(f"Stopped jail: {jail.config.name} ({jail.config.jname})",fg="green")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.option("--force",is_flag=True)
@click.argument("name",nargs=1)
@click.pass_context
def destroy(ctx,name,force):
    try:
        jail = ctx.obj["host"].jail(name)
        jail.remove(force=force)
        click.secho(f"Removed jail: {jail.config.name} ({jail.config.jname})",fg="green")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.option("--status",is_flag=True)
@click.pass_context
def list(ctx,status):
    try:
        jails = ctx.obj["host"].list_jails(status=status)
        click.echo(tabulate.tabulate(jails,headers="keys"))
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.argument("name",nargs=1)
@click.option("--user",required=True)
@click.option("--pk",required=True)
@click.pass_context
def adduser(ctx,name,user,pk):
    try:
        ctx.obj["host"].jail(name).adduser(user=user,pk=pk)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.argument("name",nargs=1)
@click.argument("args", nargs=-1)
@click.pass_context
def sysrc(ctx,name,args):
    try:
        jail = ctx.obj["host"].jail(name)
        click.secho(f"sysrc: {jail.config.name} ({jail.config.jname})",fg="yellow")
        if args:
            click.secho(jail.sysrc("-v",*args),fg="green")
        else:
            click.secho(jail.sysrc("-a","-v"),fg="green")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.argument("name",nargs=1)
@click.argument("args", nargs=-1)
@click.pass_context
def jexec(ctx,name,args):
    try:
        jail = ctx.obj["host"].jail(name)
        jail.jexec(*args)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.argument("name",nargs=-1)
@click.pass_context
def repl(ctx,name):
    try:
        if name:
            jail = ctx.obj["host"].jail(name[0])
        host = ctx.obj["host"]
        code.interact(local=locals())
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.argument("cmds",nargs=-1)
@click.option("--snapshot",is_flag=True)
@click.pass_context
def chroot_base(ctx,snapshot,cmds):
    try:
        host  = ctx.obj["host"]
        host.chroot_base(cmds=cmds,snapshot=snapshot)
        if snapshot:
            click.secho(host.get_latest_snapshot(),fg="green")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

@cli.command()
@click.pass_context
def update_base(ctx):
    try:
        host  = ctx.obj["host"]
        cmds = [ "/usr/sbin/freebsd-update --not-running-from-cron fetch | head",
                 "/usr/sbin/freebsd-update --not-running-from-cron install || echo No updates available",
                 "/usr/bin/env ASSUME_ALWAYS_YES=true /usr/sbin/pkg bootstrap",
                 "/usr/bin/env ASSUME_ALWAYS_YES=true /usr/sbin/pkg update",
                 "/usr/bin/env ASSUME_ALWAYS_YES=true /usr/sbin/pkg upgrade",
        ]
        host.chroot_base(cmds=cmds,snapshot=True)
        click.secho(host.get_latest_snapshot(),fg="green")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"{e} :: {proc_err(e)}")
    except ValueError as e:
        raise click.ClickException(f"{e}")

if __name__ == "__main__":
    cli()

