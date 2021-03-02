#!/usr/bin/env python3

import shutil

from pathlib import Path

# variable injected from shiv.bootstrap
site_packages: Path

current = site_packages.parent
cache_path = current.parent
name, build_id = current.name.split('_')

if __name__ == "__main__":
    for path in cache_path.iterdir():
        if path.name.startswith(f"{name}_") and not path.name.endswith(build_id):
            shutil.rmtree(path)
            # Also remove lock file
            lock = path.with_name(f".{path.stem}_lock")
            if lock.is_file():
                lock.unlink()

