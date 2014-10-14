# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

from hsync._version import __version__

setup(
        name = 'hsync',
        version = __version__,
        author = 'Andre Lucas',
        author_email = 'andre.lucas@devinfotech.co.uk',
        license = 'BSD',
        packages = [ 'hsync', ],

        tests_require = [ 'coverage', 'mock', 'nose' ],
        requires = [ 'urlgrabber', ],

        entry_points={
            'console_scripts': [
                'hsync = hsync.hsync:csmain',
            ],
        },

)

