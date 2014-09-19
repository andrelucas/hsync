# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

from hsync._version import __version__

setup(
        name = 'hsync',
        version = __version__,
        author = 'André Lucas',
        author_email = 'andre.lucas@devinfotech.co.uk',
        license = 'BSD',
        packages = [ 'hsync', ],

        entry_points={
            'console_scripts': [
                'hsync = hsync.hsync:csmain',
            ],
    },
)

