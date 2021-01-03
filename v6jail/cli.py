#!/usr/bin/env python3

import click,tabulate

from .host import Host
from .jail import Jail

if __name__ == "__main__":

    @click.group()
    @click.option("--debug",is_flag=True)
    @click.option("--base")
    @click.pass_context
    def cli(ctx,debug,base):
        try:
            ctx.ensure_object(dict)
            args = { "debug": debug }
            if base:
                args["base"] = base
            ctx.obj["host"] = Host(**args)
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")

    @cli.command()
    @click.argument("name",nargs=1)
    @click.pass_context
    def new(ctx,name):
        try:
            jail = ctx.obj["host"].jail(name)
            jail.create_fs()
            click.secho(f"Created jail: {jail.name} (id={jail.jname})",fg="green")
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")

    @cli.command()
    @click.argument("name",nargs=1)
    @click.option("--private",is_flag=True)
    @click.option("--params",multiple=True)
    @click.option("--fastboot",is_flag=True)
    @click.pass_context
    def run(ctx,name,private,params,fastboot):
        try:
            jail = ctx.obj["host"].jail(name)
            if not jail.check_fs():
                jail.create_fs()
            jail_params = dict([p.split("=") for p in params])
            if fastboot:
                jail_params["exec.start"] = jail.fastboot_script()
            jail.start(private=private,jail_params=jail_params)
            click.secho(f"Started jail: {jail.name} (id={jail.jname} ipv6={jail.ipv6})",fg="green")
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")

    @cli.command()
    @click.argument("name",nargs=1)
    @click.option("--params",multiple=True)
    @click.option("--private",is_flag=True)
    @click.option("--fastboot",is_flag=True)
    @click.pass_context
    def start(ctx,name,private,params,fastboot):
        try:
            jail = ctx.obj["host"].jail(name)
            jail_params = dict([p.split("=") for p in params])
            if fastboot:
                jail_params["exec.start"] = jail.fastboot_script()
            jail.start(private=private,jail_params=jail_params)
            click.secho(f"Started jail: {jail.name} (id={jail.jname} ipv6={jail.ipv6})",fg="green")
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")

    @cli.command()
    @click.argument("name",nargs=1)
    @click.pass_context
    def stop(ctx,name):
        try:
            jail = ctx.obj["host"].jail(name)
            jail.stop()
            click.secho(f"Stopped jail: {jail.name} ({jail.jname})",fg="green")
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")

    @cli.command()
    @click.option("--force",is_flag=True)
    @click.argument("name",nargs=1)
    @click.pass_context
    def remove(ctx,name,force):
        try:
            jail = ctx.obj["host"].jail(name)
            jail.remove(force=force)
            click.secho(f"Removed jail: {jail.name} ({jail.jname})",fg="green")
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")

    @cli.command()
    @click.pass_context
    def list(ctx):
        try:
            jails = [dict(name=j.name,jname=j.jname,ipv6=j.ipv6,running=j.is_running()) 
                            for j in ctx.obj["host"].get_jails()]
            click.echo(tabulate.tabulate(jails,headers="keys"))
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")

    @cli.command()
    @click.argument("name",nargs=1)
    @click.argument("args", nargs=-1)
    @click.pass_context
    def sysrc(ctx,name,args):
        try:
            jail = ctx.obj["host"].jail(name)
            click.secho(f"sysrc: {jail.name} ({jail.jname})",fg="yellow")
            if args:
                click.secho(jail.sysrc("-v",*args),fg="green")
            else:
                click.secho(jail.sysrc("-a","-v"),fg="green")
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
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
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
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
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")

    @cli.command()
    @click.argument("name",nargs=1)
    @click.option("--source",type=click.File("rb"),required=True)
    @click.option("--dest")
    @click.option("--mktemp",is_flag=True)
    @click.option("--mode",default="0755")
    @click.option("--user")
    @click.option("--group")
    @click.pass_context
    def install(ctx,name,source,dest,mktemp,mode,user,group):
        try:
            jail = ctx.obj["host"].jail(name)
            if dest:
                n = jail.install(source,dest,mode,user,group)
                click.secho(f"Installed to {dest} ({n} bytes)")
            elif mktemp:
                fd,path = jail.mkstemp(prefix="tmp_")
                n = jail.install(source,fd)
                click.secho(f"Installed to {path} ({n} bytes)")
            else:
                raise ValueError("Must specify either `--dest` or `--mktemp`")
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
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
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
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
            raise click.ClickException(f"{e} :: {e.stderr.strip()}")
        except ValueError as e:
            raise click.ClickException(f"{e}")
    cli()
