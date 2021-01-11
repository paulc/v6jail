#!/usr/bin/env python3

from setuptools import setup

with open("requirements.txt") as f:
    install_requires = f.read().splitlines()

setup(name='v6jail',
      version = '1.2',
      description = 'FreeBSD IPv6 Jail Management Utility',
      install_requires = install_requires,
      url = 'https://github.com/paulc/v6jail',
      packages = ['v6jail'],
      license = 'BSD',
      author = "paulc",
      author_email = "https://github.com/paulc",
      classifiers = [ "Operating System :: POSIX :: BSD :: FreeBSD"
                      "Programming Language :: Python :: 3",
      ],
     )
