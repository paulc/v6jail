#!/usr/bin/env python3

from setuptools import setup

setup(name='v6jail',
      version = '1.3',
      description = 'FreeBSD IPv6 Jail Management Utility',
      install_requires = ['click==7.1.2','tabulate==0.8.7'],
      url = 'https://github.com/paulc/v6jail',
      packages = ['v6jail'],
      license = 'BSD',
      author = "paulc",
      classifiers = [ "Operating System :: POSIX :: BSD :: FreeBSD",
                      "Programming Language :: Python :: 3",
      ],
     )
