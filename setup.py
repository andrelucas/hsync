# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

setup(
        name = 'hsync',
        version = '0.0.1',
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

