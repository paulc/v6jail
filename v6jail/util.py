
import subprocess
from dataclasses import dataclass

@dataclass
class Command:

    debug: bool = False

    def cmd(self,*args):
        try:
            result = subprocess.run(args,capture_output=True,check=True)
            out = result.stdout.strip().decode()
            if self.debug:
                print("CMD:",args)
                if out:
                    print("\n".join([f"   | {l}" for l in out.split("\n")]))
            return out
        except (PermissionError,FileNotFoundError) as e:
            if self.debug:
                err = e.strerror
                print("ERR:",args)
                if err:
                    print("\n".join([f"   ! {l}" for l in err.split("\n")]))
            raise
        except subprocess.CalledProcessError as e:
            if self.debug:
                err = e.stderr.strip().decode("utf8","ignore")
                print("ERR:",args)
                if err:
                    print("\n".join([f"   ! {l}" for l in err.split("\n")]))
            raise

    __call__ = cmd

    def check(self,*args):
        try:
            self.cmd(*args)
            return True
        except subprocess.CalledProcessError:
            return False

